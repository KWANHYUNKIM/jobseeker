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

일부러 뺀 곳(2026-10 조사): 리멤버·로켓펀치(약관이 자동 수집 금지), 잡플래닛(잡코리아
미러), 나인하이어·flex(약관 금지), 마이다스 recruiter(robots 가 API 차단), 그리팅(회사별
채용 호스트 robots `Disallow: /`), 프로그래머스·블라인드 하이어(서비스 종료).
나라일터는 본문이 첨부(hwp/pdf)에만 있어 아직 안 붙였다.

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


PARSERS = {"rallit": _from_rallit, "superookie": _from_superookie,
           "incruit": _from_incruit, "alio": _from_alio}


def main() -> None:
    args = sys.argv[1:]
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 100
    per_board = int(args[2]) if len(args) > 2 else 30
    crawl_ats.crawl(keyword, target, per_board, site=SITE, boards=BOARDS, parsers=PARSERS)


if __name__ == "__main__":
    main()
