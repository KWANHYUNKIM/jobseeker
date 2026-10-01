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
