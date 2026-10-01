"""부품 가격 — prices.json 과 같은 모양."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.db


def test_prices_shape(client):
    d = client.get("/api/hardware/prices").json()
    assert {"schema", "source", "day", "parts", "complete"} <= set(d)
    if not d["parts"]:
        pytest.skip("가격 없음")
    rec = next(r for r in d["parts"].values() if r.get("offers"))
    assert {"history", "day", "min", "median", "n", "offers"} <= set(rec)
    prices = [o["price"] for o in rec["offers"]]
    assert prices == sorted(prices), "매물은 싼 순서"
    assert rec["offers"][0]["url"].startswith("https://prod.danawa.com/")
