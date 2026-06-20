#!/usr/bin/env bash
# 관리자(비공개) 서버 실행 — 127.0.0.1 전용. 공개 안 됨.
# 사용:  ./admin/run.sh        (catch_capture 디렉토리에서)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # catch_capture/
cd "$HERE"
exec .venv/bin/python -m admin.server
