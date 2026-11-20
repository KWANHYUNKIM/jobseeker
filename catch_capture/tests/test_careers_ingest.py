"""커리어 후기 적재 규칙 — 회사 유형·익명 회사·경력직 출발지·간 곳."""
from __future__ import annotations

import pytest

from store.ingest import careers as c


@pytest.mark.parametrize("co,want", [
    ("카카오뱅크", "금융"), ("토스뱅크", "금융"), ("하나은행", "금융"), ("토스", "빅테크·플랫폼"),
    ("네이버웹툰", "빅테크·플랫폼"), ("LG CNS", "SI·SM"), ("현대오토에버", "SI·SM"), ("삼성전자DS", "대기업"),
    ("SKT", "대기업"), ("넥슨", "게임"), ("AWS", "외국계"), ("두번째 회사", "미분류"), ("Pre-A 단계 스타트업", "중소·스타트업"),
    ("보험회사 IT 자회사", "금융"), (None, "미분류"),
])
def test_company_type(co, want):
    assert c.company_type(co, None)[0] == want


def test_program_wins():
    assert c.company_type("SSAFY", "SSAFY") == ("교육과정", None)


def test_anonymous():
    assert c.is_anonymous("C사") and c.is_anonymous("SQLD") and c.is_anonymous("최종 합격한 회사")
    assert not c.is_anonymous("무신사") and not c.is_anonymous("기업은행")


def test_origin_only_for_career():
    assert c.origin({"level": "신입", "path": [{"step": "SI 회사"}]}) is None
    r = {"level": "경력", "transition": "SI→서비스", "path": [{"step": "x"}]}
    assert c.origin(r) == "SI·SM"
    assert c.origin({"kind": "이직", "path": [{"step": "시리즈 C 스타트업 재직"}, {"step": "카카오뱅크"}]}) == "스타트업"
    assert c.origin({"kind": "이직", "path": []}) == "확인되지 않음"


def test_destination_falls_back_to_single_pass():
    r = {"company": None, "_others": [{"company": "A", "result": "불합격"}, {"company": "OP.GG", "result": "합격"}]}
    assert c.destination(r) == ("OP.GG", "other_companies")
    r["_others"].append({"company": "B", "result": "합격"})
    assert c.destination(r) == (None, None)             # 붙은 곳이 둘이면 어디로 갔는지 모른다
