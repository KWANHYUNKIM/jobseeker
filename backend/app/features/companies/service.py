from __future__ import annotations

from app.core.exceptions import NotFound
from app.features.companies import repository
from app.utils.cache import cached


def list_companies() -> dict:
    """company_stacks.json 과 같은 모양 — 단 회사마다 목록에 필요한 필드만."""
    def load() -> dict:
        meta = repository.index_meta()
        if not meta:
            raise NotFound("회사 프로필이 아직 없다(build_company_stacks.py 가 DB 에 쓰기 전)")
        return {**meta["payload"], "detail_fields": list(repository.DETAIL_ONLY),
                "companies": repository.list_summaries()}
    return cached(("companies",), load)


def get_company(norm: str) -> dict:
    c = cached(("company", norm), lambda: repository.find(norm))
    if not c:
        raise NotFound(f"회사 {norm} 을(를) 찾지 못했습니다")
    return c
