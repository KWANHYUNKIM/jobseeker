"""외주 API — freelance.json 과 같은 모양(뷰어 features/freelance 의 FreelanceData).

프로젝트 행은 표에서 읽어 **모집 상태가 지금 것**이다. 표에 없는 계산 결과(추이·
분석·단가 기록·프로젝트별 등급 분류)는 크롤 단계가 viewer_doc 에 둔 것을 합친다.
"""
from __future__ import annotations

from app.core.exceptions import NotFound
from app.features.freelance import repository
from app.features.freelance.repository import HISTORY_KEEP
from app.utils.cache import cached


def _iso(d) -> str | None:
    return d.isoformat() if d else None


def _history(v: dict) -> dict:
    return {
        "at": v["seen_at"].isoformat(),
        "budget": {"type": v["b"], "min": v["budget_min"], "max": v["budget_max"]} if v["b"] else None,
        "status": "active" if v["source_open"] else "closed",
        "duration": f"{v['duration_days']}일" if v["duration_days"] else "",
        "applicants": v["applicants"],
    }


def to_project(r: dict, hist: list[dict], reason: str | None, cls: dict) -> dict:
    budget = ({"type": r["budget_basis"], "min": r["budget_min"], "max": r["budget_max"]}
              if r["budget_basis"] else None)
    return {
        "id": f"{r['site']}:{r['pid']}", "site": r["site"], "pid": r["pid"], "url": r["url"],
        "title": r["title"], "category": r["category"], "kind": r["work_mode"] or "",
        "location": r["location_text"], "budget": budget, "duration": r["duration_text"],
        "start": r["start_text"], "skills": list(r["skills"] or []), "career": r["career_text"],
        "posted_date": _iso(r["posted_on"]), "deadline": _iso(r["deadline_on"]),
        "applicants": r["applicants"], "summary": r["summary"], "tags": list(r["tags"] or []),
        # 화면은 active/closed 만 안다. stale 은 last_seen_at 으로 화면이 다시 가린다.
        "status": "closed" if r["status"] == "closed" else "active",
        "closed_reason": reason,
        "history": [_history(v) for v in hist[-HISTORY_KEEP:]],
        "first_seen_at": r["first_seen_at"].isoformat(), "last_seen_at": r["last_seen_at"].isoformat(),
        **cls,
    }


def freelance() -> dict:
    return cached(("freelance",), _freelance)


def _freelance() -> dict:
    meta = repository.meta()
    if not meta:
        raise NotFound("외주 분석이 아직 없다(crawl_freelance 가 DB 에 쓰기 전)")
    m = dict(meta["payload"])
    classes = m.pop("classes", {}) or {}
    rows, hist, reasons = repository.projects()
    projects = [to_project(r, hist.get(r["id"], []), reasons.get(r["id"]),
                           classes.get(f"{r['site']}:{r['pid']}", {})) for r in rows]
    return {**m, "source_of_truth": "db", "projects": projects}
