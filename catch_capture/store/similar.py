"""유사 공고 top-K — pgvector HNSW 로 계산해 `job_similar` 에 굳힌다.

`semantic/similar.py` 의 PostgreSQL 대응물. 규칙은 그대로다:
  - MIN_SCORE 아래는 "비슷하다"고 부르기 민망하니 자른다.
  - DUP_SCORE 위는 사실상 같은 공고(재게시·중복)라 추천 가치가 없다.
  - 한 회사가 추천을 도배하지 않게 MAX_PER_COMPANY 로 막는다.
  - **마감 공고는 추천하지 않는다.** 색인에는 남지만(지난 공고 통계의 재료)
    추천은 지금 지원할 수 있는 것만 의미가 있다. 지금까지는 meta JSON 에 복사해
    둔 status 를 봤지만 이제 job_state 조인이라 낡을 수가 없다.

계산 자체는 DB 안에서 끝난다. 만 건짜리 벡터를 파이썬으로 끌어올려 코사인을
돌리던 것이 8GB M1 에서 가장 무거운 단계였다.

사용:
    python -m store.similar                # job + post
    python -m store.similar --kind job
    python -m store.similar --dump         # 뷰어용 JSON 도 함께 쓴다
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys as _sys
import time
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from semantic.config import (  # noqa: E402
    DUP_SCORE, MAX_PER_COMPANY, MIN_SCORE, SIMILAR_JOBS_JSON, SIMILAR_POSTS_JSON, TOP_K,
)
from store import conn as store_conn  # noqa: E402

# 후보를 넉넉히 뽑아 놓고 마감 제외·회사 상한을 적용한 뒤 TOP_K 를 남긴다.
# 지금 데이터는 마감이 57%(9,664/17,067)라 40개를 뽑으면 살아남는 건 17개쯤이고,
# 거기서 회사 상한까지 걸면 TOP_K 5개가 안 채워질 수 있다. 60이면 여유가 있다.
CANDIDATES = 60

# hnsw.ef_search — 클수록 정확하고 느리다. 후보를 40개 뽑으려면 기본값(40)보다
# 넉넉해야 회사 필터를 거친 뒤에도 TOP_K 가 채워진다.
EF_SEARCH = 100

# ── 이 질의의 함정 ────────────────────────────────────────────────────
# 이웃을 찾는 LATERAL 안에서는 `job_embedding` 을 **직접** 읽어야 한다. 편하다고
# 벡터를 CTE(WITH pool AS ...)로 한 번 감싸면 Postgres 가 그 CTE 를 실체화하면서
# HNSW 인덱스가 사라지고, 17,067건 × 17,067건 완전탐색이 된다. 실측으로 그 차이는
# **1.7ms → 251초** 였다. 그래서 마감 필터·회사 상한은 전부 이웃을 뽑은 **뒤에**
# 건다. 마감 공고가 절반이 넘으므로 그만큼 넉넉히 뽑아 둔다(CANDIDATES).
_JOB_SQL = f"""
WITH active AS (
    SELECT job_id FROM job_state WHERE status = 'active'
),
cand AS (
    SELECT p.job_id, n.similar_id, jn.company_id, n.score
      FROM job_embedding p
      JOIN active ap ON ap.job_id = p.job_id
      CROSS JOIN LATERAL (
          -- 여기서 job_embedding 을 직접 읽는다 = HNSW 인덱스 스캔
          SELECT e.job_id AS similar_id,
                 1 - (e.embedding <=> p.embedding) AS score
            FROM job_embedding e
           WHERE e.job_id <> p.job_id
           ORDER BY e.embedding <=> p.embedding
           LIMIT {CANDIDATES}
      ) n
      JOIN active an ON an.job_id = n.similar_id
      JOIN job jn ON jn.id = n.similar_id
     WHERE n.score >= %(min_score)s AND n.score < %(dup_score)s
),
capped AS (
    SELECT *, row_number() OVER (
               PARTITION BY job_id, company_id ORDER BY score DESC
           ) AS per_company
      FROM cand
),
ranked AS (
    SELECT job_id, similar_id, score,
           row_number() OVER (PARTITION BY job_id ORDER BY score DESC) AS rank
      FROM capped WHERE per_company <= %(max_per_company)s
)
INSERT INTO job_similar (job_id, similar_id, rank, score)
SELECT job_id, similar_id, rank, score FROM ranked WHERE rank <= %(top_k)s
ON CONFLICT (job_id, similar_id) DO UPDATE
   SET rank = EXCLUDED.rank, score = EXCLUDED.score, computed_at = now()
