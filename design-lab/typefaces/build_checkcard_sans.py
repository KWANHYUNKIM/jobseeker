"""Checkcard Sans — 카카오뱅크 공고 포스터(세로형 체크카드 판) 본문용 파생 서체.

무료 서체(SIL OFL)를 바탕으로 판에 맞게 고친다(BRAND_RESEARCH.md 4절, LOCA Batang 과 같은 방식).
카카오뱅크 공식 서체가 아니다 — 이름에 회사명을 넣지 않는다.

  한글·영문  Kakao Small Sans(카카오 작은글씨) — 카카오가 2025 공개(OFL 1.1). 작은 화면용으로 자간·속공간이 넓어
             17px 회색 패널에서 Pretendard 보다 또렷하고, 둥글고 넓은 영문이 기본 고딕 인상을 지운다
  숫자 0–9   Share Tech Mono(OFL 1.1, RFN 'Share') — 각진 고정폭 OCR 계열. 카드 번호 각인 숫자처럼 보이게.
             Kakao 대문자 높이(733)에 맞춰 ×1.047, 세로획을 재서 한글 'ㅣ' 와 맞춤(35 vs 34, 400px 렌더)
  Bold 숫자  Share Tech Mono 는 굵기가 하나라 윤곽을 가로로 겹쳐 찍어 굵힌다(Kakao Bold 획 차이만큼)
  새로 그림  불릿 • 과 가운뎃점 · → 체크카드 IC 칩: 둥근 세로 사각 테두리 + 안쪽 십자 홈선(판의 흰 카드 칩과 같은 구조)
  이름       'Checkcard Sans' — 원본 저작권 셋 + OFL 전문 동봉. 'Share' 는 예약 이름이라 쓰지 않는다

    PYTHONPATH=<fonttools 설치 경로> python typefaces/build_checkcard_sans.py
    → assets/companies/카카오뱅크/fonts/CheckcardSans/CheckcardSans-{Regular,Bold}.{ttf,woff2}, OFL.txt
"""
from __future__ import annotations

from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

LAB = Path(__file__).resolve().parent.parent
FONTS = LAB / "assets/companies/카카오뱅크/fonts"
KAKAO = {"Regular": FONTS / "kakao/KakaoSmallSans-Regular.ttf", "Bold": FONTS / "kakao/KakaoSmallSans-Bold.ttf"}
MONO = FONTS / "body/ShareTechMono-Regular.ttf"
OUT = FONTS / "CheckcardSans"

FAMILY = "Checkcard Sans"
DIGIT_SCALE = 733 / 700          # Kakao 대문자 높이 / Share Tech Mono 대문자 높이
DIGIT_ADV = 530                  # 고정폭 — 카드 번호처럼 자릿수가 맞는다. 600 은 "3 0 0" 처럼 벌어져 530
BOLD_SMEAR = 34                  # Bold 숫자: 같은 윤곽을 이만큼 오른쪽에 한 번 더(겹친 윤곽, nonzero 채움)


def mono_digit(target: TTFont, name: str, mono: TTFont, src: str, smear: int) -> None:
    gs = mono.getGlyphSet()
    rec = DecomposingRecordingPen(gs)
    gs[src].draw(rec)
    w = mono["hmtx"][src][0] * DIGIT_SCALE
    dx = (DIGIT_ADV - w - smear) / 2
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, (DIGIT_SCALE, 0, 0, DIGIT_SCALE, dx, 0)))
    if smear:
        rec.replay(TransformPen(pen, (DIGIT_SCALE, 0, 0, DIGIT_SCALE, dx + smear, 0)))
    glyph = pen.glyph()
    target["glyf"][name] = glyph
    glyph.recalcBounds(target["glyf"])
    target["hmtx"][name] = (DIGIT_ADV, glyph.xMin)


def _rrect(pen, x0, y0, x1, y1, r, clockwise=True):
    """둥근 사각형 — TrueType 곡선(qCurveTo). clockwise=True 가 바깥 윤곽, False 가 구멍."""
    pts = [((x0 + r, y1), (x1 - r, y1), (x1, y1), (x1, y1 - r)),
           ((x1, y1 - r), (x1, y0 + r), (x1, y0), (x1 - r, y0)),
           ((x1 - r, y0), (x0 + r, y0), (x0, y0), (x0, y0 + r)),
           ((x0, y0 + r), (x0, y1 - r), (x0, y1), (x0 + r, y1))]
    if not clockwise:
        # 반대 방향으로 같은 모양
        pen.moveTo((x0 + r, y1))
        pen.qCurveTo((x0, y1), (x0, y1 - r))
        pen.lineTo((x0, y0 + r))
        pen.qCurveTo((x0, y0), (x0 + r, y0))
        pen.lineTo((x1 - r, y0))
        pen.qCurveTo((x1, y0), (x1, y0 + r))
        pen.lineTo((x1, y1 - r))
        pen.qCurveTo((x1, y1), (x1 - r, y1))
        pen.closePath()
        return
    pen.moveTo(pts[0][0])
    for start, end, ctrl, nxt in pts:
        pen.lineTo(end)
        pen.qCurveTo(ctrl, nxt)
    pen.closePath()


def _rect(pen, x0, y0, x1, y1):
    """채운 사각(시계 방향 = 바깥 윤곽)."""
    pen.moveTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0)); pen.lineTo((x0, y0)); pen.closePath()


