"""Ollama 임베딩 배치 — 정본 DB 판. `semantic/embed.py` 의 PostgreSQL 대응물이다.

달라진 것은 저장소뿐이다. 모델·차원·정규화·배치 크기는 `semantic/config.py` 를
그대로 쓰고, 임베딩 입력 텍스트는 `semantic/text.py` 를 그대로 쓴다 — 두 벌이
되는 순간 같은 공고의 벡터가 경로에 따라 달라진다.

증분이 전부다. 공고 1만 건을 매 사이클 다시 임베딩하면 M1 에서 한 시간이 넘게
걸리지만 실제로 본문이 바뀌는 건 사이클당 수십~수백 건이다. 대기 목록은
`job_embed_pending` 뷰가 알려준다(job.content_hash != job_embedding.content_hash).

벡터는 L2 정규화해서 넣는다. 정규화된 벡터끼리는 내적이 곧 코사인 유사도라
pgvector 의 `<=>`(코사인 거리)와 순서가 일치한다.

사용:
    python -m store.embed                  # 대기분 전부
    python -m store.embed --limit 200      # 200건만
    python -m store.embed --kind post      # 블로그 글만
    python -m store.embed --dry-run        # 대기 건수만 보고 끝
"""
from __future__ import annotations

import argparse
import json
import math
import sys as _sys
import time
import urllib.error
import urllib.request
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from semantic.config import (  # noqa: E402
    EMBED_BATCH, EMBED_DIM, EMBED_MODEL, EMBED_TIMEOUT, OLLAMA_URL,
)
from semantic.text import job_embed_text, post_embed_text  # noqa: E402
from store import conn as store_conn  # noqa: E402

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
        raise EmbedError(
            f"Ollama 에 접속할 수 없다({OLLAMA_URL}): {e}\n"
            f"  맥에서는 `brew services start ollama`."
        ) from e
    names = {m.get("name", "").split(":")[0] for m in tags.get("models") or []}
    if EMBED_MODEL.split(":")[0] not in names:
        raise EmbedError(f"임베딩 모델 '{EMBED_MODEL}' 이 없다. `ollama pull {EMBED_MODEL}`.")


def _normalize(vec) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    return list(vec) if norm == 0 else [v / norm for v in vec]


def embed_batch(texts: list[str]) -> list[list[float]]:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            res = _post("/api/embed", {"model": EMBED_MODEL, "input": texts}, EMBED_TIMEOUT)
            vecs = res.get("embeddings") or []
            if len(vecs) != len(texts):
                raise EmbedError(f"입력 {len(texts)}건에 응답 {len(vecs)}건")
            for v in vecs:
                if len(v) != EMBED_DIM:
                    raise EmbedError(
                        f"차원이 {len(v)} 다 — 스키마는 vector({EMBED_DIM}). "
                        f"모델을 바꿨다면 새 컬럼/테이블을 만들어야 한다."
                    )
            return [_normalize(v) for v in vecs]
        except Exception as e:      # 모델 로딩·다른 요청으로 잠깐 바쁠 수 있다
            last = e
            if attempt < RETRIES - 1:
                time.sleep(RETRY_WAIT)
    raise EmbedError(f"임베딩 실패({RETRIES}회 시도): {last}")


# ── 대상 조회 ─────────────────────────────────────────────────────────
_JOB_SQL = """
    SELECT j.id, j.content_hash, j.title, c.display_name AS company,
           j.career_text AS career, j.location_text AS location,
           j.main_tasks, j.qualifications, j.preferences,
           COALESCE(array_agg(t.name) FILTER (WHERE t.id IS NOT NULL), '{}') AS tech_stack
      FROM job j
      JOIN company c ON c.id = j.company_id
      JOIN job_embed_pending p ON p.id = j.id
      LEFT JOIN job_tech jt ON jt.job_id = j.id
      LEFT JOIN tech t ON t.id = jt.tech_id AND NOT t.is_noise
     GROUP BY j.id, c.display_name
     ORDER BY j.last_seen_at DESC
"""

_POST_SQL = """
    SELECT p.id, p.content_hash, p.title, p.body, p.blog_name,
           c.display_name AS company
      FROM post p
      JOIN post_embed_pending q ON q.id = p.id
      LEFT JOIN company c ON c.id = p.company_id
     ORDER BY p.last_seen_at DESC
"""


def run(kind: str, limit: int | None, dry_run: bool) -> int:
    sql = _JOB_SQL if kind == "job" else _POST_SQL
    if limit:
        sql += f" LIMIT {int(limit)}"

    with store_conn.cursor(autocommit=True) as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    if not rows:
        print(f"  [{kind}] 대기 없음")
        return 0
    print(f"  [{kind}] 대기 {len(rows):,}건")
    if dry_run:
        return 0

    check_model()
    table = "job_embedding" if kind == "job" else "post_embedding"
    key = "job_id" if kind == "job" else "post_id"

    done = 0
    t0 = time.time()
    for i in range(0, len(rows), EMBED_BATCH):
        chunk = rows[i:i + EMBED_BATCH]
        if kind == "job":
            texts = [job_embed_text(dict(r, tech_stack=list(r["tech_stack"]))) for r in chunk]
        else:
            texts = [post_embed_text(dict(r), r.get("body")) for r in chunk]
        vecs = embed_batch(texts)

        # 배치 단위로 커밋한다. 만 건짜리 배치를 한 트랜잭션으로 묶으면 중간에
        # Ollama 가 죽었을 때 그때까지 만든 벡터를 통째로 잃는다.
        with store_conn.cursor() as cur:
            for r, v in zip(chunk, vecs):
                cur.execute(
                    f"""
                    INSERT INTO {table} ({key}, model, content_hash, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT ({key}) DO UPDATE SET
                        model = EXCLUDED.model,
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        embedded_at = now()
                    """,
                    (r["id"], EMBED_MODEL, r["content_hash"], str(v)),
                )
        done += len(chunk)
        if done % 200 == 0 or done == len(rows):
            rate = done / max(time.time() - t0, 0.001)
            print(f"    {done:,}/{len(rows):,}  ({rate:.1f}건/초)")
    print(f"  [{kind}] 완료 {done:,}건 · {time.time() - t0:.0f}초")
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description="Ollama 임베딩 → 정본 DB")
    ap.add_argument("--kind", choices=["job", "post", "all"], default="all")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    kinds = ["job", "post"] if args.kind == "all" else [args.kind]
    total = 0
    for k in kinds:
        try:
            total += run(k, args.limit, args.dry_run)
        except EmbedError as e:
            # Ollama 가 꺼져 있어도 사이클 전체를 죽이지 않는다 — 임베딩만 건너뛰고
            # 다음 사이클에 다시 시도한다(대기열은 그대로 남는다).
            print(f"  [{k}] 건너뜀: {e}")
            return 1
    print(f"임베딩 {total:,}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
