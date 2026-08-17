"""Ollama 임베딩 배치 — 대기 중인 문서만 벡터로 만들어 저장한다.

증분이 전부다. 공고 1만 건을 매 사이클 다시 임베딩하면 M1 에서 한 시간이 넘게
걸리지만, 실제로 본문이 바뀌는 건 사이클당 수십~수백 건이다. ingest 가 남긴
content_hash != embedded_hash 를 대기 표시로 삼아 그것만 처리한다.

벡터는 L2 정규화해서 넣는다. 정규화된 벡터끼리는 내적이 곧 코사인 유사도라
1단계 추천에서 거리 계산이 단순해지고, sqlite-vec 의 코사인 거리와도 일치한다.

사용법:
    python -m semantic.embed                 # 대기분 전부
    python -m semantic.embed --limit 200     # 200건만 (첫 실행 감 잡을 때)
    python -m semantic.embed --kind job      # 공고만
    python -m semantic.embed --all           # 대기 여부 무시하고 전량 재임베딩
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Iterable, Sequence

import sqlite_vec

from . import db as dbm
from .config import (
    EMBED_BATCH,
    EMBED_DIM,
    EMBED_MODEL,
    EMBED_TIMEOUT,
    OLLAMA_URL,
)

# Ollama 가 잠깐 바쁠 때(모델 로딩·다른 요청)를 넘기기 위한 재시도.
RETRIES = 3
RETRY_WAIT = 5


class EmbedError(RuntimeError):
    pass


def _post(path: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_model() -> None:
    """모델이 없으면 배치를 시작하기 전에 죽는다.

    없는 모델로 /api/embed 를 부르면 Ollama 가 그때부터 pull 을 시작해 첫 요청이
    타임아웃으로 실패한다. 그 실패를 임베딩 실패로 오해하지 않게 미리 확인한다.
    """
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=10) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise EmbedError(f"Ollama 에 접속할 수 없다({OLLAMA_URL}): {e}") from e
    names = {m.get("name", "").split(":")[0] for m in tags.get("models") or []}
    if EMBED_MODEL.split(":")[0] not in names:
        raise EmbedError(
            f"임베딩 모델 '{EMBED_MODEL}' 이 없다. 먼저 `ollama pull {EMBED_MODEL}` 을 실행할 것."
        )


def _normalize(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return list(vec)
    return [v / norm for v in vec]


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """텍스트 배치를 정규화된 벡터로. 차원이 설정과 다르면 즉시 실패한다."""
    last: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            data = _post(
                "/api/embed",
                {"model": EMBED_MODEL, "input": list(texts)},
                EMBED_TIMEOUT,
            )
            vectors = data.get("embeddings")
            if not vectors or len(vectors) != len(texts):
                raise EmbedError(
                    f"임베딩 응답 개수 불일치: 요청 {len(texts)} / 응답 {len(vectors or [])}"
                )
            for v in vectors:
                if len(v) != EMBED_DIM:
                    raise EmbedError(
                        f"임베딩 차원 불일치: 설정 {EMBED_DIM} / 응답 {len(v)}. "
                        f"SEMANTIC_EMBED_DIM 또는 모델 설정을 맞출 것."
                    )
            return [_normalize(v) for v in vectors]
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            if attempt < RETRIES:
                time.sleep(RETRY_WAIT)
    raise EmbedError(f"임베딩 요청이 {RETRIES}회 모두 실패했다: {last!r}")


PENDING_SQL = """
SELECT rowid, id, kind, embed_text
  FROM documents
 WHERE (embedded_hash IS NULL OR embedded_hash <> content_hash)
"""

ALL_SQL = "SELECT rowid, id, kind, embed_text FROM documents"


def pending(conn, kind: str | None = None, limit: int | None = None,
            force: bool = False) -> list:
    sql = ALL_SQL if force else PENDING_SQL
    params: list = []
    if kind:
        sql += (" WHERE" if force else " AND") + " kind = ?"
        params.append(kind)
    # 신규가 먼저 나가도록 rowid 순서를 유지한다(중간에 끊겨도 앞쪽은 완료 상태).
    sql += " ORDER BY rowid"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def _store(conn, rows: Sequence, vectors: Sequence[Sequence[float]]) -> None:
    """벡터와 임베딩 완료 표시를 한 트랜잭션으로 반영한다.

    vec0 가상테이블은 UPDATE 지원이 버전마다 달라 지우고 다시 넣는다.
    documents 와 rowid 를 공유하므로 조인 없이 그대로 매칭된다.
    """
    now = datetime.now().isoformat(timespec="seconds")
    for row, vec in zip(rows, vectors):
        blob = sqlite_vec.serialize_float32(vec)
        conn.execute("DELETE FROM vec_documents WHERE rowid = ?", (row["rowid"],))
        conn.execute(
            "INSERT INTO vec_documents(rowid, embedding, kind) VALUES (?, ?, ?)",
            (row["rowid"], blob, row["kind"]),
        )
        conn.execute(
            """UPDATE documents
                  SET embedded_hash = content_hash,
                      embed_model   = ?,
                      embedded_at   = ?
                WHERE rowid = ?""",
            (EMBED_MODEL, now, row["rowid"]),
        )
    conn.commit()


def _chunks(items: Sequence, size: int) -> Iterable[Sequence]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def run(conn=None, kind: str | None = None, limit: int | None = None,
        force: bool = False, verbose: bool = True) -> dict:
    """대기 문서를 임베딩한다. 배치 하나가 실패해도 나머지는 계속 진행한다."""
    own = conn is None
    conn = conn or dbm.open_db()
    started = datetime.now()
    try:
        check_model()
        rows = pending(conn, kind=kind, limit=limit, force=force)
        total = len(rows)
        if verbose:
            print(f"[embed] 대상 {total}건 (model={EMBED_MODEL}, batch={EMBED_BATCH})", flush=True)
        done = failed = 0
        for i, chunk in enumerate(_chunks(rows, EMBED_BATCH), start=1):
            try:
                vectors = embed_texts([r["embed_text"] for r in chunk])
                _store(conn, chunk, vectors)
                done += len(chunk)
            except EmbedError as e:
                failed += len(chunk)
                print(f"[embed] 배치 {i} 실패({len(chunk)}건): {e}", flush=True)
            if verbose and (i % 20 == 0 or done + failed >= total):
                elapsed = (datetime.now() - started).total_seconds()
                rate = done / elapsed if elapsed else 0
                print(f"[embed] {done + failed}/{total} (성공 {done}, 실패 {failed}, "
                      f"{rate:.1f}건/s)", flush=True)
        report = {
            "total": total,
            "embedded": done,
            "failed": failed,
            "seconds": round((datetime.now() - started).total_seconds(), 1),
        }
        conn.execute(
            "INSERT INTO runs(stage, started_at, ended_at, ok, detail) VALUES (?,?,?,?,?)",
            ("embed", started.isoformat(timespec="seconds"),
             datetime.now().isoformat(timespec="seconds"),
             1 if failed == 0 else 0, json.dumps(report, ensure_ascii=False)),
        )
        conn.commit()
        return report
    finally:
        if own:
            conn.close()


def main(argv: list[str]) -> int:
    kind = None
    limit = None
    force = "--all" in argv
    if "--kind" in argv:
        kind = argv[argv.index("--kind") + 1]
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    try:
        report = run(kind=kind, limit=limit, force=force)
    except EmbedError as e:
        print(f"[embed] 중단: {e}", flush=True)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":  # python -m semantic.embed
    sys.exit(main(sys.argv[1:]))
