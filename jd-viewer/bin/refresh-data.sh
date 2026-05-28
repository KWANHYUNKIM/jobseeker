#!/usr/bin/env bash
# 가장 최근의 all_개발자_YYYYMMDD_HHMMSS 폴더로 latest 심볼릭링크를 갱신
set -euo pipefail

SCREENSHOTS_DIR="$(cd "$(dirname "$0")/../.." && pwd)/catch_capture/screenshots"
cd "$SCREENSHOTS_DIR"

LATEST=$(ls -1dt all_개발자_* 2>/dev/null | grep -v '_latest$' | head -1)
if [ -z "$LATEST" ]; then
  echo "all_개발자_* 폴더를 찾을 수 없습니다." >&2
  exit 1
fi

ln -sfn "$LATEST" all_개발자_latest
echo "latest -> $LATEST"

# enrich + mindmap 재빌드
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/enrich_jobs.py"
python3 "$SCRIPT_DIR/build_mindmap.py"
