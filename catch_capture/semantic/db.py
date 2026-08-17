"""SQLite + sqlite-vec 저장소 — 스키마 정의와 커넥션 팩토리.

문서(공고/블로그)를 `documents` 한 테이블에 담고, 벡터는 sqlite-vec 가상테이블
`vec_documents` 에 같은 rowid 로 매단다. rowid 를 공유하므로 조인 비용이 없고,
문서를 지우면 벡터도 트리거로 함께 지워진다.

증분 임베딩의 핵심은 두 해시다:
  content_hash   현재 본문에서 만든 임베딩 입력의 해시
  embedded_hash  마지막으로 임베딩을 성공시킨 시점의 content_hash
두 값이 다르거나 embedded_hash 가 NULL 이면 "임베딩 대기" 상태다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from .config import DB_PATH, EMBED_DIM

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    rowid          INTEGER PRIMARY KEY,
    id             TEXT NOT NULL UNIQUE,   -- sha1(url)[:16] — 크롤 간 안정적인 키
    kind           TEXT NOT NULL,          -- 'job' | 'post'
    url            TEXT NOT NULL UNIQUE,
    site           TEXT,
    company        TEXT,
    title          TEXT,
    meta           TEXT,                   -- kind 별 부가정보 JSON
    embed_text     TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    embedded_hash  TEXT,                   -- content_hash 와 다르면 재임베딩 대상
    embed_model    TEXT,
    first_seen     TEXT NOT NULL,
    last_seen      TEXT NOT NULL,
    embedded_at    TEXT
);

CREATE INDEX IF NOT EXISTS documents_kind_idx ON documents(kind);
CREATE INDEX IF NOT EXISTS documents_pending_idx
    ON documents(kind) WHERE embedded_hash IS NULL;

-- 파이프라인 실행 이력 (monitoring/health 와 같은 결의 운영 기록)
CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    stage      TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    ok         INTEGER,
    detail     TEXT
);
"""

VEC_SCHEMA = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS vec_documents USING vec0(
    embedding float[{EMBED_DIM}],
    kind text
);
"""

# 키워드 검색용 전문 인덱스. 하이브리드 검색에서 벡터가 못 잡는 고유명사
# (회사명·기술명·제품명)를 담당한다.
#
# external content(content='documents') 방식이라 본문을 중복 저장하지 않는다.
# 그래서 FTS5 컬럼명은 documents 의 컬럼명과 같아야 한다(embed_text 를 그대로 쓴다).
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_documents USING fts5(
    title, company, embed_text,
    content='documents',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
"""

# documents 에서 사라진 문서의 벡터·색인이 남지 않게 한다.
# FTS 갱신은 embed_text 등 색인 대상 컬럼이 실제로 바뀔 때만 돈다 — embed 배치가
# embedded_hash 만 건드릴 때까지 재색인하면 사이클마다 헛일을 한다.
TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    DELETE FROM vec_documents WHERE rowid = old.rowid;
    INSERT INTO fts_documents(fts_documents, rowid, title, company, embed_text)
    VALUES ('delete', old.rowid, old.title, old.company, old.embed_text);
END;

CREATE TRIGGER IF NOT EXISTS documents_ai_fts AFTER INSERT ON documents BEGIN
    INSERT INTO fts_documents(rowid, title, company, embed_text)
    VALUES (new.rowid, new.title, new.company, new.embed_text);
END;

CREATE TRIGGER IF NOT EXISTS documents_au_fts
AFTER UPDATE OF title, company, embed_text ON documents BEGIN
    INSERT INTO fts_documents(fts_documents, rowid, title, company, embed_text)
    VALUES ('delete', old.rowid, old.title, old.company, old.embed_text);
    INSERT INTO fts_documents(rowid, title, company, embed_text)
    VALUES (new.rowid, new.title, new.company, new.embed_text);
END;
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """sqlite-vec 확장을 적재한 커넥션을 돌려준다."""
    target = Path(path or DB_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    # 크롤 배치와 조회가 겹쳐도 읽기가 막히지 않게 WAL 을 쓴다.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init(conn: sqlite3.Connection) -> None:
    """스키마를 멱등하게 생성한다.

    FTS 인덱스가 방금 만들어졌다면(= 기존 DB 에 뒤늦게 추가된 경우) 트리거는 이후
    변경분만 잡으므로, 이미 들어있는 문서를 한 번 통째로 색인해 준다.
    """
    conn.executescript(SCHEMA)
    conn.executescript(VEC_SCHEMA)
    fresh_fts = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fts_documents'"
    ).fetchone() is None
    conn.executescript(FTS_SCHEMA)
    conn.executescript(TRIGGERS)
    if fresh_fts and conn.execute("SELECT 1 FROM documents LIMIT 1").fetchone():
        rebuild_fts(conn)
    conn.commit()


def rebuild_fts(conn: sqlite3.Connection) -> None:
    """FTS 인덱스를 documents 기준으로 통째로 다시 만든다."""
    conn.execute("INSERT INTO fts_documents(fts_documents) VALUES('rebuild')")
    conn.commit()


def open_db(path: Path | str | None = None) -> sqlite3.Connection:
    conn = connect(path)
    init(conn)
    return conn


def stats(conn: sqlite3.Connection) -> dict:
    """운영 확인용 요약 — 종류별 문서 수와 임베딩 대기 건수."""
    rows = conn.execute(
        """
        SELECT kind,
               COUNT(*) AS total,
               SUM(embedded_hash IS NOT NULL AND embedded_hash = content_hash) AS embedded
          FROM documents GROUP BY kind
        """
    ).fetchall()
    out = {r["kind"]: {"total": r["total"], "embedded": r["embedded"] or 0} for r in rows}
    for v in out.values():
        v["pending"] = v["total"] - v["embedded"]
    vec_count = conn.execute("SELECT COUNT(*) FROM vec_documents").fetchone()[0]
    return {"by_kind": out, "vectors": vec_count}
