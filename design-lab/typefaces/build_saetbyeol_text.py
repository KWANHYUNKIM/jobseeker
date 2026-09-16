"""Saetbyeol Text — 컬리 공고 포스터(샛별배송 판) 본문용 파생 서체.

무료 서체를 바탕으로 우리 판에 맞게 고친다. 처음부터 그리지 않는다(BRAND_RESEARCH.md 4절).
LOCA Batang(날카로운 명조 + Garamond + 가는 나침반 별)과 성격이 반대가 되게 잡았다.

  바탕       나눔스퀘어라운드(NanumSquareRound) R / B — 획 끝이 둥근 고딕. 16.5px 흰 모듈 상자에서
             Pretendard 보다 부드럽고(식품·새벽 배송), 굵기가 흔들리지 않는다. 영문·숫자도 같은 둥근 계열이라 그대로 둔다
  글자 사이  한글·영문 모두 +12(1000 단위) — 둥근 고딕은 획이 뭉쳐 보이기 쉬워 조금 띄운다
  새로 그림  가운뎃점 · 과 * → '샛별'(원본에 불릿 • 글리프가 없어 · 를 불릿으로 쓴다). 옆변이 안쪽으로 휜 네 갈래 반짝임(✦), 세로가 가로보다 길다.
             LOCA 의 곧은 가는 별과 달리 속이 찬 둥근 곡선이다
             느낌표 ! 의 점 → 작은 샛별 (복지 글머리 '…제공해요!' '…지원해요!' 끝에 걸린다)
  이름       'Saetbyeol Text' — 컬리 공식 서체가 아니라는 뜻으로 중립 이름. Regular(R 바탕)·Bold(B 바탕)
  라이선스   나눔글꼴 = SIL OFL 1.1 (수정·재배포 가능, 서체 자체 판매 금지). 원 저작권 + 수정 고지 + OFL 동봉

    PYTHONPATH=<fonttools+brotli> python typefaces/build_saetbyeol_text.py
    → assets/companies/컬리/fonts/SaetbyeolText/SaetbyeolText-{Regular,Bold}.woff2, OFL.txt
"""
from __future__ import annotations

from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

LAB = Path(__file__).resolve().parent.parent
BODY = LAB / "assets/companies/컬리/fonts/body"
OUT = LAB / "assets/companies/컬리/fonts/SaetbyeolText"
SOURCES = {"Regular": BODY / "NanumSquareRoundR.woff2", "Bold": BODY / "NanumSquareRoundB.woff2"}

FAMILY = "Saetbyeol Text"
TRACK = 12
DESCRIPTION = ("Saetbyeol Text: derived from NanumSquareRound (NAVER Corporation, SIL OFL 1.1) for a Kurly "
               "job poster. Letter spacing +12/1000; middle dot, bullet, asterisk and the dot of the exclamation "
               "mark redrawn as a soft four-point morning star. Not an official Kurly typeface.")


def sparkle(pen, cx: float, cy: float, rx: float, ry: float, pinch: float = 0.2) -> None:
    """네 갈래 반짝임. 끝점 넷을 안쪽으로 휜 이차 곡선으로 잇는다(위→오른쪽→아래→왼쪽, 시계 방향 = TrueType 바깥 윤곽)."""
    k = min(rx, ry) * pinch
    pts = [(cx, cy + ry), (cx + rx, cy), (cx, cy - ry), (cx - rx, cy)]
    ctrl = [(cx + k, cy + k), (cx + k, cy - k), (cx - k, cy - k), (cx - k, cy + k)]
    r = lambda p: (round(p[0]), round(p[1]))
    pen.moveTo(r(pts[0]))
    for i in range(4):
        pen.qCurveTo(r(ctrl[i]), r(pts[(i + 1) % 4]))
    pen.closePath()


def set_glyph(font: TTFont, name: str, pen: TTGlyphPen, advance: int) -> None:
    g = pen.glyph()
    font["glyf"][name] = g
    g.recalcBounds(font["glyf"])
    font["hmtx"][name] = (advance, getattr(g, "xMin", 0))


def contours(font: TTFont, name: str) -> list[list]:
    """글리프를 풀어 윤곽 단위 명령 목록으로."""
    rec = DecomposingRecordingPen(font.getGlyphSet())
    font.getGlyphSet()[name].draw(rec)
    out, cur = [], []
    for op, args in rec.value:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            out.append(cur); cur = []
    return out


def bounds(ops: list) -> tuple:
    bp = BoundsPen(None)
    for op, args in ops:
        getattr(bp, op)(*args)
    return bp.bounds


