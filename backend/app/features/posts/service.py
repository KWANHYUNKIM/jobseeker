"""글 목록 — tech_blogs.json 과 같은 모양(뷰어 features/blog 의 BlogFile).

본문(blog_content/<id>.json)은 정적 파일로 남는다. 원문과 번역문을 둘 다 들고 있는
파일인데 표(post.body)에는 한쪽만 들어간다.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, time, timezone

from app.features.posts import repository
from app.utils.cache import cached


def _ts(r: dict) -> float:
    if r["published_at"]:
        return r["published_at"].timestamp()
    d = r["published_on"]
    return datetime.combine(d, time(), tzinfo=timezone.utc).timestamp() if d else 0


def to_post(r: dict) -> dict:
    post = {
        "key": r["content_id"] or r["url"],
        "company": r["blog_name"],
        "country": r["country"],
        "title": r["title"],
        "url": r["url"],
        "published": r["published_on"].isoformat() if r["published_on"] else "",
        "published_ts": _ts(r),
        "summary": r["summary"],
        "tags": list(r["tags"] or []),
        "tech_stack": list(r["tech_stack"] or []),
        "categories": list(r["categories"] or []),
        "lang": r["lang"],
    }
    if r["content_id"]:
        post["content_id"] = r["content_id"]
    return post


def blog() -> dict:
    return cached(("posts",), _blog)


def _blog() -> dict:
    posts = [to_post(r) for r in repository.posts()]
    meta = repository.meta()
    m = meta["payload"] if meta else {}
    sources = Counter((p["company"], p["country"]) for p in posts)
    categories = m.get("categories") or sorted(
        {c for p in posts for c in p["categories"]},
        key=lambda c: -sum(c in p["categories"] for p in posts))
    return {
        "generated_at": m.get("generated_at") or "",
        "total": len(posts),
        "sources": [{"company": c, "country": k, "count": n}
                    for (c, k), n in sorted(sources.items(), key=lambda kv: (-kv[1], kv[0]))],
        "categories": categories,
        "tag_categories": m.get("tag_categories") or {},
        "posts": posts,
    }
