"""디자인 랩 — 레퍼런스 열람 / 포스터 렌더 / 소셜 발행을 한 화면에서 굴린다.

기존 대시보드(8765)·크롤 운영(8770)·검색(8771)·관리자(8910) 와 완전히 분리된
기능이다. 여기서 만든 것이 확정되기 전까지는 jd-viewer 를 건드리지 않는다.

무거운 일(크로미움 렌더, 실제 발행)은 이 프로세스에서 하지 않고 CLI 를 자식
프로세스로 부른다 — 8GB 머신에서 서버가 브라우저를 안고 있으면 안 된다.

사용법:
    python design-lab/serve.py              # 8780
    python design-lab/serve.py --port 9100
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import subprocess
import sys
import urllib.parse
from pathlib import Path

LAB_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(LAB_DIR))

from poster import assets, jobsource, render as renderer, templates   # noqa: E402
from poster.model import FORMATS, PALETTES                            # noqa: E402
from publish import caption as captions                               # noqa: E402
from publish import queue                                             # noqa: E402
from publish.base import PLATFORMS, load_config, publisher_for        # noqa: E402

REFS_JSON = LAB_DIR / "refs.json"
DEFAULT_PORT = 8780
VENV_PY = LAB_DIR.parent / "catch_capture" / ".venv" / "bin" / "python"
WORKER_PY = str(VENV_PY if VENV_PY.is_file() else sys.executable)

# 정적 파일로 열어 줄 폴더들. 이 밖은 못 나간다.
SERVED_DIRS = {"refs": LAB_DIR / "refs", "out": LAB_DIR / "out", "assets": LAB_DIR / "assets"}
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".svg": "image/svg+xml", ".md": "text/markdown; charset=utf-8"}


def run_cli(*args: str, timeout: int = 300) -> dict:
    """publish.cli 를 자식 프로세스로 돌린다."""
    proc = subprocess.run([WORKER_PY, "-m", "publish.cli", *args], cwd=str(LAB_DIR),
                          capture_output=True, text=True, timeout=timeout)
    return {"ok": proc.returncode == 0, "code": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(LAB_DIR / "static"), **kwargs)

    # ---------- GET ----------
    def do_GET(self):  # noqa: N802
        path, _, qs = self.path.partition("?")
        q = urllib.parse.parse_qs(qs)
        one = lambda k, d="": (q.get(k) or [d])[0]  # noqa: E731

        try:
            if path == "/api/refs":
                return self._json_file(REFS_JSON)
            if path == "/api/templates":
                return self._json({
                    "templates": templates.listing(),
                    "formats": [{"id": k, **v} for k, v in FORMATS.items()],
                    "palettes": PALETTES,
                })
            if path == "/api/jobs":
                return self._json({"jobs": jobsource.search(
                    one("q"), only_active=one("all") != "1", limit=int(one("limit", "40")))})
            if path == "/api/spec":
                return self._json(renderer.compose(one("job"), palette=one("palette")))
            if path == "/api/caption":
                spec = renderer.compose(one("job"), palette=one("palette"))
                return self._json(captions.preview(spec))
            if path == "/api/preview":
                html = renderer.html_for(one("job"), one("template", "role_hero"),
                                         one("format", "ig_portrait"), palette=one("palette"))
                return self._body(html.encode("utf-8"), "text/html; charset=utf-8")
            if path == "/api/queue":
                return self._json({
                    "items": queue.items(one("status")),
                    "platforms": [publisher_for(p).check() for p in PLATFORMS],
                    "public_base_url": load_config().get("public_base_url", ""),
                })
            if path == "/api/assets":
                return self._json({"companies": assets.have()})
        except Exception as e:                      # 랩이니까 실패는 화면에서 보이면 된다
            return self._json({"error": f"{type(e).__name__}: {e}"}, status=400)

        for prefix, root in SERVED_DIRS.items():
            if path.startswith(f"/{prefix}/"):
                return self._static(root, path[len(prefix) + 2:])
        return super().do_GET()

    # ---------- POST ----------
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "JSON 이 아닙니다"}, status=400)

        try:
            if self.path == "/api/queue":
                item = queue.add(
                    payload["job_key"],
                    template=payload.get("template", "role_hero"),
                    formats=payload.get("formats") or ["ig_portrait"],
                    platforms=payload.get("platforms") or ["instagram"],
                    palette=payload.get("palette", ""),
                    note=payload.get("note", ""))
                return self._json({"item": item})
            if self.path == "/api/queue/delete":
                return self._json({"removed": queue.remove(payload["id"])})
            if self.path == "/api/render":
                out = run_cli("render", payload["id"])
                return self._json({**out, "item": queue.get(payload["id"])})
            if self.path == "/api/publish":
                args = ["publish", payload["id"]]
                if payload.get("live"):
                    args.append("--live")
                if payload.get("force"):
                    args.append("--force")
                out = run_cli(*args)
                return self._json({**out, "item": queue.get(payload["id"])})
        except Exception as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, status=400)
        return self._json({"error": "모르는 경로"}, status=404)

    # ---------- 응답 도우미 ----------
    def _json(self, obj, status: int = 200):
        return self._body(json.dumps(obj, ensure_ascii=False).encode(),
                          "application/json; charset=utf-8", status)

    def _json_file(self, path: Path):
        if not path.is_file():
            return self._json({"error": f"{path.name} 이 없습니다"}, status=404)
        return self._body(path.read_bytes(), "application/json; charset=utf-8")

    def _static(self, root: Path, rel: str):
        target = (root / urllib.parse.unquote(rel.split("?")[0])).resolve()
        if root.resolve() not in target.parents:
            self.send_error(403)
            return None
        if not target.is_file():
            self.send_error(404)
            return None
        return self._body(target.read_bytes(),
                          MIME.get(target.suffix.lower(), "application/octet-stream"))

    def _body(self, body: bytes, ctype: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")   # 수집·렌더 중에는 늘 최신을 본다
        self.end_headers()
        self.wfile.write(body)
        return None

    def log_message(self, fmt, *args):
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()

    refs = len(json.loads(REFS_JSON.read_text(encoding="utf-8")).get("refs", [])) if REFS_JSON.is_file() else 0
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", args.port), Handler) as httpd:
        print(f"[design-lab] 레퍼런스 {refs}건 / 템플릿 {len(templates.TEMPLATES)}종 / 큐 {len(queue.items())}건")
        print(f"[design-lab] http://localhost:{args.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[design-lab] 종료")


if __name__ == "__main__":
    main()
