"""건강 검사 — 데이터가 반쪽으로 비어 있으면 조용히 도는 대신 여기서 말한다."""
from __future__ import annotations

from app.db.session import fetch_one


def stats() -> dict:
    s = fetch_one("""
        SELECT (SELECT count(*) FROM job) AS jobs,
               (SELECT count(*) FROM job_state WHERE status='active') AS active,
               (SELECT count(*) FROM post) AS posts,
               (SELECT count(*) FROM job_embedding) AS job_vectors,
               (SELECT count(*) FROM job_embed_pending) AS job_pending,
               (SELECT count(*) FROM post_embedding) AS post_vectors,
               (SELECT count(*) FROM job_facet) AS job_facets
    """) or {}
    s = dict(s)
    # 벡터가 하나도 없으면 검색이 FTS 로만 돈다.
    s["vector_search"] = s.get("job_vectors", 0) > 0
    return s