def chip(target: TTFont, name: str, center_y: int, height: int, advance: int, bold: bool) -> None:
    """IC 칩 — 둥근 세로 사각 테두리(한글 획 두께) + 안쪽 가로 홈선 한 줄과 가운데 세로 홈선(위아래 끝은 떨어짐).
    판 머리의 흰 카드 .chip(가로선 1 + 세로선 1, 세로선은 위·아래 22% 비움)과 같은 구조.
    처음엔 꽉 찬 사각에 홈을 팠더니 17px 에서 검은 네모로 뭉개져, 테두리형으로 바꿨다."""
    w = round(height * 0.78)
    x0 = (advance - w) // 2; x1 = x0 + w
    y0 = center_y - height // 2; y1 = y0 + height
    r = round(height * 0.2)
    t = 46 if bold else 36            # 테두리 = 한글 'ㅣ' 세로획(Regular 34 / Bold 46, 400px 렌더)
    h = 22 if bold else 16            # 안쪽 홈선
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    pen = TTGlyphPen(None)
    _rrect(pen, x0, y0, x1, y1, r, clockwise=True)
    _rrect(pen, x0 + t, y0 + t, x1 - t, y1 - t, max(r - t, 4), clockwise=False)
    _rect(pen, x0 + t, cy - h // 2, x1 - t, cy + h - h // 2)                       # 가로 홈선
    gap = round((height - 2 * t) * 0.22)
    _rect(pen, cx - h // 2, y0 + t + gap, cx + h - h // 2, y1 - t - gap)            # 세로 홈선(끝 비움)
    glyph = pen.glyph()
    target["glyf"][name] = glyph
    glyph.recalcBounds(target["glyf"])
    target["hmtx"][name] = (advance, glyph.xMin)


def rename(font: TTFont, style: str, src: Path) -> None:
    name = font["name"]
    kcopy = TTFont(src)["name"].getDebugName(0)
    mcopy = TTFont(MONO)["name"].getDebugName(0)
    ps = f"CheckcardSans-{style}"
    for rec in list(name.names):
        if rec.nameID in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25):
            name.removeNames(nameID=rec.nameID)
    values = {
        0: f"{kcopy}. {mcopy}. Modifications for Checkcard Sans, 2026.",
        1: FAMILY, 2: style, 3: f"{ps};2026-09-15", 4: f"{FAMILY} {style}", 6: ps,
        10: ("Checkcard Sans: 카카오뱅크 공고 포스터용 파생 서체(공식 서체 아님). Hangul/Latin from Kakao Small Sans, "
             "figures from Share Tech Mono (scaled, fixed 530 width), bullet and middle dot redrawn as an IC chip. "
             "Modified under the SIL Open Font License 1.1."),
        13: "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
        14: "https://openfontlicense.org",
    }
    for nid, val in values.items():
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)
    font["OS/2"].achVendID = "CKCS"


def build_style(style: str) -> Path:
    src = KAKAO[style]
    font = TTFont(src)
    mono = TTFont(MONO)
    cmap, mcmap = font.getBestCmap(), mono.getBestCmap()
    bold = style == "Bold"
    for d in "0123456789":
        mono_digit(font, cmap[ord(d)], mono, mcmap[ord(d)], BOLD_SMEAR if bold else 0)

    ga = font["glyf"][cmap[ord("가")]]
    ga.recalcBounds(font["glyf"])
    center = round((ga.yMin + ga.yMax) / 2)
    for code, height, adv in ((0x2022, 440, 600), (0x00B7, 330, 470)):
        if code in cmap:
            chip(font, cmap[code], center, height, adv, bold)

    rename(font, style, src)
    font["head"].fontRevision = 1.0

    opts = Options()
    opts.layout_features = ["kern"]      # 영문 커닝만 남긴다(숫자 대체 기능은 바꾼 글리프와 어긋난다)
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.glyph_names = False
    opts.hinting = False
    sub = Subsetter(opts)
    sub.populate(unicodes=list(cmap.keys()))
    sub.subset(font)

    OUT.mkdir(parents=True, exist_ok=True)
    ttf = OUT / f"CheckcardSans-{style}.ttf"
    font.save(ttf)
    font.flavor = "woff2"
    font.save(OUT / f"CheckcardSans-{style}.woff2")
    print(f"[Checkcard Sans {style}] 숫자 10자 교체 + 칩 2자 → {ttf.name} ({ttf.stat().st_size // 1024}KB), "
          f"woff2 {(OUT / f'CheckcardSans-{style}.woff2').stat().st_size // 1024}KB")
    return ttf


def main() -> None:
    for style in ("Regular", "Bold"):
        build_style(style)
    (OUT / "OFL.txt").write_text(
        f"{FAMILY} — modified from Kakao Small Sans and Share Tech Mono. Not an official KakaoBank typeface.\n\n"
        f"{TTFont(KAKAO['Regular'])['name'].getDebugName(0)}\n"
        f"{TTFont(MONO)['name'].getDebugName(0)}\n"
        "Modifications (C) 2026. Reserved Font Name 'Share' is not used.\n\n"
        + (FONTS / "kakao/OFL.txt").read_text(encoding="utf-8").split("-----------------------------------------------------------", 1)[-1],
        encoding="utf-8")


if __name__ == "__main__":
    main()
