"""글자 크기·자간·위치 자동 보정 + 서체 후보 고르기.

원본은 JPG 한 장이라 서체를 확정할 수 없다. 그래서 캡처에서 잰 글자의 잉크 상자
(`fit: {x, y, w, h}`)에 맞춰 이렇게 되돌린다.

    크기  ← 잉크 높이가 맞을 때까지            (세로 리듬을 먼저 맞춘다)
    자간  ← 남는/모자란 폭을 글자 사이에 나눈다  (서체 폭 차이를 흡수)
    x, y ← 잉크 왼쪽 위 모서리를 원본에 붙인다

서체 후보 중에서는 **자간을 가장 적게 건드려도 되는 것**을 고른다. 자간을 크게
벌려야 맞는다는 건 그 서체가 원본보다 좁다는 뜻이니까.

    python figma/calibrate.py hire-03                 # 지금 서체로 보정
    python figma/calibrate.py hire-03 --pick-font     # 후보를 다 재 보고 고른 뒤 보정
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

FIG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FIG_DIR))
SPECS = FIG_DIR / "specs"
FONTS = FIG_DIR / "fonts"       # 미리보기·측정용 사본. Figma 쪽은 같은 이름 서체를 쓴다


def _font_css() -> str:
    faces = []
    for f in sorted(FONTS.glob("*.ttf")) if FONTS.is_dir() else []:
        b64 = base64.b64encode(f.read_bytes()).decode()
        faces.append(f"@font-face{{font-family:'{f.stem}';"
                     f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}")
    return "".join(faces)


def _page_html(spec: dict) -> tuple[str, int, int]:
    from redraw import build
    body, defs = build(spec)
    w = spec["canvas"]["w"] * 2 + 120
    h = spec["canvas"]["h"]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
           f' width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
           f'<defs>{"".join(defs)}</defs>{body}</svg>')
    return f"<!doctype html><meta charset=utf-8><style>{_font_css()}html,body{{margin:0}}</style>{svg}", w, h


def _measure(page, spec: dict) -> dict[str, dict]:
    html, w, h = _page_html(spec)
    page.set_viewport_size({"width": min(w, 3000), "height": min(h, 3000)})
    page.set_content(html, wait_until="load")
    page.wait_for_timeout(250)
    return page.evaluate("""() => {
      const out = {};
      for (const t of document.querySelectorAll('text')) {
        const bb = t.getBBox();      // 로컬 좌표계 — 프레임 이동값은 안 들어간다
        out[t.id] = {x: bb.x, y: bb.y, w: bb.width, h: bb.height};
      }
      return out;
    }""")


def _fit_round(spec: dict, boxes: dict) -> float:
    """한 번 되돌리고, 필요한 자간의 평균 절대값(서체 적합도)을 돌려준다."""
    tracks = []
    for layer in spec["layers"]:
        fit = layer.get("fit")
        if layer["type"] != "text" or not fit:
            continue
        box = boxes.get(layer["name"])
        if not box or box["w"] <= 0 or box["h"] <= 0:
            continue
        layer["size"] = round(layer["size"] * fit["h"] / box["h"], 2)
        gaps = max(len(layer["text"]) - 1, 1)
        layer["tracking"] = round(layer.get("tracking", 0)
                                  + (fit["w"] - box["w"]) / gaps, 2)
        layer["x"] = round(layer["x"] + (fit["x"] - box["x"]), 1)
        layer["y"] = round(layer["y"] + (fit["y"] - box["y"]), 1)
        tracks.append(abs(layer["tracking"]) / layer["size"])   # 크기 대비 자간
    return round(sum(tracks) / len(tracks), 4) if tracks else 0.0


def run(spec_id: str, *, rounds: int = 3, pick_font: bool = False) -> dict:
    path = SPECS / f"{spec_id}.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    scores = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        if pick_font:
            candidates = sorted(f.stem for f in FONTS.glob("*.ttf"))
            best, best_score, best_spec = None, 1e9, None
            for fam in candidates:
                trial = json.loads(json.dumps(spec))
                for layer in trial["layers"]:
                    if layer["type"] == "text" and layer.get("fit"):
                        layer["font"] = fam
                        layer["tracking"] = 0
                for _ in range(rounds):
                    score = _fit_round(trial, _measure(page, trial))
                scores[fam] = score
                if score < best_score:
                    best, best_score, best_spec = fam, score, trial
            spec = best_spec
            spec["font_note"] = (f"{best} 로 잡았다(자간 보정량 최소). "
                                 f"원본 서체는 캡처만으로 확정 불가.")
        else:
            for _ in range(rounds):
                _fit_round(spec, _measure(page, spec))
        browser.close()

    path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"scores": dict(sorted(scores.items(), key=lambda kv: kv[1])),
            "picked": spec.get("font_note", "")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec_id")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--pick-font", action="store_true")
    args = ap.parse_args()
    out = run(args.spec_id, rounds=args.rounds, pick_font=args.pick_font)
    for fam, score in out["scores"].items():
        print(f"  {fam:<22} 자간보정량 {score}")
    if out["picked"]:
        print("→", out["picked"])


if __name__ == "__main__":
    main()
