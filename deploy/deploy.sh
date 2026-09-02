#!/usr/bin/env bash
# jobseeker 배포 스크립트 — GitHub Actions self-hosted runner 와 수동 실행 양쪽에서 쓴다.
#
#   ./deploy/deploy.sh          # origin/main 으로 동기화 후 재배포
#   ./deploy/deploy.sh --local  # 동기화 없이 현재 워킹트리로 재배포
#
# 러너는 launchd 로 뜨기 때문에 로그인 셸 PATH 를 물려받지 못한다. Homebrew
# 경로를 명시적으로 넣어줘야 docker/git 을 찾는다.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

DEPLOY_DIR="${DEPLOY_DIR:-$HOME/jobseeker}"
COMPOSE_FILE="docker-compose.prod.yml"
BRANCH="${DEPLOY_BRANCH:-main}"
HEALTH_URL="http://127.0.0.1:8080/"

log()  { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

cd "$DEPLOY_DIR" || die "배포 디렉토리가 없습니다: $DEPLOY_DIR"
[ -f "$COMPOSE_FILE" ] || die "$COMPOSE_FILE 이 없습니다"

# .env 는 선택이다. 도메인 없이 LAN 으로만 쓰면 채울 값이 없다.
# 다만 COMPOSE_PROFILES 를 여기 적어두면 GitHub Actions 처럼 셸 환경변수를
# 넘겨줄 수 없는 경로에서도 터널이 함께 뜬다. compose 는 .env 의
# COMPOSE_PROFILES 를 직접 읽지만, 아래 검증 로직도 봐야 하므로 미리 읽는다.
[ -f .env ] && . ./.env
export COMPOSE_PROFILES="${COMPOSE_PROFILES:-}"

# 고정 주소 터널을 켰다면 토큰이 반드시 있어야 한다. compose 쪽에서 `:?` 로
# 강제하면 비활성 프로필까지 평가돼 기본 구성이 막히므로 여기서 검사한다.
case "$COMPOSE_PROFILES" in
  *tunnel*)
    [ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ] \
      || die "tunnel 프로필에는 .env 의 CLOUDFLARE_TUNNEL_TOKEN 이 필요합니다"
    ;;
esac

# ── Docker 데몬 확인 ────────────────────────────────────────
# Docker Desktop 은 사용자 앱이라 재부팅 후 로그인 전까지 안 떠 있을 수 있다.
if ! docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  log "Docker 데몬이 꺼져 있어 Docker Desktop 을 기동합니다"
  open -a Docker || die "Docker Desktop 기동 실패"
  for _ in $(seq 1 30); do
    docker version --format '{{.Server.Version}}' >/dev/null 2>&1 && break
    sleep 2
  done
  docker version --format '{{.Server.Version}}' >/dev/null 2>&1 \
    || die "Docker 데몬이 60초 안에 뜨지 않았습니다"
fi

# ── 소스 동기화 ────────────────────────────────────────────
# --ff-only: 로컬에 커밋되지 않은/갈라진 변경이 있으면 조용히 덮어쓰지 않고
# 실패시킨다. 크롤러가 만든 데이터를 날리는 것보다 배포 실패가 낫다.
if [ "${1:-}" != "--local" ]; then
  log "origin/$BRANCH 동기화"
  git fetch --prune origin
  git merge --ff-only "origin/$BRANCH" \
    || die "fast-forward 불가. 로컬 변경/분기를 먼저 정리하세요 (git status 확인)"
fi
log "배포 리비전: $(git rev-parse --short HEAD) — $(git log -1 --pretty=%s)"

# ── 크롤 스케줄 재등록 ─────────────────────────────────────
# launchd 는 등록 당시의 인자를 계속 들고 돈다. setup-crawler.sh 의
# KEYWORD/COUNT/INTERVAL 기본값을 고쳐 커밋해도, 누가 손으로 재등록하기 전까지
# 서버는 옛 인자로 크롤한다. 실제로 2026-08-17 에 들어온 멀티 키워드 기본값이
# 9/2 까지 반영되지 않아 수집량이 절반이었다.
#
# --reschedule 은 plist 가 최신 기본값과 같으면 아무것도 하지 않고, 크롤이
# 돌고 있으면 사이클을 죽이지 않으려 다음 배포로 미룬다. 스케줄이 아예 등록되지
# 않은 머신(뷰어 전용)에서는 그냥 건너뛴다.
if [ -x ./deploy/setup-crawler.sh ]; then
  # 여기서 실패해도 뷰어 배포까지 막을 이유는 없다.
  ./deploy/setup-crawler.sh --reschedule || warn "크롤 스케줄 재등록 실패 — 수동 확인 필요"
fi

# ── 빌드 & 기동 ────────────────────────────────────────────
log "이미지 빌드 및 컨테이너 기동"
docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans

# ── 헬스체크 ───────────────────────────────────────────────
log "헬스체크: $HEALTH_URL"
for i in $(seq 1 30); do
  if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then
    log "정상 응답 확인 (${i}회차)"
    break
  fi
  [ "$i" -eq 30 ] && {
    docker compose -f "$COMPOSE_FILE" logs --tail=50 viewer
    die "헬스체크 실패 — 뷰어가 응답하지 않습니다"
  }
  sleep 2
done

# 터널 프로필을 켠 경우에만 검사한다. 여기가 죽으면 뷰어가 살아있어도
# 외부에서는 502 만 보인다.
case "${COMPOSE_PROFILES:-}" in
  *tunnel*)
    docker compose -f "$COMPOSE_FILE" ps --status running --services | grep -qx cloudflared || {
      docker compose -f "$COMPOSE_FILE" logs --tail=50 cloudflared
      die "cloudflared 컨테이너가 running 상태가 아닙니다"
    }
    ;;
  *quick*)
    docker compose -f "$COMPOSE_FILE" ps --status running --services | grep -qx quicktunnel || {
      docker compose -f "$COMPOSE_FILE" logs --tail=50 quicktunnel
      die "quicktunnel 컨테이너가 running 상태가 아닙니다"
    }
    # 임시 터널 주소는 매번 바뀌므로 배포 로그에 남겨준다.
    url=$(docker compose -f "$COMPOSE_FILE" logs quicktunnel 2>/dev/null \
          | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
    [ -n "$url" ] && log "임시 공개 주소: $url  (재시작하면 바뀜)"
    ;;
  *ngrok*)
    [ -n "${NGROK_AUTHTOKEN:-}" ] && [ -n "${NGROK_DOMAIN:-}" ] \
      || die "ngrok 프로필에는 .env 의 NGROK_AUTHTOKEN 과 NGROK_DOMAIN 이 필요합니다"
    docker compose -f "$COMPOSE_FILE" ps --status running --services | grep -qx ngrok || {
      docker compose -f "$COMPOSE_FILE" logs --tail=50 ngrok
      die "ngrok 컨테이너가 running 상태가 아닙니다"
    }
    log "공개 주소: https://${NGROK_DOMAIN}"
    ;;
esac

# ── 정리 ───────────────────────────────────────────────────
log "미사용 이미지 정리"
docker image prune -f >/dev/null

log "배포 완료"
docker compose -f "$COMPOSE_FILE" ps
