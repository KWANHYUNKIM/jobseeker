"""회사 API.

    GET /api/companies          목록(회사마다 요약 필드만 — 상세 필드 이름은 detail_fields)
    GET /api/companies/{norm}   회사 하나의 전체 프로필(CompanyStack)

키는 회사 이름(norm)이다. 주소 슬러그는 뷰어가 목록 전체의 norm 으로 만든다
(`src/utils/companySlug.js` — 같은 이름이 겹치면 번호가 붙어 목록을 봐야 정해진다).
"""
from __future__ import annotations

from fastapi import APIRouter

from app.features.companies import service

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("")
def list_companies() -> dict:
    return service.list_companies()


@router.get("/{norm}")
def get_company(norm: str) -> dict:
    return service.get_company(norm)
