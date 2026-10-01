"""공고 API 경로.

    GET /api/jobs?region=서울&role=백엔드&closed=hide&page=1   목록 + 칩 건수
    GET /api/jobs/{site}-{pid}                                 공고 한 건(본문 포함)
    GET /api/jobs/lookup?url=...                               url → 주소 키
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.features.jobs import service
from app.features.jobs.schemas import JobsQuery, jobs_query

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(q: JobsQuery = Depends(jobs_query)) -> dict:
    return service.list_jobs(q)


@router.get("/lookup")
def lookup(url: str = Query(..., description="공고 원문 URL")) -> dict:
    """추천 목록은 url 만 들고 있다 — 그 공고의 주소 키를 돌려준다."""
    return service.lookup(url)


@router.get("/{key}")
def get_job(key: str) -> dict:
    """공고 한 건(본문 포함). key 는 뷰어 주소의 `/jobs/<사이트>-<번호>` 그 부분이다."""
    return service.get_job(key)
