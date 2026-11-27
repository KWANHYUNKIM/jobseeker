"""채용 추이 API — 응답 모양과 정렬."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.db


def test_momentum_shape(client):
    d = client.get("/api/hiring/momentum?min_recent=0&limit=20").json()
    assert {"weeks", "reliable", "comparable", "coverage_start", "compare_weeks", "fast_days", "total", "companies", "notes"} <= set(d)
    assert len(d["weeks"]) == 12
    for c in d["companies"]:
        assert len(c["weekly"]) == 12
        assert c["trend"] in {"new", "up", "flat", "down", "unknown"}
        if not d["comparable"]:
            assert c["trend"] == "unknown"
        assert c["closed_fast"] <= c["closed"] <= c["total"]
        st = c["seats"]
        assert st["known"] <= st["of"] == c["recent"]
        if st["low"] is not None:
            assert st["low"] <= st["high"]
        if c["fast_close_ratio"] is not None:
            assert 0 <= c["fast_close_ratio"] <= 1
    recents = [c["recent"] for c in d["companies"]]
    assert recents == sorted(recents, reverse=True)


def test_momentum_rejects_short_window(client):
    assert client.get("/api/hiring/momentum?weeks=4").status_code == 422


def test_momentum_sort_by_seats(client):
    d = client.get("/api/hiring/momentum?min_recent=0&sort=seats&limit=30").json()
    lows = [c["seats"]["low"] or 0 for c in d["companies"]]
    assert lows == sorted(lows, reverse=True)
