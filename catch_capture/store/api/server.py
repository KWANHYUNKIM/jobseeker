"""뷰어 API 서버 진입점(8771) — 앱 본체는 `store/api/main.py`(FastAPI)다.

예전에는 여기가 표준 라이브러리 http.server 로 검색 하나(`/api/search`)만 답했다.
공고 목록·상세까지 DB 에서 답하게 되면서(엔드포인트가 늘고 질의 파라미터 검증이
필요해졌다) FastAPI 로 옮겼다. 실행 명령은 그대로라 launchd·setup-dashboards.sh 는
고칠 데가 없다.

**`/api/search` 응답 형식은 한 글자도 바뀌지 않았다.** 뷰어(`useHybridSearch.ts`)가
읽는 `{query, kind, total, engines, results:[…]}` 그대로다.

사용:
    python -m store.api.server                 # 127.0.0.1:8771
    python -m store.api.server --host 0.0.0.0
    (문서: http://127.0.0.1:8771/api/docs)
"""
from __future__ import annotations

import argparse
import os
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))

from store.db import conn as store_conn  # noqa: E402

DEFAULT_PORT = 8771


def main() -> int:
    ap = argparse.ArgumentParser(description="뷰어 API (정본 DB)")
    # SEARCH_HOST=0.0.0.0 으로 연다 — ops/stats 의 OPS_HOST·DASH_HOST 와 같은 규약이고,
    # setup-dashboards.sh 가 plist 에 이 이름으로 넣는다. 이걸 안 보면 launchd 로 뜬
    # 서버가 loopback 에만 붙어서, 뷰어 nginx 컨테이너가 host.docker.internal 로
    # 프록시하는 /api/ 가 전부 502 가 된다.
    ap.add_argument("--host", default=os.environ.get("SEARCH_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("API_WORKERS", "1")))
    args = ap.parse_args()

    import uvicorn
    from store.api.main import health

    # 기동하자마자 DB 를 친다 — 못 붙으면 여기서 죽어야 setup-dashboards.sh 가
    # 옛 SQLite 판(semantic.server)으로 되돌린다.
    st = health()
    print(f"[*] 정본 DB: {store_conn.dsn()}", flush=True)
    print(f"[*] 공고 {st['jobs']:,}건(모집중 {st['active']:,}) · 글 {st['posts']:,}건 · "
          f"벡터 {st['job_vectors']:,}개(대기 {st['job_pending']:,}) · 필터 축 {st['job_facets']:,}건",
          flush=True)
    if not st["vector_search"]:
        print("[!] 임베딩이 0건이라 검색이 FTS 로만 돈다. `python -m store.vectors.embed` 로 채울 것.",
              flush=True)
    if not st["job_facets"]:
        print("[!] job_facet 이 비어 있어 공고 목록이 0건이다. `python -m store.jobs.facets` 로 채울 것.",
              flush=True)
    print(f"[*] 뷰어 API: http://{args.host}:{args.port}/api/jobs  (문서 /api/docs)", flush=True)
    uvicorn.run("store.api.main:app", host=args.host, port=args.port, workers=args.workers,
                log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
