#!/usr/bin/env bash
# 소셜 자동 발행 데몬(인스타 + 페이스북 페이지)을 launchd 로 5분마다 돌린다.
#
#   ./deploy/setup-publisher.sh               # 등록·기동
#   ./deploy/setup-publisher.sh --reschedule  # 내용이 바뀐 것만 다시 등록 (배포가 부른다)
#   ./deploy/setup-publisher.sh --uninstall   # 해제
#
# 상주 프로세스가 아니라 `python -m publish.daemon tick` 1회 실행을 launchd 가 주기로 부른다
# (크롤러와 같은 방식). tick 한 번이 승인 묶음 받기 → 마감 제외 → 예약 → 발행 한 건 →
# 반응·토큰 → 상태 파일까지 하고 끝난다. 결과는 크롤 운영 대시보드(8770)의 '인스타 발행' 칸.
#
# 등록해도 config/accounts.json 의 autopublish.live 가 true 이고 인스타 자격이 있어야
# 실제로 나간다. 없으면 연습 발행(rehearsed)만 남는다 — 설치 자체로 사고가 나지 않는다.
# 계정 연결 절차는 design-lab/SOCIAL.md.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ROOT="${ROOT:-$HOME/jobseeker}"
LAB="$ROOT/design-lab"
VENV="$ROOT/catch_capture/.venv"
LABEL="com.jobseeker.publisher"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
INTERVAL="${PUBLISH_INTERVAL:-300}"

log()  { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  log "해제: $LABEL (원장·승인 이미지는 그대로 둔다)"
  exit 0
fi

write_plist() {  # $1 = 쓸 경로
  cat > "$1" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>$VENV/bin/python</string>
    <string>-m</string>
    <string>publish.daemon</string>
    <string>tick</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$LAB</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>

  <key>StartInterval</key>
  <integer>$INTERVAL</integer>

  <key>RunAtLoad</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$HOME/Library/Logs/jobseeker-publisher.out.log</string>
  <key>StandardErrorPath</key>
  <string>$HOME/Library/Logs/jobseeker-publisher.err.log</string>
</dict>
</plist>
PLIST_EOF
  plutil -lint "$1" >/dev/null || die "plist 문법 오류"
}

reload_plist() {
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || die "launchd 등록 실패"
}

if [ "${1:-}" = "--reschedule" ]; then
  [ -f "$PLIST" ] || { log "발행 데몬이 등록돼 있지 않습니다 — 재등록 건너뜀"; exit 0; }
  tmp="$(mktemp -t jobseeker-publisher-plist)"
  trap 'rm -f "$tmp"' EXIT
  write_plist "$tmp"
  if cmp -s "$tmp" "$PLIST"; then
    log "발행 데몬 최신 상태 (재등록 불필요)"
    exit 0
  fi
  cp "$tmp" "$PLIST"
  reload_plist
  log "발행 데몬 재등록 — ${INTERVAL}초마다 tick"
  exit 0
fi

[ -d "$LAB" ] || die "design-lab 이 없습니다: $LAB"
[ -x "$VENV/bin/python" ] || die "venv 가 없습니다 — ./deploy/setup-crawler.sh 를 먼저"

# 뷰어 컨테이너가 이 폴더를 /ig 로 붙인다. 없으면 docker 가 root 소유로 만들어 데몬이 못 쓴다.
mkdir -p "$LAB/exposed" "$LAB/inbox" "$LAB/state"

( cd "$LAB" && "$VENV/bin/python" -c "import publish.daemon" ) || die "import 실패: publish.daemon"

if [ ! -f "$LAB/config/accounts.json" ]; then
  warn "config/accounts.json 이 없습니다 — 연습 모드로만 돕니다 (design-lab/SOCIAL.md)"
fi

log "launchd 등록 ($LABEL, ${INTERVAL}초 주기)"
write_plist "$PLIST"
reload_plist
log "등록 완료 — 로그: ~/Library/Logs/jobseeker-publisher.*.log · 상태: 8770 '인스타 발행'"
