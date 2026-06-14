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

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from monitoring import orchestration as orch

BASE_DIR = Path(__file__).resolve().parent.parent.resolve()
ROOT_DIR = BASE_DIR.parent
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
PID_FILE = BASE_DIR / "auto_crawl.pid"
LOG_FILE = BASE_DIR / "auto_crawl.log"
REFRESH_SH = ROOT_DIR / "jd-viewer" / "bin" / "refresh-data.sh"

# 크롤 오케스트레이션이 함께 굴리는 부가 작업(흩어진 cron 을 여기로 통합)
RADAR_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_company_tech_radar.py"
REVIEWS_LOOP_SH = ROOT_DIR / "jd-viewer" / "bin" / "reviews-loop.sh"
LEARNING_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_learning.py"
CALENDAR_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_calendar.py"
RADAR_REFINE_N = 2                     # 사이클당 레이더 점진 리파인 회사 수
LEARNING_REFRESH_SECS = 6 * 3600       # 학습영상 캐시 무시 재수집 주기(기존 learning cron 대체)
LEARNING_STAMP = BASE_DIR / ".learning_refresh.stamp"

# 주기적 데이터 자동 커밋 — 누적되는 생성물(레이더·후기·집계)을 사이클마다 커밋한다.
# push 는 CLAUDE.md 규칙상 기본 OFF. 환경변수 JOBSEEKER_AUTOPUSH=1 일 때만 push 한다.
AUTOCOMMIT_PATHS = ["jd-viewer/public", "catch_capture/dashboard/data.json"]
RADAR_JSON = ROOT_DIR / "jd-viewer" / "public" / "company_tech_radar.json"
AUTOPUSH = os.environ.get("JOBSEEKER_AUTOPUSH") == "1"

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
    orch.refresh_started("dashboard")
    rc = subprocess.call(
        [py, str(BASE_DIR / "dashboard" / "serve.py"),
         "--keyword", keyword, "--build-only"],
        cwd=str(BASE_DIR),
    )
    orch.refresh_finished("dashboard", rc == 0)
    log(f"[refresh] dashboard {'완료' if rc == 0 else f'실패(rc={rc})'}")

    log("[refresh] jd-viewer enrich + mindmap")
    orch.refresh_started("viewer")
    rc = subprocess.call(["bash", str(REFRESH_SH)], cwd=str(ROOT_DIR))
    orch.refresh_finished("viewer", rc == 0)
    log(f"[refresh] jd-viewer {'완료' if rc == 0 else f'실패(rc={rc})'}")


def _gh_env() -> dict:
    """GITHUB_TOKEN 이 없으면 gh CLI 로 토큰을 실어 GitHub API 한도를 올린다(레이더 repo 검증)."""
    env = dict(os.environ)
    if not env.get("GITHUB_TOKEN"):
        try:
            tok = subprocess.check_output(["gh", "auth", "token"], text=True, timeout=10).strip()
            if tok:
                env["GITHUB_TOKEN"] = tok
        except Exception:
            pass
    return env


def enrich_radar() -> None:
    """기술 스택 레이더를 점진 리파인(claude CLI). 크롤 오케스트레이션의 부가 단계."""
    log(f"[radar] --refine {RADAR_REFINE_N} (claude CLI)")
    try:
        rc = subprocess.call([_python_executable(), str(RADAR_SCRIPT), "--refine", str(RADAR_REFINE_N)],
                             cwd=str(ROOT_DIR), env=_gh_env())
        log(f"[radar] {'완료' if rc == 0 else f'실패(rc={rc})'}")
    except Exception as e:
        log(f"[radar] 예외: {e!r}")


def ensure_reviews_daemon() -> None:
    """공개 면접 후기 적응형 수집 데몬이 살아있도록 보장(멱등). 죽었으면 재시작."""
    try:
        subprocess.call(["bash", str(REVIEWS_LOOP_SH), "start"], cwd=str(ROOT_DIR))
    except Exception as e:
        log(f"[reviews] 데몬 보장 실패: {e!r}")


def maybe_refresh_learning() -> None:
    """학습 영상 캐시 무시 재수집(--refresh)을 주기적으로(기본 6h). 기존 learning cron 을 대체."""
    try:
        last = float(LEARNING_STAMP.read_text()) if LEARNING_STAMP.exists() else 0.0
    except Exception:
        last = 0.0
    if time.time() - last < LEARNING_REFRESH_SECS:
        return
    log("[learning] 캐시 무시 재수집(--refresh)")
    try:
        rc = subprocess.call([_python_executable(), str(LEARNING_SCRIPT), "--refresh"], cwd=str(ROOT_DIR))
        LEARNING_STAMP.write_text(str(time.time()))
        log(f"[learning] {'완료' if rc == 0 else f'실패(rc={rc})'}")
    except Exception as e:
        log(f"[learning] 예외: {e!r}")


