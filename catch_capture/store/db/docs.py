"""화면용 문서(viewer_doc, db/migrations/011) 쓰기.

빌더가 계산한 결과 — 회사 프로필·외주 단가 분석처럼 SQL 로 옮기지 않은 계산 —
를 DB 에 두면 뷰어 API(backend)가 잘라서 답한다. 파일은 사전 렌더링·API 없는
배포용으로 계속 쓴다. 쓰기는 이중 쓰기 약속을 따른다: DB 가 없거나 실패해도
빌더는 죽지 않는다(`DB_DUAL_WRITE=0` 으로 끈다).
"""
from __future__ import annotations

import os
import sys

from psycopg.types.json import Jsonb

from store.db.conn import cursor


def enabled() -> bool:
    return os.environ.get("DB_DUAL_WRITE", "1") != "0"


def replace_kind(kind: str, docs: dict[str, object]) -> int:
    """kind 의 문서를 통째로 바꾼다 — 이번에 안 나온 key(사라진 회사 등)는 지운다.

    한 트랜잭션이라 API 는 옛 묶음 아니면 새 묶음만 본다.
    """
    with cursor() as cur:
        cur.execute("DELETE FROM viewer_doc WHERE kind = %s", (kind,))
        cur.executemany(
            "INSERT INTO viewer_doc (kind, key, payload) VALUES (%s, %s, %s)",
            [(kind, key, Jsonb(payload)) for key, payload in docs.items()],
        )
    return len(docs)


def put(kind: str, key: str, payload: object) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO viewer_doc (kind, key, payload) VALUES (%s, %s, %s) "
            "ON CONFLICT (kind, key) DO UPDATE SET payload = EXCLUDED.payload, built_at = now()",
            (kind, key, Jsonb(payload)),
        )


def dual_write(label: str, fn, *args) -> object | None:
    """DB 쓰기를 시도하고, 실패해도 호출자를 죽이지 않는다."""
    if not enabled():
        return None
    try:
        return fn(*args)
    except Exception as e:                                          # noqa: BLE001
        print(f"  [db] {label} 건너뜀: {e}", file=sys.stderr)
        return None
