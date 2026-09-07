"""이관 4단계 — semantic.db(SQLite + sqlite-vec)의 벡터를 정본 DB 로 옮긴다.

**재임베딩할 필요가 없다.** 같은 모델(bge-m3), 같은 차원(1024), 같은 입력 텍스트
규칙(semantic/text.py)이면 이미 만들어 둔 벡터가 그대로 유효하다. 1만 건을 다시
임베딩하면 M1 에서 한 시간이 넘는다.

이어붙이는 키는 URL 이다. SQLite 쪽 `documents.id` 는 sha1(url)[:16] 이고 정본
DB 의 `job.url` 은 UNIQUE 라 서로를 정확히 가리킨다. site+pid 로는 못 잇는다 —
그 쌍은 실제 데이터에서 충돌한 적이 있다.

옮긴 뒤 content_hash 는 **SQLite 의 값이 아니라 job 테이블의 현재 값**을 넣는다.
두 해시 규칙이 다르면(그럴 수 있다) 다음 embed 배치가 전량을 대기로 잡아 M1 에서
사이클이 끝나지 않는다. "지금 이 본문에 대해 이 벡터가 유효하다"고 선언하는 것이
이 이관의 의미다. 본문이 바뀐 공고는 어차피 크롤이 content_hash 를 바꿔 놓는다.

사용:
    python -m store.migrate_vectors --dry-run
    python -m store.migrate_vectors
    python -m store.migrate_vectors --db /path/to/semantic.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys as _sys
import time
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from store import conn as store_conn  # noqa: E402

CATCH = _Path(__file__).resolve().parent.parent
DEFAULT_SQLITE = CATCH / "semantic.db"
BATCH = 500


def open_sqlite(path: _Path) -> sqlite3.Connection:
    """sqlite-vec 를 적재한 커넥션. 벡터를 읽으려면 확장이 필요하다."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    try:
        import sqlite_vec
        sqlite_vec.load(conn)
    except Exception as e:
        raise SystemExit(
            f"sqlite-vec 를 적재할 수 없다: {e}\n"
            f"  이 스크립트는 운영 머신(맥)에서 돌린다 — `pip install sqlite-vec`."
        )
    conn.enable_load_extension(False)
    return conn


def main() -> int:
    ap = argparse.ArgumentParser(description="semantic.db → 정본 DB 벡터 이관")
    ap.add_argument("--db", default=str(DEFAULT_SQLITE))
    ap.add_argument("--kind", choices=["job", "post", "all"], default="all")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = _Path(args.db)
    if not src.exists():
        print(f"원본이 없다: {src}")
        return 1

    lite = open_sqlite(src)
    kinds = ["job", "post"] if args.kind == "all" else [args.kind]
    total = 0

    for kind in kinds:
        rows = lite.execute(
            """
            SELECT d.url, d.embed_model, v.embedding
              FROM documents d JOIN vec_documents v ON v.rowid = d.rowid
             WHERE d.kind = ? AND d.embedded_hash IS NOT NULL
            """,
            (kind,),
        ).fetchall()
        print(f"[{kind}] SQLite 에 임베딩된 문서 {len(rows):,}건")
        if args.dry_run or not rows:
            continue

        table = "job_embedding" if kind == "job" else "post_embedding"
        key = "job_id" if kind == "job" else "post_id"
        target = "job" if kind == "job" else "post"

        moved = missing = 0
        t0 = time.time()
        with store_conn.connect() as db:
            with db.cursor() as cur:
                for i in range(0, len(rows), BATCH):
                    for r in rows[i:i + BATCH]:
                        # sqlite-vec 는 float32 바이트열로 돌려준다.
                        import struct
                        raw = r["embedding"]
                        vec = list(struct.unpack(f"{len(raw)//4}f", raw))
                        cur.execute(
                            f"""
                            INSERT INTO {table} ({key}, model, content_hash, embedding)
                            SELECT t.id, %s, t.content_hash, %s
                              FROM {target} t WHERE t.url = %s
                            ON CONFLICT ({key}) DO UPDATE SET
                                model = EXCLUDED.model,
                                content_hash = EXCLUDED.content_hash,
                                embedding = EXCLUDED.embedding,
                                embedded_at = now()
                            """,
                            (r["embed_model"] or "bge-m3", str(vec), r["url"]),
                        )
                        if cur.rowcount:
                            moved += 1
                        else:
                            missing += 1   # 정본 DB 에 없는 공고(제약에 걸려 빠진 것)
                    print(f"    … {min(i+BATCH, len(rows)):,}/{len(rows):,}")
            db.commit()
        print(f"[{kind}] 옮김 {moved:,}건 · 대상 없음 {missing:,}건 · {time.time()-t0:.0f}초")
        total += moved

    lite.close()
    if not args.dry_run:
        with store_conn.cursor(autocommit=True) as cur:
            for v in ("job_embed_pending", "post_embed_pending"):
                cur.execute(f"SELECT count(*) AS n FROM {v}")
                print(f"  이관 후 {v}: {cur.fetchone()['n']:,}건 대기")
    print(f"총 {total:,}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
