"""뷰어 API(8771) — 앱 실행과 라우터 등록.

정본 DB(PostgreSQL)를 읽어 뷰어에 답한다. 쓰는 쪽은 크롤 파이프라인(catch_capture)이고
여기는 읽기만 한다. 기능별 코드는 `app/features/<기능>/` 에 있다.

실행:
    python -m app.main                       # 127.0.0.1:8771
    python -m app.main --host 0.0.0.0
    (문서: http://127.0.0.1:8771/api/docs)
"""
from __future__ import annotations

import argparse
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core import exceptions
from app.core.config import settings
from app.features.companies.router import router as companies_router
from app.features.docs.router import router as docs_router
from app.features.freelance.router import router as freelance_router
from app.features.hardware.router import router as hardware_router
from app.features.health.router import router as health_router
from app.features.jobs.router import router as jobs_router
from app.features.posts.router import router as posts_router
from app.features.search.router import router as search_router
from app.features.similar.router import router as similar_router

ROUTERS = [health_router, jobs_router, search_router, similar_router, companies_router,
           posts_router, freelance_router, hardware_router, docs_router]


def create_app() -> FastAPI:
    app = FastAPI(
        title="jobseeker 뷰어 API",
        description="정본 DB(PostgreSQL)를 읽어 뷰어에 답한다.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    # 개발 중에는 뷰어(5173)와 API(8771)의 오리진이 다르다. 운영은 nginx 가 /api/ 를
    # 같은 오리진으로 프록시한다. 읽기 전용 API 라 자격 증명은 받지 않는다.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])
    app.add_middleware(GZipMiddleware, minimum_size=2048)
    exceptions.install(app)
    for r in ROUTERS:
        app.include_router(r)

    @app.get("/", include_in_schema=False)
    @app.get("/api", include_in_schema=False)
    @app.get("/api/", include_in_schema=False)
    def root() -> dict:
        # setup-dashboards.sh 의 기동 확인이 / 를 찌른다.
        paths = sorted({route.path for r in ROUTERS for route in r.routes})
        return {"ok": True, "service": "jobseeker-api", "endpoints": paths + ["/api/docs"]}

    return app


app = create_app()


def run() -> int:
    ap = argparse.ArgumentParser(description="jobseeker 뷰어 API")
    ap.add_argument("--host", default=settings.host)
    ap.add_argument("--port", type=int, default=settings.port)
    ap.add_argument("--workers", type=int, default=settings.workers)
    args = ap.parse_args()

    import uvicorn

    from app.db.session import redacted_dsn
    from app.features.health.service import stats

    print(f"[*] 정본 DB: {redacted_dsn()}", flush=True)
    try:
        st = stats()
        print(f"[*] 공고 {st['jobs']:,}건(모집중 {st['active']:,}) · 글 {st['posts']:,}건 · "
              f"벡터 {st['job_vectors']:,}개(대기 {st['job_pending']:,}) · 필터 축 {st['job_facets']:,}건",
              flush=True)
        if not st["vector_search"]:
            print("[!] 임베딩이 0건이라 검색이 FTS 로만 돈다.", flush=True)
        if not st["job_facets"]:
            print("[!] job_facet 이 비어 있어 공고 목록이 0건이다. "
                  "catch_capture 에서 `python -m store.jobs.facets` 로 채울 것.", flush=True)
    except Exception as e:                                          # noqa: BLE001
        # 죽지 않는다 — DB 가 살아나면 그대로 답한다. 그동안 뷰어는 정적 파일로 물러선다.
        print(f"[!] 정본 DB 에 못 붙음({e}). 떠 있되 /api/* 는 503 을 돌려준다.", file=sys.stderr, flush=True)
    print(f"[*] 뷰어 API: http://{args.host}:{args.port}/api/jobs  (문서 /api/docs)", flush=True)
    uvicorn.run("app.main:app", host=args.host, port=args.port, workers=args.workers,
                log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
