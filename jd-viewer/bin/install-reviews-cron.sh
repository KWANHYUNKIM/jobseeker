#!/usr/bin/env bash
# 공개 면접 후기 자동 수집 cron 설치 (idempotent).
# 기본 12시간마다 refresh-reviews.sh 로 N개사씩 공개 후기를 수집·누적한다.
# 다시 실행해도 중복 등록되지 않는다. 제거: crontab -e 에서 해당 줄 삭제.
#
# 주의: cron 환경에서 claude CLI 인증과 웹검색이 동작해야 한다(구독 토큰 접근).
set -euo pipefail

SCRIPT="/Users/kwanhyun/jobseeker/jd-viewer/bin/refresh-reviews.sh"
SCHEDULE="15 */12 * * *"         # 12시간마다(00:15, 12:15)
N="3"
MARKER="# jobseeker-reviews-refresh"

chmod +x "$SCRIPT"

current="$(crontab -l 2>/dev/null | grep -v "$MARKER" || true)"
{
  [ -n "$current" ] && printf '%s\n' "$current"
  printf '%s %s %s %s\n' "$SCHEDULE" "$SCRIPT" "$N" "$MARKER"
} | crontab -

echo "설치 완료. 현재 crontab:"
crontab -l | grep "$MARKER"
