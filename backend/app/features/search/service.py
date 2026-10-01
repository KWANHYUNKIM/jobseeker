"""하이브리드 검색(FTS + pgvector). 응답 형식은 뷰어·외부 도구가 읽는 /api/search 그대로다."""
from __future__ import annotations

from app.features.search import repository
from app.features.search.embedding import embed_query


def search(query: str, *, kind: str = "job", limit: int = 20, include_closed: bool = False) -> dict:
    if kind == "post":
        rows = repository.search_posts(query, limit)
    else:
        rows = repository.search_jobs(query, limit, include_closed, embed_query(query))

    results = [{
        "id": str(r["id"]),
        "url": r["url"],
        "site": r["site"],
        "company": r["company"] or "",
        "title": r["title"],
        "career": r["career"] or "",
        "location": r["location"] or "",
        "tech_stack": list(r["tech_stack"] or []),
        "score": round(float(r["rrf"]), 6),
        # 이 결과가 어느 쪽에서 왔는지 — 가중치를 조정할 때 근거가 된다.
        "rank_fts": r["fts_rank"],
        "rank_vec": r["vec_rank"],
    } for r in rows]

    return {
        "query": query,
        "kind": kind,
        "total": len(results),
        "engines": {
            "fts": sum(1 for r in results if r["rank_fts"] is not None) or len(results),
            "vector": sum(1 for r in results if r["rank_vec"] is not None),
        },
        "results": results,
    }
