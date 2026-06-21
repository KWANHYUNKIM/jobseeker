#!/usr/bin/env python3
"""뷰어 상시 서빙 — dist/(빌드 셸) + public/*.json(live) 오버레이.

- 앱이 해시 라우팅(/#calendar 등)이라 SPA fallback 불필요.
- 데이터(.json)는 항상 live public/ 에서 읽어 자동 크롤 갱신을 재빌드 없이 반영.
- launchd 서비스로 상시 구동(부팅/크래시 시 자동 재시작).

실행: python3 serve_viewer.py   (포트: 환경변수 VIEWER_PORT, 기본 8137)
"""
import http.server
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # jd-viewer/
DIST = ROOT / "dist"
PUBLIC = ROOT / "public"
PORT = int(os.environ.get("VIEWER_PORT", "8137"))
HOST = os.environ.get("VIEWER_HOST", "127.0.0.1")  # 0.0.0.0 면 LAN/외부에서 IP로 접속 가능


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        rel = path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if not rel:
            rel = "index.html"
        rel = os.path.normpath(rel).lstrip("/.")  # 경로 탈출 방지
        # 데이터 JSON 은 live public 우선
        pub = PUBLIC / rel
        if rel.endswith(".json") and pub.is_file():
            return str(pub)
        dist = DIST / rel
        if dist.is_file():
            return str(dist)
        if pub.is_file():  # favicon 등 기타 public 자산
            return str(pub)
        return str(DIST / rel)  # 없으면 404

    def end_headers(self) -> None:
        if self.path.endswith(".json"):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, *args) -> None:  # 조용히
        pass


if __name__ == "__main__":
    os.chdir(DIST)
    httpd = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[viewer] serving {DIST} (+live {PUBLIC}/*.json) on {HOST}:{PORT}")
    httpd.serve_forever()
