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


def test_safe_logo_only_allows_our_own_files():
    from app.features.home.service import safe_logo
    assert safe_logo("/logos/c/30f5c8d6e7008a50.png") == "/logos/c/30f5c8d6e7008a50.png"
    assert safe_logo("https://board.catch.co.kr/Upload/Job/Company/CI/1.jpg") is None   # 바깥 주소는 이제 안 낸다
    assert safe_logo("javascript:alert(1)") is None
    assert safe_logo("/logos/c/../../etc/passwd") is None
    assert safe_logo("/logos/c/30f5c8d6e7008a50.svg") is None
    assert safe_logo("//evil.example/logos/c/30f5c8d6e7008a50.png") is None


def test_bc_card_rule_does_not_catch_mbc():
    assert classify("BC카드") == "금융"
    assert classify("엠비씨(MBC)아카데미 컴퓨터교육센터") != "금융"


def test_pipe_names_and_silicon2():
    assert display_name("Rebellions | 리벨리온") == "리벨리온"
    assert classify("실리콘투") == "유통·커머스"     # 화장품 유통사 — '실리콘' 으로 반도체에 잡혔다


def test_technologies_is_not_logistics():
    assert classify("뤼튼테크놀로지스") != "물류"
    assert classify("팔란티어테크놀로지스코리아") != "물류"
    assert classify("CJ대한통운") == "물류"
    assert classify("롯데글로벌로지스") == "물류"


def test_always_open_threshold():
    from app.features.home.service import is_always
    assert is_always(None)            # 마감일 없음
    assert is_always(355430)          # '채용시 마감'을 먼 날짜로 적은 것
    assert is_always(365)
    assert not is_always(3)
    assert not is_always(0)


def test_far_deadlines_count_as_always_open():
    from app.features.home.service import is_always
    assert is_always(346)             # 잡코리아 기본 게재 1년
    assert is_always(91)
    assert not is_always(90)
    assert not is_always(72)
