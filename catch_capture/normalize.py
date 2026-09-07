"""회사명 정규화의 단일 소스.

이 저장소에는 한때 회사명을 정규화하는 규칙이 넷 있었고, 이관 작업에서 나온 결함
다섯 중 둘이 거기서 나왔다:

  1. `pipeline/aggregate._norm_key`      공백+소문자만 → `(주)클로봇` ≠ `클로봇`
  2. `dashboard/classifier._norm_company` NFKC + 법인격 제거 (제대로 된 것)
  3. `store/slug.norm_company`            2번을 베낀 것
  4. `jd-viewer/src/lib/companyMark.ts`   TypeScript 쪽 (아래 참고)

2번과 3번이 같은 규칙의 두 구현이었다. 이 파일이 그 하나다 — classifier 와 store 가
여기서 가져다 쓴다. classifier 에 두지 않은 이유는 그 모듈이 import 할 때
companies.json 을 읽어 들이는 무거운 모듈이라, 크롤·백필 경로가 그걸 끌고 들어올
이유가 없기 때문이다.

1번(aggregate)은 일부러 그대로 둔다. 그 경로는 이관이 끝나면 사라지고, 지금 규칙을
바꾸면 이관 2단계에서 JSON 과 DB 를 나란히 놓고 비교하는 일이 어려워진다.

4번은 **다른 규칙이고 그래야 한다.** 파이썬 쪽은 `넛지헬스케어(캐시워크)` 를
`넛지헬스케어캐시워크` 로 두지만, 뷰어 쪽은 괄호 안을 통째로 버려 `넛지헬스케어` 로
만든다. 취업 브리핑을 회사명으로 찾을 때 별칭 괄호를 무시해야 맞기 때문이다.
둘을 억지로 합치면 브리핑 매칭이 깨진다. 대신 **NFKC 는 양쪽 다 건다** — `㈜`(한 글자)를
못 지워서 그 회사 브리핑이 화면에서 사라진 적이 있다.
"""
from __future__ import annotations

import re
import unicodedata

# 법인격 표기. NFKC 를 먼저 걸어 `㈜`(U+321C)가 `(주)` 로 펴진 뒤에 지운다.
_LEGAL = re.compile(
    r"\(주\)|주식회사|㈜|inc\.?|co\.?,?\s*ltd\.?|corp\.?|corporation|ltd\.?"
)
_PUNCT = re.compile(r"[\s\-_().,&/]+")


def company(name: str) -> str:
    """비교용 정규화: NFKC + 소문자 + 법인격·공백·괄호·특수문자 제거.

        '메가존클라우드㈜' → '메가존클라우드'
        '(주)클로봇'       → '클로봇'
        'Coupang Inc.'     → 'coupang'

    이 값이 정본 DB 의 `company.norm` 이고, 회사의 정체성이다.
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).lower()
    s = _LEGAL.sub("", s)
    return _PUNCT.sub("", s)
