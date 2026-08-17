"""코사인 유사도 top-K 사전계산 → 뷰어가 정적으로 읽는 JSON.

뷰어에 벡터 검색 서버를 붙이지 않는다. 공고 1만 건 규모에서 "비슷한 공고 5개"는
크롤 사이클마다 한 번 계산해 JSON 으로 떨궈두면 충분하고, 그러면 뷰어는 기존
public/*.json 소비 방식을 그대로 유지한다.

임베딩이 L2 정규화되어 있으므로 유사도는 내적 하나로 끝난다. 1만×1024 행렬의
전량 비교는 청크로 나눠 numpy 에 맡긴다(M1 에서 수 초).

추천 품질을 위해 세 가지를 거른다:
  - DUP_SCORE 이상: 사실상 같은 공고(같은 자리 재게시·사이트 간 중복)
  - MIN_SCORE 미만: "비슷하다"고 부르기 민망한 것
  - MAX_PER_COMPANY 초과: 한 회사 공고로 목록이 도배되는 것

사용법:
    python -m semantic.similar              # 공고+블로그 전부
    python -m semantic.similar --kind job   # 공고만
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# 회사 편중 제한은 표기 흔들림("칸코드"/"(주)칸코드", "삼성화재해상보험"/"…(주)")에
# 그대로 뚫린다. 대시보드가 쓰는 정규화를 재사용해 같은 회사를 같은 키로 묶는다.
from dashboard.classifier import _norm_company

from . import db as dbm
from .config import (
    DUP_SCORE,
    MAX_PER_COMPANY,
    MIN_SCORE,
    SIMILAR_JOBS_JSON,
    SIMILAR_POSTS_JSON,
    TOP_K,
)

# 한 번에 비교할 질의 행 수. 1024차원 × 2000행 × 전체(1만) = 약 160MB 로 M1 에서 안전하다.
CHUNK = 2000

OUT_PATHS = {"job": SIMILAR_JOBS_JSON, "post": SIMILAR_POSTS_JSON}


def load_vectors(conn, kind: str) -> tuple[list[dict], np.ndarray]:
    """kind 의 문서 메타와 벡터 행렬을 같은 순서로 돌려준다."""
    rows = conn.execute(
        """
        SELECT d.id, d.url, d.company, d.title, v.embedding
          FROM documents d
          JOIN vec_documents v ON v.rowid = d.rowid
         WHERE d.kind = ?
           AND d.embedded_hash IS NOT NULL
         ORDER BY d.rowid
        """,
        (kind,),
    ).fetchall()
    if not rows:
        return [], np.empty((0, 0), dtype=np.float32)
    meta = [
        {
            "id": r["id"],
            "url": r["url"],
            "company": (r["company"] or "").strip(),
            "title": (r["title"] or "").strip(),
        }
        for r in rows
    ]
    mat = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
    return meta, mat


def _pick(order: np.ndarray, scores: np.ndarray, self_pos: int,
          companies: list[str], top_k: int) -> list[tuple[int, float]]:
    """정렬된 후보에서 조건을 만족하는 top_k 를 고른다."""
    out: list[tuple[int, float]] = []
    per_company: dict[str, int] = {}
    for j in order:
        j = int(j)
        if j == self_pos:
            continue
        s = float(scores[j])
        if s < MIN_SCORE:
            break  # 내림차순이라 이 뒤는 볼 필요 없다
        if s >= DUP_SCORE:
            continue  # 사실상 동일 공고
        comp = companies[j]
        if comp:
            n = per_company.get(comp, 0)
            if n >= MAX_PER_COMPANY:
                continue
            per_company[comp] = n + 1
        out.append((j, round(s, 4)))
        if len(out) >= top_k:
            break
    return out


def compute(meta: list[dict], mat: np.ndarray, top_k: int = TOP_K) -> dict[str, list]:
    """문서별 top-K 를 {id: [[대상id, 점수], ...]} 로."""
    if not meta:
        return {}
    companies = [_norm_company(m["company"]) for m in meta]
    ids = [m["id"] for m in meta]
    n = len(meta)
    # 필터로 후보가 잘려나가므로 top_k 보다 넉넉히 확보해 둔다.
    cand = min(n, max(top_k * 6, top_k + MAX_PER_COMPANY * 4 + 10))
    result: dict[str, list] = {}

    for start in range(0, n, CHUNK):
        block = mat[start:start + CHUNK]
        sims = block @ mat.T  # 정규화된 벡터라 내적 = 코사인 유사도
        # 상위 cand 개만 부분정렬로 추린 뒤 그 안에서만 정렬한다(전량 정렬보다 훨씬 싸다).
        part = np.argpartition(-sims, kth=cand - 1, axis=1)[:, :cand]
        for i in range(block.shape[0]):
            gi = start + i
            row = sims[i]
            order = part[i][np.argsort(-row[part[i]])]
            picked = _pick(order, row, gi, companies, top_k)
            if picked:
                result[ids[gi]] = [[ids[j], s] for j, s in picked]
    return result


def build(conn, kind: str, top_k: int = TOP_K) -> dict:
    meta, mat = load_vectors(conn, kind)
    if not meta:
        return {"kind": kind, "documents": 0, "with_similar": 0, "written": None}

    similar = compute(meta, mat, top_k)
    # 추천에 등장하는 문서만 url/title 을 싣는다. 전량을 실으면 파일이 불필요하게 커진다.
    used = set(similar) | {i for v in similar.values() for i, _ in v}
    by_id = {m["id"]: m for m in meta}
    docs = {
        i: {"u": by_id[i]["url"], "c": by_id[i]["company"], "t": by_id[i]["title"]}
        for i in sorted(used)
        if i in by_id
    }

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kind": kind,
        "top_k": top_k,
        "docs": docs,      # id → {u: url, c: company}
        "similar": similar,  # id → [[id, score], ...]
    }
    out: Path = OUT_PATHS[kind]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(out)  # 뷰어가 반쯤 쓰인 파일을 읽는 일이 없도록 원자적으로 교체

    return {
        "kind": kind,
        "documents": len(meta),
        "with_similar": len(similar),
        "written": str(out),
        "bytes": out.stat().st_size,
    }


def run(conn=None, kinds: tuple[str, ...] = ("job", "post"), top_k: int = TOP_K) -> dict:
    own = conn is None
    conn = conn or dbm.open_db()
    started = datetime.now()
    try:
        report = {k: build(conn, k, top_k) for k in kinds}
        conn.execute(
            "INSERT INTO runs(stage, started_at, ended_at, ok, detail) VALUES (?,?,?,?,?)",
            ("similar", started.isoformat(timespec="seconds"),
             datetime.now().isoformat(timespec="seconds"), 1,
             json.dumps(report, ensure_ascii=False)),
        )
        conn.commit()
        return report
    finally:
        if own:
            conn.close()


def main(argv: list[str]) -> int:
    kinds = ("job", "post")
    if "--kind" in argv:
        kinds = (argv[argv.index("--kind") + 1],)
    report = run(kinds=kinds)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # python -m semantic.similar
    sys.exit(main(sys.argv[1:]))
