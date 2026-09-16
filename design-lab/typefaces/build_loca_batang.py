"""LOCA Batang — 롯데카드 공고 포스터 본문용 파생 서체.

무료 서체(SIL OFL)를 바탕으로 우리 판에 맞게 고친다. 처음부터 그리지 않는다(BRAND_RESEARCH.md 4절).

  한글       Hahmlet(함렛) wght 460 — 17px 폰 화면에서 명조가 흐려지지 않는 굵기
  숫자·영문  EB Garamond wght 480 ×1.2 — 롯데카드 'ESSENCE OF CREDIT CARD' 캠페인의 고전 로마자 세리프 계열.
             세로획 두께를 재서 한글 'ㅣ' 와 맞췄다(37 vs 36, 400px 렌더 기준). 숫자는 높이가 일정한 lining(.lf)
  새로 그림  가운뎃점 · 과 불릿 • → LOCA BI 의 가늘고 긴 네 방향 나침반 별
  이름       'LOCA Batang' (OFL 은 수정본에 새 이름을 요구한다). 두 원본 저작권 + OFL 전문 동봉

    PYTHONPATH=<fonttools 설치 경로> python typefaces/build_loca_batang.py
    → assets/companies/롯데카드/fonts/LOCABatang/LOCABatang-Regular.{ttf,woff2}, OFL.txt
"""
from __future__ import annotations

import io
import math
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

LAB = Path(__file__).resolve().parent.parent
FONTS = LAB / "assets/companies/롯데카드/fonts"
HAHMLET = FONTS / "body/Hahmlet[wght].ttf"
GARAMOND = FONTS / "EBGaramond-VF.ttf"
OUT = FONTS / "LOCABatang"

WGHT_KO = 460
WGHT_LATIN = 480
SCALE_LATIN = 1.2                # Garamond 소문자 높이(400)가 낮아 1.14(대문자 맞춤)면 한글 옆에서 작아 보였다 → 1.2
TRACK_LATIN = 8                  # 영문·숫자 글자 사이 여유(1000 단위)
LATIN = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
         "!\"#$%&'()*+,-./:;<=>?@[\\]_{|}~–—‘’“”")
STAR_CHARS = [0x00B7, 0x2022]    # · •

FAMILY = "LOCA Batang"
PS = "LOCABatang-Regular"
DESCRIPTION = ("LOCA Batang: 롯데카드 공고 포스터용 파생 서체. Hangul from Hahmlet (wght 460), "
               "Latin and figures from EB Garamond (wght 480, lining figures, scaled 1.2), "
               "middle dot and bullet redrawn as a four-point compass star. Modified under the SIL OFL 1.1.")


def static(path: Path, wght: int) -> TTFont:
    vf = TTFont(path)
    return instancer.instantiateVariableFont(vf, {"wght": wght})


def draw_into(target: TTFont, name: str, src: TTFont, src_name: str, scale: float) -> None:
    """src 글리프를 풀어서(구성요소 분해) 배율을 곱해 target 의 name 자리에 새 윤곽으로 넣는다."""
    gs = src.getGlyphSet()
    rec = DecomposingRecordingPen(gs)
    gs[src_name].draw(rec)
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, (scale, 0, 0, scale, TRACK_LATIN / 2, 0)))
    glyph = pen.glyph()
    target["glyf"][name] = glyph
    adv = round(src["hmtx"][src_name][0] * scale) + TRACK_LATIN
    glyph.recalcBounds(target["glyf"])
    target["hmtx"][name] = (adv, getattr(glyph, "xMin", 0))


def star(target: TTFont, name: str, center_y: int, radius: int, advance: int) -> None:
    """가늘고 긴 네 방향 별 — 끝점 넷, 안쪽 점 넷(반지름의 16%). LOCA BI '나침반'."""
    cx = advance // 2
    inner = radius * 0.17
    pts = []
    for k in range(8):
        ang = math.pi / 2 - k * math.pi / 4          # 위에서 시작, 시계 방향(TrueType 바깥 윤곽)
        r = radius if k % 2 == 0 else inner
        pts.append((round(cx + r * math.cos(ang)), round(center_y + r * math.sin(ang))))
    pen = TTGlyphPen(None)
    pen.moveTo(pts[0])
    for p in pts[1:]:
        pen.lineTo(p)
    pen.closePath()
    glyph = pen.glyph()
    target["glyf"][name] = glyph
    glyph.recalcBounds(target["glyf"])
    target["hmtx"][name] = (advance, glyph.xMin)


