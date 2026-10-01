"""SK Careers(그룹 통합 채용) — 네트워크 없이 파서·개발직 판정·마감 판정만 본다."""
from __future__ import annotations

from datetime import date

from crawlers import crawl_ats as ats
from pipeline import close_check as cc

DETAIL = """
<div class="detail-content-wrapper">
  <div class="detail-content-item">
    <h2 class="detail-content-title">About the job</h2>
    <div class="detail-content-box"><ul><li>&#48177;&#50644;&#46300; API 개발</li></ul></div>
  </div>
  <div class="detail-content-item">
    <h2 class="detail-content-title">Who We&#39;re Looking For</h2>
    <div class="detail-content-box"><p>Java 3년 이상</p></div>
  </div>
  <div class="detail-content-item">
    <h2 class="detail-content-title">Preferred Qualifications</h2>
    <div class="detail-content-box"><p>Kubernetes 운영 경험</p></div>
  </div>
</div>
<div class="floating-box">지원 기간</div>
"""


def test_detail_sections(monkeypatch):
    monkeypatch.setattr(ats, "http_get", lambda url, timeout=30: DETAIL.encode())
    full, structured = ats._sk_detail("R1")
    assert structured == {"주요업무": "백엔드 API 개발", "자격요건": "Java 3년 이상",
                          "우대사항": "Kubernetes 운영 경험"}
    assert "[About the job]" in full and "지원 기간" not in full


def test_dev_by_role_not_title():
    # 제목의 'Talent' 가 영어 비개발어로 걸려도 SK 직무 분류가 개발이면 개발직이다.
    assert ats._sk_is_dev("Junior Talent 채용(AT/DT)", "Tech R&D/Data Science,Backend 개발")
    assert ats._sk_is_dev("시스템 (서버) 전문가 영입", "Infra/Cloud/Infra")
    assert not ats._sk_is_dev("사업개발 담당자", "사업개발/사업개발")
    assert not ats._sk_is_dev("DC 운용 전기 전문가", "Infra/Infra 운용/관리/최적화")


def test_list_mapping(monkeypatch):
    monkeypatch.setattr(ats, "_post_form_json", lambda url, form: {"success": True, "list": [{
        "noticeID": "R262088", "title": "AT/DT", "jobRole": "Tech R&D/AI/DT",
        "corpName": "SK브로드밴드", "workingArea": "서울", "recruitType": "신입",
        "end": "2026년 10월 13일(화)"}]})
    [c] = ats._from_skcareers("sk", "SK")
    assert c["company"] == "SK브로드밴드" and c["dev"] and c["deadline"] == "~ 10/13"
    assert c["url"].endswith("/Recruit/Detail/R262088")


def test_close_check_uses_board_list():
    cache = {"skcareers": {"R1": "2026-10-13", "R2": None}}
    today = date(2026, 10, 1)
    assert cc.check_board({"pid": "skcareers:sk:R1"}, today, cache).status == "active"
    assert cc.check_board({"pid": "skcareers:sk:R2"}, today, cache).status == "active"
    assert cc.check_board({"pid": "skcareers:sk:R9"}, today, cache).status == "closed"
    assert cc.check_board({"pid": "skcareers:sk:R1"}, date(2026, 10, 20),
                          cache).status == "closed"
    # 목록을 못 받았으면 닫지 않는다
    assert cc.check_board({"pid": "skcareers:sk:R1"}, today,
                          {"skcareers": None}).status == "unknown"
