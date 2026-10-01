"""하드웨어 API.

    GET /api/hardware/prices    부품별 오늘 최저가·매물·가격 이력(prices.json 과 같은 모양)

부품·성능·스펙(parts·index·bench·models)은 조사 엔진이 손으로 쓰는 문서라 정적 파일로 둔다.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.features.hardware import service

router = APIRouter(prefix="/api/hardware", tags=["hardware"])


@router.get("/prices")
def prices() -> dict:
    return service.prices()
