"""국내 대기업·IT 회사 자체 채용 포털 어댑터 — crawl_ats 의 provider 로 붙는다.

Greenhouse·Lever 같은 공용 ATS 가 아니라 회사마다 자기 API 를 둔 곳들이다. 광고(인스타
마이크로사이트 등)로 사람을 모으는 공고도 결국 여기 올라온다 — SK 브로드밴드 광고가
skcareers 로 이어지는 것처럼. 2026-10 조사·실측(robots 허용 + 브라우저 없이 JSON/HTML).

어댑터 하나 = `(slug, company) -> 후보 list[dict]`. 후보 키는 crawl_ats 와 같다:
ext_id·title·company·url·location·category·full_jd, 선택으로 dev(개발직 판정을 직접 할 때)·
detail(개발직만 나중에 부르는 상세 → (본문, 머리말별 dict))·deadline("~ MM/DD")·career.
목록은 늘 **모집중 전부**를 준다 — close_check 가 같은 함수로 "아직 목록에 있나" 를 본다
(`board_ids`).

일부러 뺀 곳: POSCO(robots 전면 차단), 우아한형제들(API 경로 /w1/ 이 robots 차단),
마이다스 recruiter API 호스트를 쓰는 곳(컴투스 등 — 그 호스트 robots `Disallow: /`).
"""
from __future__ import annotations

import html as _html
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request

from crawlers.jobs_common import USER_AGENT, html_to_text, is_developer_job, jitter

UA = USER_AGENT


# ── 공통 ────────────────────────────────────────────────────────────────
def _req(url: str, *, data: bytes | None = None, headers: dict | None = None,
         opener=None, timeout: int = 30) -> bytes:
    h = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with (opener.open(req, timeout=timeout) if opener else
          urllib.request.urlopen(req, timeout=timeout)) as r:
        return r.read()


def _get_json(url: str, **kw) -> object:
    return json.loads(_req(url, **kw).decode("utf-8", "ignore"))


def _post_json(url: str, body: dict, headers: dict | None = None, **kw) -> object:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    h.update(headers or {})
    return json.loads(_req(url, data=json.dumps(body).encode(), headers=h, **kw)
                      .decode("utf-8", "ignore"))


def _text(fragment) -> str:
    if not fragment:
        return ""
    return re.sub(r"\s*\n\s*", "\n", html_to_text(_html.unescape(str(fragment)))).strip()


def _mmdd(value) -> str:
    """여러 날짜 표기 → job_status 가 읽는 '~ MM/DD'. 상시(2999·9999년)는 '상시채용'."""
    s = str(value or "")
    m = re.search(r"(\d{4})[-./]?(\d{2})[-./]?(\d{2})", s)
    if not m:
        return ""
    if m.group(1) in ("2999", "9999"):
        return "상시채용"
    return f"~ {m.group(2)}/{m.group(3)}"


def _sleep(ms: int = 700) -> None:
    time.sleep(jitter(ms) / 1000)


def _sections(**parts: str) -> tuple[str, dict[str, str]]:
    """머리말별 본문 → (전체 본문, build_jd_sections 용 dict). 빈 칸은 뺀다."""
    structured = {k: _text(v) for k, v in parts.items() if _text(v)}
    full = "\n\n".join(f"[{k}]\n{v}" for k, v in structured.items())
    return full[:16000], structured


# 공용 개발직 판정이 "개발" 한 글자로 잡는 비개발 직무(식품 메뉴개발·사업개발 등)를 뺀다.
_NON_DEV_KO = re.compile(r"메뉴개발|제품개발\(|상품개발|사업개발|신사업개발|교육개발|콘텐츠개발|"
                         r"점포개발|부지개발|R&D\(빵|식품|조리|베이커리|경호|경비원|양성과정|교육생")


def _dev(title: str, *more) -> bool:
    blob = " ".join([title or ""] + [str(m or "") for m in more])
    return is_developer_job(title, *[str(m or "") for m in more]) and not _NON_DEV_KO.search(blob)


# 영문 직무 단어 없이 한국어로만 쓴 IT 공고("본사 IT 생산/품질 담당", "영업데이터 자동화 개발")를
# 잡는다. 공용 판정이 모르는 그룹 포털(건설·제조)에 쓴다. 'IT 마케팅' 같은 비개발은 뺀다.
_IT_KO = re.compile(r"(?<![A-Za-z])(IT|AI|DX|ICT|SW)(?![A-Za-z])|전산|자동화 ?개발|데이터 ?(엔지니어|플랫폼|분석|자동화)|"
                    r"정보보(호|안)|보안관제|시스템 ?(개발|엔지니어)|인프라 ?엔지니어|클라우드|"
                    r"Cloud|Architect|Smart ?Factory|Tech ?QA|ERP|MES|개발 ?인재|개발직")
_NON_IT_ROLE = re.compile(r"마케팅|세일즈|B2B 영업|영업 담당")


def _dev_kr(title: str, *more) -> bool:
    blob = " ".join([title or ""] + [str(m or "") for m in more])
    return _dev(title, *more) or (bool(_IT_KO.search(blob)) and not _NON_IT_ROLE.search(title or "")
                                  and not _NON_DEV_KO.search(blob))


def _cand(ext_id, title, company, url, *, location="", category="", full_jd="",
          dev=None, detail=None, deadline="", career="") -> dict:
    c = {"ext_id": str(ext_id), "title": (title or "").strip(), "company": (company or "").strip(),
         "url": url, "location": (location or "").strip() or "—", "category": category or "",
         "full_jd": full_jd or "", "deadline": deadline, "career": career or "",
         "dev": _dev(title, category) if dev is None else dev}
    if detail is not None:
        c["detail"] = detail
    return c


# ── 토스 그룹 ────────────────────────────────────────────────────────────
# Greenhouse 를 자기 프록시 뒤에 둔다(공개 boards-api slug 는 404). 한 번에 전부 + 본문 포함.
def _toss_meta(job: dict, prefix: str) -> str:
    for m in job.get("metadata") or []:
        if str(m.get("name") or "").startswith(prefix):
            v = m.get("value")
            return ", ".join(map(str, v)) if isinstance(v, list) else str(v or "")
    return ""


def from_toss(slug: str, company: str) -> list[dict]:
    data = _get_json("https://api-public.toss.im/api/v3/ipd-eggnog/career/jobs")
    out = []
    for j in data.get("success") or []:
        affiliate = _toss_meta(j, "포지션의 소속 자회사")
        if not j.get("requisition_id") or affiliate.upper() == "ETC":
            continue
        cat = _toss_meta(j, "커리어 페이지 노출 Job Category")
        jd = _toss_meta(j, "Job Description")
        out.append(_cand(j["id"], j.get("title"), affiliate or "토스", j.get("absolute_url")
                         or f"https://toss.im/career/job-detail?gh_jid={j['id']}",
                         location=(j.get("location") or {}).get("name", ""), category=cat,
                         full_jd=_text(jd)[:16000], deadline=_mmdd(j.get("application_deadline"))))
    return out


# ── LINE / LY ───────────────────────────────────────────────────────────
def _line_detail(sid) -> tuple[str, dict]:
    d = _get_json(f"https://careers.linecorp.com/page-data/ko/jobs/{sid}/page-data.json")
    return _text(((d.get("result") or {}).get("data") or {}).get("strapiJobs", {}).get("content"))[:16000], {}


# 대부분 방콕·타이베이 공고다 — 국내 근무지만 둔다.
_LINE_KR = {"Bundang", "Gwacheon", "Seoul"}


def from_line(slug: str, company: str) -> list[dict]:
    d = _get_json("https://careers.linecorp.com/page-data/ko/jobs/page-data.json")
    edges = d["result"]["data"]["allStrapiJobs"]["edges"]
    out = []
    for e in edges:
        n = e.get("node") or {}
        cities = [c.get("name", "") for c in n.get("cities") or []]
        if not _LINE_KR.intersection(cities):
            continue
        cat = ", ".join(x.get("name", "") for x in (n.get("job_unit") or []) + (n.get("job_fields") or []))
        comp = ", ".join(c.get("name", "") for c in n.get("companies") or []) or "LINE"
        sid = n.get("strapiId")
        out.append(_cand(sid, n.get("title"), comp, f"https://careers.linecorp.com/ko/jobs/{sid}",
                         location=", ".join(cities), category=cat,
                         detail=(lambda s=sid: _line_detail(s)), deadline=_mmdd(n.get("end_date"))))
    return out


