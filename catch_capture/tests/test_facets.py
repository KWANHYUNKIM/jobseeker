"""필터 축 규칙(store.jobs.facets) — 뷰어 TS 원본과 같은 답을 내는가.

기대값은 짐작이 아니라 뷰어 TS(region.ts·classify.ts·career.ts)를 node 로 돌려 얻은
값이다. 그래서 원본 규칙의 이상한 답도 그대로 박혀 있다 — 그런 줄에는 '원본 규칙의
알려진 버그' 라고 적었다. 고치려면 TS 와 여기를 같이 고친다.
"""
from __future__ import annotations

import pytest

from store.jobs.facets import _js_slice, _stacks, career_bucket, classify_roles, facets_of, place_of

W = "　"   # 전각 공백 — JS 의 \s·trim 은 이걸 공백으로 본다


@pytest.mark.parametrize("career, want", [
    ("", "정보없음"),
    (None, "정보없음"),
    ("신입", "신입/무관"),
    ("경력무관", "신입/무관"),
    ("경력 3년 이상", "3-4년"),
    ("1~2년", "1-2년"),
    ("10년 이상", "8년+"),
    ("경력", "정보없음"),
])
def test_career_bucket(career, want):
    assert career_bucket(career) == want


@pytest.mark.parametrize("title, stack, extra, want", [
    ("백엔드 개발자", [], "", ["백엔드"]),
    ("Android 개발자", [], "", ["모바일"]),
    # 원본 규칙의 알려진 버그: JS 의 \b 는 ASCII 기준이라 한글 '안드로이드' 옆에서는
    # 경계가 안 생겨 모바일로 안 잡힌다. 파이썬도 re.ASCII 로 같은 답을 낸다.
    ("안드로이드 개발자", [], "", ["기타"]),
    ("풀스택 엔지니어", [], "", ["풀스택", "백엔드", "프론트엔드"]),
    # 전각 들여쓰기 — JS 의 \s 는 　 을 공백으로 본다(파이썬 ASCII \s 는 안 본다).
    ("사내 IT", [], f"업무시스템\n\n{W}운영 경험", ["DevOps/인프라"]),
    ("Senior Engineer", ["React", "Spring"], "", ["백엔드", "프론트엔드"]),
    ("마케팅 담당", [], "", ["기타"]),
    ("QA 엔지니어", [], "", ["QA"]),
    ("AI 연구원", [], "", ["AI/ML"]),
    ("데이터AI팀", [], "", ["AI/ML"]),
])
def test_classify_roles(title, stack, extra, want):
    assert classify_roles(title, stack, extra) == want


def test_classify_reads_only_first_500_utf16_units():
    # 자격요건은 앞 500자(JS 문자열 단위 = UTF-16)만 본다. 그 뒤의 '풀스택' 은 무시된다.
    assert classify_roles("x", [], "가" * 500 + " 풀스택") == ["기타"]
    assert classify_roles("x", [], "가" * 490 + " 풀스택") == ["풀스택", "백엔드", "프론트엔드"]


def test_js_slice_counts_astral_as_two():
    s = "😀" * 3              # BMP 밖 글자는 UTF-16 로 2칸
    assert _js_slice(s, 4) == "😀😀"
    assert _js_slice("abc", 10) == "abc"


@pytest.mark.parametrize("loc, want", [
    ("서울 강남구", ("서울", "강남구")),
    # 원본 규칙의 알려진 버그: '서울특별시' 도 '서울' 로 시작하므로 남은 '특별시' 를
    # 시군구로 읽었다가 행정 접미어라 버린다 — 강남구를 못 얻는다.
    ("서울특별시 강남구", ("서울", None)),
    ("경기성남시 분당구", ("경기", "성남시")),
    ("교육생 | 서울 송파구", ("서울", "송파구")),
    ("해외 도쿄", ("해외·원격", None)),
    ("Pangyo (Software Dream Center), South Korea", ("경기", None)),
    ("Seoul", ("서울", None)),
    ("Remote", ("해외·원격", None)),
    ("South Korea", ("정보없음", None)),
    ("", ("정보없음", None)),
    ("대한민국 서울특별시 중구", ("서울", None)),
    ("세종특별자치시", ("세종", None)),
    (f"{W}부산 해운대구", ("부산", "해운대구")),
    ("서울광역시", ("서울", None)),
])
def test_place_of(loc, want):
    assert place_of(loc) == want


def test_place_of_overseas_flag_wins():
    assert place_of("서울 강남구", overseas=True) == ("해외·원격", None)


def test_stacks_trim_and_dedupe_keep_order():
    assert _stacks([" Java", "Spring", "Java ", "", "  "]) == ["Java", "Spring"]
    assert _stacks(None) == []


def test_facets_of_uses_viewer_job_shape():
    f = facets_of({"title": "백엔드 개발자", "tech_stack": ["Java"], "qualifications": "",
                   "location": "서울 마포구", "overseas": False, "career": "신입"})
    assert f == {"region": "서울", "district": "마포구", "roles": ["백엔드"],
                 "career_bucket": "신입/무관"}
