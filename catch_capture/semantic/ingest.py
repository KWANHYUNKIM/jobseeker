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
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from . import db as dbm
from .config import (
    BLOG_CONTENT_DIR,
    BLOGS_JSON,
    JOBS_JSON,
    MAX_EMBED_CHARS,
)

# 섹션 하나가 입력 전체를 먹어치우지 않게 잘라 쓰는 상한.
SECTION_CHARS = 700

_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_CODE_FENCE = re.compile(r"```.*?```", re.S)
_WS = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


def doc_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _as_list(v: Any) -> list[str]:
    """tech_stack 등은 보통 list 지만 문자열로 굳어 들어온 스냅샷도 있다."""
    if isinstance(v, list):
        return [str(x) for x in v if x]
    if isinstance(v, str) and v.strip():
        s = v.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s.replace("'", '"'))
                if isinstance(parsed, list):
                    return [str(x) for x in parsed if x]
            except Exception:
                pass
        return [s]
    return []


def _clean(text: Any, limit: int | None = None) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    s = _CODE_FENCE.sub(" ", s)
    s = _MD_IMAGE.sub("", s)
    s = _MD_LINK.sub(r"\1", s)
    s = _WS.sub(" ", s)
    s = _BLANKS.sub("\n\n", s)
    s = s.strip()
    if limit and len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s


def job_embed_text(job: dict) -> str:
    """공고 임베딩 입력. 복지/전체 JD 원문은 뺀다 — 변별력 대비 길이만 늘린다."""
    tech = ", ".join(_as_list(job.get("tech_stack")))
    head = [job.get("title") or ""]
    facts = [job.get("company"), job.get("career"), job.get("location")]
    head.append(" | ".join(f for f in facts if f))
    if tech:
        head.append(f"기술스택: {tech}")
    parts = [p for p in head if p.strip()]
    for label, key in (
        ("주요업무", "main_tasks"),
        ("자격요건", "qualifications"),
        ("우대사항", "preferences"),
    ):
        body = _clean(job.get(key), SECTION_CHARS)
        if body:
            parts.append(f"[{label}]\n{body}")
    return _clean("\n".join(parts), MAX_EMBED_CHARS)


def post_embed_text(post: dict, content: str | None) -> str:
    """블로그 글 임베딩 입력. 번역본(content_ko)이 있으면 그쪽을 우선한다."""
    parts = [post.get("title") or ""]
    facts = [post.get("company"), post.get("country")]
    tags = _as_list(post.get("tech_stack")) + _as_list(post.get("categories"))
    if tags:
        facts.append(", ".join(dict.fromkeys(tags)))
    joined = " | ".join(f for f in facts if f)
    if joined:
        parts.append(joined)
    summary = _clean(post.get("summary"), SECTION_CHARS)
    if summary:
        parts.append(summary)
    if content:
        parts.append(_clean(content, MAX_EMBED_CHARS))
    return _clean("\n".join(p for p in parts if p.strip()), MAX_EMBED_CHARS)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def iter_jobs(path: Path = JOBS_JSON) -> Iterator[dict]:
    data = _load_json(path)
    if not isinstance(data, list):
        return
    for job in data:
        url = (job.get("url") or "").strip()
        if not url:
            continue
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
