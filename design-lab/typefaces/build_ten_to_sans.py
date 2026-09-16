"""Ten to Sans — 토스 공고 포스터(wanted-335070) 모집 내용 본문용 파생 서체.

무료 서체(SIL OFL)를 바탕으로 우리 판에 맞게 고친다. 처음부터 그리지 않는다(BRAND_RESEARCH.md 4절).
Toss Product Sans 는 이용허락이 없어 윤곽을 한 점도 가져오지 않는다 — '숫자를 UI 처럼' 이라는 성격만 따른다.

  바탕       나눔스퀘어라운드(NAVER, SIL OFL 1.1) — 획 끝이 둥글고 속공간이 넓은 네모꼴 고딕.
             토스 v3 판의 얼굴인 '10 to 100' 조합의 원·둥근 숫자와 결이 같다. 기본 고딕(Wanted Sans)과도, LOCA Batang(명조)과도 다르다
  굵기       한글·영문은 Regular 그대로. R/B 윤곽을 섞어 Medium 을 만들어 봤지만(t=0.42) 한글은 자모 조각을 조합한 글리프라
             조각 절반이 R/B 점 구조가 달라 한 글자 안에서 획 굵기가 어긋났다 → 섞지 않는다(T=0)
  숫자       Bold 의 숫자를 가져와 한글보다 한 단계 굵게(TPS 가 숫자를 한글보다 두껍게 설계한 것과 같은 방향),
             폭을 가장 넓은 숫자에 맞춘 고정폭(tabular) — '2–10년', '99.9%', '(4/7)' 이 칸에 맞춰 선다
  기호       % + / 를 Bold 에서 가져와 1.12배, 한글 글자 몸 세로 중심으로 옮긴다 — 기호를 글자가 아니라 UI 요소처럼
  새로 그림  가운뎃점 · · 불릿 • · 검은 원 ● → '10 to 100' 의 'to' 원(속이 찬 원)
             검은 네모 ■ → 같은 조합의 숫자 상자(속이 찬 정사각)
  이름       'Ten to Sans' — OFL 예약 이름(나눔)과 토스 공식 서체로 오인될 이름을 쓰지 않는다. 원본 저작권 + OFL 동봉

    PYTHONPATH=<fonttools 설치 경로> python typefaces/build_ten_to_sans.py
    → assets/companies/토스/fonts/TenToSans/TenToSans-Regular.{ttf,woff2}, OFL.txt
"""
from __future__ import annotations

import math
from pathlib import Path

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

LAB = Path(__file__).resolve().parent.parent
FONTS = LAB / "assets/companies/토스/fonts"
REG = FONTS / "body/NanumSquareRoundR.woff2"
BOLD = FONTS / "body/NanumSquareRoundB.woff2"
OUT = FONTS / "TenToSans"

T = 0.0                  # R→B 섞는 비율 — 한글 자모 조각 절반이 호환되지 않아 끈다(위 설명)
FIG_T = 1.0              # 숫자는 Bold 그대로
SYMBOL_SCALE = 1.12
SYMBOLS = "%+/"
FAMILY = "Ten to Sans"
PS = "TenToSans-Regular"
DESCRIPTION = ("Ten to Sans: derived for a Toss-style recruitment poster. Based on NanumSquareRound (NAVER, SIL OFL 1.1): "
               "Regular Hangul/Latin, tabular Bold figures, enlarged centred % + /, "
               "middle dot/bullet/black circle redrawn as a solid circle and black square as a solid square. "
               "Not affiliated with Toss; contains no Toss Product Sans outlines.")


