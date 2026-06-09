"""크롤 파이프라인 오케스트레이션 상태/이벤트 기록기.

각 단계(크롤 시작 → 사이트별 수집 → aggregate → dashboard/viewer 갱신 → 대기)에서
호출되어 catch_capture 루트의 두 파일을 갱신한다:

  - run_state.json   : 현재 스냅샷 (원자적 덮어쓰기). ops_server 가 폴링해 실시간 표시.
  - run_events.jsonl : 단계 전이 이벤트 스트림 (append, 최근 MAX_EVENTS 줄만 보관).

automation.auto_crawl 데몬 / automation.crawl_all 단독 실행 양쪽에서 import 되며,
둘 다 같은 파일을 쓴다. 실패해도 본 파이프라인을 막지 않도록 모든 함수는 예외를 삼킨다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

# catch_capture 루트 (screenshots/ 등 데이터가 사는 곳). monitoring/ 의 한 단계 위.
BASE_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
STATE_FILE = BASE_DIR / "run_state.json"
EVENTS_FILE = BASE_DIR / "run_events.jsonl"

MAX_EVENTS = 800
ALL_SITES = ["dev", "jobkorea", "jumpit", "saramin", "wanted"]

# 파이프라인 단계 식별자 (프런트의 stepper 와 1:1)
PHASE_IDLE = "idle"
PHASE_CRAWLING = "crawling"
PHASE_AGGREGATING = "aggregating"
PHASE_BLOG = "blog"
PHASE_BUILDING = "building"
PHASE_REFRESHING = "refreshing"
PHASE_WAITING = "waiting"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    try:
        state["updated_at"] = _now_iso()
        _atomic_write(STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2))
    except Exception:
        pass


def emit(event_type: str, **fields) -> None:
    """이벤트 한 줄을 run_events.jsonl 에 append."""
    try:
        rec = {"ts": _now_iso(), "type": event_type, **fields}
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _trim_events()
    except Exception:
        pass


def _trim_events() -> None:
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_EVENTS:
            with open(EVENTS_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-MAX_EVENTS:])
    except FileNotFoundError:
        pass
    except Exception:
        pass


def count_site_jobs(keyword: str, site: str) -> int | None:
    """방금 크롤한 site 의 최신 jobs.json 건수."""
    try:
        # 사이트마다 폴더 네이밍이 다르다: 일부는 `<site>_<kw>`(고정, 덮어씀),
        # 일부는 `<site>_<kw>_<timestamp>`(매회 새 폴더). 둘 다 `<site>_<kw>*` 로 잡고,
        # jobs.json 의 mtime 이 가장 최신인 폴더를 고른다(이름 정렬은 두 방식 혼재 시 부정확).
        cands = []
        for p in SCREENSHOTS_DIR.glob(f"{site}_{keyword}*"):
            if not p.is_dir():
                continue
            jf = p / "jobs.json"
            if jf.exists():
                cands.append(jf)
        if not cands:
            return None
        newest = max(cands, key=lambda f: f.stat().st_mtime)
        return len(json.loads(newest.read_text(encoding="utf-8")))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 단계별 고수준 헬퍼 (event append + state mutate 동시 수행)
# ---------------------------------------------------------------------------

def daemon_started(keyword: str, count: int, interval: int, run_now: bool) -> None:
    state = load_state()
    state["daemon"] = {
        "keyword": keyword,
        "count": count,
        "interval": interval,
        "started_at": _now_iso(),
        "pid": os.getpid(),
    }
    state["phase"] = PHASE_WAITING if not run_now else PHASE_IDLE
    state["next_run_at"] = None
    save_state(state)
    emit("daemon_start", keyword=keyword, count=count, interval=interval, run_now=run_now)


def crawl_started(keyword: str, sources: list[str]) -> None:
    state = load_state()
    state["phase"] = PHASE_CRAWLING
    state["cycle"] = {
        "started_at": _now_iso(),
        "keyword": keyword,
        "sites": {s: {"status": "pending", "count": None, "elapsed": None}
                  for s in sources},
        "aggregate": {"status": "pending", "out": None, "elapsed": None},
        "refresh": {"dashboard": "pending", "viewer": "pending"},
        "finished_at": None,
        "new_data": None,
    }
    save_state(state)
    emit("cycle_start", keyword=keyword, sources=sources)


def site_started(site: str) -> None:
    state = load_state()
    cyc = state.setdefault("cycle", {}).setdefault("sites", {})
    cyc.setdefault(site, {})
    cyc[site].update({"status": "running", "started_at": _now_iso()})
    state["phase"] = PHASE_CRAWLING
    save_state(state)
    emit("site_start", site=site)


def site_finished(site: str, ok: bool, count: int | None, elapsed: float,
                  reason: str | None = None) -> None:
    """reason: 차단/레이트리밋 감지 시 식별자(block_detect 의 R_* ). 없으면 None."""
    state = load_state()
    cyc = state.setdefault("cycle", {}).setdefault("sites", {})
    cyc.setdefault(site, {})
    cyc[site].update({
        "status": "done" if ok else "failed",
        "count": count,
        "elapsed": round(elapsed, 1),
        "reason": reason,
    })
    save_state(state)
    emit("site_done", site=site, ok=ok, count=count, elapsed=round(elapsed, 1), reason=reason)


def site_cooldown_skipped(site: str, remaining: int, info: dict | None = None) -> None:
    """차단 백오프(쿨다운)로 이번 사이클 해당 사이트 크롤을 건너뛸 때."""
    info = info or {}
    state = load_state()
    cyc = state.setdefault("cycle", {}).setdefault("sites", {})
    cyc.setdefault(site, {})
    cyc[site].update({
        "status": "cooldown",
        "reason": info.get("reason"),
        "cooldown_remaining": remaining,
        "cooldown_until": info.get("until"),
    })
    save_state(state)
    emit("site_cooldown", site=site, remaining=remaining,
         level=info.get("level"), until=info.get("until"), reason=info.get("reason"))


def aggregate_started() -> None:
    state = load_state()
    state["phase"] = PHASE_AGGREGATING
    state.setdefault("cycle", {}).setdefault("aggregate", {})["status"] = "running"
    save_state(state)
    emit("aggregate_start")


def aggregate_finished(ok: bool, out: str | None, elapsed: float) -> None:
    state = load_state()
    agg = state.setdefault("cycle", {}).setdefault("aggregate", {})
    agg.update({"status": "done" if ok else "failed",
                "out": out, "elapsed": round(elapsed, 1)})
    save_state(state)
    emit("aggregate_done", ok=ok, out=out, elapsed=round(elapsed, 1))


def blog_started() -> None:
    state = load_state()
    state["phase"] = PHASE_BLOG
    state.setdefault("cycle", {}).setdefault("blog", {})["status"] = "running"
    save_state(state)
    emit("blog_start")


def blog_finished(ok: bool, total: int | None, new: int | None,
                  sources: int | None, elapsed: float) -> None:
    """기술 블로그 크롤 결과. total/new/sources = 누적·신규·출처 수."""
    state = load_state()
    b = state.setdefault("cycle", {}).setdefault("blog", {})
    b.update({"status": "done" if ok else "failed", "total": total,
              "new": new, "sources": sources, "elapsed": round(elapsed, 1)})
    save_state(state)
    emit("blog_done", ok=ok, total=total, new=new, sources=sources, elapsed=round(elapsed, 1))


def refresh_started(target: str) -> None:
    """target: 'dashboard' | 'viewer'"""
    state = load_state()
    state["phase"] = PHASE_BUILDING if target == "dashboard" else PHASE_REFRESHING
    state.setdefault("cycle", {}).setdefault("refresh", {})[target] = "running"
    save_state(state)
    emit("refresh_start", target=target)


def refresh_finished(target: str, ok: bool) -> None:
    state = load_state()
    state.setdefault("cycle", {}).setdefault("refresh", {})[target] = "done" if ok else "failed"
    save_state(state)
    emit("refresh_done", target=target, ok=ok)


def cycle_finished(new_data: bool, elapsed: float) -> None:
    state = load_state()
    cyc = state.setdefault("cycle", {})
    cyc["finished_at"] = _now_iso()
    cyc["new_data"] = new_data
    cyc["total_elapsed"] = round(elapsed, 1)
    save_state(state)
    emit("cycle_done", new_data=new_data, elapsed=round(elapsed, 1))


def waiting(next_run_at: str, interval: int) -> None:
    state = load_state()
    state["phase"] = PHASE_WAITING
    state["next_run_at"] = next_run_at
    save_state(state)
    emit("wait", next_run_at=next_run_at, interval=interval)


def error(where: str, msg: str) -> None:
    state = load_state()
    state["last_error"] = {"where": where, "msg": msg, "ts": _now_iso()}
    save_state(state)
    emit("error", where=where, msg=msg)
