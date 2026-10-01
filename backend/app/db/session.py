"""DB 연결 — 읽기 전용 API 라 질의마다 autocommit 커넥션 하나를 쓴다.

스키마는 저장소 루트의 `db/schema.sql`(+ `db/migrations/`)이다. 쓰는 쪽은 크롤
파이프라인(catch_capture)이고 이 백엔드는 읽기만 한다.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.dsn, row_factory=dict_row, autocommit=True)


@contextmanager
def cursor() -> Iterator[psycopg.Cursor]:
    """`with cursor() as cur:` — dict 행을 돌려준다."""
    with connect() as conn:
        with conn.cursor() as cur:
            yield cur


def fetch_all(sql: str, params: dict | tuple | None = None) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(sql: str, params: dict | tuple | None = None) -> dict | None:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def redacted_dsn() -> str:
    """로그에 찍을 DSN — 비밀번호를 가린다."""
    dsn = settings.dsn
    if "@" in dsn and "://" in dsn:
        head, tail = dsn.split("://", 1)
        cred, host = tail.rsplit("@", 1)
        user = cred.split(":", 1)[0]
        return f"{head}://{user}:***@{host}"
    return dsn