def lerp_glyph(gr, gb, name: str, t: float):
    """점 구조가 같으면 좌표를 섞은 새 글리프, 아니면 None."""
    a, b = gr[name], gb[name]
    if a.isComposite() or b.isComposite() or a.numberOfContours <= 0:
        return None
    if a.numberOfContours != b.numberOfContours or list(a.endPtsOfContours) != list(b.endPtsOfContours):
        return None
    ca, cb = a.getCoordinates(gr)[0], b.getCoordinates(gb)[0]
    if len(ca) != len(cb) or [f & 1 for f in a.flags] != [f & 1 for f in b.flags]:
        return None
    import copy
    g = copy.deepcopy(a)
    g.coordinates = type(ca)([(round(x1 + (x2 - x1) * t), round(y1 + (y2 - y1) * t)) for (x1, y1), (x2, y2) in zip(ca, cb)])
    g.program = None
    if hasattr(g, "program"):
        from fontTools.ttLib.tables import ttProgram
        g.program = ttProgram.Program(); g.program.fromBytecode(b"")
    return g


def copy_scaled(target, name, src, src_name, scale=1.0, dx=0, dy=0, adv=None):
    gs = src.getGlyphSet()
    rec = DecomposingRecordingPen(gs)
    gs[src_name].draw(rec)
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, (scale, 0, 0, scale, dx, dy)))
    g = pen.glyph()
    target["glyf"][name] = g
    g.recalcBounds(target["glyf"])
    target["hmtx"][name] = (adv if adv is not None else round(src["hmtx"][src_name][0] * scale), getattr(g, "xMin", 0))


def shape_glyph(target, name, contour_pts_list, adv):
    pen = TTGlyphPen(None)
    for pts in contour_pts_list:
        pen.moveTo(pts[0])
        for p in pts[1:]:
            pen.lineTo(p)
        pen.closePath()
    g = pen.glyph()
    target["glyf"][name] = g
    g.recalcBounds(target["glyf"])
    target["hmtx"][name] = (adv, g.xMin)


def circle(cx, cy, r, n=48):
    # TrueType 바깥 윤곽은 시계 방향
    return [(round(cx + r * math.cos(-2 * math.pi * k / n + math.pi / 2)), round(cy + r * math.sin(-2 * math.pi * k / n + math.pi / 2))) for k in range(n)]


def square(cx, cy, h):
    return [(cx - h, cy - h), (cx - h, cy + h), (cx + h, cy + h), (cx + h, cy - h)]


def ensure_glyph(font, code, name):
    """cmap 에 없는 코드포인트면 새 글리프 자리를 만든다."""
    cmap = font.getBestCmap()
    if code in cmap:
        return cmap[code]
    order = font.getGlyphOrder()
    order.append(name)
    font.setGlyphOrder(order)
    font["glyf"].glyphs[name] = TTGlyphPen(None).glyph()
    font["hmtx"][name] = (0, 0)
    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap[code] = name
    return name


