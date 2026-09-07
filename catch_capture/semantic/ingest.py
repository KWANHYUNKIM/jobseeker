"""JSON 스냅샷 → SQLite 적재. 임베딩 입력 텍스트를 만들고 변경분만 표시한다.

뷰어가 소비하는 public/*.json 을 그대로 원본으로 삼는다. 크롤 파이프라인이
이미 통합·중복제거·enrich 를 끝낸 결과물이라 여기서 다시 정제할 필요가 없고,
파이프라인 뒤에 이 단계를 붙이기만 하면 된다.

문서 키는 URL 의 sha1 앞 16자다. site+pid 는 실제 데이터에서 충돌이 있었고
(10,275건 중 3건), 배열 인덱스는 재크롤마다 흔들린다. URL 은 둘 다 아니다.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

# 마감 판정은 파이프라인과 같은 규칙이어야 한다. 여기서 따로 파싱하면
# 뷰어가 '모집중'이라 부르는 공고를 검색은 '마감'이라 부르는 어긋남이 생긴다.
from pipeline.job_status import classify_status as _classify_status
from pipeline.job_status import today_date as _status_today

from . import db as dbm
from .config import (
    BLOG_CONTENT_DIR,
    BLOGS_JSON,
    JOBS_JSON,
)

# 임베딩 입력 텍스트를 만드는 규칙은 semantic/text.py 가 소유한다 — 저장소(SQLite/
# PostgreSQL)에 의존하지 않아야 두 경로가 같은 텍스트, 같은 content_hash 를 만든다.
# job_embed_text/post_embed_text 는 기존 호출부(dashboard, 테스트)를 위해 재수출한다.
from .text import as_list as _as_list  # noqa: E402
from .text import job_embed_text, post_embed_text  # noqa: E402,F401


def doc_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def iter_jobs(path: Path = JOBS_JSON) -> Iterator[dict]:
    data = _load_json(path)
    if not isinstance(data, list):
        return
    # 마감 여부는 뷰어 데이터가 만들어진 시점이 아니라 '지금' 기준으로 다시 본다.
    # enriched 파일은 크롤 회차마다 갱신되지만 그 사이에도 마감일은 지나간다.
    today = _status_today()
    for job in data:
        url = (job.get("url") or "").strip()
        if not url:
            continue
        status, _reason, deadline_iso = _classify_status(job, today)
        text = job_embed_text(job)
        if len(text) < 30:  # 제목만 있는 껍데기는 추천 품질만 해친다
            continue
        yield {
            "id": doc_id(url),
            "kind": "job",
            "url": url,
            "site": job.get("site") or "",
            "company": (job.get("company") or "").strip(),
            "title": (job.get("title") or "").strip(),
            "meta": {
                "career": job.get("career") or "",
                "location": job.get("location") or "",
                "tech_stack": _as_list(job.get("tech_stack")),
                "pid": job.get("pid") or "",
                "overseas": bool(job.get("overseas")),
                # 마감 공고도 색인에는 남긴다 — 지난 공고 기반 통계·유사도의 재료다.
                # 대신 status 를 달아두고 검색·추천에서 기본 제외한다.
                "status": status,
                "deadline_date": deadline_iso,
            },
            "embed_text": text,
        }


def _blog_content(content_id: str | None) -> str | None:
    if not content_id:
        return None
    path = BLOG_CONTENT_DIR / f"{content_id}.json"
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return None
    return d.get("content_ko") or d.get("content")


def iter_posts(path: Path = BLOGS_JSON) -> Iterator[dict]:
    data = _load_json(path)
    posts = data.get("posts") if isinstance(data, dict) else None
    if not isinstance(posts, list):
        return
    for post in posts:
        url = (post.get("url") or "").strip()
        if not url:
            continue
        text = post_embed_text(post, _blog_content(post.get("content_id")))
        if len(text) < 30:
            continue
        yield {
            "id": doc_id(url),
            "kind": "post",
            "url": url,
            "site": post.get("key") or "",
            "company": (post.get("company") or "").strip(),
            "title": (post.get("title") or "").strip(),
            "meta": {
                "country": post.get("country") or "",
                "published": post.get("published") or "",
                "categories": _as_list(post.get("categories")),
                "tech_stack": _as_list(post.get("tech_stack")),
                "content_id": post.get("content_id") or "",
            },
            "embed_text": text,
        }


UPSERT = """
INSERT INTO documents (id, kind, url, site, company, title, meta,
                       embed_text, content_hash, first_seen, last_seen)
VALUES (:id, :kind, :url, :site, :company, :title, :meta,
        :embed_text, :content_hash, :now, :now)
ON CONFLICT(id) DO UPDATE SET
    kind          = excluded.kind,
    url           = excluded.url,
    site          = excluded.site,
    company       = excluded.company,
    title         = excluded.title,
    meta          = excluded.meta,
    embed_text    = excluded.embed_text,
    content_hash  = excluded.content_hash,
    last_seen     = excluded.last_seen
"""


def upsert(conn, docs: Iterable[dict]) -> dict:
    """문서를 적재하고 신규/변경/무변경 건수를 돌려준다.

    embedded_hash 는 건드리지 않는다. 본문이 바뀌면 content_hash 만 갱신되어
    두 값이 어긋나고, 그게 곧 "재임베딩 대상" 표시가 된다.
    """
    now = datetime.now().isoformat(timespec="seconds")
    counts = {"new": 0, "changed": 0, "same": 0}
    for doc in docs:
        content_hash = hashlib.sha1(doc["embed_text"].encode("utf-8")).hexdigest()
        prev = conn.execute(
            "SELECT content_hash FROM documents WHERE id = ?", (doc["id"],)
        ).fetchone()
        if prev is None:
            counts["new"] += 1
        elif prev["content_hash"] != content_hash:
            counts["changed"] += 1
        else:
            counts["same"] += 1
        conn.execute(
            UPSERT,
            {
                **doc,
                "meta": json.dumps(doc["meta"], ensure_ascii=False),
                "content_hash": content_hash,
                "now": now,
            },
        )
    conn.commit()
    return counts


def prune(conn, kind: str, seen_ids: set[str]) -> int:
    """이번 스냅샷에 없는 문서를 지운다(벡터는 트리거가 같이 지운다)."""
    rows = conn.execute("SELECT id FROM documents WHERE kind = ?", (kind,)).fetchall()
    gone = [r["id"] for r in rows if r["id"] not in seen_ids]
    if gone:
        conn.executemany("DELETE FROM documents WHERE id = ?", [(g,) for g in gone])
        conn.commit()
    return len(gone)


def run(conn=None, kinds: tuple[str, ...] = ("job", "post")) -> dict:
    own = conn is None
    conn = conn or dbm.open_db()
    try:
        report: dict[str, Any] = {}
        sources = {"job": iter_jobs, "post": iter_posts}
        for kind in kinds:
            docs = list(sources[kind]())
            counts = upsert(conn, docs)
            counts["removed"] = prune(conn, kind, {d["id"] for d in docs})
            counts["total"] = len(docs)
            report[kind] = counts
        return report
    finally:
        if own:
            conn.close()


if __name__ == "__main__":  # python -m semantic.ingest
    print(json.dumps(run(), ensure_ascii=False, indent=2))
