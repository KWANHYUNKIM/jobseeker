"""정적 문서 — 파이프라인의 store.ingest.docs 가 viewer_doc(kind='file')에 옮겨 둔 것."""
from __future__ import annotations

from app.db.session import fetch_one

KIND = "file"


def find(path: str) -> dict | None:
    return fetch_one(
        "SELECT payload, content_hash, built_at FROM viewer_doc WHERE kind = %s AND key = %s",
        (KIND, path))