def build() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    reg, bold = TTFont(REG), TTFont(BOLD)
    gr, gb = reg["glyf"], bold["glyf"]
    cmap = reg.getBestCmap()

    # 1) 굵기 섞기
    mixed = kept = 0
    for name in (reg.getGlyphOrder() if T else []):
        if name not in gb.glyphs:
            continue
        g = lerp_glyph(gr, gb, name, T)
        if g is None:
            kept += 1
            continue
        gr[name] = g
        ar, ab = reg["hmtx"][name][0], bold["hmtx"][name][0]
        g.recalcBounds(gr)
        reg["hmtx"][name] = (round(ar + (ab - ar) * T), getattr(g, "xMin", 0))
        mixed += 1

    # 한글 글자 몸 세로 중심
    ga = gr[cmap[ord("가")]]; ga.recalcBounds(gr)
    hy = round((ga.yMin + ga.yMax) / 2)

    # 2) 숫자 — Bold, 고정폭
    bcmap = bold.getBestCmap()
    digits = [ord(c) for c in "0123456789"]
    cell = max(bold["hmtx"][bcmap[c]][0] for c in digits)
    for c in digits:
        src = bcmap[c]
        gl = gb[src]; gl.recalcBounds(gb)
        w = gl.xMax - gl.xMin
        copy_scaled(reg, cmap[c], bold, src, 1.0, dx=round((cell - w) / 2 - gl.xMin), adv=cell)

    # 3) 기호 — Bold, 1.12배, 한글 중심으로
    for ch in SYMBOLS:
        src = bcmap[ord(ch)]
        gl = gb[src]; gl.recalcBounds(gb)
        sy = (gl.yMin + gl.yMax) / 2 * SYMBOL_SCALE
        adv = round(bold["hmtx"][src][0] * SYMBOL_SCALE)
        w = (gl.xMax - gl.xMin) * SYMBOL_SCALE
        copy_scaled(reg, cmap[ord(ch)], bold, src, SYMBOL_SCALE,
                    dx=round((adv - w) / 2 - gl.xMin * SYMBOL_SCALE), dy=round(hy - sy), adv=adv)

    # 4) 새로 그림 — 'to' 원, 숫자 상자
    dot_adv, dot_r = 430, 78          # 가운뎃점
    bul_adv, bul_r = 520, 112         # 불릿
    blk_adv, blk_r = 910, 300         # ● ■ (한글 한 칸)
    shape_glyph(reg, cmap[0x00B7], [circle(dot_adv // 2, hy, dot_r)], dot_adv)
    shape_glyph(reg, ensure_glyph(reg, 0x2022, "bullet.to"), [circle(bul_adv // 2, hy, bul_r)], bul_adv)
    shape_glyph(reg, ensure_glyph(reg, 0x25CF, "blackcircle.to"), [circle(blk_adv // 2, hy, blk_r)], blk_adv)
    shape_glyph(reg, ensure_glyph(reg, 0x25A0, "blacksquare.box"), [square(blk_adv // 2, hy, 280)], blk_adv)

    # 5) 이름·라이선스
    name = reg["name"]
    orig = TTFont(REG)["name"].getDebugName(0)
    name.names = []
    values = {
        0: f"{orig} Modifications for Ten to Sans (C) 2026.",
        1: FAMILY, 2: "Regular", 3: f"{PS};2026-09-15", 4: f"{FAMILY} Regular", 5: "Version 1.000",
        6: PS, 10: DESCRIPTION,
        13: "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
        14: "https://openfontlicense.org",
    }
    for nid, val in values.items():
        name.setName(val, nid, 3, 1, 0x409)
    reg["OS/2"].achVendID = "TENT"
    reg["OS/2"].usWeightClass = 500
    reg["head"].fontRevision = 1.0

    opts = Options()
    opts.layout_features = []
    opts.name_IDs = ["*"]; opts.name_languages = ["*"]
    opts.notdef_outline = True; opts.glyph_names = False; opts.hinting = False
    sub = Subsetter(opts)
    sub.populate(unicodes=list(reg.getBestCmap().keys()))
    sub.subset(reg)

    ttf = OUT / f"{PS}.ttf"
    reg.flavor = None
    reg.save(ttf)
    reg.flavor = "woff2"
    reg.save(OUT / f"{PS}.woff2")
    (OUT / "OFL.txt").write_text(
        f"{FAMILY} — modified from NanumSquareRound.\n\n{orig}\nNanumSquareRound is licensed under the SIL Open Font License 1.1 "
        "(NAVER Nanum fonts). 'Nanum' is a reserved font name and is not used by this derivative.\n"
        "Modifications (C) 2026: tabular Bold figures, enlarged symbols, "
        "redrawn middle dot / bullet / black circle / black square.\n"
        "Ten to Sans is not affiliated with or endorsed by Toss / Viva Republica.\n\n"
        "This Font Software is licensed under the SIL Open Font License, Version 1.1.\n"
        "https://openfontlicense.org/open-font-license-official-text/\n", encoding="utf-8")
    print(f"[Ten to Sans] 섞음 {mixed} / R 유지 {kept}, 숫자 폭 {cell}, 한글 중심 {hy} → {ttf} "
          f"({ttf.stat().st_size // 1024}KB, woff2 {(OUT / f'{PS}.woff2').stat().st_size // 1024}KB)")
    return ttf


if __name__ == "__main__":
    build()
