#!/usr/bin/env bash
# 맥북을 서버로 쓰기 위한 OS 레벨 설정. sudo 가 필요한 작업만 모아뒀다.
#
#   sudo ./deploy/setup-server.sh           # SSH 켜기 + 절전 해제
#   sudo ./deploy/setup-server.sh --harden  # 위 + SSH 비밀번호 로그인 차단
#
# --harden 은 키 로그인이 되는 걸 확인한 뒤에 실행할 것. 순서를 지키지 않으면
# 원격 접속이 막힌다(물리적으로 이 맥 앞에 앉으면 언제든 복구 가능).
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "sudo 로 실행하세요: sudo $0 $*" >&2; exit 1; }

TARGET_USER="${SUDO_USER:-user}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }

# ── 1. 원격 로그인(SSH) 활성화 ─────────────────────────────
log "SSH 원격 로그인 활성화"
if systemsetup -setremotelogin on 2>/dev/null; then
  :
else
  # systemsetup 이 Full Disk Access 부족으로 실패하면 launchd 로 직접 켠다.
  warn "systemsetup 실패 — launchd 로 대체 시도"
  launchctl enable system/com.openssh.sshd
  launchctl bootstrap system /System/Library/LaunchDaemons/ssh.plist 2>/dev/null || true
fi
systemsetup -getremotelogin || true

# ── 2. 절전 해제 ───────────────────────────────────────────
# 서버가 잠들면 터널도 러너도 같이 끊긴다. 맥북은 뚜껑을 닫으면 잠들기
# 때문에 disablesleep 까지 꺼야 클램셸 상태로 상시 구동된다.
log "절전 설정 해제 (상시 구동)"
pmset -a sleep 0            # 시스템 슬립 안 함
pmset -a disksleep 0        # 디스크 슬립 안 함
pmset -a disablesleep 1     # 뚜껑 닫아도 안 잠듦 (클램셸 서버)
pmset -a womp 1             # 네트워크로 깨우기
pmset -a autorestart 1      # 정전 복구 시 자동 부팅
pmset -g custom | sed 's/^/    /'

# ── 3. SSH 강화 (선택) ─────────────────────────────────────
if [ "${1:-}" = "--harden" ]; then
  log "SSH 강화 설정 설치"
  install -m 644 -o root -g wheel \
    "$SCRIPT_DIR/sshd_jobseeker.conf" /etc/ssh/sshd_config.d/200-jobseeker.conf
  # AllowUsers 를 실제 계정명으로 치환
  sed -i '' "s/^AllowUsers .*/AllowUsers $TARGET_USER/" /etc/ssh/sshd_config.d/200-jobseeker.conf

  log "sshd 설정 문법 검사"
  sshd -t || { rm -f /etc/ssh/sshd_config.d/200-jobseeker.conf; echo "설정 오류 — 롤백함" >&2; exit 1; }

  log "sshd 재시작"
  launchctl kickstart -k system/com.openssh.sshd 2>/dev/null || true
  warn "비밀번호 로그인이 차단되었습니다. 키 로그인만 가능합니다."
else
  warn "SSH 강화는 건너뜀. 키 로그인 확인 후 --harden 으로 다시 실행하세요."
fi

log "완료"
