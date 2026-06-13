"""5개 채용 사이트 크롤러를 통합 관리.

각 크롤러는 기존대로 `screenshots/<site>_<keyword>_<timestamp>/`에 저장되고,
모든 사이트가 끝나면 `aggregate.py`가 자동 호출되어
    `screenshots/all_<keyword>_<timestamp>/`
에 통합 폴더(`all_jobs.json` + `summary.txt` + 사이트별 사본)를 만든다.

잡 크롤 5개 + aggregate 가 끝나면, 별도 단계로 기술 블로그 크롤
(`crawl_techblog_graph` — LangGraph, LLM 없음)이 실행되어
    `jd-viewer/public/tech_blogs.json`
을 누적 갱신한다. `--no-blog` 로 끌 수 있다.

마지막으로 파생 분석을 재생성한다(`--no-analyze` 로 끌 수 있다):
    `build_company_stacks.py` → 회사 취업가이드(study_blogs 재매칭)
    `build_learning.py`       → 기술별 유튜브 학습영상
원본(공고·블로그)이 늘면 이 단계만으로 모든 회사 추천이 자동 갱신된다.

사용법:
    python crawl_all.py start                       # 5개 전부 + 블로그, 기본 키워드 "개발자", 사이트당 20개
    python crawl_all.py start 개발자 30             # 키워드/사이트당 수집 개수
    python crawl_all.py start 개발자 30 --only dev,wanted   # 잡 일부만(블로그는 그대로)
    python crawl_all.py status                      # 실행 중 여부
    python crawl_all.py logs                        # 최근 로그
    python crawl_all.py logs 200                    # 최근 200줄
    python crawl_all.py stop                        # 종료(자식 프로세스 트리 포함)
    python crawl_all.py run 개발자 30               # 포그라운드로 직접 실행
    python crawl_all.py start 개발자 30 --no-aggregate   # 통합 단계 스킵
    python crawl_all.py start 개발자 30 --no-blog        # 기술 블로그 단계 스킵
    python crawl_all.py start 개발자 30 --blog-per-feed 40  # 블로그 피드당 수집 개수
    python crawl_all.py start 개발자 30 --no-analyze     # 파생 분석 재생성 스킵
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
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.resolve()
PID_FILE = BASE_DIR / "crawl_all.pid"
LOG_FILE = BASE_DIR / "crawl_all.log"
BLOCK_DIR = BASE_DIR / ".blocks"


def _block_clear(site: str) -> None:
    """직전 사이클의 차단 마커 제거 (이번 크롤 시작 전)."""
    try:
        (BLOCK_DIR / f"{site}.json").unlink()
    except (FileNotFoundError, OSError):
        pass


def _block_reason(site: str) -> str | None:
    """크롤러가 남긴 차단 마커에서 reason 추출. 없으면 None."""
    try:
        rec = json.loads((BLOCK_DIR / f"{site}.json").read_text(encoding="utf-8"))
        return rec.get("reason")
    except Exception:
        return None


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

BLOG_PER_FEED_DEFAULT = 20  # 기술 블로그 피드당 기본 수집 개수


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


def run_foreground(keyword: str, target: int, sources: list[str], do_aggregate: bool = True,
                   depth: int | None = None, do_blog: bool = True,
                   blog_per_feed: int = BLOG_PER_FEED_DEFAULT,
                   do_analyze: bool = True) -> int:
    """5개(또는 일부) 크롤러를 순차 실행. 완료 후 aggregate + 기술 블로그 크롤,
    이어서 파생 분석(회사 취업가이드·학습영상) 재생성까지 호출 — 데이터가 늘면
    추천이 자동으로 진화하도록 루프를 닫는다."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    try:
        from monitoring import orchestration as orch
    except Exception:
        orch = None

    if orch:
        orch.crawl_started(keyword, sources)

    overall_start = datetime.now()
    print(f"\n========== crawl_all 시작 {overall_start:%Y-%m-%d %H:%M:%S} ==========", flush=True)
    print(f"[*] 각 크롤러 저장 경로: {BASE_DIR / 'screenshots'}/<site>_<keyword>_<timestamp>/", flush=True)
    print(f"[*] 대상 소스({len(sources)}): {sources}", flush=True)
    print(f"[*] 키워드='{keyword}' / 사이트당 목표={target}", flush=True)
    if depth is not None:
        print(f"[*] 페이지네이션/스크롤 깊이(depth)={depth}", flush=True)
    print(f"[*] 통합(aggregate): {'예' if do_aggregate else '아니오'}\n", flush=True)

    from crawlers import block_detect

    failures: list[str] = []
    for i, source in enumerate(sources, 1):
        script = BASE_DIR / "crawlers" / SOURCES[source]["script"]
        start = datetime.now()
        print(f"\n----- [{i}/{len(sources)}] {source} 시작 {start:%H:%M:%S} -----", flush=True)

        # 자동 백오프: 직전 차단으로 쿨다운 중이면 이번 사이클은 건너뛴다.
        remaining = block_detect.cooldown_remaining(source)
        if remaining > 0:
            info = block_detect.cooldown_info(source) or {}
            mins = remaining // 60
            print(f"[⏳ skip] {source} 차단 백오프 중 — {remaining}s(~{mins}m) 남음 "
                  f"(level {info.get('level')}, reason {info.get('reason')}) → 이번 사이클 스킵",
                  flush=True)
            if orch:
                orch.site_cooldown_skipped(source, remaining, info)
            continue

        if orch:
            orch.site_started(source)
        _block_clear(source)
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
            if orch:
                orch.site_finished(source, False,
                                   orch.count_site_jobs(keyword, source),
                                   (datetime.now() - start).total_seconds(),
                                   reason=_block_reason(source))
            return 130
        elapsed = (datetime.now() - start).total_seconds()
        count = orch.count_site_jobs(keyword, source) if orch else None
        reason = _block_reason(source)
        if rc != 0:
            failures.append(source)
            print(f"[!] {source} 실패(rc={rc}, {elapsed:.0f}s)"
                  + (f" — 차단 감지: {reason}" if reason else ""), flush=True)
        elif reason:
            print(f"[OK] {source} 완료({elapsed:.0f}s) — 그러나 차단 신호 감지: {reason}", flush=True)
        else:
            print(f"[OK] {source} 완료({elapsed:.0f}s)", flush=True)

        # 자동 백오프 갱신: 차단 감지 시 쿨다운을 지수적으로 늘리고,
        # 차단 없이 정상 종료(rc==0)면 쿨다운을 해제(회복)한다.
        if reason:
            block_detect.note_block(source, reason)
        elif rc == 0:
            block_detect.note_success(source)

        if orch:
            orch.site_finished(source, rc == 0, count, elapsed, reason=reason)

    if do_aggregate:
        print(f"\n----- aggregate 통합 -----", flush=True)
        agg_start = datetime.now()
        if orch:
            orch.aggregate_started()
        try:
            sys.path.insert(0, str(BASE_DIR))
            from pipeline.aggregate import aggregate as _aggregate
            out = _aggregate(keyword)
            print(f"[OK] 통합 폴더: {out}", flush=True)
            if orch:
                orch.aggregate_finished(True, str(out),
                                        (datetime.now() - agg_start).total_seconds())
        except Exception as e:
            print(f"[!] aggregate 실패: {e}", flush=True)
            failures.append("aggregate")
            if orch:
                orch.aggregate_finished(False, None,
                                        (datetime.now() - agg_start).total_seconds())

    if do_blog:
        print(f"\n----- 기술 블로그 크롤 (LangGraph, 피드당 {blog_per_feed}개) -----", flush=True)
        blog_start = datetime.now()
        if orch:
            orch.blog_started()
        try:
            sys.path.insert(0, str(BASE_DIR))
            from crawlers.crawl_techblog_graph import run as _blog_run
            stats = _blog_run(blog_per_feed, None)
            elapsed = (datetime.now() - blog_start).total_seconds()
            print(f"[OK] 기술 블로그 완료({elapsed:.0f}s) — 총 {stats.get('total')}건 "
                  f"(신규 {stats.get('new')}, 출처 {stats.get('sources')}개) "
                  f"→ jd-viewer/public/tech_blogs.json", flush=True)
            if orch:
                orch.blog_finished(True, stats.get("total"), stats.get("new"),
                                   stats.get("sources"), elapsed)
        except Exception as e:
            print(f"[!] 기술 블로그 크롤 실패: {e}", flush=True)
            failures.append("blog")
            if orch:
                orch.blog_finished(False, None, None, None,
                                   (datetime.now() - blog_start).total_seconds())

    if do_analyze:
        # 파생 분석 재생성 — 늘어난 공고/블로그를 반영해 회사 취업가이드와
        # 학습영상 추천을 다시 만든다. 추천은 하드코딩이 아니라 '매칭'이라,
        # 원본 데이터가 늘면 이 단계만 돌려도 모든 회사 가이드가 갱신된다.
        #   1) build_company_stacks.py — 회사 스택/도메인/아키텍처/취업가이드
        #      (study_blogs 는 방금 갱신된 tech_blogs.json 과 다시 매칭됨)
        #   2) build_learning.py — 기술별 유튜브 학습영상 (캐시 사용, 신규 기술만 조회)
        py = _python_executable()
        bindir = BASE_DIR.parent / "jd-viewer" / "bin"
        analyze_steps = [
            ("회사 분석·취업가이드", [py, str(bindir / "build_company_stacks.py")]),
            ("기술별 학습영상", [py, str(bindir / "build_learning.py")]),
        ]
        for label, cmd in analyze_steps:
            print(f"\n----- 분석 재생성: {label} -----", flush=True)
            step_start = datetime.now()
            try:
                rc = subprocess.call(cmd, env=env)
                elapsed = (datetime.now() - step_start).total_seconds()
                if rc == 0:
                    print(f"[OK] {label} 완료({elapsed:.0f}s)", flush=True)
                else:
                    print(f"[!] {label} 종료코드 {rc}", flush=True)
                    failures.append(f"analyze:{label}")
            except Exception as e:
                print(f"[!] {label} 실패: {e}", flush=True)
                failures.append(f"analyze:{label}")

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


