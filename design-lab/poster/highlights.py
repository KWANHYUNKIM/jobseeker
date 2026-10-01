"""하이라이트 표지 — 프로필 아래 동그라미에 들어갈 9:16 한 장씩.

하이라이트는 웹·API 로 못 만든다(스토리부터 앱에서 올려야 한다). 그래서 여기서는 표지만 찍어 두고
사람이 앱에서 스토리로 올린 뒤 하이라이트에 넣는다. 인스타는 가운데 원만 보여 주므로 글자는 정중앙에
짧게(두 글자~네 글자) 둔다. 색은 그 시리즈의 판 색(series.THEMES)을 따른다 — 하이라이트를 누르면
같은 색의 판이 나오게.

    python -m poster.highlights        # → out/highlights/*.jpg
"""
from __future__ import annotations

from pathlib import Path

from .series import LAB_DIR, THEMES

OUT = LAB_DIR / "out" / "highlights"

#: (파일 이름, 동그라미 글자, 판 색 키, 무엇을 모으나) — GROWTH.md '하이라이트 메뉴' 와 같은 순서
MENU = [
    ("01-newgrad", "신입", "welcome", "신입 환영 · 신입 고민 · 신입 초봉"),
    ("02-pay", "연봉", "pay", "신입 초봉 · 외주 단가"),
    ("03-company", "회사", "talent", "회사 해부 · 인재상 · 채용 시그널"),
    ("04-lunch", "점심", "lunch", "점심 지도"),
    ("05-kit", "웰컴키트", "kit", "첫 출근 웰컴키트"),
    ("06-strategy", "전략", "gongchae", "공채는 끝났다 · 공부 로드맵 · JD 번역기"),
    ("07-perk", "조건", "perk", "이런 조건 되는 곳 · 출근길 지도"),
    ("08-term", "용어", "term", "IT 용어 · 면접 예상 질문"),
]

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;box-sizing:border-box}}
body{{width:1080px;height:1920px;background:{paper};display:flex;align-items:center;justify-content:center;
font-family:'Pretendard','Noto Sans KR','Malgun Gothic',sans-serif}}
.c{{width:760px;height:760px;border-radius:50%;background:{accent};display:flex;align-items:center;justify-content:center}}
b{{color:{paper};font-size:{size}px;font-weight:800;letter-spacing:-.04em;white-space:nowrap}}
</style></head><body><div class="c"><b>{word}</b></div></body></html>"""


def main() -> int:
    from .render import _page_maker, shutdown
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        for name, word, theme, what in MENU:
            t = THEMES[theme]
            size = 260 if len(word) <= 2 else 150
            page = _page_maker().new_page(viewport={"width": 1080, "height": 1920})
            try:
                page.set_content(HTML.format(paper=t["paper"], accent=t["accent"], word=word, size=size))
                page.screenshot(path=str(OUT / f"{name}.jpg"), type="jpeg", quality=92)
            finally:
                page.close()
            print(f"[highlights] {name}.jpg — {word}: {what}")
    finally:
        shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
