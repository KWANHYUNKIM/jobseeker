"""크롤된 JD 데이터 접근 — 공개 뷰어가 쓰는 enriched JSON을 읽기 전용으로 소비.

39MB 파일이라 1회 로드 후 메모리 캐시. 파일 mtime이 바뀌면(자동 크롤 갱신) 재로드.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent      # jobseeker/
ENRICHED = ROOT_DIR / "jd-viewer" / "public" / "all_jobs_enriched.json"

_lock = threading.Lock()
_cache: list[dict[str, Any]] = []
_mtime: float = 0.0


def _load() -> list[dict[str, Any]]:
    global _cache, _mtime
    if not ENRICHED.is_file():
        return []
    mtime = ENRICHED.stat().st_mtime
    with _lock:
        if mtime == _mtime and _cache:
            return _cache
        try:
            with ENRICHED.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return _cache
        _cache = data if isinstance(data, list) else []
        _mtime = mtime
        return _cache


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
