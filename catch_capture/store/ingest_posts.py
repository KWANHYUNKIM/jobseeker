"""기술블로그 글 → 정본 DB(`post`). 벡터 파이프라인의 나머지 절반이다.

`semantic/ingest.py` 가 SQLite 에 `documents(kind='post')` 로 넣던 것을 대체한다.
공고(`job`)만 옮기고 이걸 빼면 `post_embedding` · `post_similar` · `similar_posts.json`
이 전부 비어 있게 된다 — 뷰어의 기술블로그 탭에서 "관련 글"이 사라진다.

입력:
    jd-viewer/public/tech_blogs.json          글 목록(1,063건)
    jd-viewer/public/blog_content/<id>.json   본문(크롤러가 서버에서 만든다. 없어도 된다)

본문이 없으면 제목+요약만으로 임베딩한다. 지금 이 트리에는 blog_content 가 비어
있는데(서버에서만 생성) 그래도 색인 자체는 성립한다 — 본문이 들어오면
content_hash 가 바뀌어 다음 사이클에 자동으로 재임베딩된다.

회사는 `company` 테이블에 이어 붙인다. 이어지면 회사 페이지에서 그 회사의 공고와
기술블로그를 같이 볼 수 있고, 안 이어져도(해외 블로그 대부분) `blog_name` 으로 남는다.

사용:
    python -m store.ingest_posts
    python -m store.ingest_posts --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys as _sys
from datetime import datetime
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from semantic.text import post_embed_text  # noqa: E402
from store import conn as store_conn  # noqa: E402
from store.slug import norm_company  # noqa: E402

ROOT = _Path(__file__).resolve().parent.parent.parent
BLOGS_JSON = ROOT / "jd-viewer" / "public" / "tech_blogs.json"
BLOG_CONTENT = ROOT / "jd-viewer" / "public" / "blog_content"


def _content(content_id: str | None) -> str | None:
    """번역본이 있으면 그쪽을 우선한다 — 임베딩 모델이 한국어 질의를 더 잘 맞춘다."""
    if not content_id:
        return None
    path = BLOG_CONTENT / f"{content_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data.get("content_ko") or data.get("content") or None


def _published(p: dict):
    raw = (p.get("published") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw[:10]).date()
    except ValueError:
        return None


def _strs(v) -> list[str]:
    """text[] 로 넣을 값. None·비문자열이 섞여도 배열이 깨지지 않게 한다."""
    return [str(x) for x in (v or []) if x]


def ingest(dry_run: bool = False) -> dict:
    if not BLOGS_JSON.exists():
        raise SystemExit(f"입력이 없다: {BLOGS_JSON}")
    data = json.loads(BLOGS_JSON.read_text(encoding="utf-8"))
    posts = data.get("posts") or []

    usable, seen = [], set()
    skipped = 0
    for p in posts:
        url = (p.get("url") or "").strip()
        title = (p.get("title") or "").strip()
        if not title or not url.startswith(("http://", "https://")) or url in seen:
            skipped += 1
            continue
        seen.add(url)
        usable.append(p)

    stats = {"input": len(posts), "usable": len(usable), "skipped": skipped,
             "new": 0, "linked": 0, "with_body": 0}
    if dry_run:
        return stats

    with store_conn.connect() as db:
        with db.cursor() as cur:
            # 회사 이어붙이기는 **있는 회사에만** 한다. 블로그에만 있는 해외 회사를
            # company 에 새로 만들면 회사 목록이 공고 없는 이름으로 오염된다.
            cur.execute("SELECT norm, id FROM company")
            by_norm = {r["norm"]: r["id"] for r in cur.fetchall()}

            for p in usable:
                body = _content(p.get("content_id")) or ""
                if body:
                    stats["with_body"] += 1
                cid = by_norm.get(norm_company(p.get("company") or ""))
                if cid:
                    stats["linked"] += 1

                # 임베딩 입력과 같은 재료로 해시를 만든다 — 이 값이 바뀌어야
                # 재임베딩이 걸린다. 제목만 바뀐 글을 다시 임베딩하는 건 맞고,
                # 조회수 같은 게 바뀌었다고 다시 하면 M1 이 못 버틴다.
                embed_text = post_embed_text(p, body or None)
                chash = hashlib.sha1(embed_text.encode("utf-8")).hexdigest()[:16]

                cur.execute(
                    """
                    INSERT INTO post (url, content_id, company_id, blog_name, title,
                                      body, published_on, content_hash,
                                      country, lang, summary, tags, tech_stack, categories)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (url) DO UPDATE SET
                        content_id   = EXCLUDED.content_id,
                        company_id   = EXCLUDED.company_id,
                        blog_name    = EXCLUDED.blog_name,
                        title        = EXCLUDED.title,
                        body         = EXCLUDED.body,
                        published_on = EXCLUDED.published_on,
                        content_hash = EXCLUDED.content_hash,
                        country      = EXCLUDED.country,
                        lang         = EXCLUDED.lang,
                        summary      = EXCLUDED.summary,
                        tags         = EXCLUDED.tags,
                        tech_stack   = EXCLUDED.tech_stack,
                        categories   = EXCLUDED.categories,
                        last_seen_at = now()
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (p["url"].strip(), p.get("content_id") or None, cid,
                     p.get("company") or "", p["title"].strip(),
                     body, _published(p), chash,
                     p.get("country") or "", p.get("lang") or "",
                     p.get("summary") or "", _strs(p.get("tags")),
                     _strs(p.get("tech_stack")), _strs(p.get("categories"))),
                )
                if cur.fetchone()["inserted"]:
                    stats["new"] += 1
        db.commit()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="기술블로그 글 → 정본 DB")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = ingest(args.dry_run)
    print(f"글 {s['usable']:,}건 (신규 {s['new']:,} · 회사 연결 {s['linked']:,} · "
          f"본문 있음 {s['with_body']:,} · 제외 {s['skipped']:,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
