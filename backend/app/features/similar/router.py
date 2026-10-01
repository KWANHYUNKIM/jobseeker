"""유사 문서 API.

    GET /api/similar?url=<공고·글 원문 URL>&kind=job|post

뷰어의 공고 상세·글 상세가 "비슷한 공고/관련 글" 을 그린다. 예전에는 similar_jobs.json
(4MB)을 통째로 받아 브라우저에서 찾았다.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.features.similar import service

router = APIRouter(prefix="/api/similar", tags=["similar"])


@router.get("")
def similar(
    url: str = Query(..., description="원문 URL"),
    kind: Literal["job", "post"] = "job",
    limit: int = Query(5, ge=1, le=20),
) -> dict:
    return service.similar(kind, url, limit)
