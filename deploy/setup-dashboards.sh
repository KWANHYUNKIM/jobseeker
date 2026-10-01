#!/usr/bin/env bash
# 호스트 네이티브 파이썬 서버들을 launchd 로 상시 띄운다.
#
#   ops (8770)   : 크롤 파이프라인 실시간 운영 대시보드 — "지금 뭘 하는지"
#   stats(8765)  : 통계 대시보드 — 공고 분류·집계
#   search(8771) : 뷰어 API(backend/) — 공고·회사·검색… 뷰어가 /api/ 로 부른다
#   collect(8772): 행동 기록 수집 — 뷰어가 /collect 로 부른다
#
# ops·stats 는 dashboards 프로필의 터널로 외부에 직접 노출된다. search 는 다르다.
# 뷰어 nginx 가 /api/ 를 이 포트로 프록시하므로 뷰어 주소만 열려 있으면 되고,
# 별도 터널이 필요 없다.
#
# 사용:
#   ./deploy/setup-dashboards.sh              # 네 서버를 launchd 로 등록·기동
#   ./deploy/setup-dashboards.sh --reschedule # 내용이 바뀐 것만 다시 등록 (배포가 부른다)
#   ./deploy/setup-dashboards.sh --uninstall  # 해제
#
# --reschedule 이 있는 이유는 setup-crawler.sh 와 같다. launchd 는 등록 당시의
# 인자를 계속 들고 돈다 — 이 파일에서 모듈을 바꿔 커밋해도 누가 손으로 다시
# 등록하기 전까지 서버는 옛 모듈을 돌린다(2026-09-07 에 실제로 그랬다).
# 배포가 이걸 부르면 그 간격이 없어진다.
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

# 뷰어 API 는 backend/ 의 FastAPI 앱이다(크롤러와 같은 venv). DB 에 못 붙어도 죽지
# 않고 503 을 돌려준다 — 그동안 뷰어는 정적 파일로 물러서고, DB 가 살아나면 다시
# 등록하지 않아도 그대로 답한다. 예전처럼 옛 SQLite 판으로 되돌릴 자리는 없다.
API_DSN="${JOBSEEKER_DSN:-postgresql://jobseeker:jobseeker@127.0.0.1:5433/jobseeker}"

# label / 작업 폴더(ROOT 기준) / 모듈·인자 / bind 환경변수 / 포트 / 그 서비스에만 주는
# 환경변수(선택, '|' 로 여럿). 마지막 칸은 값에 ':' 가 들어갈 수 있어(DSN) 반드시 맨 뒤여야 한다.
SERVICES=(
  "com.jobseeker.ops:catch_capture:servers.ops.server|--port|8770|--no-open:OPS_HOST:8770:"
  "com.jobseeker.stats:catch_capture:servers.stats.server|--port|8765:DASH_HOST:8765:"
  "com.jobseeker.search:backend:app.main|--port|8771:SEARCH_HOST:8771:JOBSEEKER_DSN=$API_DSN"
  "com.jobseeker.collect:catch_capture:servers.collect.server|--port|8772:COLLECT_HOST:8772:"
)

# entry 를 여섯 칸으로 가른다. read 는 마지막 변수에 나머지를 통째로 넣으므로
# DSN 안의 ':' 가 살아남는다. here-string 끝에서 read 가 1 을 돌려주는데
# set -e 가 그걸 실패로 보므로 || true 로 받는다.
split_entry() {
  IFS=':' read -r S_LABEL S_DIR S_ARGS S_BIND S_PORT S_ENV <<< "$1" || true
}

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

RESCHEDULE=0
[ "${1:-}" = "--reschedule" ] && RESCHEDULE=1

[ -x "$VENV/bin/python" ] || die "venv 가 없습니다. 먼저 ./deploy/setup-crawler.sh 를 실행하세요."

