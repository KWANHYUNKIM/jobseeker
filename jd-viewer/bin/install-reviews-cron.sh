#!/usr/bin/env bash
# 적응형 후기 수집 데몬 keep-alive cron 설치 (idempotent).
# 데몬은 스스로 적응형 간격(짧게 시작 → 후기 없으면 점점 늘림, 하루 캡)으로 돈다.
# 여기서는 그 데몬이 항상 살아있도록만 보장한다:
#   - @reboot: 부팅 시 데몬 시작
#   - 매시간: reviews-loop.sh start (이미 살아있으면 멱등하게 아무것도 안 함)
# 다시 실행해도 중복 등록되지 않는다. 제거: crontab -e 에서 해당 줄 삭제 후
#   jd-viewer/bin/reviews-loop.sh stop.
set -euo pipefail

SCRIPT="/Users/kwanhyun/jobseeker/jd-viewer/bin/reviews-loop.sh"
MARKER="# jobseeker-reviews-daemon"

chmod +x "$SCRIPT"

current="$(crontab -l 2>/dev/null | grep -v "$MARKER" || true)"
{
  [ -n "$current" ] && printf '%s\n' "$current"
  printf '@reboot %s start %s\n' "$SCRIPT" "$MARKER"
  printf '0 * * * * %s start %s\n' "$SCRIPT" "$MARKER"
} | crontab -

echo "설치 완료. 현재 crontab:"
crontab -l | grep "$MARKER"
echo
echo "지금 바로 시작: $SCRIPT start    /    상태: $SCRIPT status    /    로그: tail -f jd-viewer/bin/reviews-loop.log"
