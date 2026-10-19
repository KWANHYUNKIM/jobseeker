"""표지(첫 장) 자동 검사 — 원고(deck.yaml)만 보고 판정한다. 그림을 보는 판정은 사람(8780 /design)의 몫이다.

교훈을 더할 때는 검사부터 쓴다(RED → GREEN, .claude/skills/writing-design-lessons). 검사가 없는 교훈은
"지켰다"를 기계가 말할 수 없어서 시안마다 사람이 다시 봐야 한다.

    python -m agent eval            # 지금 원고들을 검사
"""
from __future__ import annotations

import re

#: 한 줄에 들어가는 글자 수(1080px 표지, 굵은 제목 기준). '*강조*' 표시는 세지 않는다.
LINE_MAX = 14
WEEK = re.compile(r"\d{1,2}월\s?\d주차")
FACT = re.compile(r"^[\d,.]+(%|건|곳|명|만|억)?$")


def _cover(deck: dict) -> dict:
    return next((s for s in deck.get("slides") or [] if s.get("role") == "cover"), {})


def _lines(title: str) -> list[str]:
    return [l.replace("*", "").strip() for l in (title or "").split("\n") if l.strip()]


def week_pill(deck):
    c = _cover(deck)
    text = " ".join(str(c.get(k) or "") for k in ("pill", "kicker"))
    return bool(WEEK.search(text)), text or "알약 없음"


def title_two_lines(deck):
    ls = _lines(_cover(deck).get("title", ""))
    long = [l for l in ls if len(l) > LINE_MAX]
    return 0 < len(ls) <= 2 and not long, f"{len(ls)}줄" + (f", 긴 줄 {long}" if long else "")


def focal_max_3(deck):
    c = _cover(deck)
    focal = ["title"] if c.get("title") else []
    focal += [k for k in ("image", "number") if c.get(k)]
    if c.get("logos") or c.get("logo"):
        focal.append("logos")
    if c.get("items"):
        focal.append("items")
    return len(focal) <= 3, " + ".join(focal)


def known_name(deck):
    """표지에 알아보는 이름(회사)이 보이나 — 로고가 있거나, 뒤 장에 나오는 회사 이름이 표지 글에 있다."""
    c = _cover(deck)
    if c.get("logos") or c.get("logo") or c.get("brand"):
        return True, "로고"
    text = " ".join(str(c.get(k) or "") for k in ("title", "kicker", "sub", "pill"))
    names = {i.get("label") for s in deck.get("slides", [])[1:] for i in s.get("items") or [] if i.get("label")}
    hit = [n for n in names if len(n) >= 2 and n in text]
    return bool(hit), (", ".join(hit[:3]) if hit else "회사 이름·로고 없음")


def number_is_fact(deck):
    n = str(_cover(deck).get("number") or "").strip()
    if not n:
        return True, "숫자 없음(해당 없음)"
    return bool(FACT.match(n)), n


def second_pays(deck):
    """표지가 물었으면 2번째 장이 바로 답한다(끝 장·빈 장이면 안 된다)."""
    slides = deck.get("slides") or []
    c = _cover(deck)
    if "?" not in (c.get("title") or ""):
        return True, "질문 아님(해당 없음)"
    nxt = slides[1] if len(slides) > 1 else {}
    ok = nxt.get("role") not in (None, "end", "cover") and bool(nxt.get("items") or nxt.get("number") or nxt.get("rows"))
    return ok, f"2번째 장 {nxt.get('role')}"


#: id → 검사 · 교훈 문장 · 근거. 교훈(DB design_lesson)의 apply.check 가 이 id 를 가리킨다.
CHECKS = {
    "week-pill": {"fn": week_pill, "lesson": "회차 알약('10월 4주차')은 늘 같은 자리",
                  "why": "연재임을 알려 저장을 부른다 — 링커리어·캐치 [관찰]"},
    "title-two-lines": {"fn": title_two_lines, "lesson": f"제목은 두 줄, 한 줄 {LINE_MAX}자 이하",
                        "why": "작은 화면에서 1초 안에 읽힌다 — 한눈 시험 [실무]"},
    "focal-max-3": {"fn": focal_max_3, "lesson": "초점은 셋 이하", "why": "눈 갈 곳이 많으면 아무것도 안 본다 [실무]"},
    "known-name": {"fn": known_name, "lesson": "표지에 아는 이름(회사 로고·이름)",
                   "why": "채용 계정 첫 장 대부분이 회사가 주인공 — 캐치 [관찰]"},
    "number-is-fact": {"fn": number_is_fact, "lesson": "표지 숫자는 사실(건·곳·%)이지 장식(VOL.01)이 아니다",
                       "why": "숫자는 멈추게 하지만 장식 숫자는 약속을 못 갚는다 [실무]"},
    "second-pays": {"fn": second_pays, "lesson": "질문은 표지에, 답은 2번째 장에 바로",
                    "why": "안 넘긴 사람에게 2번째 장부터 다시 보여 준다 · 시청 시간으로 이긴다 [실무·공식]"},
}


def run(deck: dict) -> list[dict]:
    out = []
    for cid, c in CHECKS.items():
        ok, detail = c["fn"](deck)
        out.append({"id": cid, "ok": bool(ok), "detail": detail, "lesson": c["lesson"]})
    return out


def by_id(deck: dict, cid: str) -> dict:
    return next(r for r in run(deck) if r["id"] == cid)
