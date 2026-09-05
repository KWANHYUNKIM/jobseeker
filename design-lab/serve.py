"""디자인 랩 — 채용 상세페이지를 새로 짜기 전에 레퍼런스를 모아 두는 방.

기존 대시보드(8765)·크롤 운영(8770)·검색(8771)·관리자(8910) 와 완전히 분리된
기능이다. 여기서 만든 것이 확정되기 전까지는 jd-viewer 를 건드리지 않는다.

사용법:
    python design-lab/serve.py              # 8780
    python design-lab/serve.py --port 9100
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
from functools import partial
from pathlib import Path

LAB_DIR = Path(__file__).parent.resolve()
REFS_JSON = LAB_DIR / "refs.json"
DEFAULT_PORT = 8780


class Handler(http.server.SimpleHTTPRequestHandler):
    """static/ 을 루트로 서빙하되, /refs/ 와 /api/refs.json 만 따로 받는다."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(LAB_DIR / "static"), **kwargs)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/refs"):
            return self._send_json(REFS_JSON)
        if self.path.startswith("/refs/"):
            # 이미지 원본. static 바깥이라 경로를 직접 푼다.
            rel = self.path[len("/refs/"):].split("?")[0]
            target = (LAB_DIR / "refs" / rel).resolve()
            if LAB_DIR / "refs" not in target.parents and target != LAB_DIR / "refs":
                self.send_error(403)
                return None
            if not target.is_file():
                self.send_error(404)
                return None
            return self._send_file(target)
        return super().do_GET()

    def _send_json(self, path: Path):
        if not path.is_file():
            self.send_error(404, "refs.json 이 없습니다")
            return None
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")  # 수집 중에는 늘 최신을 본다
        self.end_headers()
        self.wfile.write(body)
        return None

    def _send_file(self, path: Path):
        body = path.read_bytes()
        ctype = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp",
            ".md": "text/markdown; charset=utf-8",
        }.get(path.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return None

    def log_message(self, fmt, *args):
        pass  # 접근 로그는 필요 없다


def count_refs() -> int:
    if not REFS_JSON.is_file():
        return 0
    return len(json.loads(REFS_JSON.read_text(encoding="utf-8")).get("refs", []))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", args.port), Handler) as httpd:
        print(f"[design-lab] 레퍼런스 {count_refs()}건")
        print(f"[design-lab] http://localhost:{args.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[design-lab] 종료")


if __name__ == "__main__":
    main()
