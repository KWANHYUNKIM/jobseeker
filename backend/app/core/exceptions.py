"""공통 예외 처리.

DB 에 못 붙는 동안에도 서버는 떠 있는다 — 예전에는 기동 때 DB 를 쳐서 죽었고,
그러면 setup-dashboards.sh 가 옛 SQLite 판으로 되돌렸다. 지금은 503 을 돌려주고,
뷰어는 `/api/jobs` 확인이 실패하면 정적 파일로 물러선다. DB 가 살아나면 서버를
다시 등록하지 않아도 그대로 답한다.
"""
from __future__ import annotations

import sys

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class NotFound(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BadRequest(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def install(app: FastAPI) -> None:
    @app.exception_handler(NotFound)
    async def _not_found(_: Request, e: NotFound) -> JSONResponse:
        return JSONResponse({"detail": {"error": e.message}}, status_code=404)

    @app.exception_handler(BadRequest)
    async def _bad_request(_: Request, e: BadRequest) -> JSONResponse:
        return JSONResponse({"detail": {"error": e.message}}, status_code=400)

    @app.exception_handler(psycopg.OperationalError)
    async def _db_down(_: Request, e: psycopg.OperationalError) -> JSONResponse:
        print(f"[db] 접속 실패: {e}", file=sys.stderr)
        return JSONResponse({"ok": False, "error": "정본 DB 에 접속할 수 없다"}, status_code=503)
