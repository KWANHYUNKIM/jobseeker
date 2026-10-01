"""글 목록 — tech_blogs.json 과 같은 모양."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.db


def test_posts_shape(client):
    d = client.get("/api/posts").json()
    assert {"generated_at", "total", "sources", "categories", "tag_categories", "posts"} <= set(d)
    assert d["total"] == len(d["posts"]) > 0
    p = d["posts"][0]
    assert {"key", "company", "title", "url", "published", "published_ts", "tags", "lang"} <= set(p)
    assert sum(s["count"] for s in d["sources"]) == d["total"]
    ts = [x["published_ts"] for x in d["posts"] if x["published_ts"]]
    assert ts == sorted(ts, reverse=True), "최신 글이 위"