# plist 본문을 파일이 아니라 표준출력으로 만든다. --reschedule 이 "지금 걸려 있는
# 것과 같은가" 를 문자열 비교 한 번으로 판정할 수 있어야 하기 때문이다.
render_plist() {  # label workdir argspec bindvar port extraenv
  local label="$1" workdir="$ROOT/$2" argspec="$3" bindvar="$4" extraenv="${6:-}"
  local prog_args="" extra_xml="" first a kv

  # argspec 을 <string> 배열로. '|' 구분, 첫 토큰이 -m 모듈이면 -m 을 앞에 붙인다.
  IFS='|' read -ra parts <<< "$argspec"
  first="${parts[0]}"
  if [[ "$first" == *.py ]]; then
    prog_args+="    <string>$first</string>"$'\n'
  else
    prog_args+="    <string>-m</string>"$'\n'"    <string>$first</string>"$'\n'
  fi
  for a in "${parts[@]:1}"; do prog_args+="    <string>$a</string>"$'\n'; done

  if [ -n "$extraenv" ]; then
    IFS='|' read -ra evs <<< "$extraenv"
    for kv in "${evs[@]}"; do
      [ -n "$kv" ] || continue
      extra_xml+="    <key>${kv%%=*}</key><string>${kv#*=}</string>"$'\n'
    done
  fi

  cat <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV/bin/python</string>
$prog_args  </array>
  <key>WorkingDirectory</key><string>$workdir</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
    <!-- 터널 컨테이너가 host.docker.internal 로 붙어야 하므로 loopback 이 아닌 전체 인터페이스에 바인딩 -->
    <key>$bindvar</key><string>0.0.0.0</string>
$extra_xml  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/jobseeker-${label##*.}.out.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/jobseeker-${label##*.}.err.log</string>
</dict>
</plist>
PLIST_EOF
}

install_service() {  # label plist 본문
  local label="$1" plist="$2" body="$3"
  printf '%s\n' "$body" > "$plist"

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
}

for entry in "${SERVICES[@]}"; do
  split_entry "$entry"
  plist="$HOME/Library/LaunchAgents/$S_LABEL.plist"
  body="$(render_plist "$S_LABEL" "$S_DIR" "$S_ARGS" "$S_BIND" "$S_PORT" "$S_ENV")"

  # 배포가 부르는 경로다. 걸려 있는 plist 가 이 파일이 만들 것과 한 글자도 다르지
  # 않고 서비스가 실제로 떠 있으면 건드리지 않는다 — 배포마다 검색 API 를 끊었다
  # 붙이면 그 몇 초 동안 뷰어의 /api/ 가 502 다.
  if [ "$RESCHEDULE" = 1 ] && [ -f "$plist" ] \
     && [ "$body" = "$(cat "$plist")" ] \
     && launchctl print "gui/$UID_N/$S_LABEL" >/dev/null 2>&1; then
    log "최신 상태 (건너뜀): $S_LABEL"
    continue
  fi

  log "등록: $S_LABEL (포트 $S_PORT, bind 0.0.0.0)"
  install_service "$S_LABEL" "$plist" "$body"
done

log "기동 확인"
sleep 3
for entry in "${SERVICES[@]}"; do
  split_entry "$entry"
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:$S_PORT/" 2>/dev/null || echo 000)
  if [ "$code" = "200" ]; then
    log "  포트 $S_PORT → HTTP 200 ($S_LABEL)"
    continue
  fi

  warn "  포트 $S_PORT → HTTP $code (로그 확인 필요)"
done

echo
echo "  터널로 외부 공개:  COMPOSE_PROFILES 에 dashboards 를 추가해 배포"
echo "     예) COMPOSE_PROFILES=quick,dashboards docker compose -f docker-compose.prod.yml up -d"
echo "  주소 확인:         ./deploy/tunnel-url.sh"
echo "  해제:              ./deploy/setup-dashboards.sh --uninstall"
