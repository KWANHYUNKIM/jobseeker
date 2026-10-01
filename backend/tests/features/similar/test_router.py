"""유사 공고 — 굳혀 둔 top-K 중 지금 모집중인 것만."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.db


def test_similar_jobs_are_open(client):
    from app.db.session import fetch_one
    r = fetch_one("SELECT j.url FROM job_similar s JOIN job j ON j.id = s.job_id LIMIT 1")
    if not r:
        pytest.skip("job_similar 비어 있음")
    d = client.get("/api/similar", params={"url": r["url"]}).json()
    assert d["kind"] == "job" and len(d["items"]) <= 5
    for it in d["items"]:
        st = fetch_one("SELECT s.status::text AS s FROM job j JOIN job_state s ON s.job_id = j.id "
                       "WHERE j.url = %s", (it["url"],))
        assert st["s"] == "active"
        assert 0 < it["score"] <= 1


def test_unknown_url_is_empty(client):
    d = client.get("/api/similar", params={"url": "https://example.com/none"}).json()
    assert d["items"] == []
