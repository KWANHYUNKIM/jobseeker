"""글자 크기·자간·위치 자동 보정 + 서체 후보 고르기.

원본은 JPG 한 장이라 서체를 확정할 수 없다. 그래서 캡처에서 잰 글자의 잉크 상자
(`fit: {x, y, w, h}`)에 맞춰 이렇게 되돌린다.

    크기  ← 잉크 높이가 맞을 때까지            (세로 리듬을 먼저 맞춘다)
    자간  ← 남는/모자란 폭을 글자 사이에 나눈다  (서체 폭 차이를 흡수)
    x, y ← 잉크 왼쪽 위 모서리를 원본에 붙인다

서체 후보는 두 가지로 점수를 매긴다.
    자간 보정량  — 크게 벌려야 맞는다는 건 그 서체가 원본보다 좁다는 뜻이다.
    획 굵기      — 가로로 훑어 잉크가 이어지는 길이. 세로획 두께가 여기서 갈린다.
굵기를 더 무겁게 본다. 폭은 자간으로 흡수되지만 굵기는 흡수가 안 되기 때문이다.

측정은 브라우저가 아니라 폰트 파일에서 직접 한다 — SVG `getBBox()` 는 잉크가 아니라
em 상자를 돌려줘서 크기가 계속 어긋난다.

    python figma/calibrate.py hire-03                 # 지금 서체로 보정
    python figma/calibrate.py hire-03 --pick-font     # 후보를 다 재 보고 고른 뒤 보정
    python figma/calibrate.py hire-03 --verify        # 실제로 그려서 남은 오차 보고
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FIG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FIG_DIR))
SPECS = FIG_DIR / "specs"
FONTS = FIG_DIR / "fonts"       # 측정·미리보기용 사본. Figma 는 같은 이름 서체를 쓴다


def _font(family: str, size: float) -> ImageFont.FreeTypeFont:
    path = FONTS / f"{family}.ttf"
    if not path.is_file():
        raise FileNotFoundError(f"{family} 폰트 파일이 없습니다: {path}")
    return ImageFont.truetype(str(path), max(int(round(size)), 1))


def ink(text: str, family: str, size: float, tracking: float = 0.0) -> tuple[float, float, float, float]:
    """기준선 원점에서 잰 잉크 상자 (x0, y0, w, h). y0 는 기준선 위쪽이라 음수."""
    f = _font(family, size)
    x0, y0, x1, y1 = f.getbbox(text, anchor="ls")
    w = (x1 - x0) + tracking * max(len(text) - 1, 0)
    return x0, y0, w, y1 - y0


def fit_layer(layer: dict, family: str, rounds: int = 6) -> float:
    """한 줄을 원본 상자에 맞춘다. 돌려주는 값은 크기 대비 자간(서체 적합도)."""
    fit, text = layer["fit"], layer["text"]
    size = layer.get("size") or 100.0
    for _ in range(rounds):                      # 잉크 높이는 크기에 딱 비례하지 않는다
        _, _, _, h = ink(text, family, size)
        if h <= 0:
            break
        size = size * fit["h"] / h
    x0, y0, w0, _ = ink(text, family, size)
    gaps = max(len(text) - 1, 1)
    tracking = (fit["w"] - w0) / gaps
    layer.update({
        "font": family,
        "size": round(size, 2),
        "tracking": round(tracking, 2),
        "x": round(fit["x"] - x0, 1),
        "y": round(fit["y"] - y0, 1),            # SVG 의 y 는 기준선
    })
    return abs(tracking) / size


def _stem_of_image(img: Image.Image, thr: int) -> float:
    """가로로 훑어 잉크가 끊기지 않고 이어지는 평균 길이 ÷ 상자 높이 = 획 굵기."""
    px = img.load()
    runs = []
    for y in range(0, img.height, 2):
        run = 0
        for x in range(img.width):
            if px[x, y] >= thr:
                run += 1
            elif run:
                if run < img.width * 0.5:      # 배경 덩어리는 획이 아니다
                    runs.append(run)
                run = 0
    if not runs:
        return 0.0
    runs.sort()
    return runs[len(runs) // 2] / max(img.height, 1)


def _density_of(text: str, family: str, size: float, tracking: float,
                box: dict) -> float:
    """그려 본 글자의 획 굵기."""
    img = Image.new("L", (int(box["w"]) + 40, int(box["h"]) + 40), 0)
    draw = ImageDraw.Draw(img)
    f = _font(family, size)
    x0, y0, _, _ = ink(text, family, size)
    x, y = 20 - x0, 20 - y0
    for ch in text:
        draw.text((x, y), ch, font=f, fill=255, anchor="ls")
        x += draw.textlength(ch, font=f) + tracking
    return _stem_of_image(img, 128)


def _source_density(spec: dict, layer: dict, thr: int = 190) -> float | None:
    """원본 캡처의 같은 자리에서 잰 획 굵기."""
    src = FIG_DIR.parent / spec["source"]
    if not src.is_file():
        return None
    im = Image.open(src).convert("L")
    s = im.width / spec["canvas"]["w"]
    fit = layer["fit"]
    box = (max(int((fit["x"] - 20) * s), 0), max(int((fit["y"] - 20) * s), 0),
           min(int((fit["x"] + fit["w"] + 20) * s), im.width),
           min(int((fit["y"] + fit["h"] + 20) * s), im.height))
    crop = im.crop(box)
    if crop.width < 4 or crop.height < 4:
        return None
    return _stem_of_image(crop, thr)


def run(spec_id: str, *, pick_font: bool = False) -> dict:
    path = SPECS / f"{spec_id}.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    texts = [l for l in spec["layers"] if l["type"] == "text" and l.get("fit")]
    scores: dict[str, float] = {}

    if pick_font:
        want = [(l, _source_density(spec, l)) for l in texts]
        for family in sorted(f.stem for f in FONTS.glob("*.ttf")):
            track_pen, dens_pen, n = 0.0, 0.0, 0
            for layer, want_d in want:
                trial = json.loads(json.dumps(layer))
                track_pen += fit_layer(trial, family)
                if want_d is not None:
                    got = _density_of(trial["text"], family, trial["size"],
                                      trial["tracking"], trial["fit"])
                    dens_pen += abs(got - want_d) / max(want_d, 1e-6)
                n += 1
            scores[family] = round((track_pen / n) + 2.0 * (dens_pen / n), 4)
        family = min(scores, key=scores.get)
        spec["font_note"] = (f"{family} 로 잡았다(자간·획굵기 오차 최소 {scores[family]}). "
                             "원본 서체는 캡처만으로 확정 불가.")
    else:
        family = texts[0].get("font", "Libre Baskerville")

    for layer in texts:
        fit_layer(layer, family)
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"family": family, "scores": dict(sorted(scores.items(), key=lambda kv: kv[1]))}


def verify(spec_id: str) -> list[dict]:
    """실제로 글자를 찍어 보고 원본 상자와의 남은 오차를 잰다(픽셀 기준)."""
    spec = json.loads((SPECS / f"{spec_id}.json").read_text(encoding="utf-8"))
    W, H = spec["canvas"]["w"], spec["canvas"]["h"]
    canvas = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(canvas)
    rows = []
    for layer in spec["layers"]:
        if layer["type"] != "text" or not layer.get("fit"):
            continue
        f = _font(layer["font"], layer["size"])
        x = layer["x"]
        for ch in layer["text"]:                 # 자간은 직접 벌려 가며 찍는다
            draw.text((x, layer["y"]), ch, font=f, fill=255, anchor="ls")
            x += draw.textlength(ch, font=f) + layer["tracking"]
        box = canvas.getbbox()
        fit = layer["fit"]
        rows.append({
            "이름": layer["name"],
            "dx": round(box[0] - fit["x"], 1), "dy": round(box[1] - fit["y"], 1),
            "dw": round((box[2] - box[0]) - fit["w"], 1),
            "dh": round((box[3] - box[1]) - fit["h"], 1),
        })
        canvas.paste(0, (0, 0, W, H))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec_id")
    ap.add_argument("--pick-font", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        for r in verify(args.spec_id):
            print(f"  {r['이름']:<24} dx={r['dx']:<7} dy={r['dy']:<7} dw={r['dw']:<7} dh={r['dh']}")
        return
    out = run(args.spec_id, pick_font=args.pick_font)
    for fam, score in out["scores"].items():
        print(f"  {fam:<22} 자간보정량 {score}")
    print("→ 서체:", out["family"])


if __name__ == "__main__":
    main()
