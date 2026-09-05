"""원본 캡처에서 배경을 벡터로 뜬다.

사진 배경은 원본 소스가 없다. 그렇다고 이미지를 그대로 깔면 글자가 같이 박혀 있어
'재구성'이 아니게 된다. 그래서 화면을 격자로 나눠 칸마다 **중앙값 색**(글자처럼
튀는 픽셀은 절반을 못 넘으므로 자연히 빠진다)을 뽑고, 그 색의 방사형 그라디언트
타원을 겹쳐 깐다 — 흐린 사진의 근사치가 벡터 레이어로 나온다.

    python figma/analyze.py refs/instagram/crops/hire-03_....jpg --cols 7 --rows 9
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

LAB_DIR = Path(__file__).resolve().parent.parent


def mesh(src: Path, canvas_w: int, canvas_h: int, cols: int, rows: int,
         spread: float = 1.7) -> list[dict]:
    im = Image.open(src).convert("RGB")
    W, H = im.size
    px = im.load()
    out: list[dict] = []
    cw, ch = W / cols, H / rows
    for r in range(rows):
        for c in range(cols):
            x0, y0 = int(c * cw), int(r * ch)
            x1, y1 = int((c + 1) * cw), int((r + 1) * ch)
            cell = [px[x, y] for y in range(y0, y1, 2) for x in range(x0, x1, 2)]
            cell.sort(key=lambda p: p[0] * 0.299 + p[1] * 0.587 + p[2] * 0.114)
            r_, g_, b_ = cell[len(cell) // 2]          # 중앙값 — 글자·하이라이트를 뺀 색
            out.append({
                "type": "ellipse",
                "name": f"배경 {r + 1}-{c + 1}",
                "cx": round((c + 0.5) * cw / W * canvas_w, 1),
                "cy": round((r + 0.5) * ch / H * canvas_h, 1),
                "rx": round(cw / W * canvas_w * spread, 1),
                "ry": round(ch / H * canvas_h * spread, 1),
                "gradient": {
                    "type": "radial",
                    "stops": [
                        {"at": 0, "color": f"#{r_:02x}{g_:02x}{b_:02x}", "opacity": 1},
                        {"at": 1, "color": f"#{r_:02x}{g_:02x}{b_:02x}", "opacity": 0},
                    ],
                },
            })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1350)
    ap.add_argument("--cols", type=int, default=7)
    ap.add_argument("--rows", type=int, default=9)
    ap.add_argument("--spread", type=float, default=1.7,
                    help="칸 반지름 배수. 클수록 더 흐리게 번진다")
    args = ap.parse_args()
    layers = mesh(LAB_DIR / args.src, args.width, args.height, args.cols, args.rows,
                  args.spread)
    print(json.dumps(layers, ensure_ascii=False))


if __name__ == "__main__":
    main()
