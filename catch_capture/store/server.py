"""검색 API 서버 — 정본 DB 판. `semantic/server.py` 를 대체한다.

**응답 형식은 한 글자도 바뀌지 않는다.** 뷰어(`src/lib/useHybridSearch.ts`)가 읽는
`{query, kind, total, engines:{fts,vector}, results:[{id,url,site,company,title,
career,location,tech_stack,score,rank_fts,rank_vec}]}` 그대로다. 바뀌는 것은 그 값이
SQLite 가 아니라 PostgreSQL 에서 온다는 것뿐이라, 뷰어는 고칠 데가 없다.

달라지는 것 셋:
  - 마감 공고 제외가 **조인 조건**이다(`job_state`). 지금까지는 색인에 복사해 둔
    status 를 봤기 때문에, 공고가 마감돼도 다음 ingest 전까지 결과에 남았다.
  - RRF 융합이 DB 안(`search_jobs()`)에서 끝난다. 파이썬은 질의 임베딩만 만든다.
  - Ollama 가 없어도 죽지 않는다. 벡터를 못 만들면 FTS 만으로 답하고 `engines.vector`
    가 0 이 된다 — 검색이 통째로 실패하는 것보다 낫다.

표준 라이브러리만 쓴다(psycopg 제외). 검색 하나를 위해 웹 프레임워크를 들이면
배포에서 의존성·컨테이너·버전을 새로 관리해야 하는데, 그만한 일이 아니다.

    GET /api/search?q=재택+백엔드&kind=job&limit=20&include_closed=1
    GET /api/health

사용:
    python -m store.server                 # 127.0.0.1:8771
    python -m store.server --host 0.0.0.0
"""
from __future__ import annotations

import argparse
import json
import os
import sys as _sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path as _Path
from urllib.parse import parse_qs, urlparse

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from store import conn as store_conn  # noqa: E402

DEFAULT_PORT = 8771

# 한 요청이 통째로 DB 를 훑어가지 못하게 막는 상한.
MAX_LIMIT = 100
MAX_QUERY_CHARS = 200

_JOB_DETAIL = """
    SELECT s.job_id AS id, s.rrf, s.fts_rank, s.vec_rank,
           v.url, v.site, v.company, v.title,
           v.career_text AS career, v.location_text AS location, v.tech_stack
      FROM search_jobs(%(q)s, %(emb)s, %(n)s, %(closed)s) s
      JOIN v_job v ON v.id = s.job_id
     ORDER BY s.rrf DESC
"""

# Ollama 가 없을 때의 길. 벡터 없이 FTS 만으로 답한다.
_JOB_FTS_ONLY = """
    SELECT v.id, ts_rank_cd(j.search_tsv, websearch_to_tsquery('simple', %(q)s)) AS rrf,
           NULL::integer AS fts_rank, NULL::integer AS vec_rank,
           v.url, v.site, v.company, v.title,
           v.career_text AS career, v.location_text AS location, v.tech_stack
      FROM job j
      JOIN v_job v ON v.id = j.id
     WHERE (%(closed)s OR v.status = 'active')
       AND j.search_tsv @@ websearch_to_tsquery('simple', %(q)s)
     ORDER BY 2 DESC LIMIT %(n)s
"""

_POST_FTS = """
    SELECT p.id, ts_rank_cd(p.search_tsv, websearch_to_tsquery('simple', %(q)s)) AS rrf,
           NULL::integer AS fts_rank, NULL::integer AS vec_rank,
           p.url, 'post' AS site, COALESCE(c.display_name, p.blog_name) AS company,
           p.title, '' AS career, '' AS location, '{}'::text[] AS tech_stack
      FROM post p LEFT JOIN company c ON c.id = p.company_id
     WHERE p.search_tsv @@ websearch_to_tsquery('simple', %(q)s)
     ORDER BY 2 DESC LIMIT %(n)s
"""


def _query_embedding(text: str):
    """질의 임베딩. Ollama 가 없으면 None — 그때는 FTS 만으로 답한다."""
    try:
        from store.embed import embed_batch
        return embed_batch([text])[0]
    except Exception as e:
        print(f"[search] 벡터 건너뜀: {e}", file=_sys.stderr)
        return None


