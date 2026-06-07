#!/usr/bin/env bash
# 가장 최근의 통합 폴더로 all_개발자_latest 심볼릭링크를 갱신.
# 멀티 키워드 통합(all_통합_*)이 있으면 그것을, 없으면 단일 키워드(all_개발자_*)를 쓴다.
# enrich_jobs.py 가 all_개발자_latest 만 읽으므로 심링크 대상만 바꿔 무수정으로 통합본을 소비한다.
set -euo pipefail

SCREENSHOTS_DIR="$(cd "$(dirname "$0")/../.." && pwd)/catch_capture/screenshots"
cd "$SCREENSHOTS_DIR"

LATEST=$(ls -1dt all_통합_* 2>/dev/null | grep -v '_latest$' | head -1)
if [ -z "$LATEST" ]; then
  LATEST=$(ls -1dt all_개발자_* 2>/dev/null | grep -v '_latest$' | head -1)
fi
if [ -z "$LATEST" ]; then
  echo "all_통합_* / all_개발자_* 폴더를 찾을 수 없습니다." >&2
  exit 1
fi

ln -sfn "$LATEST" all_개발자_latest
echo "latest -> $LATEST"

# enrich + mindmap 재빌드
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/enrich_jobs.py"
python3 "$SCRIPT_DIR/build_mindmap.py"
