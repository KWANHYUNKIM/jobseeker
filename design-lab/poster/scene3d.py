"""three.js 3D 장면 → 영상 클립. 해부도 릴스(cutaway.py)의 장면 하나를 우리가 직접 만든다.

생성 AI 가 없을 때의 길이다 — 모양은 단순한 도형이지만, 우리가 만든 것이라 권리·사칭 걱정이 없고
몇 번을 찍어도 같은 프레임이 나온다(render(t) 가 시간을 받아 그린다). 브라우저가 file:// 에서
모듈을 못 읽으므로 poster/ 를 잠깐 로컬 서버로 연다.

    python -m poster.scene3d store 5 reels/oliveyoung_3d/clips/shot02.mp4
"""
from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import subprocess
import threading
from pathlib import Path

from . import video

POSTER = Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 30


def render(name: str, seconds: float, dest: Path, *, fps: int = FPS) -> Path:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(POSTER))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    frames = dest.parent / f"_{dest.stem}_frames"
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                         "--ignore-gpu-blocklist"])
            pg = br.new_page(viewport={"width": W, "height": H})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            base, _, shot = name.partition("#")
            pg.goto(f"http://127.0.0.1:{srv.server_port}/templates/scene3d_{base}.html" + (f"#{shot}" if shot else ""))
            try:
                pg.wait_for_function("window.__ready === true", timeout=60000)
            except Exception:
                raise RuntimeError(f"장면이 안 떴다: {errs[:3]}")
            for i in range(int(seconds * fps)):
                pg.evaluate(f"window.render({i / fps:.4f})")
                pg.screenshot(path=str(frames / f"{i:05d}.jpg"), type="jpeg", quality=92)
            br.close()
    finally:
        srv.shutdown()
    subprocess.run([video.ffmpeg_exe(), "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "%05d.jpg"),
                    "-vf", "scale=in_range=full:out_range=tv,format=yuv420p", "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-color_range", "tv", str(dest)], check=True)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(prog="poster.scene3d")
    ap.add_argument("name")
    ap.add_argument("seconds", type=float)
    ap.add_argument("dest")
    a = ap.parse_args()
    d = Path(a.dest)
    d.parent.mkdir(parents=True, exist_ok=True)
    print(render(a.name, a.seconds, d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
