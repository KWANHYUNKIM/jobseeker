"""디자인 방향 — 장을 찍기 전에 '무엇으로 어떻게 보일지' 를 정하고, 왜 그랬는지 남긴다.

디자인은 네 가지가 동시에 맞아야 한다. 하나라도 따로 놀면 '그냥 어둡고 끝난' 판이 된다.

  날짜·계절   오늘 날짜 → 계절과 그 시기의 일(MOMENTS). 사진 소재와 문구가 여기서 온다
  내용        코너의 주제(마감·숫자·직군) → 사진이 말하는 것이 제목과 같아야 한다(catalog 의 tags·means)
  회사 이미지  회사가 나오는 장은 brands/*.json 의 색·서체가 이긴다. 계절은 사진·소품으로만
  트렌드      research/ig_trends_*.json — 인스타에서 직접 본 것. 판 고르기 규칙으로 쓴다

부딪히면: 회사 이미지 > 내용 > 계절 > 트렌드.

색은 사람이 정하지 않는다 — 고른 사진의 픽셀에서 뽑는다(palette_from_photo). 그래야 사진과 판이 한 장으로 읽힌다.
종이는 사진의 주된 색을 아주 옅게, 잉크는 같은 색을 아주 짙게, 강조색은 사진에서 가장 선명한 색.
검정 바탕은 기본값이 아니다 — 사진이 어두울 때만 나온다.

    from poster import direction
    d = direction.decide("deadline", tags=["마감", "시간"])     # → {season, photo, palette, trend, why}
"""
from __future__ import annotations

import colorsys
import json
from datetime import date
from pathlib import Path

from PIL import Image

LAB_DIR = Path(__file__).resolve().parent.parent
PHOTOS = LAB_DIR / "assets" / "photos" / "season"
RESEARCH = LAB_DIR / "research"

SEASONS = {12: "겨울", 1: "겨울", 2: "겨울", 3: "봄", 4: "봄", 5: "봄", 6: "여름", 7: "여름", 8: "여름",
           9: "가을", 10: "가을", 11: "가을"}
#: 그 달에 취준생·이직자가 겪는 일 — 문구와 이유에 쓴다(사진 소재는 catalog 가 정한다)
MOMENTS = {
    1: ["새해 이직 결심", "연봉 협상"], 2: ["졸업", "상반기 공채 시작"], 3: ["상반기 공채", "입학·개강"],
    4: ["상반기 공채 서류·인적성"], 5: ["상반기 면접"], 6: ["상반기 마무리", "하계 인턴"],
    7: ["하계 인턴", "여름휴가"], 8: ["하반기 공채 준비"], 9: ["하반기 공채 시작", "추석"],
    10: ["하반기 공채 막바지", "은행잎·단풍", "할로윈(10/31)"], 11: ["수능", "하반기 면접", "첫눈"],
    12: ["연말", "내년 이직 준비"],
}


# --- 색 ------------------------------------------------------------------
def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in rgb)


def _hls(rgb):
    return colorsys.rgb_to_hls(*(v / 255 for v in rgb))


def _from_hls(h, l, s):
    return tuple(v * 255 for v in colorsys.hls_to_rgb(h, l, s))


def _lum(rgb) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    r, g, b = rgb
    return .2126 * ch(r) + .7152 * ch(g) + .0722 * ch(b)


