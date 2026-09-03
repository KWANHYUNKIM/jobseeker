#!/usr/bin/env bash
# 호스트 네이티브 파이썬 서버들을 launchd 로 상시 띄운다.
#
#   ops (8770)   : 크롤 파이프라인 실시간 운영 대시보드 — "지금 뭘 하는지"
#   stats(8765)  : 통계 대시보드 — 공고 분류·집계
#   search(8771) : 하이브리드 검색 API — 뷰어가 /api/ 로 부른다
#   collect(8772): 행동 기록 수집 — 뷰어가 /collect 로 부른다
#
# ops·stats 는 dashboards 프로필의 터널로 외부에 직접 노출된다. search 는 다르다.
# 뷰어 nginx 가 /api/ 를 이 포트로 프록시하므로 뷰어 주소만 열려 있으면 되고,
# 별도 터널이 필요 없다.
#
# 사용:
#   ./deploy/setup-dashboards.sh              # 두 서버를 launchd 로 등록·기동
#   ./deploy/setup-dashboards.sh --uninstall  # 해제
#
# 터널은 docker-compose.prod.yml 의 dashboards 프로필이 담당한다.
# 이 스크립트는 파이썬 서버(호스트 네이티브)만 관리한다. 크롤러와 같은 venv 를
# 쓰고 같은 파일을 읽으므로 컨테이너가 아니라 네이티브로 돈다.
#
# ⚠️ 두 대시보드 모두 인증이 없다. 터널 주소를 아는 사람은 누구나 본다.
#    admin(8910, 개인 이력·API키)은 절대 여기 포함하지 않는다 — LAN 전용.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ROOT="${ROOT:-$HOME/jobseeker}"
CATCH="$ROOT/catch_capture"
VENV="$CATCH/.venv"
UID_N="$(id -u)"

log()  { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# label / 모듈·인자 / bind 환경변수 / 포트
SERVICES=(
  "com.jobseeker.ops:monitoring.ops_server|--port|8770|--no-open:OPS_HOST:8770"
  "com.jobseeker.stats:dashboard/serve.py|--port|8765:DASH_HOST:8765"
  "com.jobseeker.search:semantic.server|--port|8771:SEARCH_HOST:8771"
  "com.jobseeker.collect:engagement.collect|--port|8772:COLLECT_HOST:8772"
)

uninstall() {
  for entry in "${SERVICES[@]}"; do
    label="${entry%%:*}"
    plist="$HOME/Library/LaunchAgents/$label.plist"
    launchctl bootout "gui/$UID_N/$label" 2>/dev/null || true
    rm -f "$plist"
    log "해제: $label"
  done
  exit 0
}
[ "${1:-}" = "--uninstall" ] && uninstall

[ -x "$VENV/bin/python" ] || die "venv 가 없습니다. 먼저 ./deploy/setup-crawler.sh 를 실행하세요."

for entry in "${SERVICES[@]}"; do
  label="${entry%%:*}"; rest="${entry#*:}"
  argspec="${rest%%:*}"; rest="${rest#*:}"
  bindvar="${rest%%:*}"; port="${rest##*:}"
  plist="$HOME/Library/LaunchAgents/$label.plist"

  # argspec 을 <string> 배열로. '|' 구분, 첫 토큰이 -m 모듈이면 -m 을 앞에 붙인다.
  IFS='|' read -ra parts <<< "$argspec"
  prog_args=""
  first="${parts[0]}"
  if [[ "$first" == *.py ]]; then
    prog_args+="    <string>$first</string>"$'\n'
  else
    prog_args+="    <string>-m</string>"$'\n'"    <string>$first</string>"$'\n'
  fi
  for a in "${parts[@]:1}"; do prog_args+="    <string>$a</string>"$'\n'; done

  log "등록: $label (포트 $port, bind 0.0.0.0)"
  cat > "$plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV/bin/python</string>
$prog_args  </array>
  <key>WorkingDirectory</key><string>$CATCH</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
    <!-- 터널 컨테이너가 host.docker.internal 로 붙어야 하므로 loopback 이 아닌 전체 인터페이스에 바인딩 -->
    <key>$bindvar</key><string>0.0.0.0</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/jobseeker-${label##*.}.out.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/jobseeker-${label##*.}.err.log</string>
</dict>
</plist>
PLIST_EOF

  plutil -lint "$plist" >/dev/null || die "plist 문법 오류: $label"
  launchctl bootout "gui/$UID_N/$label" 2>/dev/null || true

  # bootout 은 비동기다. 아직 내려가는 중인 label 을 다시 bootstrap 하면
  # "Bootstrap failed: 5: Input/output error" 로 죽는다 — 실제로 그렇게 멈춰서
  # 서비스 하나가 내려간 채 남은 적이 있다. 사라진 것을 확인하고 올린다.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    launchctl print "gui/$UID_N/$label" >/dev/null 2>&1 || break
    sleep 1
  done

  # 그래도 경합이 남을 수 있어 몇 번 다시 시도한다. 여기서 그냥 죽으면 앞에서
  # bootout 한 서비스가 올라오지 못한 채로 스크립트가 끝난다.
  ok=0
  for attempt in 1 2 3; do
    if launchctl bootstrap "gui/$UID_N" "$plist" 2>/dev/null; then ok=1; break; fi
    warn "  bootstrap 재시도 ($attempt/3): $label"
    sleep 2
  done
  [ "$ok" = 1 ] || die "bootstrap 실패: $label (launchctl print gui/$UID_N/$label 로 확인)"
done

log "기동 확인"
sleep 3
for entry in "${SERVICES[@]}"; do
  port="${entry##*:}"
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:$port/" 2>/dev/null || echo 000)
  [ "$code" = "200" ] && log "  포트 $port → HTTP 200" || warn "  포트 $port → HTTP $code (로그 확인 필요)"
done

echo
echo "  터널로 외부 공개:  COMPOSE_PROFILES 에 dashboards 를 추가해 배포"
echo "     예) COMPOSE_PROFILES=quick,dashboards docker compose -f docker-compose.prod.yml up -d"
echo "  주소 확인:         ./deploy/tunnel-url.sh"
echo "  해제:              ./deploy/setup-dashboards.sh --uninstall"
