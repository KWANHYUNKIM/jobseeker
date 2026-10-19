"""메인 화면 API.

    GET /api/home                      회사 카드(규모 칩 건수 포함) + 로고 띠 + 구역(TOP 50 의 앞 10건)
        ?size=대기업&industry=금융&sort=popular|new|count&limit=48&offset=0
    GET /api/home/company/{slug}       회사 하나의 모집중 IT 공고 — 오른쪽 패널
    GET /api/home/section/{key}        구역 하나의 TOP 50(신입·경력·오늘 뜬·인턴·업종…) — 더보기

모집중인 IT 공고만 센다(직군이 '기타' 뿐인 공고 제외). 해외 근무 위주 회사는 규모 대신 '해외 기업'.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Path, Query

from app.features.home import service
from app.features.home.industry import INDUSTRIES

router = APIRouter(prefix="/api/home", tags=["home"])

# 받는 값은 전부 허용 목록으로 좁힌다 — 밖에 열린 API 라, 모르는 값은 계산까지 가기 전에 422 로 돌려보낸다.
Size = Literal["", "대기업", "중견기업", "중소기업", "해외 기업"]
Sort = Literal["popular", "new", "count"]
Industry = Literal[("",) + INDUSTRIES]  # type: ignore[valid-type]
SLUG = r"^[a-z0-9][a-z0-9-]{0,79}$"                       # store/db/slug.py 가 만드는 ASCII 슬러그
SECTION = r"^(entry|experienced|today|intern|midsmall|overseas|ind:[^/]{1,20})$"


@router.get("")
def home(size: Size = "", industry: Industry = "", sort: Sort = "popular",
         limit: int = Query(48, ge=1, le=200), offset: int = Query(0, ge=0, le=5000)) -> dict:
    return service.home(size=size, industry=industry, sort=sort, limit=limit, offset=offset)


@router.get("/company/{slug}")
def company(slug: str = Path(pattern=SLUG)) -> dict:
    return service.company(slug)


@router.get("/section/{key}")
def section(key: str = Path(pattern=SECTION)) -> dict:
    return service.section(key)
