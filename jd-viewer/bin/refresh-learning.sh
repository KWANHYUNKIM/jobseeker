#!/usr/bin/env bash
# 학습 영상/커리큘럼 자동 갱신 — cron 이 주기적으로 실행.
# build_learning.py --refresh 로 YouTube 를 다시 긁어 최신 영상으로 재배치하고
# public/learning_resources.json 을 갱신한다. dev 서버(5173)는 다음 새로고침 때
# 갱신된 데이터를 읽는다. (배포 dist 를 쓰면 별도로 빌드 필요.)
#
# 크론 설치는 jd-viewer/bin/install-learning-cron.sh 참고. 로그는 같은 폴더의
# refresh-learning.log 에 누적된다.
set -euo pipefail

REPO="/Users/kwanhyun/jobseeker"
PY="$REPO/catch_capture/.venv/bin/python"
SCRIPT="$REPO/jd-viewer/bin/build_learning.py"
LOG="$REPO/jd-viewer/bin/refresh-learning.log"
LOCK="$REPO/jd-viewer/bin/.refresh-learning.lock"

# 중복 실행 방지 — mkdir 은 원자적이라 이미 돌고 있으면 건너뛴다.
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') 이미 실행 중 — 건너뜀 =====" >> "$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 학습 갱신 시작 =====" >> "$LOG"
"$PY" "$SCRIPT" --refresh >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 완료 =====" >> "$LOG"
