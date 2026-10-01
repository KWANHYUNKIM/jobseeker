"""문자열 보조 함수 — 뷰어(JS)와 같은 결과를 내야 하는 것들."""
from __future__ import annotations

# JS 의 String.prototype.trim 이 공백으로 보는 문자(NBSP·전각 공백 등 포함).
# 파이썬 str.strip() 은 이 중 일부를 공백으로 안 본다 — 뷰어와 검색어가 갈리지 않게.
JS_WS = ("\t\n\v\f\r            "
         "      　﻿")


def js_trim(s: str) -> str:
    return s.strip(JS_WS)


def like_pattern(q: str) -> str:
    """부분일치 LIKE 패턴. %·_·\\ 는 글자 그대로 찾는다(ESCAPE '\\')."""
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def split_multi(values: list[str]) -> list[str]:
    """?site=a&site=b 와 ?site=a,b 를 둘 다 받는다. 순서를 지키고 중복은 뺀다."""
    out: list[str] = []
    for v in values:
        for part in v.split(","):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    return out
