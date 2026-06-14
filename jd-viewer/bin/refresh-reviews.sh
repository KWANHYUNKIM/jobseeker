#!/usr/bin/env bash
# 공개 면접 후기 자동 수집 — cron 이 주기적으로 실행.
# claude CLI 웹검색으로 공개 블로그/커리어 페이지의 면접 후기를 찾아 링크+요약으로
# 모으고 URL 실존을 검증(환각·사적사이트 차단)해 company_tech_radar.json 의
# interview.reviews 에 누적한다. 매 사이클 N개사씩 순회.
#
# 사적 후기 사이트(Blind/잡플래닛/Glassdoor 등)는 빌더가 도메인 차단한다.
# 크론 설치는 install-reviews-cron.sh 참고. 로그는 refresh-reviews.log 에 누적.
set -uo pipefail

export PATH="/Users/kwanhyun/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

REPO="/Users/kwanhyun/jobseeker"
PY="$([ -x "$REPO/catch_capture/.venv/bin/python" ] && echo "$REPO/catch_capture/.venv/bin/python" || echo python3)"
SCRIPT="$REPO/jd-viewer/bin/build_company_tech_radar.py"
LOG="$REPO/jd-viewer/bin/refresh-reviews.log"
LOCK="$REPO/jd-viewer/bin/.refresh-reviews.lock"
N="${1:-3}"

if ! mkdir "$LOCK" 2>/dev/null; then
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') 이미 실행 중 — 건너뜀 =====" >> "$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 후기 수집 시작 (N=$N) =====" >> "$LOG"
"$PY" "$SCRIPT" --reviews "$N" >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 완료 =====" >> "$LOG"
