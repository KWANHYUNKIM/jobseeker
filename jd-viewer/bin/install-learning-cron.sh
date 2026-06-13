#!/usr/bin/env bash
# 학습 영상 자동 갱신 cron 설치 (idempotent).
# 6시간마다 refresh-learning.sh 를 실행하도록 현재 사용자 crontab 에 등록한다.
# 다시 실행해도 중복 등록되지 않는다. 제거: crontab -e 에서 해당 줄 삭제.
#
# 주기를 바꾸려면 SCHEDULE 을 수정(예: 매일 새벽 4시 = "0 4 * * *").
set -euo pipefail

SCRIPT="/Users/kwanhyun/jobseeker/jd-viewer/bin/refresh-learning.sh"
SCHEDULE="0 */6 * * *"          # 6시간마다 (00,06,12,18시)
MARKER="# jobseeker-learning-refresh"

chmod +x "$SCRIPT"

# 기존 동일 마커 줄 제거 후 새로 추가
current="$(crontab -l 2>/dev/null | grep -v "$MARKER" || true)"
{
  [ -n "$current" ] && printf '%s\n' "$current"
  printf '%s %s %s\n' "$SCHEDULE" "$SCRIPT" "$MARKER"
} | crontab -

echo "설치 완료. 현재 crontab:"
crontab -l | grep "$MARKER"
