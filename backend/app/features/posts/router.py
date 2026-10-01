"""기술블로그 API.

    GET /api/posts     글 목록 + 출처·주제(tech_blogs.json 과 같은 모양)
"""
from __future__ import annotations

from fastapi import APIRouter

from app.features.posts import service

router = APIRouter(prefix="/api/posts", tags=["posts"])


@router.get("")
def posts() -> dict:
    return service.blog()