# ── 카카오(전 계열사) ──────────────────────────────────────────────────────
# company=ALL 이 없으면 카카오 본사만 온다. part=ALL 은 안 먹어 직군을 돈다.
def from_kakao(slug: str, company: str) -> list[dict]:
    out = []
    for part in ("TECHNOLOGY", "BUSINESS_SERVICES", "DESIGN", "STAFF"):
        page, total = 1, 1
        while page <= total:
            d = _get_json(f"https://careers.kakao.com/public/api/job-list?page={page}"
                          f"&company=ALL&part={part}")
            total = min(int(d.get("totalPage") or 1), 20)
            for j in d.get("jobList") or []:
                skills = ", ".join(s.get("skillSetName", "") for s in j.get("skillSetList") or [])
                full, st = _sections(소개=j.get("introduction"), 주요업무=j.get("workContentDesc"),
                                     자격요건=j.get("qualification"))
                out.append(_cand(j.get("realId"), j.get("jobOfferTitle"), j.get("companyName"),
                                 f"https://careers.kakao.com/jobs/{j.get('realId')}",
                                 location=j.get("locationName"),
                                 category=", ".join(x for x in (j.get("jobTypeName"), skills) if x),
                                 full_jd=full, deadline=_mmdd(j.get("endDate")),
                                 dev=(part == "TECHNOLOGY") or is_developer_job(j.get("jobOfferTitle"))))
            page += 1
            _sleep(400)
    return out


# ── NHN ─────────────────────────────────────────────────────────────────
def _nhn_detail(pid) -> tuple[str, dict]:
    d = _get_json(f"https://careers.nhn.com/v1/job-postings/{pid}").get("result") or {}
    items = d.get("jobPostingContentsItems") or []
    parts = {}
    for it in items:
        head = (it.get("title") or it.get("name") or "").strip() or "내용"
        body = it.get("contents") or it.get("content") or ""
        parts[head] = "\n".join(map(str, body)) if isinstance(body, list) else body
    return _sections(**parts)


def from_nhn(slug: str, company: str) -> list[dict]:
    rows = _get_json("https://careers.nhn.com/v1/job-postings?page=0&size=200").get("result")
    out = []
    for j in rows or []:
        if j.get("finishYn") == "Y":
            continue
        series = j.get("jobSeries") or []
        groups = {(s.get("jobGroup") or {}).get("name", "") for s in series}
        names = [s.get("name", "") for s in series]
        title = j.get("name") or ""
        loc = re.match(r"\[([^\]]+)\]", title)
        out.append(_cand(j["id"], title, (j.get("corporation") or {}).get("name") or "NHN",
                         f"https://careers.nhn.com/recruits/{j['id']}",
                         location=loc.group(1) if loc else "", category=", ".join(names),
                         dev=("Tech" in groups) or is_developer_job(title, names),
                         detail=(lambda i=j["id"]: _nhn_detail(i)),
                         deadline=_mmdd(j.get("postingEndDatetime")),
                         career=(j.get("careerType") or {}).get("name", "")))
    return out


# ── CJ ──────────────────────────────────────────────────────────────────
def _cj_detail(url: str) -> tuple[str, dict]:
    raw = _req(url).decode("utf-8", "ignore")
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
    raw = re.sub(r"<svg.*?</svg>", "", raw, flags=re.S)
    i = raw.find(">", raw.find('class="detail-list"')) + 1
    j = raw.find('class="popup_content', i)
    return (_text(raw[i:j if j > 0 else None]) if i > 0 else "")[:16000], {}


def from_cj(slug: str, company: str) -> list[dict]:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    _req("https://recruit.cj.net/recruit/ko/recruit/recruit/list.fo", opener=opener)
    body = {"pageVal": "1", "pageIndex": "300", "orderDesc": "1", "sch_title": "", "arrGubun": "",
            "arrRecBu": "", "arrRecJob": "", "arrRecArea": "", "schArea": "N"}
    d = _post_json("https://recruit.cj.net/recruit/ko/recruit/recruit/searchNewGonggoList.fo", body,
                   headers={"X-Requested-With": "XMLHttpRequest"}, opener=opener)
    out = []
    for j in d.get("ds_newRecruitList") or []:
        if j.get("zz_close_yn") == "Y":
            continue
        jid = j.get("zz_jo_num")
        page = ("bestDetail.fo?direct=N&zz_jo_num=" if str(j.get("gubun")) == "2"
                else "detail.fo?zz_jo_num=")
        url = f"https://recruit.cj.net/recruit/ko/recruit/recruit/{page}{jid}"
        out.append(_cand(jid, j.get("zz_title"), j.get("compnm"), url,
                         location=j.get("location_cd_nm"), category=j.get("job_cd_nm") or "",
                         dev=_dev(j.get("zz_title"), j.get("job_cd_nm")),
                         detail=(lambda u=url: _cj_detail(u)),
                         deadline="상시채용" if j.get("zz_till_hire") == "Y" else _mmdd(j.get("zz_end_dt_str")),
                         career={"A": "신입", "B": "경력"}.get(j.get("zz_target_1"), "")))
    return out


# ── 넥슨 그룹 ────────────────────────────────────────────────────────────
# 빠르게 부르면 Cloudflare 가 1분쯤 403 을 준다 — 한 번에 크게 받는다.
def from_nexon(slug: str, company: str) -> list[dict]:
    # 브라우저가 보내는 sec-fetch·Referer 가 없으면 Cloudflare 가 403 대기 페이지를 준다.
    h = {"Origin": "https://careers.nexon.com", "Referer": "https://careers.nexon.com/recruit",
         "Accept": "application/json, text/plain, */*", "sec-fetch-site": "same-site",
         "sec-fetch-mode": "cors"}
    out, page = [], 1
    while page <= 5:
        body = {"corpCodes": [], "jobCategories": [], "careerTypes": [], "employmentTypes": [],
                "workingAreas": [], "query": None, "page": page, "size": 100}
        d = _post_json("https://career-gateway.nexon.com/career/v1/open/job-posts", body, headers=h)
        rows = d.get("list") or []
        for j in rows:
            no = j.get("jobPostNo")
            out.append(_cand(no, j.get("title"), j.get("corpName") or "넥슨",
                             f"https://careers.nexon.com/recruit/{no}",
                             location=j.get("workingArea"), full_jd=_text(j.get("contents"))[:16000],
                             career=(j.get("careerType") or {}).get("description", "")
                             if isinstance(j.get("careerType"), dict) else ""))
        if len(rows) < 100:
            break
        page += 1
        _sleep(4000)
    return out


# ── 스마일게이트 ─────────────────────────────────────────────────────────
def _smilegate_detail(seq) -> tuple[str, dict]:
    d = _get_json(f"https://careers.smilegate.com/api/apply/announce/guest/{seq}")
    return _sections(소개=d.get("description"), 주요업무=d.get("workInfo"),
                     자격요건=d.get("abilityDesc"))


def from_smilegate(slug: str, company: str) -> list[dict]:
    body = {"careerTypeCd": [], "companyCd": [], "gameGenreCd": [], "hireTypeCd": [], "jobDtlCd": [],
            "jobMainCd": [], "keyword": None, "pageIndex": 1, "pageSize": 500, "projectSeq": None,
            "usreId": None}
    rows = _post_json("https://careers.smilegate.com/api/apply/announce/guest", body).get("announce") or []
    out = []
    for j in rows:
        seq = j.get("announceSeq")
        cat = " / ".join(x for x in (j.get("jobMainNm"), j.get("jobDtlNm")) if x)
        out.append(_cand(seq, j.get("title"), j.get("companyNm") or "스마일게이트",
                         f"https://careers.smilegate.com/apply/announce/view?seq={seq}",
                         category=cat, dev=_dev(j.get("title"), cat),
                         detail=(lambda s=seq: _smilegate_detail(s)),
                         deadline=_mmdd(j.get("endDate")), career=j.get("careerTypeNm") or ""))
    return out


