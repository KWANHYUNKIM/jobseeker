"""회사 사실 → 화면 모양 (DB 없이 build 만)."""
from datetime import date, datetime, timezone

from app.features.company_facts import service

ROW = {
    "company_key": "와탭랩스", "name": "와탭랩스", "employees": 92, "industry": "IT", "founded": 2015,
    "address": "서울특별시 서초구 서초대로77길 17, 13층", "address_source": "wanted", "benefit_tags": ["자기계발지원"],
    "wanted_url": "https://www.wanted.co.kr/company/1", "wanted_avg_pay": 5932, "wanted_pay_updated": date(2026, 10, 12),
    "nps_members": 95, "nps_annual_est": 6307, "nps_month": "2026-10", "nps_biz6": "123456", "nps_address": None,
    "updated_at": datetime(2026, 11, 26, tzinfo=timezone.utc),
}
SAL = [{"job_key": "wanted-1", "title": "백엔드", "url": "https://x", "pay_min": 7000, "pay_max": None, "kind": "이상",
        "career": "3~10년", "quote": "처우는 7,000만원 이상", "seen_on": date(2026, 11, 1)}]


def test_posting_salary_leads_and_sources_number_in_order():
    d = service.build(ROW, SAL)
    rows = d["pay"]["rows"]
    assert rows[0]["label"] == "공고 연봉 · 3~10년" and rows[0]["value"] == "7,000만원 이상"
    assert [r["label"] for r in rows[1:]] == ["직원 평균 연봉", "국민연금 기준 추정"]
    assert [s["n"] for s in d["sources"]] == [1, 2, 3]
    assert "[3]" in rows[0]["note"] and "[1]" in rows[1]["note"] and "[2]" in rows[2]["note"]
    assert d["location"]["map_url"].endswith("17")   # 층·호는 지도 검색에서 뺀다


def test_average_only_without_postings():
    d = service.build({**ROW, "wanted_url": None, "wanted_avg_pay": None, "benefit_tags": []}, [])
    assert d["pay"]["summary"].startswith("직원 평균은 **약 6,307만원**")
    assert d["benefits"] is None


def test_co_norm_matches_validate():
    assert service.co_norm("(주) 데이터 쿡") == "데이터쿡"
