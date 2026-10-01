"""공고 API 경로.

    GET /api/jobs?region=서울&role=백엔드&closed=hide&page=1   목록 + 칩 건수
    GET /api/jobs/{site}-{pid}                                 공고 한 건(본문 포함)
    GET /api/jobs/lookup?url=...                               url → 주소 키
    GET /api/jobs/all                                          전량(파일 내보내기와 같은 모양, ETag)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse, Response

from app.features.jobs import service
from app.features.jobs.schemas import JobsQuery, jobs_query

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(q: JobsQuery = Depends(jobs_query)) -> dict:
    return service.list_jobs(q)


@router.get("/all")
def all_jobs(if_none_match: str | None = Header(None)) -> Response:
    """공고 전량 — 전량을 메모리에 올려 검색·통계를 내는 쪽(agent-mcp·admin)용.

    크다(본문 포함 수십 MB, gzip 으로 줄어든다). 그래서 ETag 를 붙인다 — 바뀐 게 없으면 304 로
    끝나고 DB 를 훑지도 않는다. 뷰어 화면은 이걸 쓰지 않는다(쪽 단위 /api/jobs).
    """
    etag = f'"{service.fingerprint()}"'
    if if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(service.all_jobs(), headers={"ETag": etag})


@router.get("/lookup")
def lookup(url: str = Query(..., description="공고 원문 URL")) -> dict:
    """추천 목록은 url 만 들고 있다 — 그 공고의 주소 키를 돌려준다."""
    return service.lookup(url)


@router.get("/{key}")
def get_job(key: str) -> dict:
    """공고 한 건(본문 포함). key 는 뷰어 주소의 `/jobs/<사이트>-<번호>` 그 부분이다."""
    return service.get_job(key)
