"""기술블로그 글 — post 표(크롤 단계의 store/ingest/posts.py 가 회차마다 넣는다)."""
from __future__ import annotations

from app.db.docs import get_doc
from app.db.session import fetch_all

_POSTS = """
    SELECT p.url, p.content_id, p.blog_name, p.title, p.published_on, p.published_at,
           p.country, p.lang,
           p.summary, p.tags, p.tech_stack, p.categories
      FROM post p
     ORDER BY p.published_at DESC NULLS LAST, p.published_on DESC NULLS LAST, p.id
"""


def posts() -> list[dict]:
    return fetch_all(_POSTS)


def meta() -> dict | None:
    return get_doc("blog", "meta")
