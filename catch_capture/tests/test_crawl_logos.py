"""회사 로고 수집기의 네트워크 없는 부분 — 허용 호스트·이름 맞추기·뷰어 정규화."""
from crawlers import crawl_logos as cl


def test_safe_only_allows_known_https_hosts():
    assert cl._safe("https://clogo.saramin.co.kr/company/logo/202411/25/a_logo.png")
    assert cl._safe("https://cdn.rallit.com/image/2026-11-05/x.png")
    assert cl._safe("http://clogo.saramin.co.kr/a.png") is None        # http
    assert cl._safe("https://evil.example.com/a.png") is None          # 모르는 호스트
    assert cl._safe("https://pds.saramin.co.kr/a.png") is None         # 공고 페이지 쪽 서버는 안 쓴다


def test_saramin_search_hit_and_og_image():
    page = ('<a href="/zf_user/company-info/view?csn=QjAvWTRj" title="(주)제이오텍" target="_blank" '
            'class="company_popup">(주)제이오텍</a>')
    assert cl._SARAMIN_HIT.findall(page) == [("QjAvWTRj", "(주)제이오텍")]
    meta = '<meta property="og:image" content="https://clogo.saramin.co.kr/company/logo/202411/25/s_logo.png">'
    assert cl._OG_IMAGE.search(meta).group(1).endswith("s_logo.png")
    # 사람인 기본 공유 그림은 로고가 아니다
    assert cl._OG_IMAGE.search('<meta property="og:image" content="https://www.saraminimage.co.kr/m/x.png">') is None


def test_viewer_norm_matches_companymark_rules():
    assert cl._viewer_norm("㈜와탭랩스") == "와탭랩스"
    assert cl._viewer_norm("인프랩 (인프런)") == "인프랩"
    assert cl._viewer_norm("주식회사 사각") == "사각"
    assert cl._viewer_norm("Kim & Chang (김앤장 법률사무소)") == "Kim&Chang"
