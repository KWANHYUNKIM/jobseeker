"""크롤된 JD 데이터 접근 — 뷰어 API(backend, 8771)의 공고 전량을 읽기 전용으로 소비.

뷰어 화면과 같은 출처(정본 DB 를 읽는 순간의 모집 상태)다. API 가 없으면 공개 뷰어의 사본
(jd-viewer/public/all_jobs_enriched.json)으로 물러선다. 전량이 크므로 core.api 가 몇 분씩 들고
있다가 바뀌었을 때만(ETag) 다시 받는다.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path
from typing import Any

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # catch_capture

from core import api  # noqa: E402


def _load() -> list[dict[str, Any]]:
    data = api.get("/api/jobs/all", file="all_jobs_enriched.json", key="admin:jobs")
    return data if isinstance(data, list) else []


def job_key(job: dict[str, Any]) -> str:
    return f"{job.get('site','')}:{job.get('idx','')}"


_LIST_FIELDS = ("site", "idx", "company", "title", "url", "career",
                "location", "tech_stack", "deadline", "dday")


def _slim(job: dict[str, Any]) -> dict[str, Any]:
    """목록용 경량 표현(본문 제외)."""
    out = {k: job.get(k) for k in _LIST_FIELDS}
    out["key"] = job_key(job)
    return out


def search(query: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    jobs = _load()
    q = (query or "").strip().lower()
    if q:
        terms = q.split()

        def hit(job: dict[str, Any]) -> bool:
            hay = " ".join(str(job.get(k, "")) for k in
                           ("company", "title", "tech_stack", "qualifications",
                            "preferences", "main_tasks", "location")).lower()
            return all(t in hay for t in terms)

        matched = [j for j in jobs if hit(j)]
    else:
        matched = jobs
    total = len(matched)
    page = matched[offset:offset + limit]
    return {"total": total, "count": len(page), "items": [_slim(j) for j in page]}


def get(key: str) -> dict[str, Any] | None:
    for j in _load():
        if job_key(j) == key:
            return j
    return None


def all_jobs() -> list[dict[str, Any]]:
    return _load()


def matches_query(job: dict[str, Any], terms: list[str]) -> bool:
    if not terms:
        return True
    hay = " ".join(str(job.get(k, "")) for k in
                   ("company", "title", "tech_stack", "qualifications",
                    "preferences", "main_tasks", "location")).lower()
    return all(t in hay for t in terms)
