"""부품 가격 — prices.json 과 같은 모양(뷰어 features/hardware 가 읽는다)."""
from __future__ import annotations

from app.features.hardware import repository
from app.utils.cache import cached

PRODUCT_URL = "https://prod.danawa.com/info/?pcode={pcode}"


def prices() -> dict:
    return cached(("hardware-prices",), _prices)


def _prices() -> dict:
    days, offers = repository.price_rows()
    parts: dict[str, dict] = {}
    for r in days:
        rec = parts.setdefault(r["part_id"], {"history": []})
        h = {"d": r["day"].isoformat(), "min": r["min_price"], "median": r["median_price"], "n": r["n"]}
        rec["history"].append(h)
        # 마지막 날 값이 그 부품의 '오늘' 이다(날짜순이라 덮어쓰면 마지막이 남는다).
        rec.update(day=h["d"], min=h["min"], median=h["median"], n=h["n"])
    for o in offers:
        rec = parts.setdefault(o["part_id"], {"history": []})
        rec.setdefault("offers", []).append({
            "pcode": o["pcode"], "name": o["name"], "price": o["price"], "rank": o["rank"],
            "url": PRODUCT_URL.format(pcode=o["pcode"]),
        })
    meta = repository.meta()
    m = meta["payload"] if meta else {}
    return {"schema": m.get("schema") or 1, "source": m.get("source") or "danawa",
            "day": m.get("day"), "updated_at": m.get("updated_at"),
            "complete": bool(m.get("complete")), "parts": parts}
