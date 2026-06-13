#!/usr/bin/env bash
# 기술 스택 레이더 자동 갱신 — cron 이 주기적으로 실행.
# 가장 오래 갱신 안 된 N개사를 로컬 claude CLI 로 리서치해 '왜 이 언어/아키텍처인지'를
# 다시 쓰고 public/company_tech_radar.json 을 in-place 갱신한다. 매 사이클 N개씩만
# 돌려 100개사를 천천히 순회하며 계속 최신화한다(증분 루프).
#
# 크론 설치는 jd-viewer/bin/install-radar-cron.sh 참고. 로그는 같은 폴더의
# refresh-radar.log 에 누적된다. claude CLI 인증이 안 되면 빌더가 조용히 건너뛴다.
set -euo pipefail

# cron 의 빈약한 PATH 에 claude/python/gh 위치를 보강
export PATH="/Users/kwanhyun/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# gh CLI 가 로그인돼 있으면 토큰을 실어 GitHub API 한도를 5000/h 로 올린다(repo 검증·star 보강).
if [ -z "${GITHUB_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
  export GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"
fi

REPO="/Users/kwanhyun/jobseeker"
PY="$([ -x "$REPO/catch_capture/.venv/bin/python" ] && echo "$REPO/catch_capture/.venv/bin/python" || echo python3)"
SCRIPT="$REPO/jd-viewer/bin/build_company_tech_radar.py"
LOG="$REPO/jd-viewer/bin/refresh-radar.log"
LOCK="$REPO/jd-viewer/bin/.refresh-radar.lock"
N="${1:-4}"                      # 사이클당 갱신할 회사 수(인자로 조절)

# 중복 실행 방지 — mkdir 은 원자적이라 이미 돌고 있으면 건너뛴다.
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') 이미 실행 중 — 건너뜀 =====" >> "$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 레이더 갱신 시작 (N=$N) =====" >> "$LOG"
"$PY" "$SCRIPT" --refine "$N" >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 완료 =====" >> "$LOG"
