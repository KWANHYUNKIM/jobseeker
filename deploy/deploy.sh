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

log() { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

cd "$DEPLOY_DIR" || die "배포 디렉토리가 없습니다: $DEPLOY_DIR"
[ -f "$COMPOSE_FILE" ] || die "$COMPOSE_FILE 이 없습니다"
[ -f .env ] || die ".env 가 없습니다. .env.example 을 복사해 CLOUDFLARE_TUNNEL_TOKEN 을 채우세요"

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

# 터널이 실제로 커넥션을 맺었는지 확인. 여기가 죽으면 뷰어가 살아있어도
# 외부에서는 502 만 보인다.
if ! docker compose -f "$COMPOSE_FILE" ps --status running cloudflared | grep -q cloudflared; then
  docker compose -f "$COMPOSE_FILE" logs --tail=50 cloudflared
  die "cloudflared 컨테이너가 running 상태가 아닙니다"
fi

# ── 정리 ───────────────────────────────────────────────────
log "미사용 이미지 정리"
docker image prune -f >/dev/null

log "배포 완료"
docker compose -f "$COMPOSE_FILE" ps
