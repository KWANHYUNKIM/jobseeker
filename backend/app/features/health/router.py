from __future__ import annotations

from fastapi import APIRouter

from app.features.health import service

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    # DB 에 못 붙으면 core.exceptions 가 503 으로 바꾼다 — 뷰어는 그걸 보고 파일로 물러선다.
    return {"ok": True, "stats": service.stats()}