def contrast(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


def palette_from_photo(path: Path) -> dict:
    """사진 → 키트 색 다섯. 대비는 여기서 보장한다 — 잉크·강조색 모두 종이 위 4.5:1 이상(강조색이 본문에도 쓰인다)."""
    with Image.open(path) as im:
        small = im.convert("RGB").resize((160, 160))
    q = small.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:24]
    counts = sorted(q.getcolors(), reverse=True)          # [(개수, 번호)]
    cols = [(n, tuple(pal[i * 3:i * 3 + 3])) for n, i in counts]
    total = sum(n for n, _ in cols)
    # 주된 색: 가장 넓은 면적 중 너무 어둡거나 하얗지 않은 것
    dom = next((c for n, c in cols if .12 < _hls(c)[1] < .9), cols[0][1])
    # 강조색: 면적이 5% 넘는 것 중 가장 선명한(채도 × 적당한 밝기)
    def vivid(c):
        h, l, s = _hls(c)
        return s * (1 - abs(l - .5) * 1.4)
    accent = max((c for n, c in cols if n / total > .05), key=vivid)
    h, _, s = _hls(dom)
    paper = _from_hls(h, .955, min(.45, s * .6))
    ink = _from_hls(h, .11, min(.35, s * .5))
    sub = _from_hls(h, .36, min(.2, s * .3))
    line = _from_hls(h, .84, min(.25, s * .4))
    ah, al, as_ = _hls(accent)
    acc = _from_hls(ah, al, max(as_, .55))
    while contrast(acc, paper) < 4.5 and al > .05:        # 종이 위에서 본문 크기로도 읽히게 어둡게
        al -= .03
        # 노랑은 그냥 어두워지면 올리브(탁한 녹갈색)가 된다 — 호박색 쪽으로 돌리며 어둡게(은행잎이 그렇게 진다)
        if .1 < ah < .19:
            ah = max(.085, ah - .012)
        acc = _from_hls(ah, al, max(as_, .8 if ah < .19 else .55))
    return {"paper": _hex(paper), "ink": _hex(ink), "sub": _hex(sub), "accent": _hex(acc), "line": _hex(line),
            "_from": {"dominant": _hex(dom), "vivid": _hex(accent)}}


# --- 결정 ----------------------------------------------------------------
def _catalog() -> dict:
    return json.loads((PHOTOS / "catalog.json").read_text(encoding="utf-8"))


def _credits() -> dict:
    return json.loads((PHOTOS / "credits.json").read_text(encoding="utf-8"))


def trend_rules() -> tuple[dict, str]:
    files = sorted(RESEARCH.glob("ig_trends_*.json"))
    if not files:
        return {}, ""
    d = json.loads(files[-1].read_text(encoding="utf-8"))
    return d["rules"], f"{files[-1].name} ({d.get('observed_at', '')})"


def pick_photo(tags: list[str], season: str, exclude: set[str] = frozenset()) -> tuple[str, dict, int]:
    """계절이 같은 사진 중 내용 태그가 가장 많이 겹치는 것."""
    best = None
    for name, c in _catalog().items():
        if c["season"] != season or name in exclude:
            continue
        score = len(set(tags) & set(c["tags"]))
        if best is None or score > best[2]:
            best = (name, c, score)
    if best is None:
        raise LookupError(f"{season} 사진이 catalog 에 없다 — assets/photos/season/catalog.json 에 더할 것")
    return best


def decide(corner: str, tags: list[str], trends: list[str], today: date | None = None,
           brand: dict | None = None, exclude: set[str] = frozenset()) -> dict:
    """코너 하나의 방향. brand 가 있으면(회사 장) 색은 회사 것, 사진은 계절 것."""
    today = today or date.today()
    season = SEASONS[today.month]
    name, cat, score = pick_photo(tags, season, exclude)
    credit = _credits()[name]
    path = PHOTOS / name
    if brand:
        ui = brand.get("ui", {})
        palette = {k: ui.get(k) or brand.get("palette", {}).get(k) for k in ("paper", "ink", "sub", "accent", "line")}
        color_why = f"{brand.get('wordmark')} 의 브랜드 색(brands/*.json) — 회사 이미지가 계절보다 먼저"
    else:
        palette = palette_from_photo(path)
        color_why = f"사진에서 뽑음 — 주된 색 {palette['_from']['dominant']} · 가장 선명한 색 {palette['_from']['vivid']}"
    rules, src = trend_rules()
    return {
        "corner": corner,
        "date": today.isoformat(),
        "season": {"name": season, "month": today.month, "moments": MOMENTS[today.month]},
        "content": {"tags": tags, "matched": sorted(set(tags) & set(cat["tags"])), "score": score},
        "photo": {"file": name, "src": f"photos/{name}", "subject": cat["subject"], "means": cat["means"],
                  "focus": cat.get("focus", "50% 50%"), "credit": credit["credit"], "license": credit["license"],
                  "path": str(path)},
        "palette": {k: v for k, v in palette.items() if not k.startswith("_")},
        "color_why": color_why,
        "trend": [{"key": k, **rules[k]} for k in trends if k in rules],
        "trend_source": src,
        "priority": "회사 이미지 > 내용 > 계절 > 트렌드",
    }
