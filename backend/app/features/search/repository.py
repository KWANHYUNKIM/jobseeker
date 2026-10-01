"""하이브리드 검색 SQL — FTS + pgvector 를 DB 함수 `search_jobs()` 가 RRF 로 합친다."""
from __future__ import annotations

from app.db.session import fetch_all

_JOB_HYBRID = """
    SELECT s.job_id AS id, s.rrf, s.fts_rank, s.vec_rank,
           v.url, v.site, v.company, v.title,
           v.career_text AS career, v.location_text AS location, v.tech_stack
      FROM search_jobs(%(q)s, %(emb)s, %(n)s, %(closed)s) s
      JOIN v_job v ON v.id = s.job_id
     ORDER BY s.rrf DESC
"""

# Ollama 가 없을 때의 길. 벡터 없이 FTS 만으로 답한다.
_JOB_FTS_ONLY = """
    SELECT v.id, ts_rank_cd(j.search_tsv, websearch_to_tsquery('simple', %(q)s)) AS rrf,
           NULL::integer AS fts_rank, NULL::integer AS vec_rank,
           v.url, v.site, v.company, v.title,
           v.career_text AS career, v.location_text AS location, v.tech_stack
      FROM job j
      JOIN v_job v ON v.id = j.id
     WHERE (%(closed)s OR v.status = 'active')
       AND j.search_tsv @@ websearch_to_tsquery('simple', %(q)s)
     ORDER BY 2 DESC LIMIT %(n)s
"""

_POST_FTS = """
    SELECT p.id, ts_rank_cd(p.search_tsv, websearch_to_tsquery('simple', %(q)s)) AS rrf,
           NULL::integer AS fts_rank, NULL::integer AS vec_rank,
           p.url, 'post' AS site, COALESCE(c.display_name, p.blog_name) AS company,
           p.title, '' AS career, '' AS location, '{}'::text[] AS tech_stack
      FROM post p LEFT JOIN company c ON c.id = p.company_id
     WHERE p.search_tsv @@ websearch_to_tsquery('simple', %(q)s)
     ORDER BY 2 DESC LIMIT %(n)s
"""


def search_jobs(q: str, n: int, include_closed: bool, embedding: list[float] | None) -> list[dict]:
    params = {"q": q, "n": n, "closed": include_closed}
    if embedding is None:
        return fetch_all(_JOB_FTS_ONLY, params)
    return fetch_all(_JOB_HYBRID, {**params, "emb": str(embedding)})


def search_posts(q: str, n: int) -> list[dict]:
    return fetch_all(_POST_FTS, {"q": q, "n": n})
