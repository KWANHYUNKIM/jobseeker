"""Woowa Lane — 우아한형제들(배민) 공고 포스터 모집 내용 본문용 파생 서체.

무료 서체를 바탕으로 우리 판에 맞게 고친다. 처음부터 그리지 않는다(BRAND_RESEARCH.md 4절).
LOCA Batang(롯데카드 — 고전 명조 + Garamond 영문 + 나침반 별)과 성격이 정반대인 '간판 고딕' 쪽이다.

  바탕       배민 한나는11살체 — 배민 공식 무료 서체 12종 중 본문 17px·해설 13px 에서 가장 또렷하다
             (후보판 out/wanted-366409/body_font_board.jpg). 한나 계열이라 제목(한나체 Pro)과 한 집안이다.
             숫자는 원래부터 한글보다 굵다(세로획 72 vs 'ㅣ' 55, 400px 렌더) — 11가지 방법 포스터의 굵은 번호와
             같은 결이라 그대로 둔다. 영문도 한나 결 그대로 둔다(Pretendard 영문으로 바꾸면 다시 기본 고딕이 된다).
  고침       자간 +14/1000 — 해설 단 13px 에서 글자가 붙어 보이지 않게
  새로 그림  가운뎃점 · 과 불릿 • → 새 앱 아이콘의 검정 차선 막대(세로로 선 짧고 굵은 막대)
             느낌표 ! → 11가지 방법 포스터 마지막 줄 '떠나거나!' 의 기울어진 굵은 느낌표(쐐기 + 네모 점)
  이름       'Woowa Lane' — 원본 이름(BM HANNA …)은 쓰지 않는다
  라이선스   배민 서체 라이선스(woowahan.com): 자유롭게 수정·변경해 영리·비영리 사용 가능, 폰트 파일 유료 판매 금지.
             원본 저작권과 수정 내역을 LICENSE.txt 로 동봉

    PYTHONPATH=<fonttools 설치 경로> python typefaces/build_woowa_lane.py
    → assets/companies/우아한형제들/fonts/WoowaLane/WoowaLane-Regular.{ttf,woff2}, LICENSE.txt
"""
from __future__ import annotations

import math
from pathlib import Path

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

LAB = Path(__file__).resolve().parent.parent
FONTS = LAB / "assets/companies/우아한형제들/fonts"
BASE = FONTS / "BMHANNA_11yrs_ttf.ttf"
OUT = FONTS / "WoowaLane"

TRACK = 14                      # 모든 글자 오른쪽에 더하는 여유(1000 단위)
FAMILY = "Woowa Lane"
PS = "WoowaLane-Regular"
DESCRIPTION = ("Woowa Lane: 배민 공고 포스터 본문용 파생 서체. Base: BM HANNA 11yrs old (Woowa Brothers, free font). "
               "Tracking +14, middle dot and bullet redrawn as a road-lane bar, exclamation redrawn as a slanted wedge. "
               "Modified under the Woowa Brothers free font license (modification allowed, no sale of font files).")


def poly(target: TTFont, name: str, contours: list[list[tuple[float, float]]], advance: int) -> None:
    """점 목록(각각 시계 방향)으로 새 윤곽을 만들어 name 자리에 넣는다."""
    pen = TTGlyphPen(None)
    for pts in contours:
        pen.moveTo((round(pts[0][0]), round(pts[0][1])))
        for x, y in pts[1:]:
            pen.lineTo((round(x), round(y)))
        pen.closePath()
    glyph = pen.glyph()
    target["glyf"][name] = glyph
    glyph.recalcBounds(target["glyf"])
    target["hmtx"][name] = (advance, glyph.xMin)


def hangul_body(font: TTFont) -> tuple[int, int]:
    g = font["glyf"][font.getBestCmap()[ord("가")]]
    g.recalcBounds(font["glyf"])
    return g.yMin, g.yMax


def lane_bar(font: TTFont, name: str, width: int, height: int, advance: int) -> None:
    """차선 막대 — 한글 글자 몸 세로 가운데에 선 네모 막대. 끝은 둥글리지 않는다(앱 아이콘 막대가 각지다)."""
    lo, hi = hangul_body(font)
    cy = (lo + hi) / 2
    x0 = (advance - width) / 2
    x1, y0, y1 = x0 + width, cy - height / 2, cy + height / 2
    poly(font, name, [[(x0, y0), (x0, y1), (x1, y1), (x1, y0)]], advance)


def slanted_bang(font: TTFont, name: str, advance: int) -> None:
    """기울어진 굵은 느낌표 — 위가 넓은 쐐기 + 네모 점, 12° 기울임. 높이는 원래 느낌표와 같게."""
    g = font["glyf"][name]
    g.recalcBounds(font["glyf"])
    top, base = g.yMax, 0
    sl = math.tan(math.radians(12))
    sk = lambda x, y: (x + (y - base) * sl, y)                     # noqa: E731
    cx = advance / 2 - (top * sl) / 2
    stem_bot = base + 230
    wedge = [sk(cx - 70, top), sk(cx + 70, top), sk(cx + 34, stem_bot), sk(cx - 34, stem_bot)]
    wedge = [wedge[3], wedge[0], wedge[1], wedge[2]]              # 왼아래 → 왼위 → 오른위 → 오른아래(시계 방향)
    d = 56
    dot = [sk(cx - d, base), sk(cx - d, base + 2 * d - 4), sk(cx + d, base + 2 * d - 4), sk(cx + d, base)]
    poly(font, name, [wedge, dot], advance)


