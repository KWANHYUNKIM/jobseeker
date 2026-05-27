#!/usr/bin/env bash
# PID-based crawler runner.
#
# Usage:
#   ./run.sh start <crawler> [args...]   # e.g. ./run.sh start wanted 개발자 10 5
#   ./run.sh status                       # list all runs (RUN / DONE)
#   ./run.sh stop <id>                    # kill a running job
#   ./run.sh logs <id> [n]                # tail last n lines (default 50)
#   ./run.sh clean                        # delete finished pid/log files
#   ./run.sh aggregate [keyword]          # merge latest runs into screenshots/all_<keyword>_<ts>/
#
# Notes:
#   - Crawlers run headless, so no Chromium window pops up.
#   - PID and log files live under catch_capture/.runs/.
#   - <id> is the basename printed by `start` (e.g. wanted_20260519_181900).

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
RUNS_DIR="$HERE/.runs"
VENV_PY="$HERE/.venv/bin/python"
mkdir -p "$RUNS_DIR"

if [ ! -x "$VENV_PY" ]; then
    echo "[err] venv python not found at $VENV_PY" >&2
    exit 1
fi

cmd="${1:-help}"
shift || true

case "$cmd" in
  start)
    crawler="${1:-}"
    if [ -z "$crawler" ]; then
        echo "usage: $0 start <crawler> [args...]" >&2
        exit 1
    fi
    shift
    script="$HERE/crawl_${crawler}.py"
    if [ ! -f "$script" ]; then
        echo "[err] crawler script not found: $script" >&2
        exit 1
    fi
    ts="$(date +%Y%m%d_%H%M%S)"
    id="${crawler}_${ts}"
    log="$RUNS_DIR/${id}.log"
    pidfile="$RUNS_DIR/${id}.pid"
    nohup "$VENV_PY" "$script" "$@" >"$log" 2>&1 &
    pid=$!
    echo "$pid" >"$pidfile"
    echo "[start] id=$id pid=$pid log=$log"
    ;;

  status)
    shopt -s nullglob
    found=0
    for pidfile in "$RUNS_DIR"/*.pid; do
        id="$(basename "$pidfile" .pid)"
        pid="$(cat "$pidfile" 2>/dev/null || echo '?')"
        if [ "$pid" != "?" ] && ps -p "$pid" >/dev/null 2>&1; then
            printf 'RUN   %-40s pid=%s\n' "$id" "$pid"
        else
            printf 'DONE  %-40s pid=%s\n' "$id" "$pid"
        fi
        found=1
    done
    [ "$found" -eq 0 ] && echo "(no runs)"
    true
    ;;

  stop)
    id="${1:-}"
    if [ -z "$id" ]; then
        echo "usage: $0 stop <id>" >&2
        exit 1
    fi
    pidfile="$RUNS_DIR/${id}.pid"
    if [ ! -e "$pidfile" ]; then
        echo "[err] no such id: $id" >&2
        exit 1
    fi
    pid="$(cat "$pidfile")"
    if ps -p "$pid" >/dev/null 2>&1; then
        # kill the whole process group (playwright spawns chromium)
        pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
        if [ -n "$pgid" ]; then
            kill -TERM -"$pgid" 2>/dev/null || kill -TERM "$pid"
        else
            kill -TERM "$pid"
        fi
        sleep 1
        ps -p "$pid" >/dev/null 2>&1 && kill -KILL "$pid" 2>/dev/null
        echo "[stop] killed $id (pid=$pid)"
    else
        echo "[stop] $id (pid=$pid) already exited"
    fi
    ;;

  logs)
    id="${1:-}"
    n="${2:-50}"
    if [ -z "$id" ]; then
        echo "usage: $0 logs <id> [n]" >&2
        exit 1
    fi
    log="$RUNS_DIR/${id}.log"
    if [ ! -e "$log" ]; then
        echo "[err] no such log: $id" >&2
        exit 1
    fi
    tail -n "$n" "$log"
    ;;

  aggregate)
    keyword="${1:-개발자}"
    "$VENV_PY" "$HERE/aggregate.py" "$keyword"
    ;;

  clean)
    shopt -s nullglob
    removed=0
    for pidfile in "$RUNS_DIR"/*.pid; do
        pid="$(cat "$pidfile" 2>/dev/null || echo '')"
        if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
            continue
        fi
        id="$(basename "$pidfile" .pid)"
        rm -f "$pidfile" "$RUNS_DIR/${id}.log"
        removed=$((removed+1))
    done
    echo "[clean] removed $removed finished run(s)"
    ;;

  *)
    cat <<USAGE
usage:
  $0 start <crawler> [args...]   # e.g. $0 start wanted 개발자 10 5
  $0 status                       # list all runs
  $0 stop <id>                    # kill a running job
  $0 logs <id> [n]                # tail last n lines (default 50)
  $0 clean                        # remove finished pid/log files
  $0 aggregate [keyword]          # merge latest runs into all_<keyword>_<ts>/

crawler names map to crawl_<name>.py (wanted, jumpit, saramin, jobkorea, dev).
USAGE
    exit 1
    ;;
esac
