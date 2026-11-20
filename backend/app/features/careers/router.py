"""커리어 후기 API — 뷰어 기술도서 › 취업(`/wiki/careers`).

    GET /api/careers                    연도·회사 유형·스펙·이직·경로 집계 (?year=&company=&type=&level=&kind=&role=&origin=&q=)
    GET /api/careers/stories            경험담 목록(같은 거르기, &offset=&limit=)
    GET /api/careers/stories/{id}       한 건 — 구조화한 값 전부 + 원문(X-Careers-Key 가 맞을 때만)
    GET /api/careers/roster             인스타 '합격자 명단'(이름 없음) — 합격처별 학교·전공
"""
from __future__ import annotations

from fastapi import APIRouter, Header, Query

from app.features.careers import service

router = APIRouter(prefix="/api/careers", tags=["careers"])


def _f(year, company, type_, level, kind, role, origin, q) -> dict:
    return {"year": year, "company": company, "type": type_, "level": level, "kind": kind, "role": role,
            "origin": origin, "q": (q or "").strip() or None}


@router.get("")
def overview(year: int | None = None, company: str | None = None, type: str | None = None,  # noqa: A002
             level: str | None = None, kind: str | None = None, role: str | None = None,
             origin: str | None = None, q: str | None = None) -> dict:
    return service.overview(_f(year, company, type, level, kind, role, origin, q))


@router.get("/stories")
def stories(year: int | None = None, company: str | None = None, type: str | None = None,  # noqa: A002
            level: str | None = None, kind: str | None = None, role: str | None = None,
            origin: str | None = None, q: str | None = None,
            offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)) -> dict:
    return service.stories(_f(year, company, type, level, kind, role, origin, q), offset, limit)


@router.get("/roster")
def roster() -> dict:
    return service.roster()


@router.get("/stories/{post_id}")
def story(post_id: str, x_careers_key: str | None = Header(None)) -> dict:
    return service.story(post_id, x_careers_key)