def rename(font: TTFont) -> None:
    name = font["name"]
    original = name.getDebugName(0) or "WOOWA BROTHERS Corporation"
    for rec in list(name.names):
        if rec.nameID in (0, 1, 3, 4, 5, 6, 7, 10, 13, 14, 16, 17, 21, 22, 25):
            name.removeNames(nameID=rec.nameID)
    values = {
        0: f"Original: BM HANNA 11yrs old, {original}. Modifications for Woowa Lane, 2026.",
        1: FAMILY, 2: "Regular", 3: f"{PS};2026-09-15", 4: f"{FAMILY} Regular", 5: "Version 1.000", 6: PS,
        10: DESCRIPTION,
        13: "Derived from a Woowa Brothers free font. Free to modify and use commercially; selling the font file is not allowed.",
        14: "https://www.woowahan.com/fonts",
    }
    for nid, val in values.items():
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)
    font["OS/2"].achVendID = "WLNE"


def build() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    font = TTFont(BASE)
    cmap = font.getBestCmap()

    # 자간 — 모든 글자 너비에 TRACK 을 더하고 윤곽을 반만큼 오른쪽으로(좌우 여유를 똑같이)
    glyf, hmtx = font["glyf"], font["hmtx"]
    for gname in font.getGlyphOrder():
        adv, lsb = hmtx[gname]
        if adv == 0:
            continue
        g = glyf[gname]
        if g.isComposite():
            for comp in g.components:
                comp.x += TRACK // 2
        elif g.numberOfContours > 0:
            coords = g.coordinates
            for i in range(len(coords)):
                x, y = coords[i]
                coords[i] = (x + TRACK // 2, y)
        hmtx[gname] = (adv + TRACK, lsb + TRACK // 2)
    for gname in font.getGlyphOrder():          # 구성요소 글자의 경계는 부품이 다 옮겨진 뒤에
        glyf[gname].recalcBounds(glyf)

    # 첫 판(폭 96~106)은 24px 에서 영문 'ı' 로 읽혔다 → 폭을 한글 획의 3~4배(세로:가로 ≈ 2:1)로 키워 차선 토막으로 보이게
    for code, width, height, adv in ((0x00B7, 170, 330, 400), (0x2022, 220, 440, 470)):
        if code in cmap:
            lane_bar(font, cmap[code], width, height, adv)
    if ord("!") in cmap:
        slanted_bang(font, cmap[ord("!")], hmtx[cmap[ord("!")]][0] + 20)

    rename(font)
    font["head"].fontRevision = 1.0

    # 커닝만 남긴다 — 다른 대체 기능은 새로 그린 글자와 어긋날 수 있다
    opts = Options()
    opts.layout_features = ["kern"]
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.glyph_names = False
    opts.hinting = False
    sub = Subsetter(opts)
    sub.populate(unicodes=list(cmap.keys()))
    sub.subset(font)

    ttf = OUT / f"{PS}.ttf"
    font.save(ttf)
    font.flavor = "woff2"
    font.save(OUT / f"{PS}.woff2")
    (OUT / "LICENSE.txt").write_text(
        f"{FAMILY} — derived from BM HANNA 11yrs old (배달의민족 한나는 열한살).\n"
        "Original copyright: WOOWA BROTHERS Corporation. Designers: 김봉진, 금재현, 태주희, 김민정.\n\n"
        "Base font license (woowahan.com/fonts): 배달의민족 글꼴은 자유롭게 수정·변경하여 영리적·비영리적 목적으로\n"
        "개인 및 기업 사용자가 모두 사용할 수 있습니다. 인쇄물·포스터·광고·로고 등에 사용 가능하며,\n"
        "폰트 파일(otf/ttf) 자체를 유료로 판매할 수 없습니다.\n\n"
        "Modifications (2026-09-15, design-lab/typefaces/build_woowa_lane.py):\n"
        f"- renamed to '{FAMILY}' (original names not used)\n"
        f"- tracking +{TRACK}/1000 on every glyph\n"
        "- U+00B7 middle dot and U+2022 bullet redrawn as a vertical road-lane bar\n"
        "- U+0021 exclamation mark redrawn as a slanted wedge with a square dot\n", encoding="utf-8")
    print(f"[Woowa Lane] 자간 +{TRACK}, 차선 막대 2자, 느낌표 1자 → {ttf} ({ttf.stat().st_size // 1024}KB), "
          f"woff2 {(OUT / f'{PS}.woff2').stat().st_size // 1024}KB")
    return ttf


if __name__ == "__main__":
    build()
