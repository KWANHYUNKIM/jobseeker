"""사진 한 장에서 배경을 떼어 투명 PNG 로 — 표지에 쓸 물건 이미지를 만든다.

표지의 물건을 CSS 로 다시 그릴 필요가 없다. 원본 사진이 있으면 배경만 떼서 얹는 편이
깔끔하고, 이 랩이 이미 배운 것과도 맞는다 — **흉내보다 원본**(BRAND_RESEARCH 0절 4번).

    python -m poster.cutout 원본.jpg 토스플레이스 front2
    → assets/companies/토스플레이스/cutout/front2.png  (배경 투명)

어떻게 떼나: 제품 사진은 배경이 거의 단색이다. 네 변에서 시작해 **비슷한 색끼리 번져
나가며**(flood fill) 바깥을 지운다. 가운데서 시작하지 않으므로 물건 안의 흰색은 안 지워진다.
가장자리는 한 겹 부드럽게 눌러 톱니를 없앤다.

안 되는 사진: 배경이 복잡하거나(거리·무대) 물건 색이 배경과 같은 것. 그때는 말해 주고
멈춘다 — 반쯤 뜯긴 그림을 판에 올리면 판이 죽는다.
"""
from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

LAB_DIR = Path(__file__).resolve().parent.parent


def cut(src: Path, tol: int = 26, feather: float = 1.2) -> tuple[Image.Image, float]:
    """(배경 뺀 RGBA, 지워진 비율). 지워진 비율이 너무 낮거나 높으면 실패로 본다."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    q: deque[tuple[int, int]] = deque()

    def push(x: int, y: int) -> None:
        i = y * w + x
        if not seen[i]:
            seen[i] = 1
            q.append((x, y))

    # 네 변 전체가 시작점이다 — 바깥에서만 번진다
    for x in range(w):
        push(x, 0); push(x, h - 1)
    for y in range(h):
        push(0, y); push(w - 1, y)

    # 시작점들의 평균색을 배경색으로 본다
    edge = [px[x, 0] for x in range(0, w, max(1, w // 64))] + \
           [px[x, h - 1] for x in range(0, w, max(1, w // 64))] + \
           [px[0, y] for y in range(0, h, max(1, h // 64))] + \
           [px[w - 1, y] for y in range(0, h, max(1, h // 64))]
    br = sum(c[0] for c in edge) / len(edge)
    bg = sum(c[1] for c in edge) / len(edge)
    bb = sum(c[2] for c in edge) / len(edge)

    def near(c) -> bool:
        return abs(c[0] - br) <= tol and abs(c[1] - bg) <= tol and abs(c[2] - bb) <= tol

    out = bytearray(w * h)          # 1 = 배경(지움)
    while q:
        x, y = q.popleft()
        if not near(px[x, y]):
            continue
        out[y * w + x] = 1
        if x > 0: push(x - 1, y)
        if x < w - 1: push(x + 1, y)
        if y > 0: push(x, y - 1)
        if y < h - 1: push(x, y + 1)

    cleared = sum(out) / (w * h)
    mask = Image.frombytes("L", (w, h), bytes(255 - v * 255 for v in out))
    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    rgba = im.convert("RGBA")
    rgba.putalpha(mask)
    return rgba, cleared


def save(src: Path, company: str, name: str, **kw) -> Path:
    rgba, cleared = cut(src, **kw)
    if cleared < 0.08:
        raise SystemExit(f"[cutout] 배경을 거의 못 뗐다({cleared:.0%}) — 배경이 단색이 아닌 사진 같다. "
                         "다른 컷을 쓰거나 tol 을 올려 보라.")
    if cleared > 0.94:
        raise SystemExit(f"[cutout] 거의 다 지웠다({cleared:.0%}) — 물건 색이 배경과 같다. tol 을 낮춰 보라.")
    dest = LAB_DIR / "assets" / "companies" / company / "cutout" / f"{name}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(dest)
    print(f"[cutout] 배경 {cleared:.0%} 제거 → {dest.relative_to(LAB_DIR)}")
    print(f"[cutout] 판에 쓰려면 brands/{company}.json 의 ui.images 에 "
          f'"cover": "assets/companies/{company}/cutout/{name}.png" 를 넣는다')
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path, help="원본 사진(jpg/png)")
    ap.add_argument("company", help="brands/<회사>.json 의 회사 이름")
    ap.add_argument("name", help="저장할 이름(확장자 없이)")
    ap.add_argument("--tol", type=int, default=26, help="배경으로 볼 색 차이(기본 26)")
    ap.add_argument("--feather", type=float, default=1.2, help="가장자리 부드럽게(기본 1.2)")
    args = ap.parse_args()
    if not args.src.is_file():
        raise SystemExit(f"그런 파일이 없다: {args.src}")
    save(args.src, args.company, args.name, tol=args.tol, feather=args.feather)


if __name__ == "__main__":
    main()
