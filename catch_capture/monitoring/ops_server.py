"""크롤 오케스트레이션 실시간 운영 대시보드 서버.

정적 페이지(monitoring/ops_dashboard/)와 라이브 상태 JSON 을 함께 서빙한다.
프런트는 아래 엔드포인트를 폴링해 '지금 파이프라인이 뭘 하는지'를 실시간 표시한다.

  GET /                → ops_dashboard/index.html
  GET /app.js, /styles.css
  GET /api/state       → run_state.json + 데몬 생존여부(auto_crawl.pid 기준)
  GET /api/events?n=N  → run_events.jsonl 최근 N줄 (기본 80)
  GET /api/health?n=N  → health_history.jsonl 최근 N줄 (기본 30)

사용법:
    python -m monitoring.ops_server            # 8770 포트
    python monitoring/ops_server.py --port 9100
    python monitoring/ops_server.py --no-open  # 브라우저 자동 오픈 안 함
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import argparse
import http.server
import json
import os
import socketserver
import webbrowser
from pathlib import Path

CATCH_DIR = Path(__file__).resolve().parent.parent     # catch_capture/
OPS_DIR = Path(__file__).resolve().parent / "ops_dashboard"
STATE_FILE = CATCH_DIR / "run_state.json"
EVENTS_FILE = CATCH_DIR / "run_events.jsonl"
HEALTH_HISTORY = CATCH_DIR / "health_history.jsonl"
HEALTH_LATEST = CATCH_DIR / "health_latest.json"
PID_FILE = CATCH_DIR / "auto_crawl.pid"

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _daemon_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        return None
    return pid if _process_alive(pid) else None


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tail_jsonl(path: Path, n: int) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
    except Exception:
        return []
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):  # 콘솔 소음 억제
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj) -> None:
        self._send(200, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _query_int(self, qs: str, key: str, default: int) -> int:
        for part in qs.split("&"):
            if part.startswith(key + "="):
                try:
                    return int(part.split("=", 1)[1])
                except ValueError:
                    return default
        return default

    def do_GET(self) -> None:
        path, _, qs = self.path.partition("?")

        if path in STATIC:
            fname, ctype = STATIC[path]
            fp = OPS_DIR / fname
            if not fp.exists():
                self._send(404, b"not found", "text/plain")
                return
            self._send(200, fp.read_bytes(), ctype)
            return

        if path == "/api/state":
            state = _read_json(STATE_FILE)
            pid = _daemon_pid()
            state["daemon_alive"] = pid is not None
            state["daemon_pid"] = pid
            state["health_latest"] = _read_json(HEALTH_LATEST)
            self._send_json(state)
            return

        if path == "/api/events":
            n = self._query_int(qs, "n", 80)
            self._send_json(_tail_jsonl(EVENTS_FILE, n))
            return

        if path == "/api/health":
            n = self._query_int(qs, "n", 30)
            self._send_json(_tail_jsonl(HEALTH_HISTORY, n))
            return

        self._send(404, b"not found", "text/plain")


def serve(port: int, open_browser: bool) -> None:
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        print(f"[*] 오케스트레이션 대시보드: {url}", flush=True)
        print("[*] Ctrl+C 로 종료", flush=True)
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[*] 종료", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    serve(args.port, not args.no_open)


if __name__ == "__main__":
    main()
