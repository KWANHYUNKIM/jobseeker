"""국내 채용 보드·공공(site=boards)과 국내 포털(kr_portals) — 네트워크 없이 파서·판정만 본다."""
from __future__ import annotations

from datetime import date

from crawlers import crawl_boards as cb
from crawlers import kr_portals as kp
from pipeline import close_check as cc

INCRUIT_ROW = """
<ul class="c_row"  jobno="2609180002019">
 <li class="c_col">
  <div class="cell_first"><div class="cl_top"><a href="x" class="cpname" target="_blank">씨제이 푸드빌 (주)</a></div>
   <div class="cl_btm"><span class="sm-txt-icon icon">1000대</span></div></div>
  <div class="cell_mid">
   <div class="cl_top"><a target="_blank" href="https://job.incruit.com/jobdb_info/jobpost.asp?job=2609180002019">[CJ푸드빌] Back-end 개발자</a></div>
   <div class="cl_md"><span>서울 중구</span> <span>경력 4년↑</span> <span>대졸↑</span></div>
   <div class="cl_btm "><span>웹개발,</span> <span>서버·백엔드</span></div>
  </div>
  <div class="cell_last"><div class="cl_btm"><span>~10.11 (일)</span></div></div>
 </li>
</ul>
"""

ALIO_ROW = """
<tr>
  <td style="x"><label><input type="checkbox" class="ckbox idxs" name="idxs" value="305584" /></label></td>
  <td>47</td>
  <td class="left"><a href="/recruitview.do?idx=305584" target="_blank"/>동북아역사재단 직원(행정직(일반,전산)) 공개채용</a></td>
  <td>동북아역사재단</td>
  <td>  서울 </td>
  <td>  무기계약직 </td>
  <td>2026.10.01</td>
  <td>26.10.15</br><span class="orange">D-13</span></td>
  <td><span class="orange"> 진행중</span></td>
</tr>
"""


def test_incruit_row():
    [r] = cb._incruit_rows(INCRUIT_ROW)
    assert r["jobno"] == "2609180002019" and r["company"] == "씨제이 푸드빌 (주)"
    assert r["title"] == "[CJ푸드빌] Back-end 개발자"
    assert r["info"][:2] == ["서울 중구", "경력 4년↑"] and "서버·백엔드" in r["cats"]
    assert r["due"].startswith("~10.11")


def test_alio_row():
    [r] = cb._alio_rows(ALIO_ROW)
    assert r["idx"] == "305584" and r["org"] == "동북아역사재단"
    assert r["due"] == "26.10.15" and "진행중" in r["state"]
    assert cb._mmdd(r["due"]) == "~ 10/15"
    assert cb._ALIO_IT.search(r["title"])  # 전산직은 공용 개발 필터가 모른다


def test_mmdd_and_always_open():
    assert kp._mmdd("2026-10-13T23:59:00") == "~ 10/13"
    assert kp._mmdd("20261031") == "~ 10/31"
    assert kp._mmdd("2999-12-31 23:59:59") == "상시채용"
    assert kp._mmdd(None) == ""


def test_non_dev_korean_titles():
    assert kp._dev("디지털 채널 Back-end 개발자", "백엔드개발")
    assert not kp._dev("뚜레쥬르 제품개발 R&D(빵류) 경력채용", "메뉴개발")
    assert not kp._dev("부동산 개발 신입", "부동산/사업개발")


def test_portal_close_uses_list_membership():
    cache = {"toss:group": {"111", "222"}}
    today = date(2026, 10, 1)
    assert cc.check_board({"pid": "toss:group:111"}, today, cache).status == "active"
    assert cc.check_board({"pid": "toss:group:999"}, today, cache).status == "closed"
    assert cc.check_board({"pid": "toss:group:111"}, today, {"toss:group": None}).status == "unknown"


