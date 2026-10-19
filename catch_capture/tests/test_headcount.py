"""공고 본문의 사원수 추출(core.classifier.extract_headcount) — 행사 인원을 사원수로 읽지 않는다."""
from core.classifier import extract_headcount


def test_company_headcount_is_read():
    assert extract_headcount("구성원 25명 규모의 팀입니다") == 25
    assert extract_headcount("사원수 54명") == 54
    assert extract_headcount("현재 120명 규모로 성장했습니다") == 120


def test_event_size_is_not_headcount():
    # 팬딩 공고에 실린 기사 발췌 — 행사 참가 인원이다(2026-10-20 대기업으로 잘못 분류됐다)
    assert extract_headcount("팬딩, 1500명 규모 재테크 축제 '빅머니 페스티벌' 개최") is None
    assert extract_headcount("300명 규모 해커톤을 열었다") is None