# ── LG 그룹(LG U+·LG CNS 포함) ───────────────────────────────────────────
_LG_H = {"Origin": "https://careers.lg.com", "Referer": "https://careers.lg.com/"}


def _lg_detail(nid) -> tuple[str, dict]:
    d = _post_json("https://api.careers.lg.com/rmk/job/retrieveJobNoticesDetail",
                   {"jobNoticeId": nid}, headers=_LG_H)
    recs = (((d.get("data") or {}).get("jobNoticesDetail") or {}).get("recList")) or []
    parts: dict[str, str] = {}
    for r in recs:
        for head, key in (("주요업무", "mainTask"), ("자격요건", "requiredItem"),
                          ("우대사항", "preferredItem"), ("상세", "detailContext")):
            if r.get(key):
                parts[head] = (parts.get(head, "") + "\n" + str(r[key])).strip()
    return _sections(**parts)


def from_lg(slug: str, company: str) -> list[dict]:
    body = {"lnbSearch": "", "hashTagText": "", "recDate": "CREATION_DATE", "order": "DESC",
            "careerList": [], "companyCodeList": [], "desireLocList": [], "jobGroupList": []}
    d = _post_json("https://api.careers.lg.com/rmk/job/retrieveJobNoticesList", body, headers=_LG_H)
    out = []
    for j in (d.get("data") or {}).get("jobNoticeList") or []:
        if j.get("noticeStatus") not in (None, "POSTING"):
            continue
        nid = j.get("jobNoticeId")
        grp = j.get("jobGroupName") or ""
        out.append(_cand(nid, j.get("jobNoticeName"), j.get("companyName"),
                         f"https://careers.lg.com/apply/detail?id={nid}",
                         location=j.get("workLocationName"), category=grp,
                         dev=bool(re.search(r"IT|SW|S/W|소프트웨어|개발|데이터|AI|보안", grp))
                         or _dev(j.get("jobNoticeName")),
                         detail=(lambda n=nid: _lg_detail(n)),
                         deadline=_mmdd(j.get("recEndDateTime")), career=j.get("careerTypeName") or ""))
    return out


# ── 현대자동차·기아(같은 플랫폼) ──────────────────────────────────────────
# 목록은 정해진 파라미터만 보내야 JSON 이 온다(빈 필터를 더하면 오류 페이지).
_HKMC = {"hyundai": ("https://talent.hyundai.com", "HM", "1", "현대자동차"),
         "kia": ("https://career.kia.com", "KM", "2", "기아")}


def _hkmc_detail(slug: str, yy, typ, cls) -> tuple[str, dict]:
    host, svc, hgr, _ = _HKMC[slug]
    d = _get_json(f"{host}/api/rec/AP-{svc}-FO-02800?hgrCd={hgr}&lang=ko&recuYy={yy}"
                  f"&recuType={typ}&recuCls={cls}",
                  headers={"X-HKMC-SERVICE": svc, "X-HKMC-TOKEN": "null"})
    a = ((d.get("data") or {}).get("applyInfo")) or {}
    return _sections(팀소개=a.get("aboutTeamNtc"), 주요업무=a.get("privJdDtl"),
                     자격요건=a.get("privMustReq"), 우대사항=a.get("prefReq"))


def from_hkmc(slug: str, company: str) -> list[dict]:
    host, svc, hgr, name = _HKMC[slug]
    d = _get_json(f"{host}/api/rec/AP-{svc}-FO-02700?hgrCd={hgr}&lang=ko&page=1&pageblock=200",
                  headers={"X-HKMC-SERVICE": svc, "X-HKMC-TOKEN": "null"})
    out = []
    for j in (d.get("data") or {}).get("list") or []:
        yy, typ, cls = j.get("recuYy"), j.get("recuType"), j.get("recuCls")
        cat = " / ".join(x for x in (j.get("secCodeNm"), j.get("fldCodeNm")) if x)
        app = "applyKmView.hc" if slug == "kia" else "applyView.hc"
        out.append(_cand(f"{yy}{typ}{cls}", j.get("recuNoticeNm"), name,
                         f"{host}/apply/{app}?recuYy={yy}&recuType={typ}&recuCls={cls}",
                         location=j.get("workPlaceCodeNm"), category=cat,
                         dev=bool(re.search(r"\bIT\b|ICT|SW|Software|소프트웨어|데이터|Data|AI|보안", cat))
                         or _dev(j.get("recuNoticeNm")),
                         detail=(lambda a=(slug, yy, typ, cls): _hkmc_detail(*a)),
                         deadline=_mmdd(j.get("applyEndDt")), career=j.get("channelCodeNm") or ""))
    return out


# ── 한화 ────────────────────────────────────────────────────────────────
_HANWHA = "https://hwadm.hanwhain.com/new-backend/portal/api/rcRecruit"


def _hanwha_detail(seq) -> tuple[str, dict]:
    d = _post_json(f"{_HANWHA}/get-rcrt", {"rtSeq": seq, "hidnKey": None, "langCd": "ko"})
    units = ((d.get("data") or {}).get("item") or {}).get("unitDt") or []
    body = "\n\n".join(f"[{u.get('ruNm', '')}]\n{_text(u.get('ruDtlJob'))}\n근무지: {_text(u.get('ruWorkpl'))}"
                       for u in units)
    return body[:16000], {}


def from_hanwha(slug: str, company: str) -> list[dict]:
    d = _post_json(f"{_HANWHA}/search-rcrt", {"langCd": "ko", "page": 0, "size": 300})
    out = []
    for j in (d.get("data") or {}).get("list") or []:
        seq = j.get("rtSeq")
        tags = ", ".join(t.get("tagNm", "") if isinstance(t, dict) else str(t) for t in j.get("tagList") or [])
        out.append(_cand(seq, j.get("rtNm"), j.get("sdNm") or "한화",
                         f"https://www.hanwhain.com/portal/apply/recruit/detail?rtSeq={seq}",
                         category=tags, detail=(lambda s=seq: _hanwha_detail(s)),
                         deadline=_mmdd(j.get("rtAcptEndDttm"))))
    return out


# ── 신세계 ──────────────────────────────────────────────────────────────
def _shinsegae_detail(no) -> tuple[str, dict]:
    d = _get_json(f"https://job.shinsegae.com/api/rcrut/{no}")
    d = d.get("body", d)
    return _sections(모집분야=d.get("rcrtSectCn"), 직무소개=d.get("dutyInfoCn"),
                     자격요건=d.get("aplyQlfcCn"), 우대사항=d.get("prfrnCn"))


def from_shinsegae(slug: str, company: str) -> list[dict]:
    d = _get_json("https://job.shinsegae.com/api/rcrut")
    out = []
    for j in d.get("body") or []:
        no = j.get("pbancBscNo")
        duty = ", ".join(x.get("dutyNm", "") for x in j.get("dutySeCd") or [] if isinstance(x, dict))
        out.append(_cand(no, j.get("pbancNm"), j.get("coNm") or "신세계",
                         f"https://job.shinsegae.com/recruit/{no}", category=duty,
                         detail=(lambda n=no: _shinsegae_detail(n)),
                         deadline=_mmdd(j.get("rcptEndDt")), career=j.get("rcrutSeNm") or ""))
    return out


# ── 네이버 ──────────────────────────────────────────────────────────────
def _naver_detail(url: str) -> tuple[str, dict]:
    raw = _req(url).decode("utf-8", "ignore")
    i = raw.find('class="detail_box')
    if i < 0:
        return "", {}
    i = raw.find(">", i) + 1
    j = raw.find('class="detail_btn', i)
    return _text(raw[i:j if j > 0 else None])[:16000], {}


