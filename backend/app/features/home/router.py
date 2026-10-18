"""메인 화면 API.

    GET /api/home                      회사 카드(규모 칩 건수 포함) + 로고 띠 + 구역(TOP 50 의 앞 10건)
        ?size=대기업&industry=금융&sort=popular|new|count&limit=48&offset=0
    GET /api/home/company/{slug}       회사 하나의 모집중 IT 공고 — 오른쪽 패널
    GET /api/home/section/{key}        구역 하나의 TOP 50(신입·경력·오늘 뜬·인턴·업종…) — 더보기

모집중인 IT 공고만 센다(직군이 '기타' 뿐인 공고 제외). 해외 근무 위주 회사는 규모 대신 '해외 기업'.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.features.home import service

router = APIRouter(prefix="/api/home", tags=["home"])


@router.get("")
def home(size: str = "", industry: str = "", sort: str = "popular",
         limit: int = Query(48, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict:
    return service.home(size=size, industry=industry, sort=sort, limit=limit, offset=offset)


@router.get("/company/{slug}")
def company(slug: str) -> dict:
    return service.company(slug)


@router.get("/section/{key}")
def section(key: str) -> dict:
    return service.section(key)