def rename(font: TTFont) -> None:
    name = font["name"]
    hcopy = TTFont(HAHMLET)["name"].getDebugName(0)
    gcopy = TTFont(GARAMOND)["name"].getDebugName(0)
    for rec in list(name.names):
        if rec.nameID in (1, 3, 4, 6, 16, 17, 21, 22, 25):
            name.removeNames(nameID=rec.nameID)
    values = {
        0: f"{hcopy}. {gcopy}. Modifications for LOCA Batang, 2026.",
        1: FAMILY, 2: "Regular", 3: f"{PS};2026-09-15", 4: f"{FAMILY} Regular", 6: PS,
        10: DESCRIPTION,
        13: "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
        14: "https://openfontlicense.org",
    }
    for nid, val in values.items():
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)
    font["OS/2"].achVendID = "LOCA"
    if "fvar" in font:
        del font["fvar"]


def build() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    ko = static(HAHMLET, WGHT_KO)
    la = static(GARAMOND, WGHT_LATIN)
    ko_cmap, la_cmap = ko.getBestCmap(), la.getBestCmap()
    la_order = set(la.getGlyphOrder())

    replaced = 0
    for ch in LATIN:
        code = ord(ch)
        if code not in ko_cmap or code not in la_cmap:
            continue
        src = la_cmap[code]
        if ch.isdigit() and f"{src}.lf" in la_order:      # 높이가 일정한 숫자
            src = f"{src}.lf"
        draw_into(ko, ko_cmap[code], la, src, SCALE_LATIN)
        replaced += 1

    # 별 — 한글 글자 몸('가')의 세로 중심에. 원래 가운뎃점은 영문 기준(266)이라 한글 사이에서 위로 떠 보였다
    ga = ko["glyf"][ko_cmap[ord("가")]]
    ga.recalcBounds(ko["glyf"])
    hangul_center = round((ga.yMin + ga.yMax) / 2)
    for code, radius, adv in ((0x00B7, 230, 540), (0x2022, 260, 600)):
        if code in ko_cmap:
            star(ko, ko_cmap[code], hangul_center, radius, adv)

    rename(ko)
    ko["head"].fontRevision = 1.0

    # 레이아웃 기능은 뺀다 — 원래 함렛의 숫자 대체(lnum/onum/tnum)·영문 커닝이 바꿔 넣은 글리프와 어긋난다
    opts = Options()
    opts.layout_features = []
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.glyph_names = False
    opts.hinting = False
    sub = Subsetter(opts)
    sub.populate(unicodes=list(ko_cmap.keys()))
    sub.subset(ko)

    ttf = OUT / f"{PS}.ttf"
    ko.save(ttf)
    ko.flavor = "woff2"
    ko.save(OUT / f"{PS}.woff2")
    (OUT / "OFL.txt").write_text(
        f"{FAMILY} — modified from Hahmlet and EB Garamond.\n\n{TTFont(HAHMLET)['name'].getDebugName(0)}\n"
        f"{TTFont(GARAMOND)['name'].getDebugName(0)}\nModifications (C) 2026.\n\n"
        "This Font Software is licensed under the SIL Open Font License, Version 1.1.\n"
        "https://openfontlicense.org/open-font-license-official-text/\n", encoding="utf-8")
    print(f"[LOCA Batang] 한글 {WGHT_KO} + 영문·숫자 {replaced}자 교체 + 별 2자 → {ttf} ({ttf.stat().st_size // 1024}KB), "
          f"woff2 {(OUT / f'{PS}.woff2').stat().st_size // 1024}KB")
    return ttf


if __name__ == "__main__":
    build()
