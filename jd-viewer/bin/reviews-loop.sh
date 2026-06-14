#!/usr/bin/env bash
# 적응형 공개 면접 후기 수집 데몬.
# 처음엔 짧은 간격(START)으로 빠르게 후기를 담고, 더 이상 새 후기를 못 찾으면
# 간격을 BACKOFF 배씩 늘린다. 단 하루(MAX=86400s)를 절대 넘지 않는다.
# 새 후기를 찾으면 다시 짧은 간격으로 리셋한다(빌더의 --reviews 적응형 루프).
#
# 사용: reviews-loop.sh start | stop | status
# 멱등: 이미 실행 중이면 start 는 아무것도 안 한다(cron keep-alive 안전).
set -uo pipefail
export PATH="/Users/kwanhyun/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

REPO="/Users/kwanhyun/jobseeker"
PY="$([ -x "$REPO/catch_capture/.venv/bin/python" ] && echo "$REPO/catch_capture/.venv/bin/python" || echo python3)"
SCRIPT="$REPO/jd-viewer/bin/build_company_tech_radar.py"
LOG="$REPO/jd-viewer/bin/reviews-loop.log"
PIDF="$REPO/jd-viewer/bin/.reviews-loop.pid"

N="${N:-3}"               # 사이클당 회사 수
START="${START:-180}"     # 시작/최소 간격(초) — 빠르게 데이터 담기
BACKOFF="${BACKOFF:-2}"   # 후기 못 찾을 때 간격 증가 배수
MAX="${MAX:-86400}"       # 상한(하루). 빌더가 86400 으로 하드 캡.

is_running() { [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF" 2>/dev/null)" 2>/dev/null; }

case "${1:-start}" in
  start)
    if is_running; then echo "이미 실행 중 (pid $(cat "$PIDF"))"; exit 0; fi
    command -v claude >/dev/null 2>&1 || { echo "claude CLI 없음 — 시작 불가"; exit 1; }
    echo "===== $(date '+%Y-%m-%d %H:%M:%S') 데몬 시작 (N=$N start=${START}s backoff=${BACKOFF} max=${MAX}s) =====" >> "$LOG"
    nohup "$PY" "$SCRIPT" --reviews "$N" --loop \
      --interval "$START" --backoff "$BACKOFF" --max-interval "$MAX" >> "$LOG" 2>&1 &
    echo $! > "$PIDF"
    echo "시작됨 (pid $!). 로그: $LOG"
    ;;
  stop)
    if is_running; then kill "$(cat "$PIDF")" 2>/dev/null && echo "중지됨"; else echo "실행 중 아님"; fi
    rm -f "$PIDF"
    ;;
  status)
    if is_running; then echo "실행 중 (pid $(cat "$PIDF"))"; else echo "중지됨"; fi
    ;;
  *)
    echo "사용: $0 start|stop|status"; exit 1
    ;;
esac
