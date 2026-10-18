"""메인 화면의 이름 규칙 — 업종 가르기·회사 표기 정리·같은 회사 판정(DB 없이 돈다)."""
from app.features.home.industry import classify
from app.features.home.service import company_key, display_name


def test_industry_order_finance_before_platform():
    # '카카오' 가 이름에 있어도 은행·페이는 금융, 이름이 정확히 카카오면 플랫폼
    assert classify("카카오뱅크") == "금융"
    assert classify("카카오페이") == "금융"
    assert classify("카카오") == "IT·플랫폼"
    assert classify("당근마켓") == "IT·플랫폼"     # '마켓' 이 커머스로 끌고 가지 않게
    assert classify("무신사") == "유통·커머스"


def test_industry_common_suffixes():
    assert classify("NH투자증권") == "금융"
    assert classify("크래프톤 (Krafton)") == "게임"
    assert classify("DL이앤씨") == "건설·중공업"
    assert classify("") == "기타"


def test_display_name_strips_corp_marks():
    assert display_name("(주)카카오") == "카카오"
    assert display_name("주식회사스마일게이트") == "스마일게이트"
    assert display_name("쿠팡 (Coupang)") == "쿠팡 (Coupang)"   # 영문 병기는 남긴다
    assert display_name("R&amp;D랩") == "R&D랩"


def test_company_key_merges_spellings():
    assert company_key("(주)스마일게이트") == company_key("스마일게이트")
    assert company_key("쿠팡 (Coupang)") == company_key("쿠팡")
    assert company_key("토스") != company_key("토스뱅크")


def test_known_companies_beat_name_rules():
    # 이름에 업종이 안 드러나는 큰 회사는 직접 적은 표가 먼저다
    assert classify("비바리퍼블리카") == "금융"
    assert classify("Block (Square)") == "금융"
    assert classify("LG이노텍") == "반도체·전자"
    assert classify("네오플") == "게임"


def test_agencies_are_separated():
    assert classify("에이치알포유") == "채용대행·헤드헌팅"
    assert classify("원티드_일본 현지 채용") == "채용대행·헤드헌팅"


def test_same_entity_aliases_merge_but_affiliates_do_not():
    assert company_key("당근마켓") == company_key("당근 (Daangn)")
    assert company_key("NHN Cloud") == company_key("엔에이치엔클라우드")
    assert company_key("씨제이올리브영(CJ올리브영)") == company_key("CJ올리브영")
    assert company_key("토스") != company_key("토스뱅크")       # 계열사는 법인이 달라 나눈다


def test_search_firms_are_agencies_but_research_is_not():
    assert classify("라인서치") == "채용대행·헤드헌팅"      # '라인' 으로 대기업 명단에 걸리던 헤드헌팅
    assert classify("유니코써치") == "채용대행·헤드헌팅"
    assert classify("리서치앤리서치") != "채용대행·헤드헌팅"


def test_safe_logo_only_allows_known_https_hosts():
    from app.features.home.service import safe_logo
    assert safe_logo("https://board.catch.co.kr/Upload/Job/Company/CI/1.jpg")
    assert safe_logo("https://cdn.jumpit.co.kr/images/a.png")
    assert safe_logo("http://board.catch.co.kr/x.jpg") is None
    assert safe_logo("javascript:alert(1)") is None
    assert safe_logo("https://board.catch.co.kr.evil.example/x.png") is None
    assert safe_logo("https://user@board.catch.co.kr/x.png") is None
    assert safe_logo("https://imgorg.catch.co.kr/job/site/tmp02.gif") is None   # 캐치 기본 그림
