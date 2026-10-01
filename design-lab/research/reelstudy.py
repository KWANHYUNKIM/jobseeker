"""터진 릴스 공부 도구 — 영상을 받아 장면표를 만들고, 댓글과 함께 한 편씩 기록한다.

인스타 탭은 화면 뒤에 있으면 영상을 재생하지 않는다. 그래서 탭 안에서 영상 주소·숫자·캡션·댓글을 모아
이 도구의 로컬 수신기(127.0.0.1:8799)로 넘기고, 여기서 영상을 받아 ffmpeg 로 장면을 뽑는다.
영상은 분석용으로만 받고 장면표를 만든 뒤 지운다(`frames --clean`). 장면표·영상은 저장소에 넣지 않는다(작업 폴더).

  python -m research.reelstudy serve  [--dir 작업폴더]     # 수신기(백그라운드로 띄운다)
  python -m research.reelstudy frames [--dir 작업폴더] [--clean]   # 받은 영상마다 sheet_<이름>.jpg

탭 쪽 절차는 planning/01-research/method.md '영상·댓글 받기'.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB_DIR))
DEFAULT_DIR = Path(os.environ.get("REELSTUDY_DIR", Path.home() / ".reelstudy"))
PAGE = b"""<!doctype html><meta charset=utf-8><body>loading<script>
const L=JSON.parse(decodeURIComponent(location.hash.slice(1)));
fetch('/save',{method:'POST',body:JSON.stringify(L)}).then(r=>r.text()).then(t=>document.body.textContent='queued '+t);
</script>"""


def serve(d: Path, port: int = 8799) -> None:
    d.mkdir(parents=True, exist_ok=True)
    status: dict[str, object] = {}

    def grab(items: list[dict]) -> None:
        for it in items:
            name = it["name"]
            (d / f"{name}.json").write_text(json.dumps(it.get("meta") or {}, ensure_ascii=False, indent=1), encoding="utf-8")
            if not it.get("url"):
                status[name] = "no video"
                continue
            try:
                req = urllib.request.Request(it["url"], headers={"User-Agent": "Mozilla/5.0"})
                (d / f"{name}.mp4").write_bytes(urllib.request.urlopen(req, timeout=90).read())
                status[name] = (d / f"{name}.mp4").stat().st_size
            except Exception as e:                                   # noqa: BLE001
                status[name] = f"ERR {e}"[:120]

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = PAGE if self.path.split("#")[0] in ("/", "") else json.dumps(status, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            items = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            threading.Thread(target=grab, args=(items,), daemon=True).start()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(str(len(items)).encode())

        def log_message(self, *a):
            pass

    print(f"[reelstudy] 수신기 http://127.0.0.1:{port} → {d}")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


def frames(d: Path, clean: bool = False) -> None:
    """영상마다 장면표 — 0·0.5·1·1.5·2·3초(훅)와 그 뒤 고르게 10장, 시각을 적어 4열로."""
    from PIL import Image, ImageDraw, ImageFont
    from poster.video import ffmpeg_exe
    ff = ffmpeg_exe()
    font = None
    for f in ("C:/Windows/Fonts/malgunbd.ttf", "/System/Library/Fonts/AppleSDGothicNeo.ttc"):
        if Path(f).exists():
            font = ImageFont.truetype(f, 20)
            break
    for mp4 in sorted(d.glob("*.mp4")):
        name = mp4.stem
        meta = json.loads((d / f"{name}.json").read_text(encoding="utf-8")) if (d / f"{name}.json").exists() else {}
        dur = float(meta.get("dur") or 15)
        ts = [0, 0.5, 1.0, 1.5, 2.0, 3.0]
        step = max((dur - 3.0) / 10, 0.5)
        t = 3.0 + step
        while t < dur - 0.2 and len(ts) < 16:
            ts.append(round(t, 1))
            t += step
        w, h, cols = 216, 384, 4
        rows = (len(ts) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w, rows * (h + 26)), "black")
        draw = ImageDraw.Draw(sheet)
        tmp = d / "_f.jpg"
        for k, t in enumerate(ts):
            subprocess.run([ff, "-y", "-loglevel", "error", "-ss", str(t), "-i", str(mp4), "-frames:v", "1", "-q:v", "3", str(tmp)])
            if not tmp.exists():
                continue
            im = Image.open(tmp).convert("RGB")
            im.thumbnail((w, h))
            x, y = (k % cols) * w, (k // cols) * (h + 26)
            sheet.paste(im, (x + (w - im.width) // 2, y + 26))
            draw.text((x + 6, y + 2), f"{t:.1f}s", font=font, fill="#ffe066")
            tmp.unlink()
        sheet.save(d / f"sheet_{name}.jpg", quality=80)
        if clean:
            mp4.unlink()
        print(f"[reelstudy] {name} {dur:.1f}초 → sheet_{name}.jpg")


def main() -> int:
    ap = argparse.ArgumentParser(prog="research.reelstudy")
    ap.add_argument("cmd", choices=["serve", "frames"])
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    ap.add_argument("--clean", action="store_true", help="장면표를 만든 뒤 영상을 지운다")
    a = ap.parse_args()
    d = Path(a.dir)
    serve(d) if a.cmd == "serve" else frames(d, a.clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
