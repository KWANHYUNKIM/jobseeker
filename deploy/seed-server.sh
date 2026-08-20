#!/usr/bin/env bash
# 옛 서버(데이터가 온전한 쪽)에서 새 크롤 서버로 데이터를 옮겨 심는다.
#
#   ./deploy/seed-server.sh kwanhyun@192.168.45.241
#   ./deploy/seed-server.sh --dry-run kwanhyun@192.168.45.241
#
# 왜 필요한가:
#   누적 공고는 screenshots/{사이트}_{키워드}/ 고정 폴더에 쌓인다
#   (pipeline/aggregate.py 의 latest_run_dir). 이 폴더는 .gitignore 대상이라
#   git 으로는 절대 따라가지 않는다. 그래서 새 서버는 아무리 크롤을 돌려도
#   처음부터 다시 쌓는 셈이고, 한 사이클치(수백 건)밖에 못 만든다.
#
# 무엇을 옮기는가:
#   1) 누적 폴더 {사이트}_{키워드}  (~265MB)
#      과거 스냅샷 all_통합_* / all_개발자_* 는 제외한다. 39GB 인데다 파생물이라
#      옮길 이유가 없다. 새 서버가 첫 크롤을 돌리면 자기 스냅샷을 만든다.
#   2) 뷰어 데이터 jd-viewer/public/  (~90MB)
#      예전에는 git 에 추적돼서 원격이 origin/main 을 체크아웃하면 됐지만,
#      생성 데이터는 이제 추적하지 않는다(.gitignore). 그래서 여기서 함께 나른다.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

MIN_COUNT=1000
DRY_RUN=0
REMOTE=""
REMOTE_DIR="jobseeker"

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)    DRY_RUN=1; shift ;;
    --remote-dir) REMOTE_DIR="${2:?--remote-dir 뒤에 경로가 필요합니다}"; shift 2 ;;
    -h|--help)    sed -n '2,8p' "$0"; exit 0 ;;
    -*)           echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
    *)            REMOTE="$1"; shift ;;
  esac
done

[ -n "$REMOTE" ] || { echo "사용법: $0 [--dry-run] <user@host>" >&2; exit 2; }

log()  { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

PY="$([ -x "$ROOT_DIR/catch_capture/.venv/bin/python" ] \
      && echo "$ROOT_DIR/catch_capture/.venv/bin/python" || echo python3)"

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

SCREENS="$ROOT_DIR/catch_capture/screenshots"
[ -d "$SCREENS" ] || die "screenshots 가 없습니다: $SCREENS"

# ── 사전 점검 1: 이쪽 데이터가 정말 온전한가 ────────────────
# 축소된 쪽에서 실행하면 멀쩡한 서버를 망가뜨린다. 방향을 먼저 확인한다.
LOCAL_COUNT="$(count_stdin < "$ROOT_DIR/jd-viewer/public/all_jobs_enriched.json")"
[ -n "$LOCAL_COUNT" ] || die "로컬 all_jobs_enriched.json 을 읽을 수 없습니다."
[ "$LOCAL_COUNT" -ge "$MIN_COUNT" ] \
  || die "로컬이 ${LOCAL_COUNT}건뿐입니다 — 데이터가 온전한 쪽에서 실행하세요."
log "로컬 뷰어 데이터: ${LOCAL_COUNT}건"

# ── 누적 폴더 목록 ─────────────────────────────────────────
# all_* 은 스냅샷/심링크라 제외. 나머지가 {사이트}_{키워드} 누적 폴더다.
SEED_DIRS="$(cd "$SCREENS" && ls -d */ 2>/dev/null | grep -v '^all_' | tr -d '/' || true)"
[ -n "$SEED_DIRS" ] || die "옮길 누적 폴더가 없습니다."
SEED_N="$(printf '%s\n' "$SEED_DIRS" | grep -c .)"
log "옮길 누적 폴더: ${SEED_N}개"

if [ "$DRY_RUN" = "1" ]; then
  printf '%s\n' "$SEED_DIRS" | sed 's/^/    /' | head -20
  [ "$SEED_N" -gt 20 ] && echo "    ... 외 $((SEED_N - 20))개"
  warn "--dry-run 이므로 아무것도 전송하지 않았습니다."
  exit 0
fi

# ── 1) 누적 폴더 전송 ──────────────────────────────────────
# --ignore-existing 을 쓰지 않는다. 원격이 자체 크롤로 일부를 채웠을 수 있고,
# 그 경우 최신 파일로 맞춰줘야 한다. 삭제(--delete)는 하지 않는다 — 원격에만
# 있는 수집물을 날릴 이유가 없다.
log "누적 폴더 rsync → $REMOTE:~/$REMOTE_DIR/catch_capture/screenshots/"
# -r 을 반드시 명시한다. --files-from 은 -a 에 들어있는 재귀를 꺼버려서,
# 폴더 이름만 주면 빈 디렉토리만 만들고 내용은 한 파일도 안 옮긴다(무증상 실패).
printf '%s\n' "$SEED_DIRS" \
  | rsync -a -r --info=progress2 --human-readable \
      --files-from=- \
      "$SCREENS/" "$REMOTE:$REMOTE_DIR/catch_capture/screenshots/" \
  || die "rsync 실패"

# ── 2) 뷰어 데이터 전송 ────────────────────────────────────
# nginx 는 /data 볼륨(= 호스트 jd-viewer/public)에서 JSON 을 직접 읽으므로
# 컨테이너를 재시작할 필요가 없다. 파일만 바꾸면 즉시 반영된다.
#
# all_jobs.json 은 screenshots/ 안을 가리키는 심링크다. 원격의 심링크 타겟은
# 원격 크롤이 정하므로 여기서 덮어쓰지 않는다.
log "뷰어 데이터 rsync → $REMOTE:~/$REMOTE_DIR/jd-viewer/public/"
rsync -a --info=progress2 --human-readable \
    --exclude 'all_jobs.json' \
    "$ROOT_DIR/jd-viewer/public/" "$REMOTE:$REMOTE_DIR/jd-viewer/public/" \
  || die "뷰어 데이터 rsync 실패"

ssh "$REMOTE" "cd ~/$REMOTE_DIR && echo -n '  전송 후 건수: ' &&
  python3 -c 'import json;print(len(json.load(open(\"jd-viewer/public/all_jobs_enriched.json\"))))'
" || die "원격 확인 실패"

log "완료"
echo
echo "  확인 : curl -s http://<서버>:8080/all_jobs_enriched.json | head -c 80"
echo
echo "  남은 일 (원격에서):"
echo "    1) 크롤 스케줄을 멀티 키워드로 재등록 — 단일 키워드면 또 축소된다"
echo "         ./deploy/setup-crawler.sh --uninstall"
echo "         git pull        # 멀티 키워드 기본값 + refresh-data.sh 급감 가드"
echo "         ./deploy/setup-crawler.sh --schedule"
echo "    2) 첫 사이클 뒤 건수 확인 — 급감 가드가 막으면 누적이 덜 옮겨진 것이다"
