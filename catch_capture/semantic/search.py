"""하이브리드 검색 — FTS5(키워드) + 벡터(의미)를 RRF 로 합친다.

둘은 서로 다른 것을 잡는다. FTS5 는 "비바리퍼블리카", "쿠버네티스" 같은 고유명사를
정확히 집어내지만 "재택 되는 백엔드 자리"처럼 표현이 다른 질의에는 무력하다.
벡터는 그 반대다 — 의미는 잡지만 특정 회사명 하나를 정확히 찾아내지는 못한다.

두 결과를 RRF(Reciprocal Rank Fusion)로 합친다. 점수 스케일이 전혀 다른
bm25(음수, 작을수록 좋음)와 코사인 거리를 정규화 없이 섞을 수 있는 게 RRF 의 장점이다:
        score(d) = Σ  weight / (RRF_K + rank(d))
순위만 쓰기 때문에 한쪽 점수 분포가 바뀌어도 융합이 망가지지 않는다.

한국어는 교착어라 unicode61 토크나이저가 "재택근무를" 을 통째로 한 토큰으로 만든다.
그래서 질의 토큰마다 prefix(*)를 붙인다 — "재택" 이 "재택근무"·"재택가능" 을 잡는다.
그래도 중간 매칭("근무"→"재택근무")은 안 되는데, 그 자리는 벡터가 메운다.

사용법:
    python -m semantic.search "재택 가능한 백엔드"
    python -m semantic.search "쿠버네티스" --career 5-7년 --limit 10
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Sequence

import sqlite_vec

from . import db as dbm
from .config import TOP_K

# RRF 상수. 60 은 원 논문(Cormack et al.)이 쓴 값으로, 상위권 순위차를 지나치게
# 벌리지 않으면서 하위권 꼬리를 눌러준다.
RRF_K = 60

# 각 검색기에서 뽑는 후보 수. 융합·필터로 걸러지므로 최종 limit 보다 넉넉해야 한다.
CANDIDATES = 150

# 키워드/벡터 가중치. 기본은 대등하게 둔다.
W_FTS = 1.0
W_VEC = 1.0

# FTS5 질의 문법에서 의미를 갖는 문자들. 사용자가 친 그대로 넘기면 구문 오류가 난다.
_FTS_UNSAFE = re.compile(r'["\'()*:^{}\[\]\-+~]')
_TOKEN_SPLIT = re.compile(r"\s+")

CAREER_BUCKETS = ("신입/무관", "1-2년", "3-4년", "5-7년", "8년+", "정보없음")


def career_bucket(career: str) -> str:
    """뷰어 lib/career.ts 의 careerBucket 과 같은 규칙.

    검색 결과의 경력 필터가 목록 화면의 필터와 다르게 동작하면 사용자는 그걸
    버그로 받아들인다. 규칙을 한 곳에서 바꾸긴 어렵지만 최소한 같게는 맞춰둔다.
    """
    if not career:
        return "정보없음"
    if re.search(r"신입|무관", career):
        return "신입/무관"
    m = re.search(r"(\d+)", career)
    if not m:
        return "정보없음"
    n = int(m.group(1))
    if n <= 2:
        return "1-2년"
    if n <= 4:
        return "3-4년"
    if n <= 7:
        return "5-7년"
    return "8년+"


def query_tokens(query: str) -> list[str]:
    """자유 입력을 FTS5 에 넣어도 안전한 prefix 토큰들로."""
    tokens = [t for t in _TOKEN_SPLIT.split(_FTS_UNSAFE.sub(" ", query)) if t]
    # 인용 안에서 " 는 "" 로 이스케이프한다(위에서 제거하지만 방어적으로 남긴다).
    return [f'"{t.replace(chr(34), chr(34) * 2)}"*' for t in tokens]


def build_match(query: str, op: str = "AND") -> str:
    tokens = query_tokens(query)
    return f" {op} ".join(tokens) if tokens else ""


def _fts_rows(conn, match: str, kind: str, limit: int) -> list[int]:
    rows = conn.execute(
        """
        SELECT f.rowid AS rid
          FROM fts_documents f
          JOIN documents d ON d.rowid = f.rowid
         WHERE fts_documents MATCH ? AND d.kind = ?
         ORDER BY bm25(fts_documents, 4.0, 2.0, 1.0)
         LIMIT ?
        """,
        (match, kind, limit),
    ).fetchall()
    return [r["rid"] for r in rows]


def keyword_search(conn, query: str, kind: str, limit: int = CANDIDATES) -> list[int]:
    """FTS5 bm25 순으로 rowid 목록. 매칭이 없으면 빈 리스트.

    AND 로 먼저 치고, 결과가 없을 때만 OR 로 물러난다. 자연어 질의("재택 되는 백엔드
    자리")는 모든 토큰을 가진 문서가 사실상 없어서 AND 만 쓰면 키워드 쪽이 통째로
    죽는다 — 하이브리드의 절반을 잃는 셈이다. 반대로 처음부터 OR 로 가면
    "비바리퍼블리카" 같은 고유명사 질의에 관련 없는 문서가 섞인다. 그래서 순서를 둔다.
    """
    if not (tokens := query_tokens(query)):
        return []
    hits = _fts_rows(conn, " AND ".join(tokens), kind, limit)
    if not hits and len(tokens) > 1:
        hits = _fts_rows(conn, " OR ".join(tokens), kind, limit)
    return hits


def vector_search(conn, query: str, kind: str, limit: int = CANDIDATES) -> list[int]:
    """질의를 임베딩해 코사인 최근접 rowid 목록. 임베딩이 불가하면 빈 리스트."""
    from . import embed as sembed

    try:
        vec = sembed.embed_texts([query])[0]
    except sembed.EmbedError:
        # Ollama 가 죽어 있어도 키워드 검색만으로 답을 준다. 검색 전체가 죽는 것보다 낫다.
        return []
    rows = conn.execute(
        """
        SELECT rowid AS rid
          FROM vec_documents
         WHERE embedding MATCH ? AND kind = ? AND k = ?
         ORDER BY distance
        """,
        (sqlite_vec.serialize_float32(vec), kind, limit),
    ).fetchall()
    return [r["rid"] for r in rows]


def rrf(rankings: Sequence[tuple[Sequence[int], float]], k: int = RRF_K) -> dict[int, float]:
    """(순위목록, 가중치) 들을 RRF 로 합쳐 rowid → 점수."""
    scores: dict[int, float] = {}
    for ids, weight in rankings:
        for rank, rid in enumerate(ids, start=1):
            scores[rid] = scores.get(rid, 0.0) + weight / (k + rank)
    return scores


def _passes(row, filters: dict[str, Any]) -> bool:
    meta = json.loads(row["meta"] or "{}")
    # 마감 공고는 색인에 남겨두되(지난 공고 기반 통계·유사도의 재료) 결과에서는 뺀다.
    # 지원할 수 없는 공고가 상위에 앉아 있는 것만큼 검색을 못 믿게 만드는 것도 없다.
    # status 가 없는 문서는 이 필드가 생기기 전 색인이므로 통과시킨다.
    if not filters.get("include_closed") and meta.get("status") == "closed":
        return False
    if (sites := filters.get("sites")) and row["site"] not in sites:
        return False
    if (careers := filters.get("careers")) and career_bucket(meta.get("career", "")) not in careers:
        return False
    if loc := filters.get("location"):
        if loc not in (meta.get("location") or ""):
            return False
    if (stacks := filters.get("stacks")):
        have = {s.lower() for s in meta.get("tech_stack") or []}
        if not have.issuperset({s.lower() for s in stacks}):
            return False
    if (overseas := filters.get("overseas")) is not None:
        if bool(meta.get("overseas")) is not overseas:
            return False
    return True


def search(conn, query: str, *, kind: str = "job", limit: int = TOP_K * 4,
           filters: dict[str, Any] | None = None,
           candidates: int = CANDIDATES,
           w_fts: float = W_FTS, w_vec: float = W_VEC) -> dict:
    """하이브리드 검색. 각 검색기의 기여를 결과에 남겨 튜닝할 수 있게 한다."""
    query = (query or "").strip()
    if not query:
        return {"query": query, "total": 0, "results": []}

    fts_ids = keyword_search(conn, query, kind, candidates)
    vec_ids = vector_search(conn, query, kind, candidates)
    fused = rrf([(fts_ids, w_fts), (vec_ids, w_vec)])
    if not fused:
        return {"query": query, "total": 0, "results": [],
                "engines": {"fts": 0, "vector": 0}}

    fts_rank = {rid: i for i, rid in enumerate(fts_ids, start=1)}
    vec_rank = {rid: i for i, rid in enumerate(vec_ids, start=1)}

    order = sorted(fused, key=lambda r: -fused[r])
    placeholders = ",".join("?" * len(order))
    rows = {
        r["rowid"]: r
        for r in conn.execute(
            f"SELECT rowid, id, url, site, company, title, meta FROM documents "
            f"WHERE rowid IN ({placeholders})",
            order,
        ).fetchall()
    }

    filters = filters or {}
    results = []
    for rid in order:
        row = rows.get(rid)
        if row is None or not _passes(row, filters):
            continue
        meta = json.loads(row["meta"] or "{}")
        results.append({
            "id": row["id"],
            "url": row["url"],
            "site": row["site"],
            "company": row["company"],
            "title": row["title"],
            "career": meta.get("career", ""),
            "location": meta.get("location", ""),
            "tech_stack": meta.get("tech_stack") or [],
            "score": round(fused[rid], 6),
            # 이 결과가 어느 쪽에서 왔는지 — 가중치를 조정할 때 근거가 된다.
            "rank_fts": fts_rank.get(rid),
            "rank_vec": vec_rank.get(rid),
        })
        if len(results) >= limit:
            break

    return {
        "query": query,
        "kind": kind,
        "total": len(results),
        "engines": {"fts": len(fts_ids), "vector": len(vec_ids)},
        "results": results,
    }


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    query = argv[0]
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 10
    kind = argv[argv.index("--kind") + 1] if "--kind" in argv else "job"
    filters: dict[str, Any] = {}
    if "--career" in argv:
        filters["careers"] = {argv[argv.index("--career") + 1]}
    if "--location" in argv:
        filters["location"] = argv[argv.index("--location") + 1]
    if "--include-closed" in argv:
        filters["include_closed"] = True

    conn = dbm.open_db()
    try:
        out = search(conn, query, kind=kind, limit=limit, filters=filters)
    finally:
        conn.close()

    eng = out.get("engines", {})
    print(f"'{out['query']}' → {out['total']}건 "
          f"(FTS 후보 {eng.get('fts', 0)}, 벡터 후보 {eng.get('vector', 0)})\n")
    for i, r in enumerate(out["results"], start=1):
        src = f"F{r['rank_fts'] or '-'}/V{r['rank_vec'] or '-'}"
        print(f"{i:2}. [{src:>9}] {r['title'][:56]}")
        print(f"     {r['company']} · {r['career']} · {r['location']}")
    return 0


if __name__ == "__main__":  # python -m semantic.search "질의"
    sys.exit(main(sys.argv[1:]))
