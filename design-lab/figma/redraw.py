"""레퍼런스 리드로잉 — 수집한 JPG 한 장을 Figma 로 가져갈 수 있는 SVG 로 다시 그린다.

왜 SVG 인가: Figma MCP 는 Starter 플랜에서 월 20콜이라 22건을 API 로 그릴 수 없다.
Figma 는 SVG 를 임포트할 때 `<text>` 를 진짜 텍스트 레이어로, 도형을 진짜 벡터로,
`id` 를 레이어 이름으로 풀어 준다 — API 로 그린 것과 결과가 같고 쿼터를 안 쓴다.

한 장의 SVG 안에 프레임 둘을 나란히 놓는다.
    [원본(캡처)]  |  [재구성(레이어)]
원본은 대조용이라 이미지 한 장이고, 재구성만 레이어다. 눈으로 바로 맞춰 볼 수 있다.

    python figma/redraw.py hire-03          # 한 건
    python figma/redraw.py --all            # specs/ 전부 + 보드 한 장
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from xml.sax.saxutils import escape

LAB_DIR = Path(__file__).resolve().parent.parent
SPECS = Path(__file__).resolve().parent / "specs"
OUT = Path(__file__).resolve().parent / "out"
GAP = 120           # 원본과 재구성 사이 간격


# ---------------------------------------------------------------- 도형 하나씩
def _attrs(**kw) -> str:
    out = []
    for k, v in kw.items():
        if v is None or v == "":
            continue
        out.append(f'{k.replace("_", "-")}="{v}"')
    return " ".join(out)


def _paint(layer: dict, defs: list[str], uid: str) -> str:
    """단색이면 그대로, 그라디언트면 defs 에 넣고 url() 을 돌려준다."""
    grad = layer.get("gradient")
    if not grad:
        return layer.get("fill", "none")
    gid = f"g_{uid}"
    stops = "".join(
        f'<stop offset="{s["at"]}" stop-color="{s["color"]}"'
        f' stop-opacity="{s.get("opacity", 1)}"/>' for s in grad["stops"])
    if grad["type"] == "radial":
        defs.append(
            f'<radialGradient id="{gid}" cx="{grad.get("cx",.5)}" cy="{grad.get("cy",.5)}"'
            f' r="{grad.get("r",.5)}">{stops}</radialGradient>')
    else:
        defs.append(
            f'<linearGradient id="{gid}" x1="{grad.get("x1",0)}" y1="{grad.get("y1",0)}"'
            f' x2="{grad.get("x2",0)}" y2="{grad.get("y2",1)}">{stops}</linearGradient>')
    return f"url(#{gid})"


def _layer_svg(layer: dict, defs: list[str], uid: str) -> str:
    kind = layer["type"]
    name = escape(layer.get("name", kind))
    common = _attrs(id=name, opacity=layer.get("opacity"))

    if kind == "rect":
        return (f'<rect {common} x="{layer["x"]}" y="{layer["y"]}" width="{layer["w"]}"'
                f' height="{layer["h"]}" rx="{layer.get("r", 0)}"'
                f' fill="{_paint(layer, defs, uid)}"/>')
    if kind == "ellipse":
        return (f'<ellipse {common} cx="{layer["cx"]}" cy="{layer["cy"]}" rx="{layer["rx"]}"'
                f' ry="{layer["ry"]}" fill="{_paint(layer, defs, uid)}"/>')
    if kind == "path":
        return f'<path {common} d="{layer["d"]}" fill="{_paint(layer, defs, uid)}"/>'
    if kind == "text":
        # Figma 임포트에서 텍스트 레이어로 풀리려면 tspan 없이 text 하나여야 한다.
        return (f'<text {common} x="{layer["x"]}" y="{layer["y"]}"'
                f' font-family="{layer.get("font", "Inter")}"'
                f' font-size="{layer["size"]}" font-weight="{layer.get("weight", 400)}"'
                f' letter-spacing="{layer.get("tracking", 0)}"'
                f' fill="{layer.get("fill", "#ffffff")}"'
                f' xml:space="preserve">{escape(layer["text"])}</text>')
    raise ValueError(f"모르는 레이어 종류: {kind}")


# ---------------------------------------------------------------- 프레임/보드
def _image_data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def build(spec: dict, *, ox: float = 0, oy: float = 0) -> tuple[str, list[str]]:
    """스펙 하나 → (프레임 두 개의 SVG 조각, defs 조각들)."""
    w, h = spec["canvas"]["w"], spec["canvas"]["h"]
    defs: list[str] = []
    sid = spec["id"].replace("-", "_")

    src = LAB_DIR / spec["source"]
    body = [
        f'<g id="{escape(spec["id"])} · 원본(캡처)" transform="translate({ox},{oy})">',
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="#000000"/>',
        f'<image x="0" y="0" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice"'
        f' href="{_image_data_uri(src)}"/>',
        '</g>',
        f'<g id="{escape(spec["id"])} · 재구성(레이어)" transform="translate({ox + w + GAP},{oy})">',
    ]
    for i, layer in enumerate(spec["layers"]):
        body.append(_layer_svg(layer, defs, f"{sid}_{i}"))
    body.append("</g>")
    return "\n".join(body), defs


def write_one(spec_id: str) -> Path:
    spec = json.loads((SPECS / f"{spec_id}.json").read_text(encoding="utf-8"))
    w, h = spec["canvas"]["w"], spec["canvas"]["h"]
    body, defs = build(spec)
    total_w = w * 2 + GAP
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
           f' width="{total_w}" height="{h}" viewBox="0 0 {total_w} {h}">'
           f'<defs>{"".join(defs)}</defs>{body}</svg>')
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{spec_id}.svg"
    dest.write_text(svg, encoding="utf-8")
    return dest


def write_board() -> Path:
    """specs/ 전부를 세로로 쌓은 보드 한 장. Figma 에 한 번만 끌어다 놓으면 된다."""
    specs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SPECS.glob("*.json"))]
    if not specs:
        raise SystemExit("specs/ 가 비었습니다")
    parts, defs, y, width = [], [], 0.0, 0.0
    for spec in specs:
        w, h = spec["canvas"]["w"], spec["canvas"]["h"]
        body, d = build(spec, ox=0, oy=y)
        parts.append(body)
        defs += d
        width = max(width, w * 2 + GAP)
        y += h + 200
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
           f' width="{width}" height="{y}" viewBox="0 0 {width} {y}">'
           f'<defs>{"".join(defs)}</defs>{"".join(parts)}</svg>')
    dest = OUT / "board.svg"
    dest.write_text(svg, encoding="utf-8")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec_id", nargs="?", help="예: hire-03")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.all:
        for p in sorted(SPECS.glob("*.json")):
            print(f"[redraw] {write_one(p.stem)}")
        print(f"[redraw] {write_board()}")
    elif args.spec_id:
        print(f"[redraw] {write_one(args.spec_id)}")
    else:
        ap.error("spec_id 를 주거나 --all 을 쓰세요")


if __name__ == "__main__":
    main()
