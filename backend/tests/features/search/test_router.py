"""검색 API — 응답 형식은 뷰어(features/jobs)와 외부 도구가 읽는 그대로."""
from __future__ import annotations

import pytest


@pytest.mark.db
def test_search_response_format_unchanged(client):
    r = client.get("/api/search", params={"q": "백엔드", "limit": 3})
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {"query", "kind", "total", "engines", "results"}
    if d["results"]:
        assert set(d["results"][0]) == {"id", "url", "site", "company", "title", "career",
                                        "location", "tech_stack", "score", "rank_fts",
                                        "rank_vec"}


@pytest.mark.db
def test_search_posts(client):
    d = client.get("/api/search", params={"q": "kafka", "kind": "post", "limit": 3}).json()
    assert d["kind"] == "post" and all(r["site"] == "post" for r in d["results"])


def test_search_requires_query(client):
    assert client.get("/api/search", params={"q": "  "}).status_code == 400
