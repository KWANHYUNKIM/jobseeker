"""임베딩 행렬 읽기 — 군집·방향 계산을 하는 빌더(커리어 맵·블로그 가이드)용.

예전에는 두 빌더가 SQLite(semantic.db)를 직접 열었다. 이제 벡터는 정본 DB(pgvector)
한 곳에만 있으므로 여기서 numpy 행렬로 내려준다. 행은 L2 정규화돼 있다(내적 = 코사인).
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

import numpy as np

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))

from store.db import conn as store_conn  # noqa: E402

# 마감 공고도 싣는다 — 군집은 '시장이 나뉜 모양' 이라 지난 공고도 재료다(예전 SQLite 색인과 같다).
_JOBS = """
    SELECT v.id, v.url, v.title, v.company, v.site::text AS site, v.career_text, v.tech_stack,
           v.status::text AS status, e.embedding::real[] AS emb
      FROM job_embedding e
      JOIN v_job v ON v.id = e.job_id
     ORDER BY v.id
"""

_POSTS = """
    SELECT p.id, p.url, p.title, COALESCE(c.display_name, p.blog_name) AS company,
           e.embedding::real[] AS emb
      FROM post_embedding e
      JOIN post p ON p.id = e.post_id
      LEFT JOIN company c ON c.id = p.company_id
     ORDER BY p.id
"""


def _matrix(rows: list[dict]) -> np.ndarray:
    if not rows:
        return np.empty((0, 0), dtype=np.float32)
    m = np.asarray([r["emb"] for r in rows], dtype=np.float32)
    m /= np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-9, None)
    return m


def job_matrix() -> tuple[np.ndarray, list[dict]]:
    """공고 임베딩 행렬과, 같은 순서의 문서(id·url·title·company·site·tech·career·status)."""
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute(_JOBS)
        rows = cur.fetchall()
    docs = [{"id": r["id"], "url": r["url"] or "", "title": r["title"] or "",
             "company": r["company"] or "", "site": r["site"] or "",
             "tech": [t for t in (r["tech_stack"] or []) if t], "career": r["career_text"] or "",
             "status": r["status"]} for r in rows]
    return _matrix(rows), docs


def post_matrix() -> tuple[np.ndarray, list[dict]]:
    """글 임베딩 행렬과, 같은 순서의 문서(id·url·title·company)."""
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute(_POSTS)
        rows = cur.fetchall()
    docs = [{"id": r["id"], "url": r["url"] or "", "title": r["title"] or "",
             "company": r["company"] or ""} for r in rows]
    return _matrix(rows), docs