def from_naver(slug: str, company: str) -> list[dict]:
    out, first, total = [], 0, 1
    while first < total and first < 500:
        d = _get_json(f"https://recruit.navercorp.com/rcrt/loadJobList.do?firstIndex={first}")
        total = int(d.get("totalSize") or 0)
        for j in d.get("list") or []:
            aid = j.get("annoId")
            url = f"https://recruit.navercorp.com/rcrt/view.do?annoId={aid}"
            cat = " / ".join(x for x in (j.get("classCdNm"), j.get("subJobCdNm")) if x)
            out.append(_cand(aid, j.get("annoSubject"), j.get("sysCompanyCdNm") or "네이버", url,
                             category=cat, dev=("Tech" in cat) or is_developer_job(j.get("annoSubject"), cat),
                             detail=(lambda u=url: _naver_detail(u)),
                             deadline=_mmdd(j.get("endYmdTime")), career=j.get("entTypeCdNm") or ""))
        first += 10
        _sleep(400)
    return out


# ── KT 그룹 ─────────────────────────────────────────────────────────────
def from_kt(slug: str, company: str) -> list[dict]:
    d = _get_json("https://recruit.kt.com/api/recruit?currentPage=1&pageSize=200"
                  "&isInProgress=true&isContainsContents=true")
    rows = d.get("data", d)
    rows = rows.get("list") or rows.get("content") if isinstance(rows, dict) else rows
    out = []
    for j in rows or []:
        if j.get("isTimeOver"):
            continue
        title = j.get("recruitNoticeName") or ""
        comp = re.match(r"\[([^\]]+)\]", title)
        sectors = ", ".join(s.get("recruitSectorName", "") for s in j.get("recruitSectorList") or [])
        out.append(_cand(j.get("recruitNoticeSn"), title, comp.group(1) if comp else "KT",
                         j.get("recruitNoticeUrl") or "https://recruit.kt.com/",
                         category=sectors, full_jd=_text(j.get("recruitNoticeContents") or j.get("contents"))[:16000],
                         deadline=_mmdd(j.get("receiveEndDatetime")), career=j.get("recruitClassName") or ""))
    return out


# ── 카카오뱅크 ───────────────────────────────────────────────────────────
def _kakaobank_detail(sn) -> tuple[str, dict]:
    d = _get_json(f"https://recruit.kakaobank.com/api/recruits/{sn}")
    d = d.get("data", d)
    return _text(d.get("contents"))[:16000], {}


def from_kakaobank(slug: str, company: str) -> list[dict]:
    d = _post_json("https://recruit.kakaobank.com/api/recruits",
                   {"pageNumber": 1, "pageSize": 200, "receiptFilterType": "ONGOING"})
    rows = d.get("data", d)
    rows = (rows.get("list") or rows.get("content") or rows.get("recruits")) if isinstance(rows, dict) else rows
    out = []
    for j in rows or []:
        sn = j.get("recruitNoticeSn")
        out.append(_cand(sn, j.get("recruitNoticeName"), "카카오뱅크",
                         f"https://recruit.kakaobank.com/jobs/{sn}", category=j.get("recruitClassName") or "",
                         detail=(lambda s=sn: _kakaobank_detail(s)),
                         deadline=_mmdd(j.get("receiveEndDatetime"))))
    return out


# ── 넷마블 ──────────────────────────────────────────────────────────────
def _netmarble_detail(aid) -> tuple[str, dict]:
    d = _get_json(f"https://career.netmarble.com/api/v1/apply/announces/{aid}/view")
    raw = re.sub(r"<(style|script|title)[^>]*>.*?</>", "", str(d.get("annoContents") or ""),
                 flags=re.S | re.I)
    return _text(raw)[:16000], {}


def from_netmarble(slug: str, company: str) -> list[dict]:
    d = _get_json("https://career.netmarble.com/api/v1/apply/announces?page=1&size=1000")
    out = []
    for j in d.get("content") or []:
        aid = j.get("carAnnoId")
        cat = " / ".join(x for x in (j.get("carJobGroupNm"), j.get("carWorkGroupNm")) if x)
        out.append(_cand(aid, j.get("annoSubject"), j.get("companyNm") or "넷마블",
                         f"https://career.netmarble.com/announce/view?anno_id={aid}", category=cat,
                         dev=("기술" in (j.get("carJobGroupNm") or "")) or _dev(j.get("annoSubject"), cat),
                         detail=(lambda a=aid: _netmarble_detail(a)),
                         deadline=_mmdd(j.get("endDate")), career=j.get("reqTypeNm") or ""))
    return out


# ── 삼성(계열사 통합) ─────────────────────────────────────────────────────
def _samsung_detail(seq) -> tuple[str, dict]:
    d = _get_json(f"https://www.samsungcareers.com/recruit/detail.data?seqno={seq}&strCode=")
    items = ((d.get("data") or {}).get("items")) or []
    body = "\n\n".join(
        f"[{_text(i.get('titleKr'))}]\n" + "\n".join(
            f"{h}\n{_text(i.get(k))}" for h, k in (("주요업무", "taskKr"), ("자격요건", "qlfctKr"),
                                                   ("우대사항", "favorKr"), ("근무지", "workPlaceKr"))
            if i.get(k)) for i in items)
    return body[:16000], {}


def from_samsung(slug: str, company: str) -> list[dict]:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    _req("https://www.samsungcareers.com/hr/", opener=opener)
    form = ("currentPageNo=1&intNo=0&strVal=&strTxt=&strKey=&strCompany=&strType=&strOrderBy=&strEntity=")
    raw = _req("https://www.samsungcareers.com/hr/list.data", data=form.encode(), opener=opener,
               headers={"Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest"}).decode("utf-8", "ignore")
    out, seen = [], set()
    for m in re.finditer(r'data-value="([\d,]+)"(.*?)(?=data-value="|\Z)', raw, re.S):
        seq = m.group(1).replace(",", "")
        blk = m.group(2)
        comp = re.search(r'class="company"[^>]*>(.*?)<', blk, re.S)
        title = re.search(r'class="title"[^>]*>(.*?)</', blk, re.S)
        # 한 공고에 data-value 가 여러 번 붙는다(버튼마다) — 제목이 있는 블록만 쓴다.
        if not title or seq in seen:
            continue
        seen.add(seq)
        period = re.search(r'class="period"[^>]*>(.*?)</', blk, re.S)
        end = (_text(period.group(1)).split("~")[-1]) if period else ""
        out.append(_cand(seq, _text(title.group(1)) if title else "", _text(comp.group(1)) if comp else "삼성",
                         f"https://www.samsungcareers.com/hr/?no={seq}",
                         detail=(lambda s=seq: _samsung_detail(s)), deadline=_mmdd(end)))
    return out


