from __future__ import annotations

from app.features.similar import repository
from app.utils.cache import cached


def similar(kind: str, url: str, limit: int) -> dict:
    rows = cached(("similar", kind, url, limit), lambda: repository.similar(kind, url, limit))
    return {"url": url, "kind": kind,
            "items": [{"url": r["url"], "company": r["company"], "title": r["title"],
                       "score": round(float(r["score"]), 4)} for r in rows]}