def test_board_verdicts():
    t = date(2026, 10, 1)
    assert cc.verdict_rallit({"data": {"status": {"code": "HIRING"}, "endedAt": "9999-12-31"}}, t).status == "active"
    assert cc.verdict_rallit({"data": {"status": {"code": "CLOSED", "name": "모집 마감"}}}, t).status == "closed"
    assert cc.verdict_rallit({"data": {"status": {"code": "HIRING"}, "endedAt": "2026-09-20"}}, t).status == "closed"
    v = cc.verdict_alio("<th>채용기간</th><td>26.09.01 ~ 26.09.15</td>", t)
    assert v.status == "closed" and v.deadline == "2026-09-15" and v.posted == "2026-09-01"
    assert cc.verdict_alio("<th>채용기간</th><td>26.10.01 ~ 26.10.15</td>", t).status == "active"
    assert cc.verdict_jsonld_only('"validThrough": "2026-10-07T23:59:59+09:00"', t).status == "active"
    assert cc.verdict_jsonld_only("<html></html>", t).status == "unknown"


def test_korean_only_it_titles():
    assert kp._dev_kr("본사 IT 생산/품질 담당 경력 인재 채용")
    assert kp._dev_kr("본사 영업데이터 자동화 개발 담당 경력 인재 채용")
    assert kp._dev_kr("지주부문 Chief Cloud Architect 채용")
    assert not kp._dev_kr("IT B2B 마케팅(계약직)")
    assert not kp._dev_kr("시공현장 안전관리자 채용(대전/인천)")


def test_greeting_skips_robots_blocked_host(monkeypatch):
    import pytest
    monkeypatch.setitem(kp._robots_cache, "kurly.career.greetinghr.com", False)
    with pytest.raises(RuntimeError):
        kp.from_greeting("kurly", "")


def test_kofia():
    t = date(2026, 10, 1)
    assert not cb._KOFIA_IT.search("[교보AIM자산운용] 투자운용팀 채용")
    assert cb._KOFIA_IT.search("[하나증권] AI전략실 경력직")
    assert cc.verdict_kofia("<td>접수기간</td><td>20260921~20261005</td>", t).status == "active"
    assert cc.verdict_kofia("<td>접수기간</td><td>~</td>", t).status == "unknown"


def test_gamejob_and_gojobs_verdicts():
    t = date(2026, 10, 1)
    assert cc.verdict_gamejob("<p>이 공고는 마감되었습니다.</p>", t).status == "closed"
    assert cc.verdict_gamejob("<a href='/Recruit/GI_Read/View'>채용</a> 채용시 마감", t).status == "active"
    html = "<th>등록일</th><td>2026-09-30</td><th>접수마감일</th><td>2026-10-13</td>"
    v = cc.verdict_gojobs(html, t)
    assert v.status == "active" and v.deadline == "2026-10-13" and v.posted == "2026-09-30"
    assert cc.verdict_gojobs(html, date(2026, 10, 20)).status == "closed"


def test_gojobs_title_filter():
    assert cb._GOJOBS_IT.search("외교부 일반직공무원(전산7급) 전입희망자 모집")
    assert cb._GOJOBS_NON_IT.search("개인정보보호위원회 전문임기제 다급(디자이너) 경력채용")
    assert cb._GOJOBS_NOTICE.search("출입국관리직 경채 서류전형 합격 공고")


def test_rare_it_sources_filters():
    # 지금은 IT 공고가 드문 곳 — 나오면 받고, 평소 공고는 거른다.
    assert kp._NH_IT.search("데이터사업부 전문계약직 채용 공고")
    assert not kp._NH_IT.search("NH농협은행 군산시청(출) 사무지원직 직원 채용공고")
    assert kp._dev_kr("안전보건 시스템 개발 및 DATA 관리 담당자")
    assert not kp._dev_kr("e편한세상 내포 에듀플라츠 현장 채용 공고(인부)")
    assert kp._flatten([{"모집분야": [{"IT": [{"채용전형": ["신입"]}]}]}]) == ["모집분야: IT: 채용전형: 신입"]


