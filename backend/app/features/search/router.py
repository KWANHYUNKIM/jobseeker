"""검색 API.

    GET /api/search?q=...&kind=job|post&include_closed=1

검색어만 받는다. 사이트·경력 같은 축은 `/api/jobs?semantic=true` 가 후보를 뽑은 뒤
SQL 로 건다(이 경로는 파일 모드 뷰어와 외부 도구용이다).
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.core.exceptions import BadRequest
from app.features.jobs.constants import MAX_QUERY_CHARS
from app.features.search import service

router = APIRouter(prefix="/api/search", tags=["search"])

MAX_LIMIT = 100


@router.get("")
def search(
    q: str = Query("", description="검색어"),
    kind: Literal["job", "post"] = "job",
    limit: int = 20,
    include_closed: str = "0",
) -> dict:
    query = q.strip()[:MAX_QUERY_CHARS]
    if not query:
        raise BadRequest("q 파라미터가 필요하다")
    closed = include_closed not in ("0", "", "false")
    return service.search(query, kind=kind, limit=max(1, min(limit, MAX_LIMIT)), include_closed=closed)
