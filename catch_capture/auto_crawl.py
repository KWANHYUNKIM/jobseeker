"""채용 크롤 → 데이터 갱신을 주기적으로 반복하는 자동화 데몬.

매 주기마다:
  1) crawl_all.run_foreground 로 5개 사이트를 크롤하고 aggregate 까지 수행
  2) 새 screenshots/all_<keyword>_* 폴더가 생기면(= 새 데이터)
       - dashboard/data.json 재빌드 (serve.py --build-only)
       - jd-viewer/public 데이터(enrich + mindmap) 갱신 (refresh-data.sh)
  3) interval 초만큼 대기 후 반복

실행 중인 dashboard(8765) / vite(5173) 서버는 갱신된 파일을 자동 반영한다.

사용법:
    python auto_crawl.py start                         # 개발자 20건, 1시간 주기
    python auto_crawl.py start 개발자 30 1800          # 키워드 30건, 30분(1800s) 주기
    python auto_crawl.py start 개발자 20 3600 --now    # 시작하자마자 1회 크롤 (기본은 한 주기 뒤)
    python auto_crawl.py once                          # 1회만 크롤+갱신 (포그라운드)
    python auto_crawl.py status
    python auto_crawl.py logs [n]
    python auto_crawl.py stop
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
PID_FILE = BASE_DIR / "auto_crawl.pid"
LOG_FILE = BASE_DIR / "auto_crawl.log"
REFRESH_SH = ROOT_DIR / "jd-viewer" / "bin" / "refresh-data.sh"

DEFAULT_KEYWORD = "개발자"
DEFAULT_COUNT = 20
DEFAULT_INTERVAL = 3600  # 1시간


def _python_executable() -> str:
    venv_py = BASE_DIR / ".venv" / "bin" / "python"
    return str(venv_py) if venv_py.exists() else sys.executable


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        PID_FILE.unlink(missing_ok=True)
        return None
    if _process_alive(pid):
        return pid
    PID_FILE.unlink(missing_ok=True)
    return None


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)


def _latest_all_dir(keyword: str) -> str | None:
    if not SCREENSHOTS_DIR.exists():
        return None
    matches = sorted(
        (p.name for p in SCREENSHOTS_DIR.glob(f"all_{keyword}_*")
         if p.is_dir() and not p.name.endswith("_latest")),  # all_<kw>_latest 심볼릭링크 제외
        reverse=True,
    )
    return matches[0] if matches else None


def refresh_data(keyword: str) -> None:
    """dashboard + jd-viewer 데이터를 최신 크롤 결과로 갱신."""
    py = _python_executable()

    log("[refresh] dashboard/data.json 재빌드")
    rc = subprocess.call(
        [py, str(BASE_DIR / "dashboard" / "serve.py"),
         "--keyword", keyword, "--build-only"],
        cwd=str(BASE_DIR),
    )
    log(f"[refresh] dashboard {'완료' if rc == 0 else f'실패(rc={rc})'}")

    log("[refresh] jd-viewer enrich + mindmap")
    rc = subprocess.call(["bash", str(REFRESH_SH)], cwd=str(ROOT_DIR))
    log(f"[refresh] jd-viewer {'완료' if rc == 0 else f'실패(rc={rc})'}")


def run_cycle(keyword: str, count: int) -> bool:
    """크롤 1회 + (새 데이터면) 갱신. 새 데이터가 생겼으면 True."""
    from crawl_all import run_foreground

    before = _latest_all_dir(keyword)
    log(f"[crawl] 시작 keyword={keyword} count={count} (직전 폴더={before})")
    rc = run_foreground(keyword, count, ["dev", "jobkorea", "jumpit", "saramin", "wanted"])
    after = _latest_all_dir(keyword)

    if rc != 0:
        log(f"[crawl] 일부 실패(rc={rc})")
    if after and after != before:
        log(f"[crawl] 새 데이터 감지: {after} → 갱신 진행")
        refresh_data(keyword)
        return True
    log("[crawl] 새 데이터 없음 → 갱신 스킵")
    return False


def loop(keyword: str, count: int, interval: int, run_now: bool) -> None:
    sys.path.insert(0, str(BASE_DIR))
    log(f"===== auto_crawl 데몬 시작 (keyword={keyword}, count={count}, "
        f"interval={interval}s, 즉시크롤={run_now}) =====")
    if not run_now:
        log(f"[wait] 첫 크롤까지 {interval}s 대기 (--now 로 즉시 실행 가능)")
        time.sleep(interval)
    while True:
        try:
            run_cycle(keyword, count)
        except Exception as e:  # 한 주기 실패해도 데몬은 계속
            log(f"[err] 사이클 예외: {e!r}")
        log(f"[wait] 다음 크롤까지 {interval}s 대기")
        time.sleep(interval)


def cmd_start(rest: list[str]) -> None:
    existing = _read_pid()
    if existing:
        print(f"[!] 이미 실행 중: PID {existing} — 먼저 'stop' 후 재시작", flush=True)
        return
    run_now = "--now" in rest
    rest = [a for a in rest if a != "--now"]
    keyword = rest[0] if len(rest) > 0 else DEFAULT_KEYWORD
    count = int(rest[1]) if len(rest) > 1 else DEFAULT_COUNT
    interval = int(rest[2]) if len(rest) > 2 else DEFAULT_INTERVAL

    log_fh = open(LOG_FILE, "ab", buffering=0)
    log_fh.write(
        f"\n===== START {datetime.now():%Y-%m-%d %H:%M:%S}  "
        f"keyword={keyword} count={count} interval={interval} now={run_now} =====\n"
        .encode("utf-8")
    )
    proc = subprocess.Popen(
        [_python_executable(), "-u", str(Path(__file__).resolve()), "__loop",
         keyword, str(count), str(interval), "1" if run_now else "0"],
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # 새 process group → stop 시 자식 트리까지 종료
        cwd=str(BASE_DIR),
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"[*] 자동화 데몬 시작: PID {proc.pid}", flush=True)
    print(f"    설정: keyword={keyword}, count={count}, interval={interval}s, "
          f"즉시크롤={'예' if run_now else '아니오(한 주기 뒤)'}", flush=True)
    print(f"    로그: {LOG_FILE}", flush=True)
    print(f"    상태: python {Path(__file__).name} status", flush=True)
    print(f"    중지: python {Path(__file__).name} stop", flush=True)


def cmd_stop() -> None:
    pid = _read_pid()
    if not pid:
        print("[*] 실행 중인 데몬 없음", flush=True)
        return
    try:
        os.killpg(pid, signal.SIGTERM)
        print(f"[*] SIGTERM → process group {pid} (최대 15초 대기)", flush=True)
    except OSError as e:
        print(f"[!] SIGTERM 실패: {e}", flush=True)
        PID_FILE.unlink(missing_ok=True)
        return
    for _ in range(30):
        time.sleep(0.5)
        if not _process_alive(pid):
            break
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
            print(f"[*] SIGKILL → process group {pid}", flush=True)
        except OSError:
            pass
    PID_FILE.unlink(missing_ok=True)
    print("[*] 종료 완료", flush=True)


def cmd_status() -> None:
    pid = _read_pid()
    if pid:
        print(f"[*] 자동화 데몬 실행 중: PID {pid}", flush=True)
        print(f"    로그: {LOG_FILE}", flush=True)
    else:
        print("[*] 실행 중 아님", flush=True)


def cmd_logs(n: int) -> None:
    if not LOG_FILE.exists():
        print("[!] 로그 파일 없음", flush=True)
        return
    with open(LOG_FILE, "rb") as f:
        lines = f.readlines()[-n:]
    sys.stdout.write(b"".join(lines).decode("utf-8", errors="replace"))


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    sub = args[0]
    rest = args[1:]

    if sub == "start":
        cmd_start(rest)
    elif sub == "stop":
        cmd_stop()
    elif sub == "status":
        cmd_status()
    elif sub == "logs":
        n = int(rest[0]) if rest and rest[0].isdigit() else 100
        cmd_logs(n)
    elif sub == "once":
        sys.path.insert(0, str(BASE_DIR))
        keyword = rest[0] if len(rest) > 0 else DEFAULT_KEYWORD
        count = int(rest[1]) if len(rest) > 1 else DEFAULT_COUNT
        run_cycle(keyword, count)
    elif sub == "__loop":
        keyword = rest[0]
        count = int(rest[1])
        interval = int(rest[2])
        run_now = rest[3] == "1"
        loop(keyword, count, interval, run_now)
    else:
        print(f"[!] 알 수 없는 명령: {sub}", flush=True)
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