# ── 그리팅(greetinghr) — 회사마다 robots 가 다르다 ───────────────────────────
# 한때 통째로 뺐지만 robots 는 회사(호스트)마다 다르다: 무신사·컬리·카카오페이는 공고 페이지를
# 허용하고, 토스·롯데카드·카카오뱅크는 `Disallow: /` 다. 그래서 회차마다 그 회사 호스트의
# robots 를 읽어 공고 페이지(/ko/o/<id>)가 허용될 때만 받는다. 목록·본문은 공개 API
# (api.greetinghr.com, robots 없음)에서 받는다 — 목록에 제목·직군이 있어 개발직만 상세를 부른다.
# slug → (workspaceId, 호스트, 회사명). workspaceId 는 회사 채용 홈 HTML 에만 있어 표로 둔다.
GREETING: dict[str, tuple[int, str, str]] = {
    "musinsa": (1455, "www.musinsacareers.com", "무신사"),
    "kurly": (6012, "kurly.career.greetinghr.com", "컬리"),
    "kakaopay": (9737, "kakaopay.career.greetinghr.com", "카카오페이"),
    "kakaomobility": (14346, "kakaomobility.career.greetinghr.com", "카카오모빌리티"),
    "kakaogames": (7144, "recruit.kakaogames.com", "카카오게임즈"),
    "kakaoent": (5191, "careers.kakaoent.com", "카카오엔터테인먼트"),
    "kakaoenterprise": (12556, "careers.kakaoenterprise.com", "카카오엔터프라이즈"),
    "nextsecurities": (15545, "nextsecurities.career.greetinghr.com", "넥스트증권"),
    "kbsec": (5652, "kbsec.career.greetinghr.com", "KB증권"),
    "wooricard": (17669, "wooricard.career.greetinghr.com", "우리카드"),
    "rebellions": (6706, "rebellions.career.greetinghr.com", "리벨리온"),
    "cashwalk12": (4018, "cashwalk12.career.greetinghr.com", "넛지헬스케어(캐시워크)"),
    "estfamily": (413, "estfamily.career.greetinghr.com", "이스트소프트"),
    "xcena": (12659, "xcena.career.greetinghr.com", "엑시나"),
    "wrtn": (5727, "career.wrtn.io", "뤼튼테크놀로지스"),
    "gccompany": (3017, "gccompany.career.greetinghr.com", "여기어때"),
    "enki": (11539, "enki.career.greetinghr.com", "엔키화이트햇"),
    "mobilinthire": (6442, "mobilinthire.career.greetinghr.com", "모빌린트"),
    "supercent": (2730, "supercent.career.greetinghr.com", "슈퍼센트"),
    "pfct": (3907, "pfct.career.greetinghr.com", "PFCT"),
    "linqalpha": (16435, "linqalpha.career.greetinghr.com", "링크알파"),
    "ex-em": (15598, "ex-em.career.greetinghr.com", "엑셈"),
    "medistream": (756, "medistream.career.greetinghr.com", "메디스트림"),
    "mangoboost": (12290, "mangoboost.career.greetinghr.com", "망고부스트"),
    "nuua": (4236, "nuua.career.greetinghr.com", "누아"),
    "crowdworks": (15138, "crowdworks.career.greetinghr.com", "크라우드웍스"),
    "gowid": (358, "gowid.career.greetinghr.com", "고위드"),
    "sionicai": (16371, "sionicai.career.greetinghr.com", "사이오닉에이아이"),
    "buzzvil": (2204, "buzzvil.career.greetinghr.com", "버즈빌"),
    "sianalytics": (6387, "sianalytics.career.greetinghr.com", "에스아이에이"),
    "zigbang": (1724, "zigbang.career.greetinghr.com", "직방"),
    "moreh": (15374, "moreh.career.greetinghr.com", "모레"),
    "storelink": (8458, "storelink.career.greetinghr.com", "스토어링크"),
    "deepauto-ai": (17885, "deepauto-ai.career.greetinghr.com", "딥오토"),
    "s2w": (3616, "s2w.career.greetinghr.com", "S2W"),
    "kmong": (3430, "kmong.career.greetinghr.com", "크몽"),
    "roai": (15355, "roai.career.greetinghr.com", "로아이"),
    "enerzai": (6701, "enerzai.career.greetinghr.com", "에너자이"),
    "hyundai-autoever": (13782, "career.hyundai-autoever.com", "현대오토에버"),
    "skshieldus": (11263, "www.skshieldusapply.com", "SK쉴더스"),
    "hybe": (10002, "careers.hybecorp.com", "HYBE"),
    "11st": (10686, "11st.career.greetinghr.com", "11번가"),
    "nice": (13465, "nice.career.greetinghr.com", "NICE그룹"),
    "devsisters": (12227, "careers.devsisters.com", "데브시스터즈"),
    "hancom": (9044, "hancom.career.greetinghr.com", "한글과컴퓨터"),
}
_GREETING_API = "https://api.greetinghr.com/ats"
_GREETING_DEV = re.compile(r"Engineer|Develop|Software|Backend|Frontend|Server|Data|AI|ML|Infra|DevOps|"
                           r"Security|QA|Tech|개발|엔지니어|데이터|보안|인프라|기술", re.I)
_GREETING_CAREER = {"NEW_COMER": "신입", "NOT_MATTER": "경력무관"}
_robots_cache: dict[str, bool] = {}


def robots_allows(host: str, path: str) -> bool:
    """그 호스트의 robots.txt 가 path 를 허용하나(회차당 호스트마다 한 번). 못 읽으면 막힌 것으로 본다."""
    import urllib.robotparser
    if host not in _robots_cache:
        try:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(_req(f"https://{host}/robots.txt").decode("utf-8", "ignore").splitlines())
            _robots_cache[host] = rp.can_fetch("*", f"https://{host}{path}")
        except Exception:                                           # noqa: BLE001
            _robots_cache[host] = False
    return _robots_cache[host]


def _greeting_detail(ws: int, oid) -> tuple[str, dict]:
    d = _get_json(f"{_GREETING_API}/v3.5/career/workspaces/{ws}/openings/{oid}")
    info = ((d.get("data") or {}).get("openingsInfo")) or {}
    return _text(info.get("detail"))[:16000], {}


def from_greeting(slug: str, company: str) -> list[dict]:
    ws, host, name = GREETING[slug]
    if not robots_allows(host, "/ko/o/1"):
        raise RuntimeError(f"{host} robots 가 공고 페이지를 막는다")
    d = _get_json(f"{_GREETING_API}/v1.1/career/workspaces/{ws}/openings?page=0&pageSize=500")
    out = []
    for j in (d.get("data") or {}).get("datas") or []:
        title = j.get("title") or ""
        if re.search(r"인재\s*pool|인재풀|talent pool", title, re.I):
            continue
        pos = (j.get("openingJobPosition") or {}).get("openingJobPositions") or []
        occ = [((p.get("workspaceOccupation") or {}).get("occupation") or "") for p in pos]
        jobs = [((p.get("workspaceJob") or {}).get("job") or "") for p in pos]
        place = next(((p.get("workspacePlace") or {}).get("location")
                      or (p.get("workspacePlace") or {}).get("place") or "" for p in pos), "")
        car = next((p.get("jobPositionCareer") or {} for p in pos), {})
        ctype = car.get("careerType") or ""
        career = _GREETING_CAREER.get(ctype) or (
            f"경력 {car['careerFrom']}년↑" if ctype == "EXPERIENCED" and car.get("careerFrom") else
            "경력" if ctype == "EXPERIENCED" else "")
        cat = ", ".join(x for x in dict.fromkeys(occ + jobs) if x)
        oid = j.get("openingId")
        is_dev = (_dev(title, cat) or bool(_GREETING_DEV.search(" ".join(occ + jobs)))) \
            and not _NON_DEV_KO.search(title)
        out.append(_cand(oid, title, (j.get("group") or {}).get("name") or name,
                         f"https://{host}/ko/o/{oid}", location=place, category=cat, dev=is_dev,
                         detail=(lambda w=ws, o=oid: _greeting_detail(w, o)),
                         deadline=_mmdd(j.get("dueDate")) if j.get("dueDate") else "상시채용",
                         career=career))
    return out


# ── KB금융(계열사 통합) ───────────────────────────────────────────────────
# 목록에 본문(cn)까지 온다. jbClsfiCd 가 IT·DIGITAL_DATA 면 IT 직군이다.
def from_kbfg(slug: str, company: str) -> list[dict]:
    out, page, total = [], 1, 1
    while page <= total:
        d = _get_json(f"https://careers.kbfg.com/api/career/recruites?page={page}")["result"]
        total = min(int((d.get("paging") or {}).get("totalPageCount") or 1), 20)
        for j in d.get("recruties") or []:
            eid = j.get("enggId")
            cls = j.get("jbClsfiCd") or ""
            out.append(_cand(eid, j.get("enggTitl"), j.get("affcomNm") or "KB금융",
                             f"https://careers.kbfg.com/recruit/{eid}", category=j.get("jbClsfiNm") or "",
                             full_jd=_text(j.get("cn"))[:16000],
                             dev=cls in ("IT", "DIGITAL_DATA") or _dev(j.get("enggTitl")),
                             deadline=_mmdd(j.get("enggEddt")), career=j.get("carrTypNm") or ""))
        page += 1
    return out


