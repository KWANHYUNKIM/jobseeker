"""Snap 2001 Gothic — 무신사 공고 포스터(v3 '무진장 신발 사진이 많은 곳') 본문용 파생 서체.

LOCA Batang(롯데카드, 명조 + 가라몬드 + 나침반 별)과 성격이 정반대인 쪽으로 간다:
좁고 단단한 고딕 몸에 2001년 웹 커뮤니티 간판 같은 픽셀 숫자·기호. 몸 전체를 픽셀로 만들지는
않는다 — 17px 본문에서 한글 픽셀 서체는 읽기 힘들다(후보판 out/wanted-375793/body_font_board.jpg).

  한글·영문   Paperlogy (SIL OFL 1.1, PT&) — 좁고 단단한 고딕. Regular ← 5 Medium, Bold ← 7 Bold
  픽셀로 교체  숫자 0–9 와 - : % ~ ← Galmuri (SIL OFL 1.1, Lee Minseo)
               Regular 은 Galmuri9 를 칸 비트맵으로 읽어 가로 1.3배로 다시 칠함(세로획을 Paperlogy 5 와 맞춤),
               Bold 는 Galmuri11 Bold(2칸 획) 그대로. 숫자 높이를 Paperlogy 숫자 높이(≈710/900)에 맞췄다
  새로 그림    가운뎃점 · 과 불릿 • → 꽉 찬 정사각 픽셀 한 칸(한글 글자 몸 세로 중심)
  이름         'Snap 2001 Gothic' — 무신사 공식 서체로 오해되지 않는 중립 이름(OFL 수정본 새 이름 조건)

    PYTHONPATH=<fonttools 설치 경로> python typefaces/build_snap2001_gothic.py
    → assets/companies/무신사/fonts/Snap2001Gothic/Snap2001Gothic-{Regular,Bold}.{ttf,woff2}, OFL.txt
"""
from __future__ import annotations

from pathlib import Path

from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

LAB = Path(__file__).resolve().parent.parent
SRC = LAB / "assets/companies/무신사/fonts/body"
OUT = LAB / "assets/companies/무신사/fonts/Snap2001Gothic"

FAMILY = "Snap 2001 Gothic"
DIGIT_TOP = 710                    # Paperlogy 숫자 윗선(UPM 900)
PIXEL_CHARS = "0123456789-:%~"   # ( ) / 는 첫 견본에서 가는 계단선이 괄호로 안 읽혀 뺐다(바탕 그대로)
TALL = ""
SQUARE_CHARS = {0x00B7: 2.3, 0x2022: 2.8}   # 정사각 한 변 = 픽셀 칸의 몇 배 — 17px 에서 3px 이상 보이게

WEIGHTS = {
    # 이름: (바탕 Paperlogy, 픽셀 원본, 원본 숫자 높이, 숫자 좌우 여유, 픽셀 원본 한 칸, 가로 굵힘 배수)
    # Regular: Galmuri9 1칸 획이 Paperlogy 5 세로획(49/450px)보다 20% 가늘다(39) → 픽셀을 비트맵으로 읽어 가로로 1.3배 칠한다
    "Regular": ("Paperlogy-5Medium.woff2", "Galmuri9.ttf", 900, 50, 100, 1.3),
    "Bold": ("Paperlogy-7Bold.woff2", "Galmuri11-Bold.ttf", 1100, 50, 100, 1.0),
}


def put(target: TTFont, name: str, src: TTFont, src_name: str, scale: float, dx: float, dy: float, adv: int) -> None:
    gs = src.getGlyphSet()
    rec = DecomposingRecordingPen(gs)
    gs[src_name].draw(rec)
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, (scale, 0, 0, scale, dx, dy)))
    g = pen.glyph()
    target["glyf"][name] = g
    g.recalcBounds(target["glyf"])
    target["hmtx"][name] = (adv, getattr(g, "xMin", 0))


