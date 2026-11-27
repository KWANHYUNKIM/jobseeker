"""채용 추이 API.

    GET /api/hiring/momentum?weeks=12&size=대기업&sort=recent|growth|fast|active|seats&min_recent=3&limit=50
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.features.hiring import service

router = APIRouter(prefix="/api/hiring", tags=["hiring"])

Sort = Literal["recent", "growth", "fast", "active", "seats"]
Size = Literal["", "대기업", "중견기업", "중소기업", "해외 기업", "미분류"]


@router.get("/momentum")
def momentum(
    weeks: int = Query(12, ge=9, le=52, description="주 수(이번 주 포함). 최근 4주 대 그 전 4주를 비교하므로 9 이상"),
    size: Size = Query("", description="회사 규모"),
    sort: Sort = Query("recent", description="recent=최근 4주 공고 수 · growth=증가폭 · fast=빨리 닫힌 비율 · active=모집중 · seats=자리 수(최소)"),
    min_recent: int = Query(3, ge=0, le=100, description="최근 4주 새 공고가 이보다 적은 회사는 뺀다"),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    return service.momentum(weeks=weeks, size=size, sort=sort, min_recent=min_recent, limit=limit)