def test_gamejob_image_body_goes_through_ocr(monkeypatch):
    """게임잡 그림 공고 — 글은 자리표시 '-' 뿐이라 버리고, 그림을 OCR 해 본문을 채운다."""
    pages = {
        "GI_Read_Comt_Ifrm": r'<body><img src="https://file.gamejob.co.kr/net/Help/NoticeImg/View?FN=\Tong_1_.png"'
                             ' width="100%"></body>',
        "GI_Read_GI_Comment_Ifrm": "<body class='giworkTable'>\n  -\n</body>",
    }
    monkeypatch.setattr(cb, "http_get", lambda url, referer=None: next(
        v for k, v in pages.items() if f"/{k}?" in url).encode())
    seen = {}

    def fake_ocr(urls, referer=None):
        seen["urls"], seen["referer"] = urls, referer
        return "[주요업무]\n- 게임 서버 개발\n[자격요건]\n- C++ 3년 이상"

    monkeypatch.setattr(cb, "OCR_AVAILABLE", True)
    monkeypatch.setattr(cb, "ocr_images", fake_ocr)
    full, parts = cb._gamejob_detail("286066")
    assert parts == {}
    assert "C++ 3년 이상" in full and "[이미지 OCR]" in full
    assert seen["urls"] == [r"https://file.gamejob.co.kr/net/Help/NoticeImg/View?FN=\Tong_1_.png"]
    assert seen["referer"].endswith("GI_No=286066")
    # refetch_bodies 는 우리 pid 를 그대로 넘긴다
    _, text = cb.gamejob_fetch_jd("gamejob:dev:286066")
    assert text == ""


def test_gamejob_text_body_skips_ocr(monkeypatch):
    monkeypatch.setattr(cb, "http_get", lambda url, referer=None: (
        "<body>담당업무<br>- 언리얼 클라이언트 개발<br>- 전투 시스템 구현 및 최적화, 툴 개발과 유지보수</body>"
        if "Comt_Ifrm" in url else "<body>자격요건<br>- C++ 능숙</body>").encode())
    monkeypatch.setattr(cb, "OCR_AVAILABLE", True)
    monkeypatch.setattr(cb, "ocr_images", lambda *a, **k: (_ for _ in ()).throw(AssertionError("OCR 불필요")))
    full, parts = cb._gamejob_detail("1")
    assert set(parts) == {"주요업무", "자격요건"} and "C++ 능숙" in full


def test_gamejob_image_with_apply_links_still_ocr(monkeypatch):
    """GI_No=286190 꼴 — 그림 위에 '바로 지원하기' 링크 몇 줄이 글로 붙어 있어도 본문은 그림이다.
    링크가 '주요업무' 칸을 차지하지 않고 칸은 OCR 글로 나뉜다."""
    links = ("● [[AD-Tech] 백엔드 개발자(4~7년)] 바로 지원하기↓ ↓ ↓ ↓<br>"
             "https://supercent.career.greetinghr.com/ko/o/213168<br>"
             "● 다른 포지션 더 보기↓ ↓ ↓ ↓<br>https://supercent.career.greetinghr.com/position")
    monkeypatch.setattr(cb, "http_get", lambda url, referer=None: (
        f'<body><img src="https://file.gamejob.co.kr/x.jpg" alt="배너 이미지">{links}</body>'
        if "Comt_Ifrm" in url else "<body>-</body>").encode())
    monkeypatch.setattr(cb, "OCR_AVAILABLE", True)
    monkeypatch.setattr(cb, "ocr_images", lambda urls, referer=None: "담당업무\n- 광고 서버 개발\n자격요건\n- Go 4년")
    full, parts = cb._gamejob_detail("286190")
    assert parts == {}
    assert "광고 서버 개발" in full and "greetinghr" in full


def test_ocr_tiles_cut_tall_image_on_blank_rows():
    pytest = __import__("pytest")
    Image = pytest.importorskip("PIL.Image")
    from PIL import ImageDraw

    from crawlers import jobs_common as jc
    w, h = 900, 10000
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    for y in range(40, h - 40, 60):                 # 글줄 높이 30, 사이 여백 30
        d.rectangle((50, y, w - 50, y + 30), fill="black")
    tiles = jc.ocr_tiles(img)
    assert len(tiles) >= 3 and sum(t.size[1] for t in tiles) == h
    y = 0
    for t in tiles[:-1]:
        y += t.size[1]
        assert (y - 40) % 60 >= 30 or y < 40, f"글줄 한가운데서 잘렸다: {y}"
    assert jc.ocr_tiles(Image.new("RGB", (900, 2000))) and len(jc.ocr_tiles(Image.new("RGB", (900, 2000)))) == 1
    wide = jc.ocr_tiles(Image.new("RGB", (4000, 3000)))
    assert wide[0].size[0] == jc.OCR_MAX_W
