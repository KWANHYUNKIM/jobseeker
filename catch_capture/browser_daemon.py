"""Chromium 영구 브라우저 데몬 — PID 기반 관리.

크롤러를 반복 실행할 때 매번 브라우저가 열리고 닫히는 문제를 해결한다.
이 데몬을 한 번 띄워두면, 모든 크롤러가 같은 브라우저(같은 세션/쿠키)를
재사용한다.

사용법:
    python browser_daemon.py start          # 백그라운드로 Chromium 기동
    python browser_daemon.py stop           # 종료 (SIGTERM)
    python browser_daemon.py status         # 상태 + PID + CDP 엔드포인트
    python browser_daemon.py restart        # stop + start
    python browser_daemon.py start 9333     # 다른 포트로 기동

다른 크롤러는 jobs_common.connect_browser() 로 이 데몬에 연결한다.
데몬이 없으면 크롤러가 자체적으로 brower를 띄우는 폴백 동작을 한다.

상태 파일:
    catch_capture/.browser_state.json   # PID, port, CDP endpoint
    catch_capture/.browser_daemon.log   # stdout/stderr
    catch_capture/.chrome_profile/      # user-data-dir (쿠키/로그인 유지)
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / ".browser_state.json"
LOG_FILE = BASE_DIR / ".browser_daemon.log"
USER_DATA_DIR = BASE_DIR / ".chrome_profile"
DEFAULT_PORT = 9222


def _read_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _clear_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def _is_pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _find_chromium() -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[!] playwright 미설치 — `pip install playwright && playwright install chromium`", file=sys.stderr)
        sys.exit(2)
    with sync_playwright() as p:
        path = p.chromium.executable_path
    if not path or not Path(path).exists():
        print(f"[!] Chromium 바이너리 없음: {path}", file=sys.stderr)
        print("    `playwright install chromium` 실행 필요", file=sys.stderr)
        sys.exit(2)
    return path


def _wait_cdp_ready(port: int, timeout: float = 15.0) -> bool:
    """CDP 포트가 응답할 때까지 대기."""
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.3)
    return False


def cmd_start(port: int = DEFAULT_PORT) -> int:
    state = _read_state()
    if state and _is_pid_alive(state.get("pid", 0)):
        print(f"[browser-daemon] 이미 실행 중 (PID {state['pid']}, port {state.get('port')})")
        print(f"  CDP: {state.get('cdp_endpoint')}")
        return 0
    if state:
        _clear_state()

    chromium_exe = _find_chromium()
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    log_fp = open(LOG_FILE, "ab", buffering=0)
    log_fp.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} 데몬 기동 (port {port}) ===\n".encode())

    proc = subprocess.Popen(
        [
            chromium_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={USER_DATA_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=Translate",
            "--window-size=1440,900",
        ],
        stdout=log_fp,
        stderr=log_fp,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )

    if not _wait_cdp_ready(port, timeout=15.0):
        print(f"[browser-daemon] CDP 응답 없음 (port {port}) — 로그 확인: {LOG_FILE}")
        try:
            proc.terminate()
        except Exception:
            pass
        return 1

    cdp_endpoint = f"http://127.0.0.1:{port}"
    _write_state({
        "pid": proc.pid,
        "port": port,
        "cdp_endpoint": cdp_endpoint,
        "user_data_dir": str(USER_DATA_DIR),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    print(f"[browser-daemon] 시작됨 (PID {proc.pid})")
    print(f"  CDP: {cdp_endpoint}")
    print(f"  프로필: {USER_DATA_DIR}")
    print(f"  로그: {LOG_FILE}")
    return 0


def cmd_stop() -> int:
    state = _read_state()
    if not state:
        print("[browser-daemon] state 없음 — 이미 정지")
        return 0
    pid = state.get("pid", 0)
    if not _is_pid_alive(pid):
        print(f"[browser-daemon] PID {pid} 이미 죽음, state 정리")
        _clear_state()
        return 0
    print(f"[browser-daemon] SIGTERM → PID {pid}")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _clear_state()
        return 0
    except Exception as e:
        print(f"[browser-daemon] SIGTERM 실패: {e}")
        return 1
    for _ in range(50):
        time.sleep(0.2)
        if not _is_pid_alive(pid):
            break
    if _is_pid_alive(pid):
        print(f"[browser-daemon] 응답 없음 → SIGKILL")
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
        time.sleep(0.5)
    _clear_state()
    print("[browser-daemon] 정지 완료")
    return 0


def cmd_status() -> int:
    state = _read_state()
    if not state:
        print("[browser-daemon] 정지 (state 없음)")
        return 1
    pid = state.get("pid", 0)
    if _is_pid_alive(pid):
        print("[browser-daemon] 실행 중")
        print(f"  PID:       {pid}")
        print(f"  Port:      {state.get('port')}")
        print(f"  CDP:       {state.get('cdp_endpoint')}")
        print(f"  프로필:    {state.get('user_data_dir')}")
        print(f"  시작 시각: {state.get('started_at')}")
        return 0
    print(f"[browser-daemon] 죽음 (state는 있으나 PID {pid} 없음) — state 정리")
    _clear_state()
    return 1


def cmd_restart(port: int = DEFAULT_PORT) -> int:
    cmd_stop()
    time.sleep(0.5)
    return cmd_start(port)


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    port = int(args[1]) if len(args) > 1 else DEFAULT_PORT

    if cmd == "start":
        return cmd_start(port)
    if cmd == "stop":
        return cmd_stop()
    if cmd == "status":
        return cmd_status()
    if cmd == "restart":
        return cmd_restart(port)
    print(f"알 수 없는 명령: {cmd}")
    print("사용법: start [port] | stop | status | restart [port]")
    return 2


if __name__ == "__main__":
    sys.exit(main())