def search(query: str, *, kind: str = "job", limit: int = 20,
           include_closed: bool = False) -> dict:
    vec = _query_embedding(query) if kind == "job" else None
    params = {"q": query, "n": limit, "closed": include_closed}

    with store_conn.cursor(autocommit=True) as cur:
        if kind == "post":
            cur.execute(_POST_FTS, params)
        elif vec is None:
            cur.execute(_JOB_FTS_ONLY, params)
        else:
            cur.execute(_JOB_DETAIL, {**params, "emb": str(vec)})
        rows = cur.fetchall()

    results = [{
        "id": str(r["id"]),
        "url": r["url"],
        "site": r["site"],
        "company": r["company"] or "",
        "title": r["title"],
        "career": r["career"] or "",
        "location": r["location"] or "",
        "tech_stack": list(r["tech_stack"] or []),
        "score": round(float(r["rrf"]), 6),
        # 이 결과가 어느 쪽에서 왔는지 — 가중치를 조정할 때 근거가 된다.
        "rank_fts": r["fts_rank"],
        "rank_vec": r["vec_rank"],
    } for r in rows]

    return {
        "query": query,
        "kind": kind,
        "total": len(results),
        "engines": {
            "fts": sum(1 for r in results if r["rank_fts"] is not None) or len(results),
            "vector": sum(1 for r in results if r["rank_vec"] is not None),
        },
        "results": results,
    }


def health() -> dict:
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute("""
            SELECT (SELECT count(*) FROM job) AS jobs,
                   (SELECT count(*) FROM job_state WHERE status='active') AS active,
                   (SELECT count(*) FROM post) AS posts,
                   (SELECT count(*) FROM job_embedding) AS job_vectors,
                   (SELECT count(*) FROM job_embed_pending) AS job_pending,
                   (SELECT count(*) FROM post_embedding) AS post_vectors
        """)
        s = dict(cur.fetchone())
    # 벡터가 하나도 없으면 검색이 FTS 로만 돈다. 조용히 반쪽으로 도는 것보다
    # 건강 검사가 말해 주는 편이 낫다.
    s["vector_search"] = s["job_vectors"] > 0
    return s


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # 개발 중에는 뷰어(5173)와 API(8771)의 오리진이 다르다.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        # setup-dashboards.sh 의 기동 확인이 / 를 찌른다. 다른 서버들과 같이 200 을 준다.
        if parsed.path in ("/", "/api", "/api/"):
            self._send(200, {"ok": True, "service": "store-search",
                             "endpoints": ["/api/search?q=", "/api/health"]})
            return

        if parsed.path == "/api/health":
            try:
                self._send(200, {"ok": True, "stats": health()})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})
            return

        if parsed.path != "/api/search":
            self._send(404, {"error": "not found"})
            return

        query = (qs.get("q", [""])[0] or "").strip()[:MAX_QUERY_CHARS]
        if not query:
            self._send(400, {"error": "q 파라미터가 필요하다"})
            return
        kind = qs.get("kind", ["job"])[0]
        if kind not in ("job", "post"):
            self._send(400, {"error": "kind 는 job 또는 post"})
            return
        try:
            limit = min(int(qs.get("limit", ["20"])[0]), MAX_LIMIT)
        except ValueError:
            limit = 20
        closed = qs.get("include_closed", ["0"])[0] not in ("0", "", "false")

        try:
            self._send(200, search(query, kind=kind, limit=max(limit, 1),
                                   include_closed=closed))
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": repr(e)})

    def log_message(self, fmt: str, *args) -> None:
        _sys.stderr.write(f"[search] {self.address_string()} {fmt % args}\n")


def serve(host: str, port: int) -> None:
    st = health()
    print(f"[*] 정본 DB: {store_conn.dsn()}", flush=True)
    print(f"[*] 공고 {st['jobs']:,}건(모집중 {st['active']:,}) · 글 {st['posts']:,}건 · "
          f"벡터 {st['job_vectors']:,}개(대기 {st['job_pending']:,})", flush=True)
    if not st["vector_search"]:
        print("[!] 임베딩이 0건이라 검색이 FTS 로만 돈다. "
              "`python -m store.embed` 로 채울 것.", flush=True)
    print(f"[*] 검색 API: http://{host}:{port}/api/search?q=...", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


def main() -> int:
    ap = argparse.ArgumentParser(description="검색 API (정본 DB)")
    # SEARCH_HOST=0.0.0.0 으로 연다 — ops/stats 의 OPS_HOST·DASH_HOST 와 같은 규약이고,
    # setup-dashboards.sh 가 plist 에 이 이름으로 넣는다. 이걸 안 보면 launchd 로 뜬
    # 서버가 loopback 에만 붙어서, 뷰어 nginx 컨테이너가 host.docker.internal 로
    # 프록시하는 /api/ 가 전부 502 가 된다(semantic.server 는 이미 이렇게 읽는다).
    ap.add_argument("--host", default=os.environ.get("SEARCH_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    try:
        serve(args.host, args.port)
    except KeyboardInterrupt:
        print("\n[*] 종료", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