# ── 신한투자증권 ─────────────────────────────────────────────────────────
# 한 페이지에 지난 공고까지 다 온다 — 마감 표기가 붙은 줄은 뺀다.
_SHINHANSEC = "https://recruit.shinhansec.com/recruit"


def _shinhansec_detail(aid) -> tuple[str, dict]:
    raw = _req(f"{_SHINHANSEC}/view.do?annoId={aid}").decode("utf-8", "ignore")
    i = raw.find('class="cont')
    i = raw.find(">", i) + 1 if i >= 0 else 0
    j = raw.find("</section>", i)
    return _text(raw[i:j if j > 0 else None])[:16000], {}


def from_shinhansec(slug: str, company: str) -> list[dict]:
    raw = _req(f"{_SHINHANSEC}/list.do").decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'<li class="recruit_list__item"(.*?)</li>', raw, re.S):
        blk = m.group(1)
        aid = re.search(r"goView\('(\d+)'\)", blk)
        title = re.search(r'recruit_list__tit[^>]*>(.*?)</p>', blk, re.S)
        when_m = re.search(r'recruit_list__date[^>]*>(.*?)</p>', blk, re.S)
        if not aid or not title:
            continue
        when = _text(when_m.group(1)) if when_m else ""
        if "마감" in when:
            continue
        kind = re.search(r'data-reqtypenm="([^"]*)"', blk)
        out.append(_cand(aid.group(1), _text(title.group(1)), "신한투자증권",
                         f"{_SHINHANSEC}/view.do?annoId={aid.group(1)}",
                         detail=(lambda a=aid.group(1): _shinhansec_detail(a)),
                         deadline=_mmdd(when), career=kind.group(1) if kind else ""))
    return out


# ── 건설·제조 그룹(2026-10 조사) ─────────────────────────────────────────────
# 건설사는 IT 직무가 드물다. 시공 30위권 가운데 목록을 받을 수 있고 IT 공고가 실제로 있던 곳만
# 붙였다. 두산건설·GS건설·현대엔지니어링·쌍용·금호·서희·대방은 마이다스 recruiter(API 호스트
# robots 차단), 대우건설·HDC·부영은 자기 robots 가 막는다. 삼성물산·SK에코플랜트·한화 건설은
# 그룹 포털로 이미 받는다.

# 현대건설 — robots 가 /v1/ 을 막되 /v1/apply_list 만 연다. 상세(/v1/apply_view)는 막혀 있어
# 제목·직무 키워드만 받는다. 상세는 목록 화면 안의 창이라 공고별 주소가 없다.
def from_hdec(slug: str, company: str) -> list[dict]:
    d = _get_json("https://recruit.hdec.co.kr/v1/apply_list/search01?reClass=&reDtlClass=")
    out = []
    for j in d.get("response") or []:
        if j.get("STATUS_CD") not in (None, "A"):
            continue
        kw = _html.unescape(" ".join(x for x in (j.get("JOB_SRC_KEYWORD"), j.get("GDS_SRC_KEYWORD")) if x))
        loc = _html.unescape(j.get("LOC_SRC_KEYWORD") or "").replace("#", "").strip()
        title = j.get("TITLE") or ""
        out.append(_cand(j.get("RE_NO"), title, "현대건설", "https://recruit.hdec.co.kr/JobPosting",
                         location=loc, category=kw.replace("#", "").strip(),
                         dev=_dev_kr(title, _html.unescape(j.get("JOB_SRC_KEYWORD") or "")),
                         full_jd=f"[직무 키워드]\n{kw}\n[접수기간]\n{j.get('GIGANDETAIL') or ''}",
                         deadline=_mmdd(j.get("RCP_END_YMD")), career=j.get("RE_CLASS_NM") or ""))
    return out


# KCC 그룹(KCC·KCC건설·KCC글라스·KCC실리콘 …) — 계열사 코드마다 목록을 받는다. robots 없음(410).
_KCC = "https://recruit.kccworld.co.kr/recruit"
_KCC_CORP = {"1": "KCC", "2": "KCC건설", "3": "KCC", "4": "KCC", "5": "KCC", "6": "KCC글라스", "7": "KCC실리콘"}


def _kcc_detail(seq) -> tuple[str, dict]:
    d = _post_json(f"{_KCC}/recruitInfoDtlAjax", {"SEQ_R_INFO": str(seq)})
    body = ((d.get("recruitInfoDtl") or {}).get("CONTENTS")) or ""
    return _text(_html.unescape(body))[:16000], {}   # 엔티티가 두 겹이다


def from_kcc(slug: str, company: str) -> list[dict]:
    out, seen = [], set()
    for corp, name in _KCC_CORP.items():
        d = _post_json(f"{_KCC}/recruitInfoListAjax", {"CORP": corp, "TYPE": ""})
        for j in d.get("recruitInfoList") or []:
            seq = j.get("SEQ_R_INFO")
            if seq in seen or j.get("CODE_NM") not in (None, "서류접수"):
                continue
            seen.add(seq)
            period = j.get("FROM_TO") or ""
            end = period.split("~")[-1]
            out.append(_cand(seq, _html.unescape(j.get("TITLE") or ""), name,
                             f"{_KCC}/announce?SEQ_R_INFO={seq}", dev=_dev_kr(j.get("TITLE")),
                             detail=(lambda s=seq: _kcc_detail(s)),
                             deadline="상시채용" if "채용시" in end else _mmdd(end)))
        _sleep(300)
    return out


# 코오롱 그룹(코오롱글로벌·코오롱베니트 …) — field_nm 에 모집 직무가 쉼표로 온다.
_KOLON = "https://dream.kolon.com/RECRUIT_KOLON/hr/rec/recruit/jobopen/controller/candidate"


def from_kolon(slug: str, company: str) -> list[dict]:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    _req("https://dream.kolon.com/", opener=opener)
    raw = _req(f"{_KOLON}/JobOpen310WebController/searchJobOpenByCandidate2018Renew.hr", opener=opener,
               data=b"recruit_type=&order_by=CLOSE_DT&group_yn=Y",
               headers={"Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest", "Referer": "https://dream.kolon.com/"})
    d = json.loads(raw.decode("utf-8", "ignore"))
    out = []
    for j in ((d.get("resultData") or {}).get("list")) or []:
        if str(j.get("receive_div_cd")) == "99":   # 인재 등록(상시 풀)
            continue
        jid = j.get("jobopen_id")
        field = j.get("field_nm") or ""
        # 상세 화면도 본문 없이 모집분야만 다시 보여 준다 — 목록의 모집분야가 곧 본문이다.
        out.append(_cand(jid, j.get("jobopen_nm"), j.get("unit_nm") or "코오롱",
                         f"https://dream.kolon.com/?jobopen_id={jid}", category=field,
                         full_jd=f"[모집분야]\n{field}", dev=_dev_kr(j.get("jobopen_nm"), field),
                         deadline=_mmdd(j.get("receive_end_dt")),
                         career={"01": "신입", "02": "경력", "03": "신입/경력"}.get(str(j.get("experience")), "")))
    return out


# 두산 그룹(두산에너빌리티·두산로보틱스·디지털이노베이션 …) — 목록 HTML 한 쪽에 전부 온다.
# 상세는 화면 프레임워크 호출이라 아직 못 받는다 — 제목·계열사·마감만 싣는다.
def from_doosan(slug: str, company: str) -> list[dict]:
    raw = _req("https://career.doosan.com/dsp/sa/RecList.jsp").decode("utf-8", "ignore")
    out = []
    for blk in re.findall(r"<li>(.*?)</li>", raw, re.S):
        m = re.search(r"goDetail\('([^']+)'", blk)
        title = re.search(r"<strong[^>]*>(.*?)</strong>", blk, re.S)
        if not m or not title or "접수마감" in blk:
            continue
        comp = re.search(r'class="company"[^>]*>\s*([^<]+)', blk)
        kind = re.search(r'class="badge-type"[^>]*>(.*?)</span>', blk, re.S)
        dl = re.search(r'class="deadline".*?</span>(.*?)</div>', blk, re.S)
        end = _text(dl.group(1)).split("~")[-1] if dl else ""
        t = _text(title.group(1))
        out.append(_cand(m.group(1), t, _text(comp.group(1)) if comp else "두산",
                         "https://career.doosan.com/dsp/sa/RecList.jsp",
                         # 디지털이노베이션은 그룹 IT 계열사다 — 제목에 직무가 없는 수시채용도 IT 다.
                         dev=_dev_kr(t) or "디지털이노베이션" in (comp.group(1) if comp else ""),
                         deadline=_mmdd(end), career=_text(kind.group(1)) if kind else ""))
    return out


