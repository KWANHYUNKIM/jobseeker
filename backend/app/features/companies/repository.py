"""회사 프로필 — 빌더(jd-viewer/bin/build_company_stacks.py)가 viewer_doc 에 쓴 것을 읽는다."""
from __future__ import annotations

from app.db.docs import get_doc
from app.db.session import fetch_all, fetch_one

# 목록에서 빼는 필드 — 회사 하나를 열 때만 쓴다. 15MB 중 대부분이 이 넷이다
# (career_guide 4.4MB · postings 1.1MB · architecture 0.35MB · summary·titles).
DETAIL_ONLY = ("career_guide", "postings", "architecture", "summary", "titles")


def index_meta() -> dict | None:
    return get_doc("company_index")


def list_summaries() -> list[dict]:
    drop = " - ".join(f"'{k}'" for k in DETAIL_ONLY)
    rows = fetch_all(f"""
        SELECT payload - {drop} AS c FROM viewer_doc
         WHERE kind = 'company'
         ORDER BY (payload->>'posting_count')::int DESC, key
    """)
    return [r["c"] for r in rows]


def find(norm: str) -> dict | None:
    r = fetch_one("SELECT payload FROM viewer_doc WHERE kind = 'company' AND key = %s", (norm,))
    return r["payload"] if r else None
