#!/usr/bin/env bash
# 크롤 파이프라인을 이 머신에 설치한다 — venv + Playwright + launchd 주기 실행.
#
#   ./deploy/setup-crawler.sh              # 설치만 (스케줄 등록 안 함)
#   ./deploy/setup-crawler.sh --schedule   # 설치 + launchd 주기 실행 등록
#   ./deploy/setup-crawler.sh --uninstall  # 스케줄 해제
#
# 크롤러는 컨테이너가 아니라 네이티브로 돈다. Playwright 가 실제 브라우저를
# 띄우고 사이트마다 봇 탐지를 우회해야 해서, 컨테이너 안의 헤드리스 환경보다
# 호스트에서 도는 쪽이 안정적이다. paths.py 와 refresh-data.sh 도
# catch_capture/.venv 를 전제로 하고 있다.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ROOT="${ROOT:-$HOME/jobseeker}"
CATCH="$ROOT/catch_capture"
VENV="$CATCH/.venv"
LABEL="com.jobseeker.crawler"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

# 크롤 주기·규모. 옛 서버가 쓰던 값(개발자 100건, 30분)을 그대로 쓴다.
KEYWORD="${CRAWL_KEYWORD:-개발자}"
COUNT="${CRAWL_COUNT:-100}"
INTERVAL="${CRAWL_INTERVAL:-1800}"

log()  { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# ── 언인스톨 ───────────────────────────────────────────────
if [ "${1:-}" = "--uninstall" ]; then
  log "스케줄 해제"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || launchctl unload -w "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  log "해제 완료 (venv 와 데이터는 그대로 둔다)"
  exit 0
fi

[ -d "$CATCH" ] || die "catch_capture 가 없습니다: $CATCH"

# ── 파이썬 ─────────────────────────────────────────────────
# 시스템 python3 는 macOS 15 기준 3.9 라 numpy>=2 / model2vec 을 못 쓴다.
PY313=/opt/homebrew/opt/python@3.13/bin/python3.13
if [ ! -x "$PY313" ]; then
  log "python@3.13 설치"
  brew install python@3.13
fi

if [ ! -x "$VENV/bin/python" ]; then
  log "venv 생성 ($VENV)"
  "$PY313" -m venv "$VENV"
fi
log "파이썬: $("$VENV/bin/python" --version)"

# ── 의존성 ─────────────────────────────────────────────────
log "의존성 설치"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r "$CATCH/requirements.txt"

log "Playwright 브라우저 설치"
"$VENV/bin/python" -m playwright install chromium

# ── import 스모크 테스트 ───────────────────────────────────
log "모듈 로드 확인"
( cd "$CATCH" && for m in automation.auto_crawl automation.crawl_all pipeline.aggregate \
    monitoring.orchestration crawlers.crawl_saramin crawlers.crawl_techblog_graph; do
    "$VENV/bin/python" -c "import $m" || die "import 실패: $m"
  done )
log "모든 모듈 정상"

# ── 스케줄 등록 ────────────────────────────────────────────
if [ "${1:-}" != "--schedule" ]; then
  warn "스케줄 등록은 건너뜀. 등록하려면 --schedule 로 다시 실행하세요."
  exit 0
fi

# 스냅샷 이력이 없으면 build_trends.py 가 시계열을 하루치로 재생성해버린다.
# (기존 trends.json 을 병합하지 않고 screenshots/all_통합_* 에서 통째로 만든다)
if ! ls -d "$CATCH/screenshots"/all_통합_* >/dev/null 2>&1 \
   && ! ls -d "$CATCH/screenshots"/all_개발자_* >/dev/null 2>&1; then
  warn "screenshots/ 에 스냅샷 이력이 없습니다."
  warn "이 상태로 크롤을 돌리면 trends.json 이 하루치로 축소됩니다."
  warn "옛 서버의 catch_capture/screenshots/ 를 먼저 rsync 로 가져오세요."
  die "안전을 위해 스케줄 등록을 중단합니다 (--schedule 없이 실행하면 설치만 됩니다)"
fi

log "launchd 등록 ($LABEL, ${INTERVAL}초 주기)"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <!-- 자체 데몬(start)이 아니라 1회 실행(once)을 launchd 가 주기로 돌린다.
       PID 파일 관리가 사라지고, 한 사이클이 주기보다 길어져도 launchd 가
       같은 job 을 중복 실행하지 않는다. -->
  <key>ProgramArguments</key>
  <array>
    <string>$VENV/bin/python</string>
    <string>-m</string>
    <string>automation.auto_crawl</string>
    <string>once</string>
    <string>$KEYWORD</string>
    <string>$COUNT</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$CATCH</string>

  <key>EnvironmentVariables</key>
  <dict>
    <!-- launchd 는 로그인 셸 PATH 를 주지 않는다. autocommit 이 git 을 부르므로 필요. -->
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
    <!-- 데이터 커밋을 push 까지 한다. 끄면 로컬 커밋만 쌓여 origin 과 갈라지고,
         deploy.sh 의 git merge --ff-only 가 실패해 자동 배포가 멈춘다. -->
    <key>JOBSEEKER_AUTOPUSH</key>
    <string>1</string>
  </dict>

  <key>StartInterval</key>
  <integer>$INTERVAL</integer>

  <!-- 등록 즉시 크롤하지 않는다. 첫 실행은 한 주기 뒤. -->
  <key>RunAtLoad</key>
  <false/>

  <key>StandardOutPath</key>
  <string>$HOME/Library/Logs/jobseeker-crawler.out.log</string>
  <key>StandardErrorPath</key>
  <string>$HOME/Library/Logs/jobseeker-crawler.err.log</string>
</dict>
</plist>
PLIST_EOF

plutil -lint "$PLIST" >/dev/null || die "plist 문법 오류"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 \
  && log "등록 완료 — ${INTERVAL}초마다 '$KEYWORD' $COUNT건 크롤" \
  || die "launchd 등록 실패"

echo
echo "  상태 :  launchctl print gui/\$(id -u)/$LABEL | head -20"
echo "  로그 :  tail -f ~/Library/Logs/jobseeker-crawler.out.log"
echo "  즉시 :  launchctl kickstart -k gui/\$(id -u)/$LABEL"
echo "  해제 :  ./deploy/setup-crawler.sh --uninstall"
