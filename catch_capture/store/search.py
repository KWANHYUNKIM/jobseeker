"""하이브리드 검색 CLI — `semantic/search.py` 의 PostgreSQL 대응물.

FTS5 + sqlite-vec 를 파이썬에서 RRF 로 합치던 것이 DB 안의 `search_jobs()` 하나가
됐다. 파이썬이 하는 일은 질의문을 Ollama 로 임베딩해 넘기는 것뿐이다.

마감 공고 제외가 조인 조건이라(`JOIN job_state`) 색인에 복사해 둔 상태값이 필요
없다. 지금까지는 ingest 시점의 status 사본을 봤기 때문에, 공고가 마감돼도 다음
ingest 전까지 검색 결과에 남았다.

사용:
    python -m store.search "재택 되는 백엔드"
    python -m store.search "임베디드 펌웨어" --include-closed -n 30
    python -m store.search "쿠팡" --no-vector      # Ollama 없이 FTS 만
"""
from __future__ import annotations

import argparse
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from store import conn as store_conn  # noqa: E402


def query_embedding(text: str) -> list[float] | None:
    """질의문 임베딩. Ollama 가 없으면 None — 그때는 FTS 만으로 답한다."""
    try:
        from store.embed import embed_batch
        return embed_batch([text])[0]
    except Exception as e:
        print(f"  (벡터 검색 건너뜀 — {e})", file=_sys.stderr)
        return None


_FTS_ONLY = """
    SELECT j.id AS job_id,
           ts_rank_cd(j.search_tsv, websearch_to_tsquery('simple', %(q)s)) AS rrf,
           NULL::integer AS fts_rank, NULL::integer AS vec_rank
      FROM job j JOIN job_state s ON s.job_id = j.id
     WHERE (%(include_closed)s OR s.status = 'active')
       AND j.search_tsv @@ websearch_to_tsquery('simple', %(q)s)
     ORDER BY 2 DESC LIMIT %(n)s
"""

_DETAIL = """
    SELECT v.job_key, v.company, v.title, v.site, v.status, v.status_source,
           v.dday, v.url, v.tech_stack, v.location_text
      FROM v_job v WHERE v.id = %s
"""


def search(q: str, n: int, include_closed: bool, use_vector: bool) -> list[dict]:
    vec = query_embedding(q) if use_vector else None
    with store_conn.cursor(autocommit=True) as cur:
        if vec is None:
            cur.execute(_FTS_ONLY, {"q": q, "n": n, "include_closed": include_closed})
        else:
            cur.execute(
                "SELECT * FROM search_jobs(%s, %s, %s, %s)",
                (q, str(vec), n, include_closed),
            )
        hits = cur.fetchall()
        out = []
        for h in hits:
            cur.execute(_DETAIL, (h["job_id"],))
            row = cur.fetchone()
            if row:
                out.append({**row, "rrf": h["rrf"],
                            "fts_rank": h.get("fts_rank"), "vec_rank": h.get("vec_rank")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="공고 하이브리드 검색")
    ap.add_argument("query")
    ap.add_argument("-n", type=int, default=10)
    ap.add_argument("--include-closed", action="store_true")
    ap.add_argument("--no-vector", action="store_true", help="FTS 만 (Ollama 불필요)")
    args = ap.parse_args()

    rows = search(args.query, args.n, args.include_closed, not args.no_vector)
    if not rows:
        print("결과 없음")
        return 0
    for i, r in enumerate(rows, 1):
        dday = f"D{r['dday']:+d}" if r["dday"] is not None else "마감일 모름"
        mark = "" if r["status"] == "active" else " [마감]"
        rank = f"fts#{r['fts_rank']}" if r.get("fts_rank") else ""
        rank += f" vec#{r['vec_rank']}" if r.get("vec_rank") else ""
        print(f"{i:>2}. {r['company']} — {r['title']}{mark}")
        print(f"    {r['site']}/{r['job_key']} · {r['location_text'] or '지역 미상'} · "
              f"{dday} ({r['status_source']}) · {rank.strip()}")
        if r["tech_stack"]:
            print(f"    {', '.join(r['tech_stack'][:8])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
