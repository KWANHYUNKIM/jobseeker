#!/usr/bin/env python3
"""뷰어 상시 서빙 — dist/(빌드 셸) + public/*.json(live) 오버레이.

- 앱이 경로 라우팅(/jobs/wanted-364849 등)이라 SPA fallback 이 필요하다. 빌드가
  주소별 정적 HTML(dist/jobs/<id>/index.html)을 깔아 두므로 그게 있으면 그걸 주고,
  없으면 index.html 을 줘서 브라우저에서 라우터가 이어받게 한다.
- 데이터(.json)는 항상 live public/ 에서 읽어 자동 크롤 갱신을 재빌드 없이 반영.
- /api/ 는 하이브리드 검색 서버(semantic.server, 8771)로 넘긴다. 검색은 질의마다
  임베딩이 필요해 정적 파일로 만들 수 없다. 뷰어와 같은 오리진으로 묶어 CORS 를 없앤다.
- launchd 서비스로 상시 구동(부팅/크래시 시 자동 재시작).

실행: python3 serve_viewer.py   (포트: 환경변수 VIEWER_PORT, 기본 8137)
"""
import http.server
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # jd-viewer/
DIST = ROOT / "dist"
PUBLIC = ROOT / "public"
PORT = int(os.environ.get("VIEWER_PORT", "8137"))
HOST = os.environ.get("VIEWER_HOST", "127.0.0.1")  # 0.0.0.0 면 LAN/외부에서 IP로 접속 가능
SEARCH_API = os.environ.get("SEARCH_API", "http://127.0.0.1:8771")
# 질의 임베딩이 걸려 정적 응답보다 느리다. 그래도 무한정 붙잡고 있지는 않는다.
SEARCH_TIMEOUT = int(os.environ.get("SEARCH_TIMEOUT", "30"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler 규약)
        if self.path.startswith("/api/"):
            self._proxy_search()
            return
        super().do_GET()

    def _proxy_search(self) -> None:
        """검색 서버로 그대로 넘긴다.

        검색 서버가 없으면(미설치·정지) 502 를 돌려준다. 뷰어는 /api/health 실패를
        보고 의미 검색 UI 자체를 감추므로, 나머지 화면은 그대로 동작한다.
        """
        try:
            with urllib.request.urlopen(SEARCH_API + self.path, timeout=SEARCH_TIMEOUT) as r:
                body, status, ctype = r.read(), r.status, r.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as e:
            body, status, ctype = e.read(), e.code, "application/json; charset=utf-8"
        except Exception:
            body, status, ctype = b'{"error":"search unavailable"}', 502, "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def translate_path(self, path: str) -> str:
        # 퍼센트 인코딩을 먼저 푼다 — 회사 이름처럼 한글이 든 경로가 실제 파일명과
        # 맞아야 프리렌더된 HTML 이 잡힌다(nginx 도 같은 순서로 처리한다).
        rel = urllib.parse.unquote(path.split("?", 1)[0].split("#", 1)[0]).lstrip("/")
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
        # 프리렌더된 주소(dist/jobs/<id>/index.html). 디렉터리로 두면 기본 핸들러가
        # 끝에 슬래시를 붙이라고 301 을 내므로, 여기서 바로 파일을 가리킨다.
        if (dist / "index.html").is_file():
            return str(dist / "index.html")
        if pub.is_file():  # favicon 등 기타 public 자산
            return str(pub)
        # 확장자가 있는 요청은 진짜 없는 파일이다(404). 그 외는 라우터가 처리할
        # 앱 경로로 보고 셸을 돌려준다 — 새로고침·딥링크가 404 로 죽지 않게.
        if "." in os.path.basename(rel):
            return str(DIST / rel)
        return str(DIST / "index.html")

    def end_headers(self) -> None:
        path = self.path.split("?", 1)[0]
        # 데이터와 HTML 은 캐시하지 않는다. 해시가 박힌 /assets/ 만 오래 캐시해도 안전하다
        # (프리렌더된 HTML 을 브라우저가 오래 들고 있으면 공고가 갱신돼도 옛 내용이 보인다).
        if path.endswith(".json") or path.endswith(".html") or not os.path.splitext(path)[1]:
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        elif path.startswith("/assets/"):
            self.send_header("Cache-Control", "public, max-age=2592000, immutable")
        super().end_headers()

    def log_message(self, *args) -> None:  # 조용히
        pass


if __name__ == "__main__":
    os.chdir(DIST)
    httpd = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[viewer] serving {DIST} (+live {PUBLIC}/*.json) on {HOST}:{PORT}")
    httpd.serve_forever()
