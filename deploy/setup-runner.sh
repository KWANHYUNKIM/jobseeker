#!/usr/bin/env bash
# GitHub Actions self-hosted runner 설치 — 이 맥이 GitHub 로 아웃바운드 접속만
# 하므로 SSH 포트를 외부에 열 필요가 없다.
#
#   1) https://github.com/KWANHYUNKIM/jobseeker/settings/actions/runners/new
#      에서 "Configure" 섹션의 --token 값(AXXXX... 형태)을 복사한다.
#   2) ./deploy/setup-runner.sh <TOKEN>
#
# 토큰은 1시간 뒤 만료되므로 발급 직후 실행할 것.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

REPO_URL="https://github.com/KWANHYUNKIM/jobseeker"
RUNNER_DIR="$HOME/actions-runner"
TOKEN="${1:-}"

log() { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

[ -n "$TOKEN" ] || die "등록 토큰이 필요합니다: $0 <TOKEN>
  발급: $REPO_URL/settings/actions/runners/new"

[ "$(id -u)" -ne 0 ] || die "root 로 실행하지 마세요. 러너는 일반 사용자로 돌아야 합니다."

# ── 다운로드 ───────────────────────────────────────────────
if [ ! -f "$RUNNER_DIR/config.sh" ]; then
  log "최신 러너 버전 조회"
  VERSION=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
    | grep -m1 '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/')
  [ -n "$VERSION" ] || die "러너 버전 조회 실패"
  log "runner v$VERSION 다운로드 (osx-arm64)"

  mkdir -p "$RUNNER_DIR"
  TARBALL="actions-runner-osx-arm64-${VERSION}.tar.gz"
  curl -fsSL -o "/tmp/$TARBALL" \
    "https://github.com/actions/runner/releases/download/v${VERSION}/${TARBALL}"
  tar xzf "/tmp/$TARBALL" -C "$RUNNER_DIR"
  rm -f "/tmp/$TARBALL"
else
  log "러너가 이미 설치되어 있습니다: $RUNNER_DIR"
fi

cd "$RUNNER_DIR"

# ── 등록 ───────────────────────────────────────────────────
if [ -f .runner ]; then
  log "이미 등록된 러너입니다. 재등록하려면 ./config.sh remove 후 다시 실행하세요."
else
  log "GitHub 에 러너 등록"
  # 라벨은 workflow 의 runs-on: [self-hosted, macOS, ARM64] 와 맞춘다(기본 제공).
  ./config.sh \
    --url "$REPO_URL" \
    --token "$TOKEN" \
    --name "$(hostname -s)-jobseeker" \
    --work _work \
    --unattended \
    --replace
fi

# ── 서비스 등록 ────────────────────────────────────────────
# svc.sh 는 LaunchAgent 를 만든다 → 사용자 로그인 시 자동 기동.
log "launchd 서비스로 등록"
./svc.sh install
./svc.sh start
sleep 3
./svc.sh status || true

log "완료 — $REPO_URL/settings/actions/runners 에서 Idle 상태인지 확인하세요"