"""

# 블로그 글에는 마감이 없어 필터가 없다. 그래도 CTE 로 감싸지 않는 규칙은 같다.
_POST_SQL = f"""
WITH cand AS (
    SELECT p.post_id, n.similar_id, n.score
      FROM post_embedding p
      CROSS JOIN LATERAL (
          SELECT e.post_id AS similar_id,
                 1 - (e.embedding <=> p.embedding) AS score
            FROM post_embedding e
           WHERE e.post_id <> p.post_id
           ORDER BY e.embedding <=> p.embedding
           LIMIT {CANDIDATES}
      ) n
     WHERE n.score >= %(min_score)s AND n.score < %(dup_score)s
),
ranked AS (
    SELECT post_id, similar_id, score,
           row_number() OVER (PARTITION BY post_id ORDER BY score DESC) AS rank
      FROM cand
)
INSERT INTO post_similar (post_id, similar_id, rank, score)
SELECT post_id, similar_id, rank, score FROM ranked WHERE rank <= %(top_k)s
ON CONFLICT (post_id, similar_id) DO UPDATE
   SET rank = EXCLUDED.rank, score = EXCLUDED.score, computed_at = now()
"""


def compute(kind: str) -> int:
    sql = _JOB_SQL if kind == "job" else _POST_SQL
    table = "job_similar" if kind == "job" else "post_similar"
    params = {
        "min_score": MIN_SCORE, "dup_score": DUP_SCORE,
        "max_per_company": MAX_PER_COMPANY, "top_k": TOP_K,
    }
    t0 = time.time()
    with store_conn.cursor() as cur:
        cur.execute(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}")
        # 계산 전에 비운다. 마감된 공고의 옛 추천이 남으면 화면이 죽은 링크를 보여준다.
        cur.execute(f"TRUNCATE {table}")
        cur.execute(sql, params)
        n = cur.rowcount
    print(f"  [{kind}] {n:,}쌍 · {time.time() - t0:.1f}초")
    return n


def _doc_id(url: str) -> str:
    """문서 id — semantic/ingest.doc_id 와 **같은 규칙이어야 한다**.

    뷰어(`src/lib/useSimilar.ts`)는 공고의 url 로 docs 를 뒤져 id 를 얻고, 그 id 로
    similar 를 찾는다. 여기서 id 규칙이 갈리면 추천이 통째로 빈다.
    """
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def dump_json(kind: str) -> None:
    """뷰어가 읽는 정적 JSON. 형식은 `useSimilar.ts` 의 SimilarFile 그대로다:

        docs    : 문서 id → {u: url, c: 회사, t: 제목}
        similar : 문서 id → [[대상 id, 점수], ...]

    `site-pid` 같은 다른 키를 쓰면 화면이 조용히 빈 추천을 보여준다(오류도 안 난다).
    """
    if kind == "job":
        sql = """
            SELECT j.url AS src_url, c.display_name AS src_company, j.title AS src_title,
                   k.url AS dst_url, d.display_name AS dst_company, k.title AS dst_title,
                   s.rank, s.score
              FROM job_similar s
              JOIN job j ON j.id = s.job_id
              JOIN company c ON c.id = j.company_id
              JOIN job k ON k.id = s.similar_id
              JOIN company d ON d.id = k.company_id
             ORDER BY j.id, s.rank
        """
        out = SIMILAR_JOBS_JSON
    else:
        sql = """
            SELECT p.url AS src_url, COALESCE(c.display_name, p.blog_name) AS src_company,
                   p.title AS src_title,
                   q.url AS dst_url, COALESCE(e.display_name, q.blog_name) AS dst_company,
                   q.title AS dst_title, s.rank, s.score
              FROM post_similar s
              JOIN post p ON p.id = s.post_id
              LEFT JOIN company c ON c.id = p.company_id
              JOIN post q ON q.id = s.similar_id
              LEFT JOIN company e ON e.id = q.company_id
             ORDER BY p.id, s.rank
        """
        out = SIMILAR_POSTS_JSON

    with store_conn.cursor(autocommit=True) as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    docs: dict[str, dict] = {}
    similar: dict[str, list] = {}
    for r in rows:
        sid, did = _doc_id(r["src_url"]), _doc_id(r["dst_url"])
        docs.setdefault(sid, {"u": r["src_url"], "c": r["src_company"] or "", "t": r["src_title"]})
        docs.setdefault(did, {"u": r["dst_url"], "c": r["dst_company"] or "", "t": r["dst_title"]})
        similar.setdefault(sid, []).append([did, round(float(r["score"]), 4)])

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": kind,
        "top_k": TOP_K,
        "docs": docs,
        "similar": similar,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out)
    print(f"  [{kind}] {out.name} ← 출발 {len(similar):,}개 · 문서 {len(docs):,}개")


def main() -> int:
    ap = argparse.ArgumentParser(description="유사 문서 top-K 계산")
    ap.add_argument("--kind", choices=["job", "post", "all"], default="all")
    ap.add_argument("--dump", action="store_true", help="뷰어용 JSON 도 쓴다")
    args = ap.parse_args()

    kinds = ["job", "post"] if args.kind == "all" else [args.kind]
    for k in kinds:
        compute(k)
        if args.dump:
            dump_json(k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
