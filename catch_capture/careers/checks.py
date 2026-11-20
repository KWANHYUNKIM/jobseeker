"""원문으로 확인하는 규칙 — 모델이 고른 값이 글에 근거가 있는지, 글이 IT 이야기인지.

로컬 모델(qwen3:14b)은 모르면 null 대신 그럴듯한 값을 고르는 일이 많다(2026-11 확인: '비전공 4년제' 2,417건 중
절반쯤은 원문에 전공 이야기가 없었다). 그래서 학력·전환은 원문에 근거 낱말이 있을 때만 남기고, 없으면 지운다.
화면에서는 지운 값을 '확인되지 않음' 으로 보여 준다.
"""
from __future__ import annotations

import re

UNKNOWN = "확인되지 않음"

# IT 이야기인지 — 제목+본문에 하나라도 있어야 한다. 'IT' 는 대문자로만(영어 it 와 헷갈리지 않게).
_IT_CASE = re.compile(r"(?<![A-Za-z])(IT|SW|S/W|SI|SM|AI|QA|PM|CS|iOS|AWS|KDT|SSAFY|FAANG|SQLD?|ADsP|ADSP|TIL|DB|API)(?![A-Za-z])")
_IT = re.compile(
    r"개발|프로그래|코딩|코테|소프트웨어|백엔드|프론트|풀스택|서버|데이터|인공지능|머신러닝|딥러닝|클라우드|인프라|"
    r"데브옵스|엔지니어|안드로이드|부트캠프|국비|싸피|우테코|우아한테크코스|부스트캠프|항해\s?99|42\s?서울|소프트웨어\s?마에스트로|"
    r"컴퓨터|컴공|전산|정보처리|정보통신|정보보안|리눅스|네트워크|빅데이터|내배캠|내일배움캠프|자바|파이썬|스프링|리액트|깃허브|알고리즘|퍼블리셔|테크리드|기술\s?면접|"
    r"devops|developer|engineer|software|programm|coding|frontend|backend|full[- ]?stack|github|leetcode|"
    r"java|python|spring|react|kotlin|swift|typescript|javascript|node\.?js|django|kubernetes|docker",
    re.I)

# 비전공·비개발 근거
_NON = re.compile(
    r"비전공|문과|인문|비개발|비컴공|전공이\s*아닌|전공자가\s*아닌|전공과\s*(무관|상관\s*없|다른)|타\s?전공|다른\s*전공|"
    r"경영학|경제학|국문|영문과|어문|심리학|사회학|행정학|법학|디자인\s*전공|미술|음악|체육|간호|화학과|생명|물리학과|"
    r"기계공학|화공|건축|토목|산업공학|신소재|"
    r"non[- ]?(cs|tech)|no (cs|computer science) degree|career (change|switch|chang)|self[- ]taught|without a (cs )?degree",
    re.I)
# 컴퓨터 계열 전공 근거
_CS = re.compile(
    r"컴퓨터\s*공학|컴공|전산|소프트웨어\s*(학|공학|전공)|컴퓨터\s*(과학|전공|학과|학부)|정보통신|정보보호|정보보안\s*학|"
    r"(cs|CS)\s*전공|전공자(?!가\s*아닌)|computer science|cs degree|cs major|컴퓨터\s*교육",
    re.I)
# 개발 전에 다른 일을 했다는 근거(비개발→개발 전환)
_PRIOR_JOB = re.compile(
    r"영업|마케팅|마케터|디자이너|공무원|교사|선생님|강사|간호|회계|생산직|공정|반도체|군인|부사관|장교|서비스직|"
    r"기획자|은행원|승무원|요리|바리스타|자영업|물류|연구원|사무직|퇴사\s*후\s*(개발|코딩)|전직|이전\s*직장|"
    r"(was|worked) (a|as)n? (teacher|nurse|designer|marketer|chef|accountant|lawyer|sales)",
    re.I)


def is_it(text: str) -> bool:
    return bool(_IT_CASE.search(text or "") or _IT.search(text or ""))


DEV_PLATFORMS = {"velog", "devto"}   # 개발자만 쓰는 곳 — 본문에 '개발' 이 없어도('최종합격!' 엔씨 후기 등) 개발자 글이다


def is_it_item(source: str | None, text: str) -> bool:
    """출처까지 보고 IT 글인지 — 인스타·티스토리·Medium·캡처처럼 누구나 쓰는 곳만 본문을 검사한다."""
    return source in DEV_PLATFORMS or is_it(text)


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in ("", "null", "none", "모름", "unknown", UNKNOWN))


def check_background(r: dict, text: str) -> dict:
    """학력·전공·전환을 원문 근거로 다시 본다. 근거 없는 값은 지우고 *_unverified 에 모델이 고른 값을 남긴다."""
    bg = r.get("background")
    if isinstance(bg, dict):
        ed = bg.get("education")
        if isinstance(ed, str) and not blank(ed):
            if "비전공" in ed and not _NON.search(text):
                bg["education"], bg["education_unverified"] = None, ed
            elif re.search(r"CS|컴퓨터|IT", ed) and not _CS.search(text):
                bg["education"], bg["education_unverified"] = None, ed
        mf = bg.get("major_field")
        if isinstance(mf, str) and not blank(mf):
            if mf == "컴퓨터" and not _CS.search(text):
                bg["major_field"], bg["major_field_unverified"] = None, mf
            elif mf != "컴퓨터" and not _NON.search(text):
                bg["major_field"], bg["major_field_unverified"] = None, mf
        elif blank(mf):
            bg["major_field"] = None
        if blank(bg.get("education")):
            bg["education"] = None
    tr = r.get("transition")
    if isinstance(tr, str) and re.search(r"비개발|비전공", tr) and not (_NON.search(text) or _PRIOR_JOB.search(text)):
        r["transition"], r["transition_unverified"] = None, tr
    return r
