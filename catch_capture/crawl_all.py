"""5개 채용 사이트 크롤러를 통합 관리.

각 크롤러는 기존대로 `screenshots/<site>_<keyword>_<timestamp>/`에 저장되고,
모든 사이트가 끝나면 `aggregate.py`가 자동 호출되어
    `screenshots/all_<keyword>_<timestamp>/`
에 통합 폴더(`all_jobs.json` + `summary.txt` + 사이트별 사본)를 만든다.

사용법:
    python crawl_all.py start                       # 5개 전부, 기본 키워드 "개발자", 사이트당 20개
    python crawl_all.py start 개발자 30             # 키워드/사이트당 수집 개수
    python crawl_all.py start 개발자 30 --only dev,wanted   # 일부만
    python crawl_all.py status                      # 실행 중 여부
    python crawl_all.py logs                        # 최근 로그
    python crawl_all.py logs 200                    # 최근 200줄
    python crawl_all.py stop                        # 종료(자식 프로세스 트리 포함)
    python crawl_all.py run 개발자 30               # 포그라운드로 직접 실행
    python crawl_all.py start 개발자 30 --no-aggregate   # 통합 단계 스킵
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
PID_FILE = BASE_DIR / "crawl_all.pid"
LOG_FILE = BASE_DIR / "crawl_all.log"


def _python_executable() -> str:
    """playwright/bs4가 설치된 venv python을 우선 사용."""
    venv_py = BASE_DIR / ".venv" / "bin" / "python"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable

SOURCES: dict[str, dict] = {
    "dev":      {"script": "crawl_dev.py"},
    "jobkorea": {"script": "crawl_jobkorea.py"},
    "jumpit":   {"script": "crawl_jumpit.py"},
    "saramin":  {"script": "crawl_saramin.py"},
    "wanted":   {"script": "crawl_wanted.py"},
}


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


def _parse_sources(only: str | None) -> list[str]:
    if not only:
        return list(SOURCES.keys())
    picked = [s.strip() for s in only.split(",") if s.strip()]
    unknown = [s for s in picked if s not in SOURCES]
    if unknown:
        print(f"[!] 알 수 없는 소스: {unknown}. 사용 가능: {list(SOURCES.keys())}", flush=True)
        sys.exit(2)
    return picked


def run_foreground(keyword: str, target: int, sources: list[str], do_aggregate: bool = True, depth: int | None = None) -> int:
    """5개(또는 일부) 크롤러를 순차 실행. 완료 후 aggregate 호출."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    overall_start = datetime.now()
    print(f"\n========== crawl_all 시작 {overall_start:%Y-%m-%d %H:%M:%S} ==========", flush=True)
    print(f"[*] 각 크롤러 저장 경로: {BASE_DIR / 'screenshots'}/<site>_<keyword>_<timestamp>/", flush=True)
    print(f"[*] 대상 소스({len(sources)}): {sources}", flush=True)
    print(f"[*] 키워드='{keyword}' / 사이트당 목표={target}", flush=True)
    if depth is not None:
        print(f"[*] 페이지네이션/스크롤 깊이(depth)={depth}", flush=True)
    print(f"[*] 통합(aggregate): {'예' if do_aggregate else '아니오'}\n", flush=True)

    failures: list[str] = []
    for i, source in enumerate(sources, 1):
        script = BASE_DIR / SOURCES[source]["script"]
        start = datetime.now()
        print(f"\n----- [{i}/{len(sources)}] {source} 시작 {start:%H:%M:%S} -----", flush=True)
        cmd = [_python_executable(), "-u", str(script), keyword, str(target)]
        if depth is not None:
            cmd.append(str(depth))
        try:
            rc = subprocess.call(
                cmd,
                env=env,
                cwd=str(BASE_DIR),
            )
        except KeyboardInterrupt:
            print(f"[!] {source} 중단(KeyboardInterrupt)", flush=True)
            return 130
        elapsed = (datetime.now() - start).total_seconds()
        if rc != 0:
            failures.append(source)
            print(f"[!] {source} 실패(rc={rc}, {elapsed:.0f}s)", flush=True)
        else:
            print(f"[OK] {source} 완료({elapsed:.0f}s)", flush=True)

    if do_aggregate:
        print(f"\n----- aggregate 통합 -----", flush=True)
        try:
            sys.path.insert(0, str(BASE_DIR))
            from aggregate import aggregate as _aggregate
            out = _aggregate(keyword)
            print(f"[OK] 통합 폴더: {out}", flush=True)
        except Exception as e:
            print(f"[!] aggregate 실패: {e}", flush=True)
            failures.append("aggregate")

    total = (datetime.now() - overall_start).total_seconds()
    print(f"\n========== 전체 완료 ({total:.0f}s) ==========", flush=True)
    if failures:
        print(f"[!] 실패: {failures}", flush=True)
        return 1
    return 0


def cmd_start(rest: list[str]) -> None:
    existing = _read_pid()
    if existing:
        print(f"[!] 이미 실행 중: PID {existing} — 먼저 'stop' 후 재시작", flush=True)
        return
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_fh = open(LOG_FILE, "ab", buffering=0)
    log_fh.write(f"\n===== START {started_at}  args={rest} =====\n".encode("utf-8"))
    # 백그라운드 워커: 자기 자신을 'run' 서브커맨드로 호출
    proc = subprocess.Popen(
        [_python_executable(), "-u", str(Path(__file__).resolve()), "run", *rest],
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # 새 process group → killpg으로 자식 트리까지
        cwd=str(BASE_DIR),
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"[*] 백그라운드 시작: PID {proc.pid} (process group)", flush=True)
    print(f"    로그: {LOG_FILE}", flush=True)
    print(f"    상태: python {Path(__file__).name} status", flush=True)
    print(f"    중지: python {Path(__file__).name} stop", flush=True)


def cmd_stop() -> None:
    pid = _read_pid()
    if not pid:
        print("[*] 실행 중인 프로세스 없음", flush=True)
        return
    # process group 전체에 SIGTERM (start_new_session=True로 만든 그룹)
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
        except OSError as e:
            print(f"[!] SIGKILL 실패: {e}", flush=True)
    PID_FILE.unlink(missing_ok=True)
    print("[*] 종료 완료", flush=True)


def cmd_status() -> None:
    pid = _read_pid()
    if pid:
        print(f"[*] 실행 중: PID {pid}", flush=True)
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


def _parse_run_args(args: list[str]) -> tuple[str, int, list[str], bool, int | None]:
    do_aggregate = True
    if "--no-aggregate" in args:
        do_aggregate = False
        args.remove("--no-aggregate")
    only = None
    if "--only" in args:
        i = args.index("--only")
        if i + 1 >= len(args):
            print("[!] --only 다음에 콤마 구분 소스 목록이 필요합니다.", flush=True)
            sys.exit(2)
        only = args[i + 1]
        del args[i:i + 2]
    depth: int | None = None
    if "--depth" in args:
        i = args.index("--depth")
        if i + 1 >= len(args):
            print("[!] --depth 다음에 정수가 필요합니다.", flush=True)
            sys.exit(2)
        depth = int(args[i + 1])
        del args[i:i + 2]
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 20
    return keyword, target, _parse_sources(only), do_aggregate, depth


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
    elif sub == "run":
        keyword, target, sources, do_aggregate, depth = _parse_run_args(rest)
        sys.exit(run_foreground(keyword, target, sources, do_aggregate, depth))
    else:
        print(f"[!] 알 수 없는 명령: {sub}", flush=True)
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
