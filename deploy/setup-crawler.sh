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

# 크롤 주기·규모 — 옛 서버(automation/start-auto-crawl.sh)와 같은 값을 쓴다.
#
# 여기를 단일 키워드("개발자")로 두면 안 된다. run_cycle 은 키워드가 하나면
# all_통합_* 을 만들지 않고 all_개발자_* 만 남기는데, refresh-data.sh 는 통합
# 폴더가 없으면 그 단일 키워드 폴더로 폴백하고 enrich_jobs.py 는 그 폴더 하나로
# public/all_jobs_enriched.json 을 통째 덮어쓴다. 2026-08-17 에 이 조합으로
# 누적 10,275건이 25건으로 교체됐다(refresh-data.sh 의 급감 가드가 2차 방어선).
KEYWORD="${CRAWL_KEYWORD:-개발자,프론트엔드,백엔드,풀스택,안드로이드,iOS,데이터엔지니어,데이터분석,머신러닝,AI,데브옵스,클라우드,플랫폼엔지니어,SRE,보안,자바,파이썬,자바스크립트,리액트,노드}"
COUNT="${CRAWL_COUNT:-50}"
# 키워드 20개 × 5사이트라 한 사이클이 30분을 넘는다. launchd 는 실행 중인 job 을
# 중복 기동하지 않지만, 주기는 실제 소요에 맞춰 1시간으로 둔다.
INTERVAL="${CRAWL_INTERVAL:-3600}"

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
    <!-- launchd 는 로그인 셸 PATH 를 주지 않는다. 크롤러가 git/docker 를 부르므로 필요. -->
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
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
  && log "등록 완료 — ${INTERVAL}초마다 '${KEYWORD}' ${COUNT}건 크롤" \
  || die "launchd 등록 실패"

echo
echo "  상태 :  launchctl print gui/\$(id -u)/$LABEL | head -20"
echo "  로그 :  tail -f ~/Library/Logs/jobseeker-crawler.out.log"
echo "  즉시 :  launchctl kickstart -k gui/\$(id -u)/$LABEL"
echo "  해제 :  ./deploy/setup-crawler.sh --uninstall"