def auto_commit_data() -> None:
    """누적된 생성 데이터(레이더·후기·집계)를 주기적으로 git 커밋한다.
    - 레이더 JSON 이 갱신 중(파싱 실패)이면 이번 사이클은 건너뛴다(반쪽 커밋 방지).
    - 데이터 경로만 스테이징하므로 코드 변경은 섞이지 않는다.
    - push 는 JOBSEEKER_AUTOPUSH=1 일 때만(기본 OFF, CLAUDE.md 규칙 준수)."""
    if RADAR_JSON.exists():
        try:
            json.loads(RADAR_JSON.read_text(encoding="utf-8"))
        except Exception:
            log("[autocommit] 데이터 파일 갱신 중 — 이번 사이클 스킵")
            return
    try:
        subprocess.call(["git", "add", "--", *AUTOCOMMIT_PATHS], cwd=str(ROOT_DIR))
        # 스테이징된 변경이 없으면 커밋하지 않는다(빈 커밋 방지)
        if subprocess.call(["git", "diff", "--cached", "--quiet"], cwd=str(ROOT_DIR)) == 0:
            return
        msg = f"chore(data): 자동 갱신 {datetime.now():%Y-%m-%d %H:%M} [auto]"
        rc = subprocess.call(["git", "commit", "-q", "--no-verify", "-m", msg], cwd=str(ROOT_DIR))
        if rc != 0:
            log(f"[autocommit] 커밋 실패(rc={rc})")
            return
        log(f"[autocommit] 데이터 커밋{' + push' if AUTOPUSH else ''}")
        if AUTOPUSH:
            prc = subprocess.call(["git", "push", "origin", "HEAD"], cwd=str(ROOT_DIR))
            if prc != 0:
                log(f"[autocommit] push 실패(rc={prc}) — 로컬 커밋은 유지됨")
    except Exception as e:
        log(f"[autocommit] 예외: {e!r}")


def rebuild_calendar() -> None:
    """모집 캘린더(job_calendar.json)를 매 사이클 재생성 — 데이터가 쌓이는 즉시 반영하고
    상대 마감(D-N)도 오늘 기준으로 최신화한다. enriched 데이터만 있으면 빠르게 동작."""
    try:
        rc = subprocess.call([_python_executable(), str(CALENDAR_SCRIPT)], cwd=str(ROOT_DIR))
        if rc != 0:
            log(f"[calendar] 실패(rc={rc})")
    except Exception as e:
        log(f"[calendar] 예외: {e!r}")


def enrich_extras() -> None:
    """크롤과 무관하게 매 사이클 굴리는 부가 작업: 레이더 리파인 + 후기 데몬 보장 + 학습 재수집
    + 모집 캘린더 재생성 + 누적 데이터 자동 커밋."""
    maybe_refresh_learning()
    enrich_radar()
    ensure_reviews_daemon()
    rebuild_calendar()
    auto_commit_data()


def run_cycle(keyword: str, count: int) -> bool:
    """크롤 1회 + (새 데이터면) 갱신. 새 데이터가 생겼으면 True.

    keyword 는 콤마로 여러 개를 줄 수 있다("개발자,백엔드,프론트엔드").
    여러 개면 키워드별로 크롤한 뒤 한 통합 폴더(all_통합_*)로 병합한다.
    """
    from automation.crawl_all import run_foreground
    from pipeline.aggregate import aggregate

    kws = [k.strip() for k in keyword.split(",") if k.strip()]
    multi = len(kws) > 1
    label = "통합" if multi else (kws[0] if kws else keyword)

    cycle_start = datetime.now()
    before = _latest_all_dir(label)
    log(f"[crawl] 시작 keywords={kws} count={count} label={label} (직전 폴더={before})")

    rc_fail = 0
    for kw in kws:
        # 멀티 키워드면 키워드별 단일 통합은 생략하고 마지막에 1회만 통합한다.
        # 기술 블로그는 키워드와 무관 → 사이클당 1회(마지막 키워드)만 실행
        rc = run_foreground(kw, count, ["dev", "jobkorea", "jumpit", "saramin", "wanted"],
                            do_aggregate=not multi, do_blog=(kw == kws[-1]))
        if rc != 0:
            rc_fail += 1
            log(f"[crawl] '{kw}' 일부 실패(rc={rc})")

    if multi:
        log(f"[aggregate] {len(kws)}개 키워드 통합 → all_{label}_*")
        aggregate(kws[0], keywords=kws, label=label)

    after = _latest_all_dir(label)
    new_data = bool(after and after != before)
    if new_data:
        log(f"[crawl] 새 데이터 감지: {after} → 갱신 진행")
        refresh_data(label)
    else:
        log("[crawl] 새 데이터 없음 → 갱신 스킵")
    orch.cycle_finished(new_data, (datetime.now() - cycle_start).total_seconds())
    return new_data


def loop(keyword: str, count: int, interval: int, run_now: bool) -> None:
    sys.path.insert(0, str(BASE_DIR))
    log(f"===== auto_crawl 데몬 시작 (keyword={keyword}, count={count}, "
        f"interval={interval}s, 즉시크롤={run_now}) =====")
    orch.daemon_started(keyword, count, interval, run_now)
    ensure_reviews_daemon()  # 시작 시 후기 적응형 데몬도 함께 띄운다
    if not run_now:
        next_at = (datetime.now() + timedelta(seconds=interval)).isoformat(timespec="seconds")
        orch.waiting(next_at, interval)
        log(f"[wait] 첫 크롤까지 {interval}s 대기 (--now 로 즉시 실행 가능)")
        time.sleep(interval)
    while True:
        try:
            run_cycle(keyword, count)
        except Exception as e:  # 한 주기 실패해도 데몬은 계속
            log(f"[err] 사이클 예외: {e!r}")
            orch.error("cycle", repr(e))
        try:
            enrich_extras()  # 레이더 리파인 + 후기 데몬 보장 + 학습 재수집(크롤 결과와 무관)
        except Exception as e:
            log(f"[err] enrich 예외: {e!r}")
        next_at = (datetime.now() + timedelta(seconds=interval)).isoformat(timespec="seconds")
        orch.waiting(next_at, interval)
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
    # 오케스트레이션의 일부인 후기 적응형 데몬도 함께 중지
    try:
        subprocess.call(["bash", str(REVIEWS_LOOP_SH), "stop"], cwd=str(ROOT_DIR))
    except Exception:
        pass
    print("[*] 종료 완료 (후기 데몬 포함)", flush=True)


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
