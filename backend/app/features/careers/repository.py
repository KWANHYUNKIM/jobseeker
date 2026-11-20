"""커리어 후기 — career_post·career_story·career_roster(019, 파이프라인 store/ingest/careers.py 가 쓴다)."""
from __future__ import annotations

from app.db.session import fetch_all, fetch_one

_STORY_COLS = """s.post_id AS id, s.kind, s.year, s.period, s.company, s.company_key, s.program, s.company_type,
                 s.company_size, s.role, s.level, s.years_before::float AS years_before, s.transition, s.transition_cat,
                 s.origin, s.education, s.age, s.data,
                 p.source, p.url, p.title, p.posted_on"""


def stories() -> list[dict]:
    """집계에 넣는 경험담 전부(본문 없이). 4천여 건이라 한 번에 읽고 서비스가 자른다."""
    return fetch_all(f"SELECT {_STORY_COLS} FROM career_story s JOIN career_post p ON p.id = s.post_id "
                     "WHERE s.counted ORDER BY s.year DESC NULLS LAST, p.posted_on DESC NULLS LAST, s.post_id")


def story(post_id: str) -> dict | None:
    return fetch_one(f"SELECT {_STORY_COLS}, p.body, p.tags, p.collected_at FROM career_story s "
                     "JOIN career_post p ON p.id = s.post_id WHERE s.post_id = %s", (post_id,))


def counts() -> dict:
    return fetch_one("SELECT (SELECT count(*) FROM career_post) AS posts, "
                     "(SELECT count(*) FROM career_story WHERE is_story) AS stories, "
                     "(SELECT count(*) FROM career_story WHERE counted) AS counted, "
                     "(SELECT max(updated_at) FROM career_story) AS updated_at") or {}


def roster() -> list[dict]:
    return fetch_all("SELECT post, url, tag, posted_on, poster, list_kind, it, rows FROM career_roster "
                     "ORDER BY posted_on DESC NULLS LAST")
