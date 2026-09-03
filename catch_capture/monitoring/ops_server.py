"""크롤 오케스트레이션 실시간 운영 대시보드 서버.

정적 페이지(monitoring/ops_dashboard/)와 라이브 상태 JSON 을 함께 서빙한다.
프런트는 아래 엔드포인트를 폴링해 '지금 파이프라인이 뭘 하는지'를 실시간 표시한다.

  GET /                → ops_dashboard/index.html
  GET /app.js, /styles.css
  GET /api/state       → run_state.json + 데몬 생존여부(auto_crawl.pid 기준)
  GET /api/events?n=N  → run_events.jsonl 최근 N줄 (기본 80)
  GET /api/health?n=N  → health_history.jsonl 최근 N줄 (기본 30)
  GET /api/engagement  → public/engagement.json (방문·유입·행동 점수)

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
import time
import webbrowser
from datetime import datetime
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


# 하트비트 기준 — 프로세스가 살아만 있는 게 아니라 "실제로 진행 중"인지 판단한다.
WAITING_GRACE = 600    # 대기 종료 예정(next_run_at)을 이만큼 넘기면 지연으로 본다
CRAWL_STALL = 1200     # 크롤/통합 등 작업 단계에서 이 시간 이상 갱신 없으면 멈춤(hang) 의심


def _parse_iso(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except Exception:
        return None


def _daemon_health(state: dict, alive: bool) -> tuple[str, int | None]:
    """살아있음(os.kill) 너머로 '진행 중'인지까지 본다 → ok / stalled / stopped.

    - 죽었으면 stopped.
    - 대기 단계: 다음 크롤 예정 시각(next_run_at)을 유예시간 이상 넘기면 stalled.
    - 작업 단계: 마지막 갱신(updated_at)이 너무 오래되면 hang 으로 보고 stalled.
    PID 재사용으로 죽은 데몬이 alive 로 오판돼도, 갱신이 멈춰 stalled 로 잡힌다.
    """
    if not alive:
        return "stopped", None
    now = datetime.now()
    phase = state.get("phase") or ""
    if phase in ("waiting", "idle"):
        nxt = _parse_iso(state.get("next_run_at"))
        if nxt:
            overdue = int((now - nxt).total_seconds())
            if overdue > WAITING_GRACE:
                return "stalled", overdue
        return "ok", 0
    updated = _parse_iso(state.get("updated_at"))
    if updated:
        idle = int((now - updated).total_seconds())
        return ("stalled" if idle > CRAWL_STALL else "ok"), idle
    return "ok", None


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

    def do_GET(self) -> None:  # noqa: D102
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
            health, stale = _daemon_health(state, pid is not None)
            state["daemon_health"] = health        # ok | stalled | stopped
            state["daemon_stale_sec"] = stale       # 마지막 진행 이후 경과(초)
            state["health_latest"] = _read_json(HEALTH_LATEST)
            self._send_json(state)
            return

        if path == "/api/events":
            n = self._query_int(qs, "n", 80)
            self._send_json(_tail_jsonl(EVENTS_FILE, n))
            return

        if path == "/api/engagement":
            # 방문자가 만든 유일한 데이터다. 크롤 상태와 달리 여기가 비어 있으면
            # '아직 아무도 안 왔다'와 '수집 서버가 안 떴다'를 구분해야 하므로
            # 파일이 없을 때 null 을 그대로 돌려준다(프런트가 안내를 띄운다).
            self._send_json(_read_json(VIEWER_PUBLIC / "engagement.json"))
            return

        if path == "/api/builders":
            self._send_json(_builder_outputs())
            return

        if path == "/api/autoguide":
            self._send_json(_autoguide_summary())
            return

        if path == "/api/health":
            n = self._query_int(qs, "n", 30)
            self._send_json(_tail_jsonl(HEALTH_HISTORY, n))
            return

        self._send(404, b"not found", "text/plain")


# 뷰어가 실제로 읽는 산출물. 사이클 상태(run_state)만 보면 데몬이 멈춘 뒤로는 아무것도
# 알 수 없다 — 화면은 며칠 전 JSON 을 그대로 잘 보여주기 때문이다. 파일 자체의 수정
# 시각을 함께 내보내야 "이 화면은 지금 며칠째 옛날 데이터" 가 드러난다.
BUILDER_OUTPUTS = [
    ("모집 캘린더", "job_calendar.json"),
    ("개발 트렌드", "trends.json"),
    ("기술 관계", "tech_relations.json"),
    ("재공고 추적", "reposts.json"),
    ("커리어 맵", "career_map.json"),
    ("블로그 가이드", "blog_guides.json"),
    ("인프런 강의", "inflearn_courses.json"),
    ("학습 영상", "learning_resources.json"),
    ("기업 스택", "company_stacks.json"),
    ("직군 인사이트", "role_insights.json"),
    ("행동 점수", "engagement.json"),
]
VIEWER_PUBLIC = CATCH_DIR.parent / "jd-viewer" / "public"


# 자동 브리핑(guide-engine/autoguide.py)은 크롤 산출물에서 기계가 확정할 수 있는
# 것만 뽑아 쌓는다. 사이클 산출물과 달리 손으로 돌리므로, 여기서 보여줘야 할 것은
# "몇 건 나왔나" 보다 **언제 돌렸나** — 공고는 매 사이클 바뀌는데 이건 안 바뀐다.
# index.json 은 뷰어 조회용(slug·aliases)이라 집계가 없다. 대시보드는 stats.json 을 본다.
AUTOGUIDE_INDEX = CATCH_DIR.parent / "jd-viewer" / "public" / "guide" / "auto" / "stats.json"
AUTOGUIDE_TOP = 12


def _autoguide_summary() -> dict:
    if not AUTOGUIDE_INDEX.exists():
        return {"exists": False}
    st = AUTOGUIDE_INDEX.stat()
    doc = _read_json(AUTOGUIDE_INDEX)
    cos = doc.get("companies", []) or []

    def total(key: str) -> int:
        return sum((c.get("counts") or {}).get(key, 0) for c in cos)

    return {
        "exists": True,
        "age_sec": int(time.time() - st.st_mtime),
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        "generator": doc.get("generator", ""),
        "updated_at": doc.get("updated_at", ""),
        "companies": len(cos),
        "postings": total("postings"),
        "active": total("active"),
        "distinct_active": total("distinct_active"),
        "with_body": total("with_body"),
        "with_facts": sum(1 for c in cos if c.get("has_facts")),
        "with_salary": sum(1 for c in cos if c.get("has_salary")),
        "top": [{
            "name": c.get("name", ""), "slug": c.get("slug", ""),
            "active": (c.get("counts") or {}).get("active", 0),
            "distinct": (c.get("counts") or {}).get("distinct_active", 0),
            "body": (c.get("counts") or {}).get("with_body", 0),
            "facts": bool(c.get("has_facts")), "salary": bool(c.get("has_salary")),
        } for c in cos[:AUTOGUIDE_TOP]],
    }


def _builder_outputs() -> list[dict]:
    out = []
    now = time.time()
    for label, fname in BUILDER_OUTPUTS:
        fp = VIEWER_PUBLIC / fname
        if fp.exists():
            st = fp.stat()
            out.append({
                "name": label, "file": fname, "exists": True,
                "size": st.st_size, "age_sec": int(now - st.st_mtime),
                "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            })
        else:
            out.append({"name": label, "file": fname, "exists": False})
    return out


def serve(port: int, open_browser: bool) -> None:
    # 기본은 loopback(안전). 터널 컨테이너가 host.docker.internal 로 붙어야 하는
    # 배포에서는 OPS_HOST=0.0.0.0 으로 열어준다.
    host = os.environ.get("OPS_HOST", "127.0.0.1")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((host, port), Handler) as httpd:
        url = f"http://{host}:{port}/"
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
