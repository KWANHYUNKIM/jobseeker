"""행동 기록 수집기 — 뷰어가 보낸 클릭·체류 이벤트를 받아 적는다.

포트는 8772 다. 이 프로젝트의 로컬 서버 배치는
    8765 stats(통계) / 8770 ops(크롤 운영) / 8771 search(검색) / 8910 admin(개인 이력)
이고 여기에 8772 collect 가 붙는다. 뷰어 nginx 가 `/collect` 를 여기로 넘긴다.

**무엇을 적는가.** 세션 난수, 사건 종류, 대상 키, 어디서 왔는지, 머문 초. 그게 전부다.
이름·이메일·IP·User-Agent 는 받지도 적지도 않는다. 알고 싶은 것은 '누구'가 아니라
'어떤 공고가 다음 공고를 부르는가' 이고, 그건 익명 세션만으로 답할 수 있다.
개인을 식별할 수 있는 것을 안 적으면 유출될 것도 없다.

**받아 적기만 한다.** 집계·점수는 engagement.score 가 따로 한다. 수집기는 쓰기만
하므로 크롤 사이클이 돌든 말든 상관없이 항상 응답할 수 있어야 한다 — 여기서 뭘
계산하기 시작하면 느려지고, 느려지면 브라우저가 이벤트를 버린다.

사용법:
    python -m engagement.collect                    # 127.0.0.1:8772
    python -m engagement.collect --port 8772 --host 0.0.0.0
    python -m engagement.collect --stats            # 쌓인 것 요약만 보고 끝
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import argparse
import json
import socketserver
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EVENTS = BASE_DIR / "events.jsonl"

DEFAULT_PORT = 8772
MAX_BODY = 64 * 1024        # 한 요청 상한. 이보다 크면 우리가 보낸 게 아니다.
MAX_EVENTS = 200            # 한 요청에 담을 수 있는 사건 수
MAX_FIELD = 400             # 키·출처 문자열 길이 상한 (URL 이 들어온다)
MAX_DWELL = 3600            # 1시간 넘는 체류는 창을 띄워 둔 것이지 본 게 아니다
ROTATE_BYTES = 64 * 1024 * 1024

# 받아들이는 사건 종류. 모르는 종류는 버린다 — 스키마가 조용히 늘어나면
# 나중에 집계하는 쪽에서 무엇이 무엇인지 아무도 모르게 된다.
KINDS = {"session", "view", "click", "dwell", "search", "filter"}


def _rotate_if_big() -> None:
    try:
        if EVENTS.exists() and EVENTS.stat().st_size > ROTATE_BYTES:
            EVENTS.replace(EVENTS.with_suffix(".jsonl.1"))
    except OSError:
        pass


MAX_SKEW = 24 * 3600     # 브라우저 시계가 이보다 어긋나면 상대 간격을 믿지 않는다


def _clean(raw: dict, sid: str, at: float) -> dict | None:
    """브라우저가 보낸 한 건을 신뢰할 수 있는 모양으로 줄인다. 아니면 None."""
    kind = str(raw.get("t") or "")[:20]
    if kind not in KINDS:
        return None
    rec: dict = {"sid": sid, "t": kind, "ts": round(at, 3)}
    key = raw.get("k")
    if key:
        rec["k"] = str(key)[:MAX_FIELD]
    src = raw.get("from")
    if src:
        rec["from"] = str(src)[:MAX_FIELD]
    if kind == "dwell":
        try:
            secs = int(raw.get("s") or 0)
        except (TypeError, ValueError):
            return None
        if secs < 1 or secs > MAX_DWELL:
            return None
        rec["s"] = secs
    return rec


def _timeline(events: list, now: float) -> list[float]:
    """각 사건이 '실제로 일어난' 시각을 서버 시계 위에 놓는다.

    이벤트는 10초마다, 또는 페이지를 떠날 때 **묶여서** 온다. 받은 시각을 그대로
    쓰면 한 묶음이 전부 같은 시각이 되고, 그러면 세션이 얼마나 이어졌는지가 통째로
    사라진다 — 체류시간을 보려고 만든 것이 정작 체류시간을 못 재게 된다.

    그래서 브라우저가 붙인 상대 간격은 살리되 기준점만 서버 시계로 잡는다. 절대
    시각을 브라우저 말대로 믿으면 시계가 틀어진 기기 하나가 집계를 흔든다.
    간격이 말이 안 되면(하루 이상) 그 묶음은 간격을 포기하고 받은 시각으로 둔다.
    """
    stamps: list[float | None] = []
    for raw in events:
        v = raw.get("ts") if isinstance(raw, dict) else None
        stamps.append(float(v) / 1000.0 if isinstance(v, (int, float)) and v > 0 else None)
    known = [x for x in stamps if x is not None]
    if not known:
        return [now] * len(events)
    latest, earliest = max(known), min(known)
    if latest - earliest > MAX_SKEW:
        return [now] * len(events)
    return [now - (latest - x) if x is not None else now for x in stamps]


def append(sid: str, events: list, now: float | None = None) -> int:
    """정제해서 append. 실제로 적은 건수를 돌려준다."""
    now = now if now is not None else time.time()
    events = events[:MAX_EVENTS]
    at = _timeline(events, now)
    lines = []
    for raw, when in zip(events, at):
        if not isinstance(raw, dict):
            continue
        rec = _clean(raw, sid, when)
        if rec:
            lines.append(json.dumps(rec, ensure_ascii=False))
    if not lines:
        return 0
    _rotate_if_big()
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return len(lines)


def stats() -> dict:
    """쌓인 것 요약. /health 와 --stats 가 같이 쓴다."""
    if not EVENTS.exists():
        return {"events": 0, "bytes": 0, "sessions": 0, "since": None}
    kinds: dict[str, int] = {}
    sids: set[str] = set()
    first = None
    n = 0
    try:
        with EVENTS.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                n += 1
                kinds[r.get("t", "?")] = kinds.get(r.get("t", "?"), 0) + 1
                if r.get("sid"):
                    sids.add(r["sid"])
                if first is None:
                    first = r.get("ts")
    except OSError:
        pass
    return {
        "events": n,
        "bytes": EVENTS.stat().st_size,
        "sessions": len(sids),
        "kinds": kinds,
        "since": datetime.fromtimestamp(first).isoformat(timespec="seconds") if first else None,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "jobseeker-collect"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        """접속 로그를 남기지 않는다.

        기본 구현은 요청마다 클라이언트 IP 를 stderr 에 적는다. 본문에서 IP 를
        빼 놓고 로그로 흘리면 아무 의미가 없다.
        """

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass  # 페이지를 떠나며 보낸 beacon 은 응답을 안 기다린다

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", "/collect/health"):
            self._send(200, {"ok": True, **stats()})
            return
        self._send(404, {"ok": False})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") not in ("/collect", ""):
            self._send(404, {"ok": False})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._send(413, {"ok": False})
            return
        try:
            doc = json.loads(self.rfile.read(length).decode("utf-8", "replace"))
        except (json.JSONDecodeError, OSError):
            self._send(400, {"ok": False})
            return
        if not isinstance(doc, dict):
            self._send(400, {"ok": False})
            return
        sid = str(doc.get("sid") or "")[:40]
        events = doc.get("events")
        if not sid or not isinstance(events, list):
            self._send(400, {"ok": False})
            return
        try:
            n = append(sid, events)
        except OSError as e:
            self._send(500, {"ok": False, "error": str(e)[:120]})
            return
        self._send(200, {"ok": True, "n": n})


class Server(socketserver.ThreadingTCPServer):
    # 브라우저가 여러 탭에서 동시에 보낸다. 한 건이 느려도 나머지가 밀리면 안 된다.
    daemon_threads = True
    allow_reuse_address = True


def serve(host: str, port: int) -> None:
    with Server((host, port), Handler) as httpd:
        print(f"[*] 행동 수집 서버: http://{host}:{port}/  (POST /collect)", flush=True)
        print(f"[*] 저장: {EVENTS}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[*] 종료", flush=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="행동 기록 수집 서버")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--stats", action="store_true", help="쌓인 것만 요약하고 끝낸다")
    args = ap.parse_args(argv)
    if args.stats:
        s = stats()
        print(f"이벤트 {s['events']:,}건 · 세션 {s['sessions']:,}개 · "
              f"{s['bytes']:,} bytes · 시작 {s['since'] or '-'}")
        for k, v in sorted((s.get("kinds") or {}).items(), key=lambda kv: -kv[1]):
            print(f"  {k:8s} {v:,}")
        return 0
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
