#!/usr/bin/env bash
# 기술 스택 레이더 자동 갱신 cron 설치 (idempotent).
# 6시간마다 refresh-radar.sh 를 실행해 N개사씩 claude CLI 로 리서치·갱신한다.
# 다시 실행해도 중복 등록되지 않는다. 제거: crontab -e 에서 해당 줄 삭제.
#
# 주기/개수를 바꾸려면 SCHEDULE, N 을 수정(예: 매시간 2개사 = SCHEDULE "0 * * * *", N=2).
set -euo pipefail

SCRIPT="/Users/kwanhyun/jobseeker/jd-viewer/bin/refresh-radar.sh"
SCHEDULE="30 */6 * * *"         # 6시간마다(00:30,06:30,12:30,18:30) — learning 과 30분 비켜서 실행
N="4"                           # 사이클당 갱신할 회사 수
MARKER="# jobseeker-radar-refresh"

chmod +x "$SCRIPT"

# 기존 동일 마커 줄 제거 후 새로 추가
current="$(crontab -l 2>/dev/null | grep -v "$MARKER" || true)"
{
  [ -n "$current" ] && printf '%s\n' "$current"
  printf '%s %s %s %s\n' "$SCHEDULE" "$SCRIPT" "$N" "$MARKER"
} | crontab -

echo "설치 완료. 현재 crontab:"
crontab -l | grep "$MARKER"
