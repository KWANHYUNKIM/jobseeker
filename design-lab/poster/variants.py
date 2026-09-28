"""한 공고를 판의 여러 갈래로 찍어 한 장에 나란히 붙인다 — 고를 수 있게.

절차 8절("눈으로 검증·반복, 이전 판과 나란히")을 사람이 손으로 하던 것을 한 줄로 만든 것이다.
갈래는 판이 정한다(템플릿이 `D.variant` 로 읽는 `.v-<이름>` 클래스). 여기서는 이름만 넘긴다.

    python -m poster.variants wanted-353819 --variants "" orange huge light
    python -m poster.variants wanted-353819                 # 판이 아는 갈래 전부

결과: out/<공고키>/_variants.jpg  (그리고 갈래마다 brand_<갈래>_ig_portrait.jpg)
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import brands, carousel, jobsource

LAB_DIR = Path(__file__).resolve().parent.parent
OUT = LAB_DIR / "out"
TPL_DIR = Path(__file__).resolve().parent / "templates"

#: 시트 글자용. 어느 회사 폴더에 있든 상관없다 — 비교표의 제목일 뿐이다.
_LABEL_FONTS = [
    "assets/companies/네이버웹툰/fonts/GothicA1-Black.ttf",
    "assets/companies/롯데카드/fonts/NotoSansKR-VF.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]


def known_variants(company: str) -> list[str]:
    """판 HTML 에 선언된 `.v-<이름>` 을 그대로 읽는다 — 목록을 두 군데 적지 않는다."""
    brand = brands.find(company) or {}
    frame = brand.get("frame")
    if not frame:
        return [""]
    html = (TPL_DIR / frame).read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"\.v-([a-z0-9_-]+)", html)))
    return ["", *names]


def _label_font(size: int):
    for p in _LABEL_FONTS:
        f = Path(p) if Path(p).is_absolute() else LAB_DIR / p
        if f.is_file():
            try:
                return ImageFont.truetype(str(f), size)
            except OSError:
                continue
    return ImageFont.load_default()


def sheet(job_key: str, variants: list[str], fmt: str = "ig_portrait",
          width: int = 620) -> tuple[Path, list[tuple[str, float]]]:
    tiles, stats = [], []
    for v in variants:
        dest, layout = carousel.render_onepage(job_key, fmt, frame="brand", variant=v)
        im = Image.open(dest).convert("RGB")
        tiles.append((im.resize((width, round(im.height * width / im.width)), Image.LANCZOS),
                      v or "기본", layout["font_px"]))
        stats.append((v or "기본", layout["font_px"]))

    pad, gap, top = 26, 22, 92
    f_n, f_s = _label_font(27), _label_font(19)
    h = max(t[0].height for t in tiles)
    canvas = Image.new("RGB", (pad * 2 + width * len(tiles) + gap * (len(tiles) - 1),
                               top + h + pad), "#0f0f11")
    d = ImageDraw.Draw(canvas)
    for i, (im, name, px) in enumerate(tiles):
        x = pad + i * (width + gap)
        d.text((x, 24), name, font=f_n, fill="#ffffff")
        d.text((x, 60), f"본문 {px}px", font=f_s, fill="#8b8b93")
        canvas.paste(im, (x, top))
    out = OUT / job_key / "_variants.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=88)
    return out, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_key")
    ap.add_argument("--variants", nargs="*", default=None,
                    help='갈래 이름들. 비우면 판이 아는 것 전부. 기본 갈래는 "" 로 넣는다')
    ap.add_argument("--format", dest="fmt", default="ig_portrait")
    args = ap.parse_args()
    job = jobsource.get(args.job_key)
    if not job:
        raise SystemExit(f"모르는 공고: {args.job_key}")
    vs = args.variants if args.variants is not None else known_variants(job["company"])
    try:
        out, stats = sheet(args.job_key, vs, args.fmt)
        for name, px in stats:
            print(f"  {name:10s} 본문 {px}px")
        print(f"[variants] {len(vs)}갈래 → {out}")
    finally:
        carousel.shutdown()


if __name__ == "__main__":
    main()
