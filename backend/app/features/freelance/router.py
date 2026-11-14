"""외주 API.

    GET /api/freelance                         프로젝트 전량 + 추이·단가 분석(freelance.json 과 같은 모양)
    GET /api/freelance/projects/{site}/{pid}   한 건 + 상세 본문(project_body) — 뷰어 /freelance/<site>-<pid>
"""
from __future__ import annotations

from fastapi import APIRouter

from app.features.freelance import service

router = APIRouter(prefix="/api/freelance", tags=["freelance"])


@router.get("")
def freelance() -> dict:
    return service.freelance()


@router.get("/projects/{site}/{pid}")
def project(site: str, pid: str) -> dict:
    return service.project(site, pid)
