"""채용 크롤 → 데이터 갱신을 주기적으로 반복하는 자동화 데몬.

매 주기마다:
  1) crawl_all.run_foreground 로 키워드 사이트 5곳을 키워드마다 크롤하고,
     키워드 무관 소스(remote·ats)는 사이클당 1회 붙인 뒤 aggregate 까지 수행
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
    python auto_crawl.py prune [keep] [--dry-run]   # 오래된 스냅샷 정리 (데몬도 매 사이클 수행)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import json
import os
import re
import shutil
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
# 사이클당 마감 재확인 건수(원본 사이트 조회). 올리면 한 바퀴가 빨라지지만 차단 위험도 오른다.
CLOSE_CHECK_LIMIT = int(os.environ.get("CLOSE_CHECK_LIMIT", "400"))

# 키워드로 검색하는 국내 사이트. 사이클마다 키워드 수만큼 돈다.
KEYWORD_SITES = ["dev", "jobkorea", "jumpit", "saramin", "wanted"]
# 키워드와 무관한 소스(해외 원격 보드·회사 ATS). 보드 전체를 훑으므로 키워드마다
# 돌 이유가 없다 — 기술 블로그와 같이 사이클당 1회(마지막 키워드)만 붙인다.
AGNOSTIC_SITES = ["remote", "ats"]

# 크롤 오케스트레이션이 함께 굴리는 부가 작업(흩어진 cron 을 여기로 통합)
RADAR_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_company_tech_radar.py"
REVIEWS_LOOP_SH = ROOT_DIR / "jd-viewer" / "bin" / "reviews-loop.sh"
LEARNING_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_learning.py"
CALENDAR_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_calendar.py"
TRENDS_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_trends.py"
RELATIONS_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_tech_relations.py"
REPOSTS_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_reposts.py"
CAREER_MAP_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_career_map.py"
BLOG_GUIDES_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_blog_guides.py"
INFLEARN_SCRIPT = ROOT_DIR / "jd-viewer" / "bin" / "build_inflearn.py"
RADAR_REFINE_N = 2                     # 사이클당 레이더 점진 리파인 회사 수
LEARNING_REFRESH_SECS = 6 * 3600       # 학습영상 캐시 무시 재수집 주기(기존 learning cron 대체)
# 인프런은 강의 상세를 한 건씩 받아오느라 기술 24개에 6~8분이 든다. 강의 카탈로그는
# 공고처럼 30분마다 바뀌지 않으므로 사이클마다 돌릴 이유가 없다.
INFLEARN_REFRESH_SECS = 12 * 3600
LEARNING_STAMP = BASE_DIR / ".learning_refresh.stamp"
INFLEARN_STAMP = BASE_DIR / ".inflearn_refresh.stamp"

RADAR_JSON = ROOT_DIR / "jd-viewer" / "public" / "company_tech_radar.json"

DEFAULT_KEYWORD = "개발자"
DEFAULT_COUNT = 20
DEFAULT_INTERVAL = 3600  # 1시간

# 디스크 유지보수 — 무한 로그/스냅샷 누적으로 디스크가 꽉 차 데몬이 죽는 사고 방지.
LOG_MAX_BYTES = 20 * 1024 * 1024   # auto_crawl.log 로테이션 임계치(20MB)
SNAPSHOT_KEEP = 3                  # screenshots 타임스탬프 폴더 계열별 보관 개수
                                   # 8개일 때 통합 계열만 2.3GB(파일 25만 개)를 물고 있어
                                   # 디스크가 8GB 밑으로 떨어지고 스왑이 터졌다. 3개면 충분하다
                                   # — 스냅샷은 사이클마다 다시 만들어진다.
_TS_RE = re.compile(r"_\d{8}_\d{6}$")  # <prefix>_YYYYMMDD_HHMMSS 접미사


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


def prune_snapshots(keep: int = SNAPSHOT_KEEP, dry_run: bool = False) -> list[Path]:
    """screenshots/<계열>_YYYYMMDD_HHMMSS/ 를 계열별 최신 keep 개만 남긴다.

    타임스탬프가 없는 폴더(saramin_리액트 같은 고정 누적 폴더, *_latest)는
    크롤러가 계속 덮어쓰는 현재 상태라 대상에서 제외한다.
    반환값은 삭제한(dry_run 이면 삭제 대상) 폴더 목록.
    """
    if not SCREENSHOTS_DIR.exists():
        return []
    series: dict[str, list[Path]] = {}
    for d in SCREENSHOTS_DIR.iterdir():
        if not d.is_dir():
            continue
        m = _TS_RE.search(d.name)
        if not m:
            continue
        series.setdefault(d.name[: m.start()], []).append(d)

    targets: list[Path] = []
    for dirs in series.values():
        # 이름에 박힌 타임스탬프가 곧 생성 순서다. mtime 은 복사/rsync 로 흐트러질 수 있어
        # 어느 스냅샷이 최신인지 판단하는 근거로 쓰지 않는다.
        dirs.sort(key=lambda p: p.name, reverse=True)
        targets.extend(dirs[keep:])

    if dry_run:
        return targets

    removed: list[Path] = []
    for old in targets:
        try:
            shutil.rmtree(old)
            removed.append(old)
        except OSError as e:
            log(f"[prune] {old.name} 삭제 실패: {e}")
    if removed:
        log(f"[prune] 스냅샷 {len(removed)}개 삭제 (계열별 최신 {keep}개 유지)")
    return removed


def rotate_log() -> None:
    """auto_crawl.log 가 임계치를 넘으면 최근 분량만 남기고 제자리에서 잘라낸다.

    데몬의 stdout 은 cmd_start 가 O_APPEND 로 열어 물려준 fd 다. 파일을 rename 해서
    새 파일로 미는 방식은 자식이 옛 inode 에 계속 써서 디스크가 돌아오지 않는다.
    그래서 같은 inode 를 truncate 한다. 이 함수는 데몬 자신이 사이클 사이에 부르므로
    그 시점에 동시 쓰기는 없다.
    """
    try:
        size = LOG_FILE.stat().st_size
    except OSError:
        return
    if size <= LOG_MAX_BYTES:
        return
    keep_bytes = LOG_MAX_BYTES // 4
    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(-keep_bytes, os.SEEK_END)
            f.readline()  # 중간에서 잘린 첫 줄은 버린다
            tail = f.read()
        with open(LOG_FILE, "r+b") as f:
            f.write(tail)
            f.truncate()
    except OSError as e:
        log(f"[rotate] 로그 정리 실패: {e}")
        return
    log(f"[rotate] auto_crawl.log {size // (1 << 20)}MB → 최근 {len(tail) // (1 << 20)}MB 만 유지")


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

    refresh_semantic()


def refresh_closures(limit: int = CLOSE_CHECK_LIMIT) -> int:
    """공고 마감 재확인 — 원본 사이트에 다시 물어 끝난 공고를 닫는다. 닫은 건수 반환.

    크롤은 "지금 올라온 공고"만 가져오지, 어제 가져온 공고가 아직 살아 있는지는 말해
    주지 않는다. 누적 폴더는 한 번 수집한 공고를 계속 들고 있으므로 확인해 주는 쪽이
    없으면 마감 공고가 영원히 모집중으로 남는다 — 특히 마감일 표기 자체가 없는 wanted.

    회차당 상한을 두고 오래 방치된 것부터 돌아가며 확인한다. 몇 사이클에 걸쳐 전체를
    한 바퀴 돌게 되는데, 그래도 사이트마다 수천 건을 한 번에 두드리는 것보다 낫다
    (차단당하면 크롤 본체까지 같이 죽는다). 실패해도 사이클은 그대로 진행한다.
    """
    try:
        from pipeline import close_check
    except ImportError as e:
        log(f"[close] 모듈 적재 실패 — 건너뜀: {e}")
        return 0
    orch.builder_started("마감 재확인")
    t0 = time.time()
    try:
        stats = close_check.run(limit=limit, verbose=False)
        detail = (f"확인 {stats['checked']}건 → 마감 {stats['closed']} / "
                  f"모집중 {stats['active']} / 불명 {stats['unknown']}")
        log(f"[close] {detail}")
        orch.builder_finished("마감 재확인", True, time.time() - t0, detail)
        return stats["closed"]
    except Exception as e:                                          # noqa: BLE001
        log(f"[close] 실패: {e!r}")
        orch.builder_finished("마감 재확인", False, time.time() - t0, repr(e))
        return 0


def refresh_semantic() -> None:
    """시맨틱 갱신: 적재 → 변경분 임베딩 → 유사 공고 JSON 재생성.

    public/*.json 이 갱신된 뒤에 부른다(그 파일들이 곧 입력이다). 임베딩은 증분이라
    사이클당 실제 대상은 보통 수십~수백 건이다.

    Ollama 가 꺼져 있거나 모델이 없으면 로그만 남기고 넘어간다 — 추천은 부가 기능이고,
    이것 때문에 크롤 사이클이 멈추면 손해가 더 크다.
    """
    try:
        from semantic import db as sdb, embed as sembed, ingest as singest, similar as ssim
    except ImportError as e:
        log(f"[semantic] 모듈 적재 실패 — 건너뜀: {e}")
        return

    conn = None
    try:
        conn = sdb.open_db()
        counts = singest.run(conn)
        log("[semantic] 적재 " + ", ".join(
            f"{k}: 신규 {v['new']}/변경 {v['changed']}/삭제 {v['removed']}"
            for k, v in counts.items()))

        rep = sembed.run(conn, verbose=False)
        log(f"[semantic] 임베딩 {rep['embedded']}건 "
            f"(실패 {rep['failed']}, {rep['seconds']}s)")

        if rep["embedded"] or rep["failed"] == 0:
            sim = ssim.run(conn)
            log("[semantic] 추천 " + ", ".join(
                f"{k}: {v['with_similar']}/{v['documents']}건" for k, v in sim.items()))
    except sembed.EmbedError as e:
        log(f"[semantic] 임베딩 불가 — 건너뜀: {e}")
    except Exception as e:
        log(f"[semantic] 실패: {e!r}")
    finally:
        if conn is not None:
            conn.close()


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


def run_builder(label: str, script: Path, args: list[str] | None = None,
                stamp: Path | None = None, every_secs: int = 0) -> None:
    """뷰어 데이터 빌더 하나를 돌리고 결과를 운영 상태에 남긴다.

    빌더마다 같은 try/except 를 세 번 복사해 두었던 것을 하나로 모은다. 여기서 중요한
    것은 예외를 삼키는 것 자체가 아니라 **삼킨 사실을 남기는 것**이다. 빌더가 실패해도
    뷰어는 지난번 JSON 을 그대로 잘 보여주기 때문에, 기록이 없으면 어떤 화면이 며칠째
    멈춰 있는지 아무도 모른다.

    stamp/every_secs 를 주면 그 주기 안에는 건너뛴다(인프런처럼 느린 수집용).
    """
    if stamp is not None and every_secs:
        try:
            last = float(stamp.read_text()) if stamp.exists() else 0.0
        except (OSError, ValueError):
            last = 0.0
        if time.time() - last < every_secs:
            orch.builder_finished(label, True, 0.0,
                                  f"주기 {every_secs // 3600}h 내 — 건너뜀", skipped=True)
            return

    orch.builder_started(label)
    t0 = time.time()
    try:
        rc = subprocess.call([_python_executable(), str(script), *(args or [])],
                             cwd=str(ROOT_DIR))
        ok = rc == 0
        if stamp is not None and ok:
            stamp.write_text(str(time.time()))
        log(f"[{label}] {'완료' if ok else f'실패(rc={rc})'} ({time.time() - t0:.0f}s)")
        orch.builder_finished(label, ok, time.time() - t0, "" if ok else f"rc={rc}")
    except Exception as e:                                          # noqa: BLE001
        log(f"[{label}] 예외: {e!r}")
        orch.builder_finished(label, False, time.time() - t0, repr(e))


def enrich_extras() -> None:
    """크롤과 무관하게 매 사이클 굴리는 부가 작업.

    순서에 의존성이 있다. 트렌드가 tracked 기술 목록을 만들고 인프런이 그것을 읽으므로
    트렌드가 먼저다. 재공고·커리어 맵·블로그 가이드는 refresh_data/refresh_semantic 이
    만들어 둔 enriched JSON 과 semantic.db 를 읽으므로 그 뒤에 온다.
    """
    maybe_refresh_learning()
    enrich_radar()
    ensure_reviews_daemon()
    run_builder("모집 캘린더", CALENDAR_SCRIPT)
    run_builder("개발 트렌드", TRENDS_SCRIPT)
    run_builder("기술 관계", RELATIONS_SCRIPT)
    # 재공고는 매 사이클 돌아야 한다. 여기서 한 번 거르면 그 회차의 변경은 영영 기록되지
    # 않고, 나중에 되돌아가 채울 방법도 없다(공고 원본이 이미 사라진다).
    run_builder("재공고 추적", REPOSTS_SCRIPT)
    run_builder("커리어 맵", CAREER_MAP_SCRIPT)
    run_builder("블로그 가이드", BLOG_GUIDES_SCRIPT)
    run_builder("인프런 강의", INFLEARN_SCRIPT, stamp=INFLEARN_STAMP,
                every_secs=INFLEARN_REFRESH_SECS)


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
        last = kw == kws[-1]
        rc = run_foreground(kw, count, KEYWORD_SITES + (AGNOSTIC_SITES if last else []),
                            do_aggregate=not multi, do_blog=last)
        if rc != 0:
            rc_fail += 1
            log(f"[crawl] '{kw}' 일부 실패(rc={rc})")

    if multi:
        log(f"[aggregate] {len(kws)}개 키워드 통합 → all_{label}_*")
        aggregate(kws[0], keywords=kws, label=label)

    # 마감 재확인은 갱신 **전**에 온다. 원장을 먼저 채워야 enrich 가 그 판정을 반영해
    # 뷰어 데이터를 쓴다(순서가 바뀌면 닫은 공고가 한 사이클 늦게 반영된다).
    closed_now = refresh_closures()

    after = _latest_all_dir(label)
    new_data = bool(after and after != before)
    if new_data:
        log(f"[crawl] 새 데이터 감지: {after} → 갱신 진행")
        refresh_data(label)
    elif closed_now:
        # 새 공고가 없어도 마감이 생겼으면 화면은 바뀌어야 한다.
        log(f"[crawl] 새 데이터는 없지만 마감 {closed_now}건 → 갱신 진행")
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
        # 디스크 유지보수 — 사이클마다 스냅샷·로그가 무한히 쌓이면 결국 데몬이 디스크로 죽는다.
        try:
            prune_snapshots()
            rotate_log()
        except Exception as e:
            log(f"[err] 유지보수 예외: {e!r}")
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
    elif sub == "prune":
        keep = int(rest[0]) if rest and rest[0].isdigit() else SNAPSHOT_KEEP
        dry = "--dry-run" in rest
        targets = prune_snapshots(keep, dry_run=dry)
        if dry:
            for t in sorted(targets, key=lambda p: p.name):
                print(t.name, flush=True)
            print(f"[*] 삭제 대상 {len(targets)}개 (계열별 최신 {keep}개 유지) — 실제 삭제 안 함", flush=True)
        else:
            print(f"[*] 스냅샷 {len(targets)}개 삭제 완료", flush=True)
        rotate_log()
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