def pixel_put(target: TTFont, name: str, src: TTFont, src_name: str, cell: int, scale: float, widen: float, pad: int) -> None:
    """픽셀 서체 글리프를 칸 단위 비트맵으로 읽어 다시 칠한다 — 칸은 정사각 유지, 가로로만 widen 배 굵힌다."""
    gs = src.getGlyphSet()
    rec = DecomposingRecordingPen(gs)
    gs[src_name].draw(rec)
    from fontTools.pens.boundsPen import BoundsPen
    bp = BoundsPen(gs); gs[src_name].draw(bp)
    adv_src = src["hmtx"][src_name][0]
    pen = TTGlyphPen(None)
    if bp.bounds:
        x0, y0, x1, y1 = bp.bounds
        u = cell * scale
        for gy in range(int(y0 // cell), int(-(-y1 // cell))):
            for gx in range(int(x0 // cell), int(-(-x1 // cell))):
                ip = PointInsidePen(gs, ((gx + .5) * cell, (gy + .5) * cell))
                rec.replay(ip)
                if not ip.getResult():
                    continue
                L = round(gx * u + pad / 2); B = round(gy * u)
                R = round(L + u * widen); T = round(B + u)
                pen.moveTo((L, B)); pen.lineTo((L, T)); pen.lineTo((R, T)); pen.lineTo((R, B)); pen.closePath()
    g = pen.glyph()
    target["glyf"][name] = g
    g.recalcBounds(target["glyf"])
    target["hmtx"][name] = (round(adv_src * scale + cell * scale * (widen - 1)) + pad, getattr(g, "xMin", 0))


def square(target: TTFont, name: str, side: int, cy: int, margin: int) -> None:
    x0, y0 = margin, cy - side // 2
    pen = TTGlyphPen(None)
    pen.moveTo((x0, y0)); pen.lineTo((x0, y0 + side)); pen.lineTo((x0 + side, y0 + side)); pen.lineTo((x0 + side, y0))
    pen.closePath()
    g = pen.glyph()
    target["glyf"][name] = g
    g.recalcBounds(target["glyf"])
    target["hmtx"][name] = (side + 2 * margin, x0)


def rename(font: TTFont, style: str, base_copy: str, pixel_copy: str) -> None:
    ps = f"Snap2001Gothic-{style}"
    name = font["name"]
    name.names = [r for r in name.names if r.nameID not in range(0, 26)]
    vals = {
        0: f"{base_copy} (Paperlogy). {pixel_copy} (Galmuri). Modifications for {FAMILY}, 2026.",
        1: FAMILY, 2: style, 3: f"{ps};2026-09-15", 4: f"{FAMILY} {style}", 5: "Version 1.000", 6: ps,
        10: (f"{FAMILY}: derived body typeface for a job-posting poster. Hangul and Latin from Paperlogy, "
             "figures and - : % ~ from Galmuri pixel fonts, middle dot and bullet redrawn as a square pixel. "
             "Not an official MUSINSA font."),
        13: "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
        14: "https://openfontlicense.org",
    }
    for nid, v in vals.items():
        name.setName(v, nid, 3, 1, 0x409)
    font["OS/2"].achVendID = "SNAP"
    font["OS/2"].usWeightClass = 700 if style == "Bold" else 400
    font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~0b1100001) | (0b100000 if style == "Bold" else 0b1000000)
    font["head"].macStyle = 1 if style == "Bold" else 0


def build_one(style: str, base_file: str, pixel_file: str, pixel_digit_h: int, pad: int, cell: int, widen: float) -> Path:
    base = TTFont(SRC / base_file)
    px = TTFont(SRC / pixel_file)
    bcm, pcm = base.getBestCmap(), px.getBestCmap()
    scale = DIGIT_TOP / pixel_digit_h
    tall_scale = 796 / pixel_digit_h           # ( ) / 는 -48..748
    for ch in PIXEL_CHARS:
        c = ord(ch)
        if c not in bcm or c not in pcm:
            continue
        pixel_put(base, bcm[c], px, pcm[c], cell, scale, widen, pad)

    ga = base["glyf"][bcm[ord("가")]]
    ga.recalcBounds(base["glyf"])
    cy = round((ga.yMin + ga.yMax) / 2)
    upm = base["head"].unitsPerEm
    stem = round(scale * cell)                                          # 픽셀 한 칸
    for c, k in SQUARE_CHARS.items():
        if c in bcm:
            side = round(stem * k * (1.0 if widen == 1 else 0.85))
            square(base, bcm[c], side, cy, round(side * 0.55))

    for t in ("kern", "GPOS", "GSUB", "vhea", "vmtx"):     # 옛 커닝은 바꿔 넣은 숫자와 어긋난다
        if t in base:
            del base[t]
    rename(base, style, base["name"].getDebugName(0) or "Copyright 2024 PT&", "Copyright 2019-2025 Lee Minseo")

    OUT.mkdir(parents=True, exist_ok=True)
    ttf = OUT / f"Snap2001Gothic-{style}.ttf"
    base.save(ttf)
    base.flavor = "woff2"
    base.save(OUT / f"Snap2001Gothic-{style}.woff2")
    print(f"[{FAMILY} {style}] 픽셀 기호 {len(PIXEL_CHARS)}자 · 정사각 점 2자 · 배율 {scale:.3f} · 픽셀 {stem}u → "
          f"{(OUT / f'Snap2001Gothic-{style}.woff2').stat().st_size // 1024}KB")
    return ttf


def build() -> None:
    for style, args in WEIGHTS.items():
        build_one(style, *args)
    (OUT / "OFL.txt").write_text(
        f"{FAMILY} — modified from Paperlogy and Galmuri. Not an official MUSINSA font.\n\n"
        "Paperlogy: Copyright (c) 2024 PT& (www.designptn.com)\n"
        "Galmuri: Copyright (c) 2019-2025 Lee Minseo (quiple@quiple.dev)\n"
        "Modifications (c) 2026.\n\n"
        "This Font Software is licensed under the SIL Open Font License, Version 1.1.\n"
        "https://openfontlicense.org/open-font-license-official-text/\n\n"
        + (SRC / "Galmuri-OFL.txt").read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    build()
