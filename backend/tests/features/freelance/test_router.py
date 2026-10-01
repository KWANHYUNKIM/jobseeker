"""외주 API — project 표 + 분석 문서를 freelance.json 과 같은 모양으로."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.db


def test_shape_matches_file(client):
    r = client.get("/api/freelance")
    if r.status_code == 404:
        pytest.skip("외주 분석 문서 없음(store.market.freelance ingest)")
    d = r.json()
    assert {"updated_at", "trend", "analysis", "rate_history", "projects"} <= set(d)
    p = d["projects"][0]
    assert {"id", "site", "url", "title", "budget", "status", "history", "first_seen_at"} <= set(p)
    assert p["status"] in ("active", "closed")
    assert "classes" not in d, "분류는 프로젝트마다 펼쳐 싣는다"
    assert any("grade" in x for x in d["projects"])
