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

# 로그에 찍힌 주소가 **지금도** 살아 있는지. quick 터널은 연결이 오래 끊기면 이름이
# 회수되는데 컨테이너는 running 으로 남는다. 그래서 로그만 보면 죽은 주소를 산 것처럼
# 알려 준다(2026-09-17 에 ops·stats·뷰어 셋 다 그랬다 — 1.1.1.1 에서 NXDOMAIN).
alive() {
  local code
  # 이 맥의 로컬 DNS 는 갓 발급된 trycloudflare 이름을 한동안 못 찾는다. 그러면 살아 있는
  # 터널을 죽었다고 판정한다(2026-09-17 교체 직후 실제로 그랬다 — 밖에서는 200 이었다).
  # 공개 리졸버에 DoH 로 직접 묻는다. curl 이 --doh-url 을 모르면 그냥 간다.
  # grep 에 -q 를 쓰지 않는다: 일찍 끝나면 curl 이 SIGPIPE 를 맞고, pipefail 아래서는
  # 찾았는데도 못 찾은 것으로 나온다.
  if curl --help all 2>/dev/null | grep -- '--doh-url' >/dev/null; then
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 --doh-url https://1.1.1.1/dns-query "$1" 2>/dev/null || true)
  else
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$1" 2>/dev/null || true)
  fi
  case "${code:-000}" in
    000) echo "끊김 — 이름이 없다, 재시작 필요" ;;
    530) echo "끊김 — 터널이 원본에 안 붙음, 재시작 필요" ;;
    5*)  echo "원본 오류 HTTP $code" ;;
    *)   echo "살아 있음" ;;
  esac
}

if docker ps --format '{{.Names}}' | grep -qx jobseeker-quicktunnel; then
  url=$(docker compose -f "$COMPOSE_FILE" logs quicktunnel 2>/dev/null \
        | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
  [ -n "$url" ] && { echo "quick   : $url  (재시작하면 바뀜)  [$(alive "$url")]"; found=1; }
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
    [ -n "$url" ] && { printf "%-8s: %s  (인증 없음, 재시작하면 바뀜)  [%s]\n" "$svc" "$url" "$(alive "$url")"; found=1; }
  fi
done

if docker ps --format '{{.Names}}' | grep -qx jobseeker-viewer; then
  ip=$(ipconfig getifaddr en0 2>/dev/null || echo "?")
  echo "LAN     : http://${ip}:8080"
  found=1
fi

[ "$found" -eq 1 ] || { echo "떠 있는 서비스가 없습니다. ./deploy/deploy.sh 를 먼저 실행하세요." >&2; exit 1; }
