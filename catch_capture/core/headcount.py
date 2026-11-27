"""모집인원 — 공고가 '몇 자리'를 뽑는가. (회사 사원수는 `core.classifier.extract_headcount` — 다른 것이다)

공고 수는 채용의 크기가 아니다. 공고 한 건이 1명일 수도 있고 두 자릿수일 수도 있다. 그런데
개발 공고의 모집인원은 숫자로 안 쓰는 경우가 많고, 대신 **자릿수로** 쓴다:

    1명 · 3명      → 정확한 수 (n=1, 3 · digits=1)
    ○명 · O명      → 한 자릿수 (1~9명)
    ○○명 · 00명    → 두 자릿수 (10~99명)
    0명 · 빈칸      → 밝히지 않음(잡코리아 입력칸의 기본값) — 0명을 뽑는 공고는 없다

잡코리아는 공고 페이지에 '모집인원' 칸이 따로 있다(close_check 가 이미 그 페이지를 받는다).
다른 사이트는 칸이 없어서 본문의 "모집인원 : ○명" 같은 문구에서 읽는다.
"""
from __future__ import annotations

import re
from typing import NamedTuple

_MARK = "○◯〇oOㅇ"


class Headcount(NamedTuple):
    raw: str               # 원문 그대로('○○명')
    n: int | None          # 정확한 수. 자릿수 표기면 None
    digits: int | None     # 자릿수 — 1: 1~9명, 2: 10~99명 …  모르면 None

    @property
    def low(self) -> int | None:
        if self.n is not None:
            return self.n
        return 10 ** (self.digits - 1) if self.digits else None

    @property
    def high(self) -> int | None:
        if self.n is not None:
            return self.n
        return 10 ** self.digits - 1 if self.digits else None


_VALUE = re.compile(
    rf"^\s*(?:약|총)?\s*(?P<num>\d{{1,4}})?(?P<mark>[{_MARK}]{{1,3}})?(?P<zeros>0{{2,3}})?\s*(?:여\s*)?명")


def parse(raw: str | None) -> Headcount | None:
    """'모집인원' 칸의 값 하나. 숫자도 자릿수도 아니면 None('0명'·'미정'·'-')."""
    if not raw:
        return None
    s = raw.strip()
    m = _VALUE.match(s)
    if not m:
        return None
    num, mark, zeros = m.group("num"), m.group("mark"), m.group("zeros")
    if mark and not num:
        return Headcount(s, None, len(mark))
    if zeros and not num:                       # '00명' — ○○ 를 0 으로 친 것
        return Headcount(s, None, len(zeros))
    if num:
        v = int(num)
        if v == 0:
            # '0명' 은 입력칸 기본값(밝히지 않음). '00명' 은 ○○ 를 0 으로 친 것 — 두 자릿수다.
            return Headcount(s, None, len(num)) if len(num) >= 2 and not mark else None
        if mark:                                # '1○명'(십몇 명) 같은 드문 표기
            return Headcount(s, None, len(num) + len(mark))
        return Headcount(s, v, len(str(v)))
    return None


# 잡코리아 공고 페이지의 '모집인원' 칸. 값 안에 React 주석(<!-- -->)이 끼어 있다.
_JOBKOREA_FIELD = re.compile(r"모집인원</span>\s*<span[^>]*>(.*?)</span>", re.S)
_TAGS = re.compile(r"<!--.*?-->|<[^>]+>", re.S)


def from_jobkorea_page(html: str) -> str | None:
    """잡코리아 공고 페이지 → 모집인원 원문. 칸이 없으면 None."""
    m = _JOBKOREA_FIELD.search(html or "")
    if not m:
        return None
    v = _TAGS.sub("", m.group(1)).strip()
    return v or None


# 본문의 "모집인원 : ○명" · "채용 인원 2명" · "선발인원: 00명"
_TEXT = re.compile(
    rf"(?:모집|채용|선발)\s*인원\s*[:：\-]?\s*(?:은|는)?\s*((?:약|총)?\s*(?:\d{{1,4}}|[{_MARK}]{{1,3}}|0{{2,3}})\s*(?:여\s*)?명)")


def from_text(text: str | None) -> str | None:
    """본문에서 모집인원 원문. 여러 번 나오면(직무가 여럿인 공고) 첫 것."""
    m = _TEXT.search(text or "")
    return m.group(1).strip() if m else None