def build_one(style: str, src: Path) -> Path:
    f = TTFont(src)
    cmap = f.getBestCmap()
    hm = f["hmtx"]

    # 글자 사이 — 모든 글리프의 폭에 TRACK, 윤곽은 가운데로 TRACK/2 옮긴다(합성 글리프는 폭만)
    glyf = f["glyf"]
    for name in f.getGlyphOrder():
        adv, lsb = hm[name]
        if adv == 0:
            continue
        g = glyf[name]
        if g.numberOfContours > 0:
            coords, ends, flags = g.getCoordinates(glyf)
            coords.translate((TRACK // 2, 0))
            g.coordinates = coords
            g.recalcBounds(glyf)
            hm[name] = (adv + TRACK, getattr(g, "xMin", lsb + TRACK // 2))
        else:
            hm[name] = (adv + TRACK, lsb)

    ga = glyf[cmap[ord("가")]]; ga.recalcBounds(glyf)
    mid = round((ga.yMin + ga.yMax) / 2)            # 한글 글자 몸 세로 중심

    # 가운뎃점 · — 작은 샛별
    if 0xB7 in cmap:
        n = cmap[0xB7]; adv = hm[n][0]
        pen = TTGlyphPen(None); sparkle(pen, adv / 2, mid, 175, 250, 0.13); set_glyph(f, n, pen, adv)
    # 불릿 • — 원본에 있으면 조금 더 큰 샛별(나눔스퀘어라운드엔 없음)
    if 0x2022 in cmap:
        n = cmap[0x2022]; adv = max(hm[n][0], 620)
        pen = TTGlyphPen(None); sparkle(pen, adv / 2, mid, 215, 300, 0.13); set_glyph(f, n, pen, adv)
    # * — 위쪽 샛별
    if ord("*") in cmap:
        n = cmap[ord("*")]; adv = hm[n][0]
        pen = TTGlyphPen(None); sparkle(pen, adv / 2, 560, 140, 190); set_glyph(f, n, pen, adv)
    # ! 의 점 → 작은 샛별 (세로 획은 그대로)
    if ord("!") in cmap:
        n = cmap[ord("!")]; adv = hm[n][0]
        parts = contours(f, n)
        pen = TTGlyphPen(None)
        for ops in parts:
            x0, y0, x1, y1 = bounds(ops)
            if y1 < 200:                                 # 바닥의 점
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                sparkle(pen, cx, cy - 6, (x1 - x0) * 0.95, (y1 - y0) * 0.98, 0.15)
            else:
                for op, args in ops:
                    getattr(pen, op)(*args)
        set_glyph(f, n, pen, adv)

    # 이름
    name = f["name"]
    orig = name.getDebugName(0) or "Copyright 2017 NAVER Corporation."
    ps = f"SaetbyeolText-{style}"
    for rec in list(name.names):
        if rec.nameID in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25):
            name.removeNames(nameID=rec.nameID)
    for nid, val in {0: f"{orig} Modifications (Saetbyeol Text), 2026.", 1: FAMILY, 2: style,
                     3: f"{ps};2026-09-15", 4: f"{FAMILY} {style}", 6: ps, 10: DESCRIPTION,
                     13: "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
                     14: "https://openfontlicense.org"}.items():
        name.setName(val, nid, 3, 1, 0x409)
    f["OS/2"].achVendID = "SBTX"
    f["OS/2"].usWeightClass = 700 if style == "Bold" else 400
    f["head"].macStyle = 1 if style == "Bold" else 0
    f["head"].fontRevision = 1.0

    opts = Options()
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]; opts.name_languages = ["*"]
    opts.notdef_outline = True; opts.glyph_names = False; opts.hinting = False
    sub = Subsetter(opts); sub.populate(unicodes=list(cmap.keys())); sub.subset(f)

    OUT.mkdir(parents=True, exist_ok=True)
    f.flavor = "woff2"
    dest = OUT / f"{ps}.woff2"
    f.save(dest)
    print(f"[Saetbyeol Text] {style} ← {src.name} · +{TRACK} · 샛별 → {dest.name} ({dest.stat().st_size // 1024}KB)")
    return dest


def main() -> None:
    for style, src in SOURCES.items():
        build_one(style, src)
    (OUT / "OFL.txt").write_text(
        "Saetbyeol Text — modified from NanumSquareRound (나눔스퀘어라운드).\n"
        "Copyright 2017 NAVER Corporation. Font designed by Sandoll Communications Inc.\n"
        "Modifications 2026: letter spacing, redrawn middle dot / bullet / asterisk / exclamation dot (morning star).\n"
        "Not an official Kurly typeface.\n\n"
        "This Font Software is licensed under the SIL Open Font License, Version 1.1.\n"
        "https://openfontlicense.org/open-font-license-official-text/\n"
        "나눔글꼴 라이선스: https://hangeul.naver.com (SIL OFL 1.1 — 수정·재배포 가능, 글꼴 자체 유료 판매 금지)\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
