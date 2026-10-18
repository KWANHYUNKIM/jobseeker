"""메인 화면 API.

    GET /api/home                      회사 카드(규모·업종 칩 건수 포함) + 신입·경력 구간별 공고
        ?size=대기업&industry=금융&sort=popular|new|count&limit=48&offset=0
    GET /api/home/company/{slug}       회사 하나의 모집중 IT 공고 — 오른쪽 패널

모집중인 국내 IT 공고만 센다(직군이 '기타' 뿐인 공고·해외 공고 제외).
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
