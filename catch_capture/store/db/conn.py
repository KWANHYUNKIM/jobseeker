"""정본 DB 커넥션 — DSN 의 단일 소스.

스키마는 `db/schema.sql`, 띄우는 법은 `db/README.md` 에 있다.
DSN 은 환경변수 `JOBSEEKER_DSN` 이 우선이고, 없으면 db/docker-compose.db.yml 이
띄우는 로컬 컨테이너를 가리킨다(포트 5433 — 다른 Postgres 와 겹치지 않게).
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

DEFAULT_DSN = "postgresql://jobseeker:jobseeker@127.0.0.1:5433/jobseeker"


def dsn() -> str:
    return os.environ.get("JOBSEEKER_DSN", DEFAULT_DSN)


def connect(*, autocommit: bool = False) -> psycopg.Connection:
    """dict 행을 돌려주는 커넥션. 기본은 수동 커밋이다 —
    크롤 한 사이클이 하나의 트랜잭션이어야 부분 실패가 롤백된다."""
    return psycopg.connect(dsn(), row_factory=dict_row, autocommit=autocommit)


@contextmanager
def cursor(*, autocommit: bool = False):
    """`with cursor() as cur:` — 정상 종료 시 커밋, 예외 시 롤백."""
    with connect(autocommit=autocommit) as conn:
        with conn.cursor() as cur:
            yield cur


def ping() -> str:
    """접속 확인용. 서버 버전과 pgvector 유무를 돌려준다."""
    with cursor(autocommit=True) as cur:
        cur.execute("SELECT version() AS v")
        ver = cur.fetchone()["v"].split(",")[0]
        cur.execute("SELECT extname FROM pg_extension ORDER BY extname")
        exts = [r["extname"] for r in cur.fetchall()]
    return f"{ver} · 확장: {', '.join(exts)}"


if __name__ == "__main__":
    print(dsn())
    print(ping())
