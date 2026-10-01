"""국내 채용 보드·공공기관 채용 → 표준 jobs.json 스키마로 누적 저장(site = "boards").

wanted·jumpit·jobkorea·saramin·catch 밖에 있던 곳들이다. 회사 자체 채용페이지(ats)와
같은 방식으로 돈다 — 출처마다 목록 파서 하나, 개발직만 상세를 받고, 수집 루프는
crawl_ats.crawl 을 그대로 쓴다(site·boards·parsers 만 바꾼다).

  rallit     랠릿 — 공개 JSON(/client/api/v1/position), jobGroup=DEVELOPER. robots 허용.
  superookie 슈퍼루키 — /jobs 페이지에 박힌 공개 토큰으로 검색 API. robots 전면 허용.
             본문이 대개 이미지라 텍스트는 짧다.
  incruit    인크루트 — job.incruit.com 목록 HTML(EUC-KR, occ1=150 IT) + 본문 iframe.
             robots 의 * 는 jobpostcontpartner 만 막는다. 앞 몇 쪽만 본다.
  alio       잡알리오(공공기관) — 목록 HTML, NCS 정보통신(R600020) 진행중. robots 없음.
  gojobs     나라일터 — 국가·지자체·공공기관 공무원 채용. '전산' 등 키워드 검색 목록 + 상세 요약
             (본문 전문은 hwp/pdf 첨부). robots 는 Googlebot 규칙만 있다.
  gamejob    게임잡 — 게임사 공고가 모인다(그라비티 등은 자기 사이트 대신 여기로 보낸다). 개발 직무
             코드로 서버가 거른 목록(POST _GI_Job_List) + 담당업무·자격조건 iframe. robots 는 /List_GG/ 만 막는다.
  kofia      금융투자협회 회원사 채용안내 — 증권·자산운용사 공고가 모인다(recruiter 호스트라
             못 받는 NH투자·키움·하나증권 공고도 여기 온다). 목록 HTML, 앞 몇 쪽만 본다.
             마감일(접수기간)은 상세에만 있다. robots 없음.

일부러 뺀 곳(2026-10 조사): 리멤버·로켓펀치(약관이 자동 수집 금지), 잡플래닛(잡코리아
미러), 나인하이어·flex(약관 금지), 마이다스 recruiter(robots 가 API 차단), 프로그래머스·
블라인드 하이어(서비스 종료). 그리팅은 회사마다 robots 가 달라 kr_portals 가 허용된 곳만 받는다.

사용법:
    python -m crawlers.crawl_boards 개발자 100
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import html as _html
import json
import re
import sys
import time

from crawlers import crawl_ats, kr_portals
from crawlers.jobs_common import html_to_text, http_get, is_developer_job, jitter

SITE = "boards"

BOARDS: list[dict] = [
    {"provider": "alio", "slug": "it", "company": "잡알리오(공공기관)", "region": "kr",
     "per_board": 30, "company_page": False, "label": "공공기관 채용정보"},
    {"provider": "rallit", "slug": "dev", "company": "랠릿", "region": "kr",
     "per_board": 40, "company_page": False, "label": "랠릿"},
    {"provider": "incruit", "slug": "it", "company": "인크루트", "region": "kr",
     "per_board": 30, "company_page": False, "label": "인크루트", "complete": False},
    {"provider": "kofia", "slug": "recruit", "company": "금융투자협회 채용안내", "region": "kr",
     "per_board": 20, "company_page": False, "label": "금융투자협회", "complete": False},
    {"provider": "gojobs", "slug": "gov", "company": "나라일터", "region": "kr",
     "per_board": 20, "company_page": False, "label": "나라일터(공무원·공공)", "complete": False},
    {"provider": "gamejob", "slug": "dev", "company": "게임잡", "region": "kr",
     "per_board": 30, "company_page": False, "label": "게임잡", "complete": False},
    {"provider": "superookie", "slug": "it", "company": "슈퍼루키", "region": "kr",
     "per_board": 20, "company_page": False, "label": "슈퍼루키"},
]


def _text(fragment: str) -> str:
    return re.sub(r"\s*\n\s*", "\n", html_to_text(_html.unescape(fragment or ""))).strip()


def _mmdd(y_m_d: str) -> str:
    """'2026-10-13…' / '26.10.15' → job_status 가 읽는 '~ MM/DD'. 못 읽으면 빈칸."""
    m = re.search(r"(\d{2,4})[-./](\d{1,2})[-./](\d{1,2})", y_m_d or "")
    return f"~ {int(m.group(2)):02d}/{int(m.group(3)):02d}" if m else ""


def _sleep() -> None:
    time.sleep(jitter(700) / 1000)


# ── 랠릿 ────────────────────────────────────────────────────────────────
RALLIT_LIST = ("https://www.rallit.com/client/api/v1/position"
               "?pageNumber={page}&pageSize=50&jobGroup=DEVELOPER")
RALLIT_DETAIL = "https://www.rallit.com/client/api/v1/position/{id}"
_RALLIT_LEVEL = {"INTERN": "인턴", "JUNIOR": "신입", "MIDDLE": "경력", "SENIOR": "경력",
                 "LEAD": "경력", "IRRELEVANT": "경력무관"}


def _rallit_detail(pid: int) -> tuple[str, dict[str, str]]:
    d = json.loads(http_get(RALLIT_DETAIL.format(id=pid)).decode("utf-8", "ignore"))["data"]
    structured = {"주요업무": _text(d.get("responsibilities")),
                  "자격요건": _text(d.get("basicQualifications")),
                  "우대사항": _text(d.get("preferredQualifications")),
                  "복지": _text(d.get("benefits"))}
    parts = [_text(d.get("description"))] + [f"[{k}]\n{v}" for k, v in structured.items() if v]
    if d.get("addressMain"):
        parts.append(f"[근무지]\n{d['addressMain']}")
    return crawl_ats._clean("\n\n".join(p for p in parts if p)), structured


def _from_rallit(slug: str, company: str) -> list[dict]:
    out, page, total_pages = [], 1, 1
    while page <= total_pages:
        data = json.loads(http_get(RALLIT_LIST.format(page=page)).decode("utf-8", "ignore"))["data"]
        total_pages = min(int(data.get("totalPage") or 1), 20)
        for j in data.get("items") or []:
            if (j.get("status") or {}).get("code") != "HIRING":
                continue
            ended = j.get("endedAt") or ""
            levels = sorted({_RALLIT_LEVEL.get(x, "") for x in j.get("jobLevels") or []} - {""})
            out.append({
                "ext_id": str(j["id"]),
                "title": (j.get("title") or "").strip(),
                "company": (j.get("companyName") or "").strip(),
                "url": j.get("url") or f"https://www.rallit.com/positions/{j['id']}",
                "location": j.get("addressRegion") or "—",
                "category": ", ".join(j.get("jobSkillKeywords") or []),
                "full_jd": "",
                "dev": True,  # jobGroup=DEVELOPER 로 서버가 이미 걸렀다
                "detail": (lambda i=j["id"]: _rallit_detail(i)),
                "deadline": "상시채용" if ended.startswith("9999") else _mmdd(ended),
                "career": "·".join(levels),
            })
        page += 1
        if page <= total_pages:
            _sleep()
    return out


# ── 슈퍼루키 ─────────────────────────────────────────────────────────────
SUPEROOKIE_PAGE = "https://www.superookie.com/jobs"
SUPEROOKIE_API = ("https://www.superookie.com/api/jobs/search?access_token={token}&job_type=job"
                  "&page={page}&page_length=48&short=1&duty_group%5B%5D=661de91a8b129f42ef6c2564")
_SUPEROOKIE_TOKEN = re.compile(r"access_token'\]\s*=\s*'([A-Za-z0-9]+)'")


def _from_superookie(slug: str, company: str) -> list[dict]:
    # 토큰은 페이지에 공개로 박혀 있고 바뀔 수 있어 매번 페이지에서 읽는다.
    m = _SUPEROOKIE_TOKEN.search(http_get(SUPEROOKIE_PAGE).decode("utf-8", "ignore"))
    if not m:
        raise RuntimeError("superookie 토큰을 못 찾음")
    out, page, last = [], 1, 1
    while page <= last:
        data = json.loads(http_get(SUPEROOKIE_API.format(token=m.group(1), page=page))
                          .decode("utf-8", "ignore"))
        last = min(int(data.get("last_page") or 1), 10)
        for j in data.get("data") or []:
            title = (j.get("job_title_decoded") or j.get("job_title") or "").strip()
            team = j.get("team_decoded") or ""
            body = _text(j.get("custom_field"))
            out.append({
                "ext_id": str(j.get("_id")),
                "title": title,
                "company": (j.get("company_name_decoded") or j.get("company_name") or "").strip(),
                "url": f"https://www.superookie.com/jobs/{j.get('_id')}",
                "location": ((j.get("company") or {}).get("address1") or "—")
                            if isinstance(j.get("company"), dict) else "—",
                "category": team,
                "full_jd": crawl_ats._clean(body),
                "dev": is_developer_job(title, team),
                "deadline": _mmdd(j.get("end_at") or ""),
                "career": j.get("job_level") or "",
            })
        page += 1
        if page <= last:
            _sleep()
    return out


# ── 인크루트 ─────────────────────────────────────────────────────────────
INCRUIT_LIST = "https://job.incruit.com/jobdb_list/searchjob.asp?occ1=150&page={page}"
INCRUIT_POST = "https://job.incruit.com/jobdb_info/jobpost.asp?job={id}"
INCRUIT_BODY = "https://job.incruit.com/s_common/jobpost/jobpostcont.asp?job={id}"
INCRUIT_PAGES = 5   # 쪽당 60건. 최신순 앞쪽만 본다(complete: false).
_INCRUIT_ROW = re.compile(r'<ul class="c_row"\s+jobno="(\d+)"(.*?)</ul>', re.S)


def _spans(block: str) -> list[str]:
    return [s for s in (_text(x).strip(" ,") for x in re.findall(r"<span[^>]*>(.*?)</span>", block, re.S)) if s]


def _incruit_rows(html: str) -> list[dict]:
    out = []
    for jobno, row in _INCRUIT_ROW.findall(html):
        cp = re.search(r'class="cpname"[^>]*>(.*?)</a>', row, re.S)
        tt = re.search(r'jobpost\.asp\?job=\d+"[^>]*>(.*?)</a>', row, re.S)
        md = re.search(r'<div class="cl_md">(.*?)</div>', row, re.S)
        # 직무 칸(cl_btm)은 셋째 칸(cell_last)에도 같은 이름으로 있다 — 가운데 칸 안에서만 찾는다.
        mid = row[row.find('class="cell_mid"'):row.find('class="cell_last"')]
        mids = re.findall(r'<div class="cl_btm ?">(.*?)</div>', mid, re.S)
        last = re.search(r'<div class="cell_last">(.*?)</div>', row, re.S)
        info = _spans(md.group(1)) if md else []
        cats = _spans(mids[-1]) if mids else []
        due = _spans(last.group(1)) if last else []
        out.append({"jobno": jobno, "company": _text(cp.group(1)) if cp else "",
                    "title": _text(tt.group(1)) if tt else "", "info": info, "cats": cats,
                    "due": due[0] if due else ""})
    return out


def _incruit_detail(jobno: str) -> tuple[str, dict[str, str]]:
    raw = http_get(INCRUIT_BODY.format(id=jobno), referer=INCRUIT_POST.format(id=jobno))
    body = raw.decode("euc-kr", "ignore")
    body = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", body, flags=re.S | re.I)
    return crawl_ats._clean(_text(body)), {}


def _from_incruit(slug: str, company: str) -> list[dict]:
    out = []
    for page in range(1, INCRUIT_PAGES + 1):
        html = http_get(INCRUIT_LIST.format(page=page)).decode("euc-kr", "ignore")
        rows = _incruit_rows(html)
        if not rows:
            break
        for r in rows:
            out.append({
                "ext_id": r["jobno"],
                "title": r["title"],
                "company": r["company"],
                "url": INCRUIT_POST.format(id=r["jobno"]),
                "location": r["info"][0] if r["info"] else "—",
                "category": ", ".join(r["cats"]),
                "full_jd": "",
                # 공채는 직무를 열몇 개씩 달고 그중 하나가 IT 다 — 직무가 몇 개 안 될 때만 직무로 본다.
                "dev": kr_portals._dev(r["title"])
                       or (len(r["cats"]) <= 3 and kr_portals._dev("", r["cats"])),
                "detail": (lambda n=r["jobno"]: _incruit_detail(n)),
                "deadline": r["due"],
                "career": r["info"][1] if len(r["info"]) > 1 else "",
            })
        _sleep()
    return out


# ── 잡알리오(공공기관) ─────────────────────────────────────────────────────
ALIO_LIST = "https://job.alio.go.kr/recruit.do?pageNo={page}&detail_code=R600020&ing=2"
ALIO_VIEW = "https://job.alio.go.kr/recruitview.do?idx={idx}"
_ALIO_ROW = re.compile(r'<tr>\s*<td[^>]*>\s*<label><input[^>]*name="idxs" value="(\d+)"(.*?)</tr>', re.S)
# 정보통신 분류에도 업무보조원·시설 같은 비개발 공고가 섞인다. 전산직 이름은 개발 필터가 모른다.
_ALIO_IT = re.compile(r"전산|정보(보안|화|통신|시스템|기술)|ICT|\bIT\b|SW|소프트웨어|데이터|개발|보안|네트워크")
# 상세의 머리말 → build_jd_sections 가 아는 이름
_ALIO_SECTIONS = {"응시자격": "자격요건", "우대내용": "우대사항", "근무분야": "주요업무"}


def _alio_rows(html: str) -> list[dict]:
    out = []
    for idx, row in _ALIO_ROW.findall(html):
        tds = [_text(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        tt = re.search(r'recruitview\.do\?idx=\d+"[^>]*>(.*?)</a>', row, re.S)
        # tds: 번호, 제목, 기관명, 근무지, 고용형태, 등록일, 마감일(+D-n), 상태
        if len(tds) < 7:
            continue
        out.append({"idx": idx, "title": _text(tt.group(1)) if tt else tds[1],
                    "org": tds[2], "location": tds[3], "type": tds[4], "posted": tds[5],
                    "due": tds[6].split("\n")[0], "state": tds[7] if len(tds) > 7 else ""})
    return out


def _alio_detail(idx: str) -> tuple[str, dict[str, str]]:
    raw = http_get(ALIO_VIEW.format(idx=idx)).decode("utf-8", "ignore")
    i = raw.find(">", raw.find('id="contentRV"')) + 1
    body = re.sub(r"<script.*?</script>", "", raw[i:], flags=re.S)
    text = _text(body)
    structured: dict[str, str] = {}
    lines = text.split("\n")
    for head, key in _ALIO_SECTIONS.items():
        if head in lines:
            k = lines.index(head)
            nxt = next((n for n in range(k + 1, len(lines)) if lines[n] in _ALIO_SECTIONS
                        or lines[n] in ("결격사유", "전형절차/방법", "채용구분", "고용형태")), len(lines))
            structured[key] = "\n".join(lines[k + 1:nxt]).strip()
    return crawl_ats._clean(text), structured


def _from_alio(slug: str, company: str) -> list[dict]:
    out = []
    for page in range(1, 21):
        rows = _alio_rows(http_get(ALIO_LIST.format(page=page)).decode("utf-8", "ignore"))
        if not rows:
            break
        for r in rows:
            if "마감" in r["state"]:
                continue
            out.append({
                "ext_id": r["idx"],
                "title": r["title"],
                "company": r["org"],
                "url": ALIO_VIEW.format(idx=r["idx"]),
                "location": re.sub(r"\s+", " ", r["location"]) or "—",
                "category": f"공공기관 · {r['type']}".strip(" ·"),
                "full_jd": "",
                "dev": bool(_ALIO_IT.search(r["title"])) or is_developer_job(r["title"]),
                "detail": (lambda i=r["idx"]: _alio_detail(i)),
                "deadline": _mmdd(r["due"]),
                "career": "",
            })
        if len(rows) < 10:
            break
        _sleep()
    return out


# ── 금융투자협회 회원사 채용안내 ──────────────────────────────────────────────
KOFIA_LIST = "https://www.kofia.or.kr/brd/m_96/list.do?page={page}"
KOFIA_VIEW = "https://www.kofia.or.kr/brd/m_96/view.do?seq={seq}"
KOFIA_PAGES = 8   # 쪽당 10건, 하루 15건 남짓 올라온다 — 닷새 치쯤
_KOFIA_ROW = re.compile(r'<td class="first num">\d+</td>\s*(?:<!--[^>]*-->)?\s*<td>(.*?)</td>(.*?)</tr>', re.S)
# 영문 약어는 앞뒤가 영문이 아닐 때만(교보AIM 의 AIM 은 AI 가 아니다).
_KOFIA_IT = re.compile(r"(?<![A-Za-z])(IT|AI|ICT)(?![A-Za-z])|전산|디지털|정보보호|보안|데이터")
_KOFIA_PERIOD = re.compile(r"접수기간\s*(\d{8})\s*~\s*(\d{8})")


def _kofia_get(url: str) -> str:
    """이 서버는 chunked 응답을 자주 중간에 끊는다 — 세 번까지 다시 받고, 끝내 끊기면 받은 데까지 쓴다."""
    import http.client
    partial = b""
    for _ in range(3):
        try:
            return http_get(url).decode("utf-8", "ignore")
        except http.client.IncompleteRead as e:
            partial = max(partial, e.partial or b"", key=len)
            _sleep()
    return partial.decode("utf-8", "ignore")


def _kofia_detail(seq: str) -> tuple[str, dict[str, str], dict]:
    raw = _kofia_get(KOFIA_VIEW.format(seq=seq))
    text = _text(re.sub(r"<(script|style)[^>]*>.*?</>", "", raw, flags=re.S | re.I))
    i = text.find("회원사 채용안내 상세보기")
    body = text[i if i >= 0 else 0:]
    j = body.find("목록")
    body = body[:j if j > 0 else None]
    m = _KOFIA_PERIOD.search(re.sub(r"\s+", " ", body))
    extra = {"deadline": cb_mmdd(m.group(2))} if m else {}
    return crawl_ats._clean(body), {}, extra


def cb_mmdd(yyyymmdd: str) -> str:
    return f"~ {yyyymmdd[4:6]}/{yyyymmdd[6:8]}"


def _from_kofia(slug: str, company: str) -> list[dict]:
    out = []
    for page in range(1, KOFIA_PAGES + 1):
        html = _kofia_get(KOFIA_LIST.format(page=page))
        rows = _KOFIA_ROW.findall(html)
        if not rows:
            break
        for firm, rest in rows:
            seq = re.search(r"view\.do\?seq=(\d+)", rest)
            title = re.search(r"</span>\s*(.*?)</a>", rest, re.S)
            if not seq or not title:
                continue
            t = _text(title.group(1))
            out.append({
                "ext_id": seq.group(1), "title": t, "company": _text(firm),
                "url": KOFIA_VIEW.format(seq=seq.group(1)), "location": "—",
                "category": "금융투자", "full_jd": "",
                "dev": kr_portals._dev(t) or bool(_KOFIA_IT.search(t)),
                "detail": (lambda s=seq.group(1): _kofia_detail(s)),
                "deadline": "", "career": "",
            })
        _sleep()
    return out


# ── 게임잡(게임 업계 채용) ──────────────────────────────────────────────────
# 게임사(그라비티 등)는 공고를 자기 사이트 대신 여기로 보낸다. robots 는 /List_GG/ 만 막는다.
# 목록은 직무 코드로 서버가 거른다 — 게임 클라이언트·모바일·AI 개발, 플랫폼 개발, 서버·네트워크·
# 엔진·시스템DB·보안·클라우드, 빅데이터 분석. 본문은 담당업무·자격조건 iframe 두 개다(이미지인 공고도 많다).
GAMEJOB = "https://www.gamejob.co.kr/Recruit"
GAMEJOB_DUTIES = "1,2,3,12,16,17,18,19,20,21,30"
GAMEJOB_PAGES = 15   # 쪽당 40건
_GJ_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_GJ_DEV = re.compile(r"프로그래머|프로그래밍|개발자|엔지니어|서버|클라이언트|DBA|보안|데브옵스|DevOps|TA\b", re.I)


def _gamejob_detail(no: str) -> tuple[str, dict[str, str]]:
    ref = f"{GAMEJOB}/GI_Read/View?GI_No={no}"
    parts = {}
    for head, path in (("주요업무", "GI_Read_Comt_Ifrm"), ("자격요건", "GI_Read_GI_Comment_Ifrm")):
        raw = http_get(f"{GAMEJOB}/{path}?gno={no}&v1", referer=ref).decode("utf-8", "ignore")
        raw = re.sub(r"<(script|style|title)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
        if (t := _text(raw)):
            parts[head] = t
    full = "\n\n".join(f"[{k}]\n{v}" for k, v in parts.items())
    return crawl_ats._clean(full), parts


def _from_gamejob(slug: str, company: str) -> list[dict]:
    import urllib.request
    out, seen = [], set()
    for page in range(1, GAMEJOB_PAGES + 1):
        req = urllib.request.Request(
            f"{GAMEJOB.lower()}/_GI_Job_List",
            data=f"Page={page}&duty={GAMEJOB_DUTIES}&menucode=duty".encode(),
            headers={"User-Agent": kr_portals.UA, "X-Requested-With": "XMLHttpRequest",
                     "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "ignore")
        rows = [b for b in _GJ_ROW.findall(html) if "GI_No=" in b]
        if not rows:
            break
        for blk in rows:
            no = re.search(r"GI_No=(\d+)", blk).group(1)
            if no in seen:
                continue
            seen.add(no)
            comp = re.search(r'class="company[^"]*".*?<strong>(.*?)</strong>', blk, re.S)
            title = re.search(r'class="tit".*?<strong>(.*?)</strong>', blk, re.S)
            info = [_text(x) for x in re.findall(r"<span>(.*?)</span>", blk, re.S)]
            duty = re.search(r"IsNullOrWhiteSpace\('([^']*)'\)", blk)
            date_ = re.search(r'class="date">(.*?)</span>', blk, re.S)
            t = _text(title.group(1)) if title else ""
            out.append({
                "ext_id": no, "title": t,
                "company": _text(comp.group(1)) if comp else "",
                "url": f"{GAMEJOB}/GI_Read/View?GI_No={no}",
                "location": next((x for x in info if ">" in x), "—"),
                "category": _html.unescape(duty.group(1)) if duty else "게임 개발",
                # 직무 필터는 '여러 직무 중 하나라도' 라서 원화·사업 PM 도 섞인다 — 제목으로 한 번 더 본다.
                "full_jd": "", "dev": kr_portals._dev_kr(t) or bool(_GJ_DEV.search(t)),
                "detail": (lambda n=no: _gamejob_detail(n)),
                "deadline": _text(date_.group(1)) if date_ else "",
                "career": info[0] if info else "",
            })
        _sleep()
    return out


# ── 나라일터(인사혁신처 — 국가·지자체·공공기관 공무원 채용) ─────────────────────────
# 전산직은 '전산주사보'·'전산사무관' 처럼 직급 이름이라 공용 개발 필터가 모른다 — 키워드로
# 서버 검색을 하고, 같은 검색에 섞이는 '합격자 발표'·'결과' 안내글은 제목으로 뺀다.
# 본문 전문은 hwp/pdf 첨부라 상세의 요약(채용직급·근무지역·접수기간·소개)만 싣는다.
GOJOBS = "https://www.gojobs.go.kr"
GOJOBS_KEYWORDS = ("전산", "정보보호", "정보화", "데이터")
GOJOBS_PAGES = 3   # 키워드마다 최신순 30건
_GOJOBS_NOTICE = re.compile(r"합격|결과|발표|면접시험|시험\s*안내|일정\s*공고|등록\s*안내|취소|변경")


_GOJOBS_IT = re.compile(r"전산|정보보호|정보화|정보통신|데이터|(?<![A-Za-z])(AI|ICT|IT)(?![A-Za-z])|보안|포렌식|"
                        r"소프트웨어|시스템")
_GOJOBS_NON_IT = re.compile(r"디자이너|보좌역|조사관|통계조사")


def _gojobs_view(code: str, sn: str) -> str:
    page = "smbView.do" if code == "060" else "apmView.do"
    return f"{GOJOBS}/{page}?searchJobsecode={code}&empmnsn={sn}&menuNo=401"


def _gojobs_detail(url: str) -> tuple[str, dict[str, str]]:
    text = _text(re.sub(r"<(script|style)[^>]*>.*?</\1>", "", http_get(url).decode("utf-8", "ignore"),
                        flags=re.S | re.I))
    i = text.find("공고명")
    j = text.find("\n목록", i)
    return crawl_ats._clean(text[i if i >= 0 else 0:j if j > 0 else None]), {}


def _from_gojobs(slug: str, company: str) -> list[dict]:
    import urllib.parse
    from datetime import date
    today = date.today().isoformat()
    out, seen = [], set()
    for kw in GOJOBS_KEYWORDS:
        for page in range(1, GOJOBS_PAGES + 1):
            q = urllib.parse.urlencode({"menuNo": 401, "pageIndex": page, "searchKeyword": kw})
            html = http_get(f"{GOJOBS}/apmList.do?{q}").decode("utf-8", "ignore")
            rows = [r for r in re.findall(r"<tr\s*>(.*?)</tr>", html, re.S) if "fn_apmView" in r]
            if not rows:
                break
            for r in rows:
                ids = re.search(r"fn_apmView\('(\d+)',\s*'(\d+)'\)", r)
                tds = [_text(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
                if not ids or len(tds) < 5:
                    continue
                code, sn = ids.groups()
                title, org, end = tds[1], tds[2], tds[4]
                if sn in seen or end < today or _GOJOBS_NOTICE.search(title):
                    continue
                seen.add(sn)
                url = _gojobs_view(code, sn)
                out.append({
                    "ext_id": f"{code}-{sn}", "title": title, "company": org, "url": url,
                    "location": "—", "category": f"공무원·공공 · {kw}", "full_jd": "",
                    # 검색은 본문까지 훑어 디자이너·조사관도 걸린다 — 제목에 IT 직렬이 있어야 한다.
                    "dev": bool(_GOJOBS_IT.search(title)) and not _GOJOBS_NON_IT.search(title),
                    "detail": (lambda u=url: _gojobs_detail(u)),
                    "deadline": _mmdd(end), "career": "",
                })
            _sleep()
    return out


PARSERS = {"gojobs": _from_gojobs, "rallit": _from_rallit, "superookie": _from_superookie,
           "incruit": _from_incruit, "alio": _from_alio, "kofia": _from_kofia,
           "gamejob": _from_gamejob}


def main() -> None:
    args = sys.argv[1:]
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 100
    per_board = int(args[2]) if len(args) > 2 else 30
    crawl_ats.crawl(keyword, target, per_board, site=SITE, boards=BOARDS, parsers=PARSERS)


if __name__ == "__main__":
    main()
