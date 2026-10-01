"""5개 채용 사이트 크롤러를 통합 관리.

각 크롤러는 기존대로 `screenshots/<site>_<keyword>_<timestamp>/`에 저장되고,
모든 사이트가 끝나면 `aggregate.py`가 자동 호출되어
    `screenshots/all_<keyword>_<timestamp>/`
에 통합 폴더(`all_jobs.json` + `summary.txt` + 사이트별 사본)를 만든다.

잡 크롤 5개 + aggregate 가 끝나면, 별도 단계로 기술 블로그 크롤
(`crawl_techblog_graph` — LangGraph, LLM 없음)이 실행되어
    `jd-viewer/public/tech_blogs.json`
을 누적 갱신한다. `--no-blog` 로 끌 수 있다.

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
    python crawl_all.py start 개발자 30 --no-freelance   # 외주·프리 단계 스킵
    python crawl_all.py start 개발자 30 --no-hardware    # PC 부품 가격 단계 스킵
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

from core.sites import BY_KEY

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

# 사이트 목록은 core/sites.py 하나다(크롤러 스크립트 이름까지).
SOURCES: dict[str, dict] = {k: {"script": s.script} for k, s in BY_KEY.items()}

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


def fix_locations() -> None:
    """근무지 보수(pipeline.backfill_location)를 **통합 전에** 돈다.

    크롤이 못 채운 근무지를 원본(wanted 상세 API / jobkorea JSON-LD)에서 받아 누적 폴더를
    고친다. 통합(aggregate → 정본 DB 적재) 앞에 두어야 고친 값이 그 회차 DB 에 바로 실린다.
    캐시가 있어 이미 확인한 공고는 다시 묻지 않는다. 실패해도 사이클은 계속 간다.
    """
    rc = subprocess.call([sys.executable, "-m", "pipeline.backfill_location"], cwd=str(BASE_DIR))
    if rc != 0:
        print(f"[!] 근무지 보수 실패(rc={rc}) — 기존 값으로 계속합니다.", flush=True)


def run_foreground(keyword: str, target: int, sources: list[str], do_aggregate: bool = True,
                   depth: int | None = None, do_blog: bool = True,
                   blog_per_feed: int = BLOG_PER_FEED_DEFAULT, do_freelance: bool = True,
                   do_hardware: bool = True) -> int:
    """지정한 크롤러를 순차 실행. 완료 후 aggregate + 기술 블로그 + 외주·프리 + 부품 가격 크롤 호출."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    try:
        from automation import orchestration as orch
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
        fix_locations()
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
            # 정본 DB(post)에도 넣는다 — 뷰어 API 의 글 목록·관련 글·글 임베딩이 이 표를 읽는다.
            # 예전에는 손으로만(db-migrate.yml) 돌아서 post 가 크롤과 따로 놀았다.
            # 실패해도 사이클은 계속 간다(이중 쓰기 약속).
            if os.environ.get("DB_DUAL_WRITE", "1") != "0":
                try:
                    from store.ingest.posts import ingest as _posts_ingest
                    print(f"  [db] post {_posts_ingest()}", flush=True)
                except Exception as e:                              # noqa: BLE001
                    print(f"  [db] post 건너뜀: {e}", flush=True)
        except Exception as e:
            print(f"[!] 기술 블로그 크롤 실패: {e}", flush=True)
            failures.append("blog")
            if orch:
                orch.blog_finished(False, None, None, None,
                                   (datetime.now() - blog_start).total_seconds())

    if do_freelance:
        # 외주·프리랜서 프로젝트. 채용 공고와 섞지 않고 freelance.json 에 따로 쌓는다
        # (crawlers/crawl_freelance.py 머리말). 실패해도 사이클은 계속 간다.
        print(f"\n----- 외주·프리 프로젝트 크롤 -----", flush=True)
        fl_start = datetime.now()
        if orch:
            orch.freelance_started()
        try:
            sys.path.insert(0, str(BASE_DIR))
            from crawlers.crawl_freelance import run as _fl_run
            stats = _fl_run()
            elapsed = (datetime.now() - fl_start).total_seconds()
            print(f"[OK] 외주·프리 완료({elapsed:.0f}s) — 누적 {stats.get('total')}건 "
                  f"(모집중 {stats.get('active')}, 신규 {stats.get('new')}, 출처 {stats.get('sources')}곳) "
                  f"→ jd-viewer/public/freelance.json", flush=True)
            if orch:
                orch.freelance_finished(bool(stats.get("sources")), stats.get("total"),
                                        stats.get("new"), stats.get("active"), elapsed)
        except Exception as e:
            print(f"[!] 외주·프리 크롤 실패: {e}", flush=True)
            failures.append("freelance")
            if orch:
                orch.freelance_finished(False, None, None, None,
                                        (datetime.now() - fl_start).total_seconds())

    if do_hardware:
        # PC 부품 가격. 하루 한 번만 실제로 돈다(crawlers/crawl_hardware.py 머리말) —
        # 그날 이미 받았으면 파일만 보고 바로 돌아온다. 실패해도 사이클은 계속 간다.
        print(f"\n----- PC 부품 가격 크롤 -----", flush=True)
        hw_start = datetime.now()
        if orch:
            orch.stage_started("hardware")
        try:
            sys.path.insert(0, str(BASE_DIR))
            from crawlers.crawl_hardware import run as _hw_run
            stats = _hw_run()
            elapsed = (datetime.now() - hw_start).total_seconds()
            if orch:
                orch.stage_finished("hardware", not stats.get("failed"), elapsed, **stats)
            if not stats.get("skipped"):
                print(f"[OK] 부품 가격 완료({elapsed:.0f}s) — 부품 {stats.get('total')}개 중 "
                      f"{stats.get('priced')}개 가격, 실패 {stats.get('failed')} "
                      f"→ jd-viewer/public/hardware/prices.json", flush=True)
            if stats.get("failed"):
                failures.append("hardware")
        except Exception as e:
            print(f"[!] 부품 가격 크롤 실패: {e}", flush=True)
            failures.append("hardware")
            if orch:
                orch.stage_finished("hardware", False, (datetime.now() - hw_start).total_seconds(), error=str(e)[:200])
        # 완제품 조립PC — 부품 가격 다음에 돈다(구성을 그날 부품 목록에 잇는다). 역시 하루 한 번.
        pb_start = datetime.now()
        if orch:
            orch.stage_started("prebuilt")
        try:
            from crawlers.crawl_prebuilt import run as _pb_run
            stats = _pb_run()
            if orch:
                orch.stage_finished("prebuilt", not stats.get("failed"), (datetime.now() - pb_start).total_seconds(), **stats)
            if not stats.get("skipped"):
                print(f"[OK] 완제품 {stats.get('total')}개(오늘 {stats.get('seen_today')}) · 구성 새로 읽음 "
                      f"{stats.get('specs_read')} · 목록에 없는 CPU·GPU {stats.get('unmapped_cpu_gpu')}"
                      f" → jd-viewer/public/hardware/prebuilt.json", flush=True)
            if stats.get("failed"):
                failures.append("prebuilt")
        except Exception as e:
            print(f"[!] 완제품 크롤 실패: {e}", flush=True)
            failures.append("prebuilt")
            if orch:
                orch.stage_finished("prebuilt", False, (datetime.now() - pb_start).total_seconds(), error=str(e)[:200])

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


def _parse_run_args(args: list[str]) -> tuple[str, int, list[str], bool, int | None, bool, int, bool, bool]:
    do_hardware = True
    if "--no-hardware" in args:
        do_hardware = False
        args.remove("--no-hardware")
    do_freelance = True
    if "--no-freelance" in args:
        do_freelance = False
        args.remove("--no-freelance")
    do_aggregate = True
    if "--no-aggregate" in args:
        do_aggregate = False
        args.remove("--no-aggregate")
    do_blog = True
    if "--no-blog" in args:
        do_blog = False
        args.remove("--no-blog")
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
    return (keyword, target, _parse_sources(only), do_aggregate, depth, do_blog, blog_per_feed, do_freelance,
            do_hardware)


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
        (keyword, target, sources, do_aggregate, depth, do_blog, blog_per_feed, do_freelance,
         do_hardware) = _parse_run_args(rest)
        sys.exit(run_foreground(keyword, target, sources, do_aggregate, depth, do_blog, blog_per_feed,
                                do_freelance, do_hardware))
    else:
        print(f"[!] 알 수 없는 명령: {sub}", flush=True)
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