def _parse_run_args(args: list[str]) -> tuple[str, int, list[str], bool, int | None, bool, int]:
    do_aggregate = True
    if "--no-aggregate" in args:
        do_aggregate = False
        args.remove("--no-aggregate")
    do_blog = True
    if "--no-blog" in args:
        do_blog = False
        args.remove("--no-blog")
    do_analyze = True
    if "--no-analyze" in args:
        do_analyze = False
        args.remove("--no-analyze")
    blog_per_feed = BLOG_PER_FEED_DEFAULT
    if "--blog-per-feed" in args:
        i = args.index("--blog-per-feed")
        if i + 1 >= len(args):
            print("[!] --blog-per-feed 다음에 정수가 필요합니다.", flush=True)
            sys.exit(2)
        blog_per_feed = int(args[i + 1])
        del args[i:i + 2]
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
    return (keyword, target, _parse_sources(only), do_aggregate, depth,
            do_blog, blog_per_feed, do_analyze)


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
        (keyword, target, sources, do_aggregate, depth,
         do_blog, blog_per_feed, do_analyze) = _parse_run_args(rest)
        sys.exit(run_foreground(keyword, target, sources, do_aggregate, depth,
                                do_blog, blog_per_feed, do_analyze))
    else:
        print(f"[!] 알 수 없는 명령: {sub}", flush=True)
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
