"""화면용 문서(viewer_doc, db/migrations/011) 읽기.

빌더가 계산한 결과(회사 프로필·외주 분석 등)를 파이프라인이 여기에 쓴다. 여러 기능이
같이 읽으므로 기능 폴더가 아니라 db/ 에 둔다.
"""
from __future__ import annotations

from app.db.session import fetch_one


def get_doc(kind: str, key: str = "") -> dict | None:
    """문서 하나와 만든 시각. 없으면 None."""
    r = fetch_one("SELECT payload, built_at FROM viewer_doc WHERE kind = %s AND key = %s", (kind, key))
    return {"payload": r["payload"], "built_at": r["built_at"]} if r else None
