#!/usr/bin/env bash
# 뷰어 데이터(jd-viewer/public/*.json)를 git 이력의 마지막 정상본으로 되돌린다.
#
# ⚠️ 2026-08-18 부터 생성 데이터는 git 이 추적하지 않는다(.gitignore). 이 스크립트가
#    닿는 이력은 그 이전 커밋까지다. 지금 데이터를 복구해야 한다면 누적 폴더가 원본이므로
#    `jd-viewer/bin/refresh-data.sh` 로 다시 만드는 쪽이 맞다(급감 가드 내장).
#    다른 서버에서 통째로 받아오려면 `deploy/seed-server.sh` 를 쓴다.
#
#   ./deploy/restore-data.sh              # 이력에서 정상본을 찾아 복구
#   ./deploy/restore-data.sh <rev>        # 특정 리비전에서 복구
#   ./deploy/restore-data.sh --dry-run    # 무엇을 되돌릴지만 보여주고 끝
#   ./deploy/restore-data.sh --min 5000   # "정상" 판정 최소 건수 (기본 1000)
#   ./deploy/restore-data.sh --force      # 현재 데이터가 멀쩡해도 강행
#
# 왜 origin/main 을 그냥 쓰지 않는가:
#   크롤 서버의 autocommit 은 JOBSEEKER_AUTOPUSH=1 로 push 까지 한다
#   (deploy/setup-crawler.sh 의 launchd plist). 그래서 축소된 데이터가 이미
#   origin/main 에 올라가 있을 수 있고, 그 경우 origin 에서 받으면 축소본을
#   그대로 다시 받는다. 여기서는 이력을 최신부터 훑어 건수가 정상인 커밋을
#   직접 찾는다.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

TARGET="jd-viewer/public/all_jobs_enriched.json"
PUBLIC_DIR="jd-viewer/public"
MIN_COUNT=1000
DRY_RUN=0
FORCE=0
REV=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --force)   FORCE=1; shift ;;
    --min)     MIN_COUNT="${2:?--min 뒤에 숫자가 필요합니다}"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    -*)        echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
    *)         REV="$1"; shift ;;
  esac
done

log()  { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

PY="$([ -x "$ROOT_DIR/catch_capture/.venv/bin/python" ] \
      && echo "$ROOT_DIR/catch_capture/.venv/bin/python" || echo python3)"

# stdin 의 JSON 배열 길이를 찍는다. 배열이 아니거나 깨졌으면 아무것도 안 찍는다.
count_stdin() {
  "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if isinstance(d, list):
    print(len(d))
' 2>/dev/null || true
}

git rev-parse --git-dir >/dev/null 2>&1 || die "git 저장소가 아닙니다: $ROOT_DIR"

CURRENT=""
[ -f "$TARGET" ] && CURRENT="$(count_stdin < "$TARGET")"
log "현재 작업트리: ${CURRENT:-읽을 수 없음}건"

if [ -z "$REV" ]; then
  log "이력에서 ${MIN_COUNT}건 이상인 마지막 커밋 탐색 (최신순)"
  # 파일을 건드린 커밋만 훑는다. 보통 1~2개 안에 걸린다.
  while read -r c; do
    [ -n "$c" ] || continue
    n="$(git show "$c:$TARGET" 2>/dev/null | count_stdin)"
    [ -n "$n" ] || { printf '    %s  (읽기 실패)\n' "${c:0:8}"; continue; }
    printf '    %s  %s건\n' "${c:0:8}" "$n"
    if [ "$n" -ge "$MIN_COUNT" ]; then REV="$c"; FOUND_COUNT="$n"; break; fi
  done < <(git rev-list HEAD -- "$TARGET" | head -50)
  [ -n "$REV" ] || die "최근 50개 커밋 안에 ${MIN_COUNT}건 이상인 정상본이 없습니다. --min 을 낮추거나 리비전을 직접 지정하세요."
else
  FOUND_COUNT="$(git show "$REV:$TARGET" 2>/dev/null | count_stdin)"
  [ -n "$FOUND_COUNT" ] || die "$REV 에서 $TARGET 을 읽을 수 없습니다."
fi

SUBJECT="$(git log -1 --format='%h %cd %s' --date=format:'%Y-%m-%d %H:%M' "$REV")"
log "복구 대상: $SUBJECT"
log "  ${CURRENT:-?}건  →  ${FOUND_COUNT}건"

if [ -n "$CURRENT" ] && [ "$CURRENT" -ge "$FOUND_COUNT" ] && [ "$FORCE" != "1" ]; then
  warn "현재 데이터(${CURRENT}건)가 복구본(${FOUND_COUNT}건)보다 적지 않습니다 — 복구할 이유가 없습니다."
  warn "그래도 되돌리려면 --force 를 붙이세요."
  exit 0
fi

# 파생 JSON(mindmap, company_stacks, trends ...)도 같은 스냅샷에서 나온 것이라
# 함께 되돌려야 숫자가 서로 안 맞는 상태를 피할 수 있다.
# mapfile 은 bash 4+ 전용이라 macOS 기본 bash(3.2)에서 깨진다 — 쓰지 않는다.
FILES="$(git ls-tree -r --name-only "$REV" -- "$PUBLIC_DIR")"
log "되돌릴 파일 $(printf '%s\n' "$FILES" | grep -c .)개 ($PUBLIC_DIR)"

if [ "$DRY_RUN" = "1" ]; then
  printf '%s\n' "$FILES" | sed 's/^/    /'
  warn "--dry-run 이므로 아무것도 바꾸지 않았습니다."
  exit 0
fi

git checkout "$REV" -- "$PUBLIC_DIR"

AFTER="$(count_stdin < "$TARGET")"
[ "$AFTER" = "$FOUND_COUNT" ] || die "복구 후 건수가 예상과 다릅니다: ${AFTER:-읽기 실패} (예상 $FOUND_COUNT)"
log "복구 완료 — ${AFTER}건"

echo
echo "  남은 일:"
echo "    1) 크롤 스케줄이 다시 덮어쓰지 않는지 확인 — refresh-data.sh 의 급감 가드가 막아준다"
echo "    2) 커밋 : git commit -m 'fix(data): 축소된 뷰어 데이터를 정상본으로 복구' $PUBLIC_DIR"
echo "    3) 서버라면 누적 폴더도 함께 복구해야 다음 크롤이 정상 건수를 낸다:"
echo "       rsync -a <옛서버>:~/jobseeker/catch_capture/screenshots/ catch_capture/screenshots/"
