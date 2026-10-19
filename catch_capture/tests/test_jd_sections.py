"""공고 본문 → 주요업무·자격요건·우대사항 나누기(crawlers/jobs_common.split_jd_sections).

머리말을 말로 쓰는 공고("이런 업무를 해요", "You will:")가 통째로 비던 것을 고친 규칙을 지킨다.
"""
from crawlers.crawl_jobkorea import _element_inner
from crawlers.jobs_common import extract_img_urls, is_image_only, split_jd_sections


def _split(text):
    p = split_jd_sections(text)
    return {k: p[k] for k in ("main_tasks", "qualifications", "preferences") if p[k]}


def test_conversational_korean_headers_toss_style():
    t = "# 합류하면 함께할 업무예요\n- 결제 서버 개발\n# 이런 분과 함께하고 싶어요\n- 백엔드 3년\n" \
        "# 이런 경험이 있다면 더 좋아요\n- Kafka 운영\n# 토스로의 합류 여정\n- 서류 > 면접"
    p = _split(t)
    assert p["main_tasks"] == "- 결제 서버 개발"
    assert p["qualifications"] == "- 백엔드 3년"
    assert p["preferences"] == "- Kafka 운영"          # 합류 여정에서 끊긴다


def test_english_headers_greenhouse_style():
    t = "About Acme\nWe build things.\nYou will:\nShip features\nYou have:\n5+ years of Go\n" \
        "Bonus Points\nKubernetes\nSalary Range\n$100—$200"
    p = _split(t)
    assert p == {"main_tasks": "Ship features", "qualifications": "5+ years of Go", "preferences": "Kubernetes"}


def test_bracket_headers_nhn_style():
    t = "[이런 업무를 해요 (주요 업무)]\n클라우드 개발\n[이런 분들을 찾고 있어요 (자격 요건)]\nJava\n" \
        "[이런 분이면 더 좋아요 (우대 사항)]\nK8s\n[꼭 확인해주세요]\n유의"
    assert _split(t) == {"main_tasks": "클라우드 개발", "qualifications": "Java", "preferences": "K8s"}


def test_body_lines_are_not_headers():
    # 글머리표·'항목 : 값' 줄은 '자격'·'우대' 낱말이 있어도 본문이다
    t = "우대사항\nㆍ자격증 : 정보처리기사\n- 관련 자격 보유자 우대\n"
    assert _split(t) == {"preferences": "ㆍ자격증 : 정보처리기사\n- 관련 자격 보유자 우대"}


def test_about_role_fills_main_tasks_only_when_missing():
    assert _split("About the Role\nLead the platform team\nRequirements\nGo")["main_tasks"] == "Lead the platform team"
    p = _split("About the Role\nIntro\nResponsibilities\nShip\nRequirements\nGo")
    assert p["main_tasks"] == "Ship"


def test_prose_jd_split_by_paragraph_lead():
    t = "(주)엔씨, 연구원 채용\n주요 업무는 3D 에셋 자동 생성 연구를 리딩하는 일이다.\n" \
        "자격 요건은 관련 석사 이상이다.\n강화학습 경험자를 우대한다."
    p = _split(t)
    assert p["main_tasks"].startswith("주요 업무는")
    assert p["qualifications"].startswith("자격 요건은")
    assert p["preferences"].startswith("강화학습")


def test_poster_with_short_boilerplate_needs_ocr():
    html = '<img src="https://pds.saramin.co.kr/a.jpg">'
    text = "🛎️ 유의사항\n• 입사지원 서류에 허위사실이 발견될 경우, 채용확정 이후라도 채용이 취소될 수 있습니다."
    assert is_image_only(html, text)
    assert not is_image_only("<p>본문</p>", text)


def test_element_inner_balances_nested_tags():
    raw = '<div id="detail-content"><table><tr><td><div>채용분야</div></td></tr></table>' \
          '<div>담당업무</div></td><div>자격요건</div></div><p>밖</p>'
    inner = _element_inner(raw, 'id="detail-content"')
    assert "자격요건" in inner and "밖" not in inner


def test_doubled_image_url_is_repaired():
    assert extract_img_urls('<img src="https://a.kr/https://a.kr/r/x.jpg">') == ["https://a.kr/r/x.jpg"]


def test_exclaimed_header_daangn_style():
    # 당근(잡코리아) — 우대 머리말이 느낌표로 끝난다. 문장 끝(!)으로 보고 버려서 우대사항이 자격요건에 붙었다(2026-10-19)
    t = "이런 일을 해요\nㆍAPI 설계\n이런 분과 함께하고 싶어요\nㆍ서버 5년\n이런 분이면 더 좋아요!\nㆍNode.js 경험"
    p = _split(t)
    assert p["qualifications"] == "ㆍ서버 5년"
    assert p["preferences"] == "ㆍNode.js 경험"


def test_long_exclaimed_sentence_is_still_body():
    t = "자격요건\n- 서버 3년\n이런 분과 함께라면 정말 즐겁게 오래오래 성장할 수 있을 거예요!\n- Kafka"
    p = _split(t)
    assert "Kafka" in p["qualifications"] and "preferences" not in p