# ── 게임·제조·유통(2026-10 조사) ─────────────────────────────────────────────
# 엔씨소프트 — 세션 쿠키 + CSRF. Accept 를 JSON 으로 주지 않으면 404 HTML 이 온다.
# "Development" 직군은 대부분 아트라 jobTypeName(Game Programming·AI R&D …)으로 가른다.
_NC = "https://careers.ncsoft.com"
_NC_DEV = re.compile(r"Programming|AI R&D|System|Information|Engineer|Data|Security|QA|개발|프로그래밍", re.I)


def _nc_session():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    page = _req(f"{_NC}/apply/list", opener=opener).decode("utf-8", "ignore")
    m = re.search(r'name="_csrf"\s+content=\s*"([^"]+)"', page)
    if not m:
        raise RuntimeError("ncsoft CSRF 토큰을 못 찾음")
    return opener, m.group(1)


def _nc_detail(opener, token: str, jid, op) -> tuple[str, dict]:
    raw = _req(f"{_NC}/apply/view/?companyId={op}", opener=opener,
               data=urllib.parse.urlencode({"jopenId": jid, "regOpId": op, "_csrf": token}).encode(),
               headers={"Content-Type": "application/x-www-form-urlencoded"}).decode("utf-8", "ignore")
    raw = re.sub(r"<(script|style|header|footer|nav)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
    return _text(raw)[:16000], {}


def from_ncsoft(slug: str, company: str) -> list[dict]:
    opener, token = _nc_session()
    body = ("order_type=ORDER_ETC&order_direction=desc&page=1&pagesize=200&channelCds=&keywords="
            "&job_group_cd=&search_text=&job_type_cd=&companyIds=")
    d = json.loads(_req(f"{_NC}/interface/apply/list", opener=opener, data=body.encode(), headers={
        "X-CSRF-TOKEN": token, "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}).decode("utf-8", "ignore"))
    out = []
    for j in ((d.get("result") or {}).get("data") or {}).get("record") or []:
        jid, op = j.get("jopenId"), j.get("regOpId")
        cat = " / ".join(x for x in (j.get("jobGroupName"), j.get("jobTypeName"), j.get("jobName")) if x)
        out.append(_cand(jid, j.get("jopenNm"), j.get("companyNm") or "엔씨소프트",
                         f"{_NC}/apply/view/?companyId={op}&jopenId={jid}&regOpId={op}", category=cat,
                         dev=bool(_NC_DEV.search(f"{j.get('jobTypeName') or ''} {j.get('jobName') or ''}"))
                         or _dev(j.get("jopenNm")),
                         detail=(lambda i=jid, o=op: _nc_detail(opener, token, i, o)),
                         deadline=_mmdd(j.get("endDt")), career=j.get("channelNm") or ""))
    return out


# 펄어비스 — 목록 HTML 한 쪽에 전부.
_PA = "https://www.pearlabyss.com/ko-KR/Company/Careers"


def _pa_detail(no) -> tuple[str, dict]:
    raw = _req(f"{_PA}/detail?_jobOpeningNo={no}").decode("utf-8", "ignore")
    raw = re.sub(r"<(script|style|header|footer|nav)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
    return _text(raw)[:16000], {}


def from_pearlabyss(slug: str, company: str) -> list[dict]:
    raw = _req(f"{_PA}/List?_pageNo=1").decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'_jobOpeningNo=(\d+)"[^>]*class="career_list_item"(.*?)</a>', raw, re.S):
        no, blk = m.group(1), m.group(2)
        blk = blk[blk.find(">") + 1:]   # 정규식이 <a> 태그 꼬리부터 잡는다
        title = re.search(r'class="title"[^>]*>(.*?)</p>', blk, re.S)
        if not title:
            continue
        spans = {k: _text(v) for k, v in re.findall(r'<span class="(date|career|office)"[^>]*>(.*?)</span>', blk, re.S)}
        rest = re.sub(r'<(p|span) class="(title|date|career|office)".*?</\1>', " ", blk, flags=re.S)
        cat = " ".join(dict.fromkeys(_text(rest).split()))
        t = _text(title.group(1))
        if t == "인재 Pool":
            continue
        out.append(_cand(no, t, "펄어비스", f"{_PA}/detail?_jobOpeningNo={no}",
                         location=spans.get("office", ""), category=cat, dev=_dev_kr(t, cat),
                         detail=(lambda n=no: _pa_detail(n)),
                         deadline="상시채용" if "상시" in spans.get("date", "") else _mmdd(spans.get("date")),
                         career=spans.get("career", "")))
    return out


# 현대모비스 — 목록 HTML. 지원은 recruiter 로 가지만 목록·상세는 자기 호스트(robots Allow)다.
_MOBIS = "https://careers.mobis.com"


def _mobis_detail(seq) -> tuple[str, dict]:
    raw = _req(f"{_MOBIS}/jobs-view?seq={seq}").decode("utf-8", "ignore")
    raw = re.sub(r"<(script|style|header|footer|nav)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
    raw = re.sub(r'<[^>]+class="[^"]*(tooltip|glossary|term)[^"]*"[^>]*>.*?</[^>]+>', "", raw, flags=re.S)
    i = raw.find('class="view-cont')
    i = raw.find(">", i) + 1 if i >= 0 else 0
    return _text(raw[i:])[:16000], {}


def from_mobis(slug: str, company: str) -> list[dict]:
    raw = _req(f"{_MOBIS}/jobs").decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'href="/jobs-view\?seq=(\d+)"(.*?)</a>', raw, re.S):
        seq, blk = m.group(1), m.group(2)
        if 'class="dday' not in blk:   # 지난 행사 링크가 섞인다
            continue
        p = lambda c: _text((re.search(rf'class="{c}"[^>]*>(.*?)</p>', blk, re.S) or [None, ""])[1])  # noqa: E731
        info = re.findall(r"<p[^>]*>(.*?)</p>", (re.search(r'class="info-wrap02"(.*?)</div>', blk, re.S) or [None, ""])[1], re.S)
        info = [_text(x) for x in info]
        title = " ".join(x for x in (p("integrated"), p("tit")) if x)
        cat = " / ".join(info[:3])
        out.append(_cand(seq, title, "현대모비스", f"{_MOBIS}/jobs-view?seq={seq}",
                         location=info[3] if len(info) > 3 else "", category=cat,
                         dev=_dev_kr(p("tit"), cat) or "SW" in cat,
                         detail=(lambda s=seq: _mobis_detail(s)),
                         deadline=_mmdd(p("date").split(" - ")[-1]), career=p("career")))
    return out


# 롯데그룹 — 목록 HTML(봇 관리 스크립트가 있지만 쿠키만 들고 가면 받힌다).
_LOTTE = "https://recruit.lotte.co.kr"


def _lotte_detail(path: str, opener) -> tuple[str, dict]:
    raw = _req(f"{_LOTTE}{path}", opener=opener).decode("utf-8", "ignore")
    raw = re.sub(r"<(script|style|header|footer|nav)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
    return _text(raw)[:16000], {}


def from_lotte(slug: str, company: str) -> list[dict]:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    raw = _req(f"{_LOTTE}/apply/announcement", opener=opener).decode("utf-8", "ignore")
    out, seen = [], set()
    # 카드의 링크 안에는 제목만 있다 — 기간·마감 표기는 링크 바로 뒤에 온다.
    for m in re.finditer(r'href="(/apply/announcement/detail/(\d+)\?compcd=[^"]*)"[^>]*>(.*?)</a>', raw, re.S):
        path, aid = _html.unescape(m.group(1)), m.group(2)
        title = _text(m.group(3))
        tail = _text(raw[m.end():m.end() + 1500])
        period = re.search(r"\d{4}\.\d{2}\.\d{2}\s*~\s*(\d{4}\.\d{2}\.\d{2})", tail)
        if aid in seen or not title or ("마감" in tail[:120] and "D-" not in tail[:120]):
            continue
        seen.add(aid)
        comp = re.search(r"(롯데\S+?)(?:\s|$)", title)
        out.append(_cand(aid, title, comp.group(1) if comp else "롯데", f"{_LOTTE}{path}", dev=_dev_kr(title),
                         detail=(lambda q=path: _lotte_detail(q, opener)),
                         deadline=_mmdd(period.group(1)) if period else ""))
    return out


# 시프트업 — 한 페이지에 공고와 본문이 다 있다. 공고 번호가 없어 제목의 해시를 키로 쓴다.
def from_shiftup(slug: str, company: str) -> list[dict]:
    import hashlib
    raw = _req("https://shiftup.co.kr/recruit/recruit.php").decode("utf-8", "ignore")
    out = []
    for blk in re.split(r'<div class=["\']recruit_list', raw)[1:]:
        if not re.search(r"""class=['"]status ing""", blk):
            continue
        title = re.search(r"<h4[^>]*>(.*?)</h4>", blk, re.S)
        if not title:
            continue
        t = _text(title.group(1))
        lis = [_text(x) for x in re.findall(r"<li[^>]*>(.*?)</li>", blk.split("recruit_content")[0], re.S)]
        body = blk.split("recruit_content", 1)[1] if "recruit_content" in blk else ""
        key = hashlib.sha1(t.encode()).hexdigest()[:12]
        out.append(_cand(key, t, "시프트업", "https://shiftup.co.kr/recruit/recruit.php",
                         category=lis[0] if lis else "", full_jd=_text("<div" + body)[:16000],
                         dev=_dev_kr(t, lis[0] if lis else ""), career=lis[1] if len(lis) > 1 else ""))
    return out


# HD현대(전 계열사) — 목록 API 하나에 지난 공고까지 다 온다(1.4MB). 본문은 recruiter 호스트의
# 이미지라(그 호스트는 빼기로 했다) 공고명·계열사·모집 직무만 싣는다. 공고별 화면 주소가 없어
# 채용 메인으로 잇는다.
def from_hd(slug: str, company: str) -> list[dict]:
    from datetime import datetime
    d = _get_json("https://recruit.hd.com/api/v1/jobda/getRecruitNoticeList?isPost=true&LANG=KR",
                  headers={"X-User-Role": "FRONT"}, timeout=60)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = []
    for j in d.get("data") or []:
        end = j.get("receiveEndDatetime") or ""
        if end and end[:16] < now:
            continue
        title = j.get("recruitNoticeName") or ""
        if re.search(r"인재\s*POOL|인재풀", title, re.I):
            continue
        sectors = [f"{s.get('job') or ''}/{s.get('jobDetail') or ''}".strip("/")
                   for s in j.get("recruitSectorList") or []]
        areas = sorted({s.get("area") or "" for s in j.get("recruitSectorList") or []} - {""})
        cat = ", ".join(x for x in sectors if x)
        it = [x for x in sectors if _dev_kr(x)]
        out.append(_cand(j.get("recruitNoticeSn"), title, j.get("companyCategory") or "HD현대",
                         "https://recruit.hd.com/kr", location=", ".join(areas[:3]), category=cat,
                         full_jd=f"[모집 직무]\n{cat}",
                         # 한 공고에 직무가 여럿이다 — IT 직무가 하나라도 있으면 받는다.
                         dev=bool(it) or _dev_kr(title),
                         deadline="상시채용" if end.startswith("2099") else _mmdd(end),
                         career=j.get("recruitClassName") or ""))
    return out


# 더존(더존비즈온·더존ICT) — 열린 JSON 목록. 본문은 이미지라 공고명만 싣는다.
# 이 회사는 개발 채용을 '상시 인재Pool' 공고로 받는다 — 다른 곳과 달리 풀 공고를 빼지 않는다.
def from_douzone(slug: str, company: str) -> list[dict]:
    from datetime import date
    today = date.today().strftime("%Y%m%d")
    out = []
    for j in _get_json("https://recruit.douzone.com/api/rec-post/list?keyword=") or []:
        if (j.get("end_dt") or "") < today or j.get("opbl_yn") == "N":
            continue
        title = j.get("pblancsj_dc") or ""
        out.append(_cand(f"{j.get('company_cd')}-{j.get('pblanc_no')}", title, "더존ICT그룹",
                         "https://recruit.douzone.com/", location=j.get("workarea_cd") or "",
                         category=j.get("hire_fg_cd") or "", dev=_dev_kr(title.replace("더존ICT", "")),
                         deadline=_mmdd(j.get("end_dt"))))
    return out


# 한국투자금융 그룹(한국투자증권 …) — 본문은 이미지 한 장이다. 대신 annoCategory 에 모집부문
# 목록이 JSON 으로 와서, IT/Digital 부문이 있는 공고를 고르고 부문 목록을 본문으로 싣는다.
def from_koreainvest(slug: str, company: str) -> list[dict]:
    d = _get_json("https://career.koreainvestment.com/annoucement?company=ALL&annoType=ALL",
                  headers={"AJAX": "true"})
    out = []
    for j in d.get("annoList") or []:
        roles: list[str] = []
        try:
            for comp in json.loads(j.get("annoCategory") or "[]"):
                for groups in comp.values():
                    for g in groups:
                        for v in g.values():
                            roles += v
        except (ValueError, AttributeError, TypeError):
            pass
        it = [r for r in roles if re.search(r"IT|Digital|디지털|AI|개발|정보보호|클라우드|엔지니어|데이터", r)]
        rid = j.get("recruitId")
        out.append(_cand(rid, j.get("title"), j.get("companyName") or "한국투자금융",
                         f"https://career.koreainvestment.com/announcementView?recruitId={rid}",
                         category=", ".join(it or roles[:5]),
                         full_jd="[모집부문]\n" + "\n".join(roles), dev=bool(it) or _dev_kr(j.get("title")),
                         deadline=_mmdd(j.get("eDate")), career=j.get("annoType") or ""))
    return out


PARSERS = {
    "douzone": from_douzone, "koreainvest": from_koreainvest,
    "hd": from_hd,
    "ncsoft": from_ncsoft, "pearlabyss": from_pearlabyss, "mobis": from_mobis, "lotte": from_lotte,
    "shiftup": from_shiftup,
    "hdec": from_hdec, "kcc": from_kcc, "kolon": from_kolon, "doosan": from_doosan,
    "toss": from_toss, "line": from_line, "kakao": from_kakao, "nhn": from_nhn, "cj": from_cj,
    "nexon": from_nexon, "smilegate": from_smilegate, "lg": from_lg, "hkmc": from_hkmc,
    "hanwha": from_hanwha, "shinsegae": from_shinsegae, "naver": from_naver, "kt": from_kt,
    "kakaobank": from_kakaobank, "netmarble": from_netmarble, "samsung": from_samsung,
    "greeting": from_greeting, "kbfg": from_kbfg, "shinhansec": from_shinhansec,
}


def board_ids(provider: str, slug: str, cache: dict) -> set[str] | None:
    """close_check 용 — 그 포털의 지금 모집중 공고 id 집합(회차당 한 번만 받는다). 실패면 None."""
    key = f"{provider}:{slug}"
    if key not in cache:
        try:
            rows = PARSERS[provider](slug, "")
            cache[key] = {c["ext_id"] for c in rows} if rows else None
        except Exception:                                           # noqa: BLE001
            cache[key] = None
    return cache[key]
