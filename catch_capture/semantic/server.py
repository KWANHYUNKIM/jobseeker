"""검색 API 서버 — 뷰어가 하이브리드 검색을 부를 수 있게 하는 최소 HTTP 계층.

뷰어는 정적 JSON 소비가 원칙이지만 검색만은 그럴 수 없다. 질의마다 임베딩이
필요하고, 그건 Ollama 가 있는 호스트에서만 가능하다. 그래서 이 서버는 크롤러와
같은 자리(호스트 네이티브)에 산다 — semantic.db 와 Ollama 를 둘 다 붙잡을 수 있는
유일한 위치다.

표준 라이브러리만 쓴다. 검색 한 종류를 위해 웹 프레임워크를 들이면 배포에서
의존성·컨테이너·버전을 새로 관리해야 하는데, 그만한 일이 아니다.

    GET /api/search?q=재택+백엔드&kind=job&limit=20&career=5-7년&location=서울
    GET /api/health

사용법:
    python -m semantic.server                 # 127.0.0.1:8771
    python -m semantic.server --port 8771 --host 0.0.0.0

포트는 8771 이다. 이 프로젝트의 로컬 서버 배치는
    8765 stats(통계) / 8770 ops(크롤 운영) / 8910 admin(개인 이력) / 8771 search
로 나뉘어 있다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import db as dbm
from . import search as ssearch

DEFAULT_PORT = 8771

# 한 요청이 통째로 DB 를 훑어가지 못하게 막는 상한.
MAX_LIMIT = 100
MAX_QUERY_CHARS = 200

# SQLite 커넥션은 만든 스레드에서만 쓸 수 있다. ThreadingHTTPServer 는 요청마다
# 스레드를 만드므로 스레드로컬에 커넥션을 붙여 재사용한다.
_local = threading.local()


def _conn():
    c = getattr(_local, "conn", None)
    if c is None:
        c = _local.conn = dbm.connect()
    return c


def _first(qs: dict, key: str, default: str = "") -> str:
    v = qs.get(key)
    return v[0].strip() if v and v[0] else default


def build_filters(qs: dict) -> dict:
    filters: dict = {}
    if careers := [c for c in qs.get("career", []) if c.strip()]:
        filters["careers"] = set(careers)
    if sites := [s for s in qs.get("site", []) if s.strip()]:
        filters["sites"] = set(sites)
    if stacks := [s for s in qs.get("stack", []) if s.strip()]:
        filters["stacks"] = stacks
    if loc := _first(qs, "location"):
        filters["location"] = loc
    overseas = _first(qs, "overseas")
    if overseas in ("0", "1", "true", "false"):
        filters["overseas"] = overseas in ("1", "true")
    return filters


class Handler(BaseHTTPRequestHandler):
    server_version = "jobseeker-semantic/1.0"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # 개발 중에는 뷰어(5173)와 오리진이 다르다. 읽기 전용 공개 데이터라 * 로 둔다.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler 규약)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        # setup-dashboards.sh 의 기동 확인이 / 를 찌른다. 다른 서버들과 같이 200 을 준다.
        if parsed.path in ("/", "/api", "/api/"):
            self._send(200, {"ok": True, "service": "semantic-search",
                             "endpoints": ["/api/search?q=", "/api/health"]})
            return

        if parsed.path == "/api/health":
            try:
                stats = dbm.stats(_conn())
                self._send(200, {"ok": True, "stats": stats})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})
            return

        if parsed.path != "/api/search":
            self._send(404, {"error": "not found"})
            return

        query = _first(qs, "q")[:MAX_QUERY_CHARS]
        if not query:
            self._send(400, {"error": "q 파라미터가 필요하다"})
            return

        kind = _first(qs, "kind", "job")
        if kind not in ("job", "post"):
            self._send(400, {"error": "kind 는 job 또는 post"})
            return
        try:
            limit = min(int(_first(qs, "limit", "20")), MAX_LIMIT)
        except ValueError:
            limit = 20

        try:
            out = ssearch.search(_conn(), query, kind=kind, limit=max(limit, 1),
                                 filters=build_filters(qs))
            self._send(200, out)
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": repr(e)})

    def log_message(self, fmt: str, *args) -> None:
        # 기본 구현은 stderr 로 매 요청을 찍는다. 형식만 통일해 둔다.
        sys.stderr.write(f"[search] {self.address_string()} {fmt % args}\n")


def serve(host: str, port: int) -> None:
    # 스키마 생성·FTS 최초 색인은 여기서 한 번만. 요청 경로에서는 connect 만 한다.
    dbm.open_db().close()
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"[*] 검색 API: http://{host}:{port}/api/search?q=...", flush=True)
    print("[*] Ctrl+C 로 종료", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] 종료", flush=True)
    finally:
        httpd.server_close()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="하이브리드 검색 API")
    # 기본은 loopback. nginx 컨테이너가 host.docker.internal 로 붙는 배포에서는
    # SEARCH_HOST=0.0.0.0 으로 연다 — ops/stats 대시보드의 OPS_HOST·DASH_HOST 와 같은 규약.
    ap.add_argument("--host", default=os.environ.get("SEARCH_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args(argv)
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":  # python -m semantic.server
    sys.exit(main(sys.argv[1:]))
