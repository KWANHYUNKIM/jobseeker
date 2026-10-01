"""유사 공고·글 top-K — 파이프라인(store/vectors/similar.py)이 job_similar·post_similar 에 굳혀 둔다.

추천 대상은 **지금 모집중인 공고만** 남긴다 — 표는 계산 시점의 것이지만 상태는
job_state 가 읽는 순간 계산하므로, 그 사이 닫힌 공고가 추천에 남지 않는다.
"""
from __future__ import annotations

from app.db.session import fetch_all

_JOBS = """
    SELECT t.url, COALESCE(co.display_name, '') AS company, t.title, s.score
      FROM job src
      JOIN job_similar s  ON s.job_id = src.id
      JOIN job t          ON t.id = s.similar_id
      JOIN job_state st   ON st.job_id = t.id AND st.status = 'active'
      LEFT JOIN company co ON co.id = t.company_id
     WHERE src.url = %(url)s
     ORDER BY s.rank
     LIMIT %(n)s
"""

_POSTS = """
    SELECT t.url, COALESCE(co.display_name, t.blog_name) AS company, t.title, s.score
      FROM post src
      JOIN post_similar s ON s.post_id = src.id
      JOIN post t         ON t.id = s.similar_id
      LEFT JOIN company co ON co.id = t.company_id
     WHERE src.url = %(url)s
     ORDER BY s.rank
     LIMIT %(n)s
"""


def similar(kind: str, url: str, n: int) -> list[dict]:
    return fetch_all(_POSTS if kind == "post" else _JOBS, {"url": url, "n": n})
