#!/usr/bin/env python3
"""뷰어 상시 서빙 — dist/(빌드 셸) + public/*.json(live) 오버레이.

- 앱이 경로 라우팅(/jobs/wanted-364849 등)이라 SPA fallback 이 필요하다. 빌드가
  주소별 정적 HTML(dist/jobs/<id>/index.html)을 깔아 두므로 그게 있으면 그걸 주고,
  없으면 index.html 을 줘서 브라우저에서 라우터가 이어받게 한다.
- 데이터(.json)는 항상 live public/ 에서 읽어 자동 크롤 갱신을 재빌드 없이 반영.
- /api/ 는 뷰어 API(backend, 8771)로 넘긴다. 뷰어와 같은 오리진으로 묶어 CORS 를 없앤다.
- launchd 서비스로 상시 구동(부팅/크래시 시 자동 재시작).

실행: python3 serve_viewer.py   (포트: 환경변수 VIEWER_PORT, 기본 8137)
"""
import http.server
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # jd-viewer/
DIST = Path(os.environ.get("VIEWER_DIST", ROOT / "dist"))  # 시험 빌드를 띄울 때만 바꾼다
PUBLIC = ROOT / "public"
PORT = int(os.environ.get("VIEWER_PORT", "8137"))
HOST = os.environ.get("VIEWER_HOST", "127.0.0.1")  # 0.0.0.0 면 LAN/외부에서 IP로 접속 가능
SEARCH_API = os.environ.get("SEARCH_API", "http://127.0.0.1:8771")
# 질의 임베딩이 걸려 정적 응답보다 느리다. 그래도 무한정 붙잡고 있지는 않는다.
SEARCH_TIMEOUT = int(os.environ.get("SEARCH_TIMEOUT", "30"))

# 보안 헤더는 nginx 와 같은 파일에서 읽는다(security-headers.conf 가 원본) — 둘이 따로 놀면
# 도커 배포와 이 맥(ngrok 이 외부에 여는 것)의 방어가 달라진다.
_HEADER_LINE = re.compile(r'^\s*add_header\s+([A-Za-z-]+)\s+"([^"]*)"\s+always;\s*$')


def _security_headers() -> list[tuple[str, str]]:
    out = []
    for line in (ROOT / "security-headers.conf").read_text(encoding="utf-8").splitlines():
        m = _HEADER_LINE.match(line)
        if m:
            out.append((m.group(1), m.group(2)))
    if not out:
        raise SystemExit("[viewer] security-headers.conf 에서 헤더를 하나도 못 읽었다 — 보안 헤더 없이 뜨지 않는다")
    return out


SECURITY_HEADERS = _security_headers()
# 뷰어 API 중 밖에 열 이유가 없는 것 — FastAPI 의 자동 문서(엔드포인트 목록). 화면이 쓰는
# /api/docs/<경로>(엔진 문서)는 막지 않는다. 정확히 이 주소만 막는다.
API_BLOCKED = {"/api/docs", "/api/docs/", "/api/openapi.json", "/api/redoc"}


class Handler(http.server.SimpleHTTPRequestHandler):
    # 응답에 서버 종류·파이썬 버전을 싣지 않는다(기본은 'SimpleHTTP/0.6 Python/3.x')
    server_version = "jd-viewer"
    sys_version = ""

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler 규약)
        if self.path.startswith("/api/"):
            if self.path.split("?", 1)[0] in API_BLOCKED:
                self.send_error(404)
                return
            self._proxy_search()
            return
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self.send_error(405)
            return
        super().do_HEAD()

    def list_directory(self, path):  # 폴더 목록은 절대 내보내지 않는다
        self.send_error(404)
        return None

    def _proxy_search(self) -> None:
        """검색 서버로 그대로 넘긴다.

        검색 서버가 없으면(미설치·정지) 502 를 돌려준다. 뷰어는 /api/health 실패를
        보고 의미 검색 UI 자체를 감추므로, 나머지 화면은 그대로 동작한다.
        """
        # 경로는 /api/ 로 시작하는 것만 여기 오고, 붙일 곳(SEARCH_API)은 고정이다 — 요청이 다른 호스트로
        # 새 나갈 수 없다. 제어 문자·공백이 든 주소는 넘기지 않는다(헤더 주입·요청 분할 방지).
        if re.search(r"[\x00-\x20\x7f]", self.path) or len(self.path) > 2048:
            self.send_error(400)
            return
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
        # 점으로 시작하는 이름(.env·.git 따위)은 어디에 있든 내주지 않는다
        if any(part.startswith(".") for part in rel.split(os.sep)):
            return str(DIST / ".__denied__")
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
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)
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
