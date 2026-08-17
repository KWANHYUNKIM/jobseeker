#!/usr/bin/env bash
# 지금 떠 있는 터널의 공개 주소를 출력한다.
#
#   ./deploy/tunnel-url.sh
#
# quick 프로필의 trycloudflare 주소는 재시작마다 바뀌므로, 밖에 나가 있을 때
# 주소를 잃어버리면 서버에 붙어서 이걸 실행해야 한다. 그게 곤란하면 ngrok
# 정적 도메인(NGROK_DOMAIN)이나 Cloudflare 고정 터널로 바꾸는 게 낫다.
set -euo pipefail

# ipconfig 는 /usr/sbin 에 있다. 빼먹으면 LAN 주소가 "?" 로 나온다.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "${DEPLOY_DIR:-$HOME/jobseeker}"
COMPOSE_FILE="docker-compose.prod.yml"

found=0

if docker ps --format '{{.Names}}' | grep -qx jobseeker-quicktunnel; then
  url=$(docker compose -f "$COMPOSE_FILE" logs quicktunnel 2>/dev/null \
        | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
  [ -n "$url" ] && { echo "quick   : $url  (재시작하면 바뀜)"; found=1; }
fi

if docker ps --format '{{.Names}}' | grep -qx jobseeker-ngrok; then
  url=$(docker compose -f "$COMPOSE_FILE" logs ngrok 2>/dev/null \
        | grep -o 'https://[a-zA-Z0-9.-]*\.ngrok[a-z.-]*' | tail -1)
  [ -n "$url" ] && { echo "ngrok   : $url  (고정)"; found=1; }
fi

if docker ps --format '{{.Names}}' | grep -qx jobseeker-tunnel; then
  echo "tunnel  : Cloudflare 대시보드에 설정한 도메인  (고정)"
  found=1
fi

for svc in ops stats; do
  name="jobseeker-${svc}-tunnel"
  if docker ps --format '{{.Names}}' | grep -qx "$name"; then
    url=$(docker compose -f "$COMPOSE_FILE" logs "${svc}-tunnel" 2>/dev/null \
          | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
    [ -n "$url" ] && { printf "%-8s: %s  (인증 없음, 재시작하면 바뀜)\n" "$svc" "$url"; found=1; }
  fi
done

if docker ps --format '{{.Names}}' | grep -qx jobseeker-viewer; then
  ip=$(ipconfig getifaddr en0 2>/dev/null || echo "?")
  echo "LAN     : http://${ip}:8080"
  found=1
fi

[ "$found" -eq 1 ] || { echo "떠 있는 서비스가 없습니다. ./deploy/deploy.sh 를 먼저 실행하세요." >&2; exit 1; }
