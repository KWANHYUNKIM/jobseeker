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
    h = {"Origin": "https://careers.nexon.com", "Referer": "https://careers.nexon.com/"}
    out, page = [], 1
    while page <= 5:
        body = {"corpCodes": [], "jobCategories": [], "careerTypes": [], "employmentTypes": [],
                "workingAreas": [], "query": None, "page": page, "size": 100}
        d = _post_json("https://career-gateway.nexon.com/career/v1/open/job-posts", body, headers=h)
        rows = d.get("content") or d.get("jobPosts") or d.get("data") or (d if isinstance(d, list) else [])
        if isinstance(rows, dict):
            rows = rows.get("content") or []
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


PARSERS = {
    "toss": from_toss, "line": from_line, "kakao": from_kakao, "nhn": from_nhn, "cj": from_cj,
    "nexon": from_nexon, "smilegate": from_smilegate, "lg": from_lg, "hkmc": from_hkmc,
    "hanwha": from_hanwha, "shinsegae": from_shinsegae, "naver": from_naver, "kt": from_kt,
    "kakaobank": from_kakaobank, "netmarble": from_netmarble, "samsung": from_samsung,
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
