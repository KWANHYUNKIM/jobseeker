"""회사 사실 API — 공고 상세의 연봉·복지 태그·위치·연차별 시세.

    GET /api/company-facts?name=<회사명>   회사 하나(뷰어 RolePayBenefits·RoleLocation 이 그리는 모양) — 없으면 404
    GET /api/market-wage                   직종 × 경력년수, 규모 × 연령(대졸) 연봉 — 최신 해
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.features.company_facts import service

router = APIRouter(prefix="/api", tags=["company-facts"])


@router.get("/company-facts")
def company_facts(name: str = Query(..., min_length=1, max_length=200)) -> dict:
    return service.company(name)


@router.get("/market-wage")
def market_wage() -> dict:
    return service.market_wage()
