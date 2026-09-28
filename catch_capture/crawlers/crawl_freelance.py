"""외주·프리랜서 프로젝트 크롤러 → jd-viewer/public/freelance.json (누적).

채용 공고와 섞지 않는다. 프로젝트는 단가·기간·상주 여부가 핵심이고 '회사'가 대개
에이전시라, all_jobs 에 넣으면 회사 통계·기술 통계를 흐린다. 그래서 기술 블로그처럼
사이클 끝의 별도 단계로 돌고 산출물도 따로 둔다.

수집처와 경로 (2026-09-28 조사 — robots/약관 확인):
  wanted_gigs : 원티드 긱스 목록 JSON  GET /gigs/api-v2/projects?page=N   (20건/쪽)
  freemoa     : 프리모아 목록 JSON      POST /m4a/s41a  page=N          (10건/쪽)
                응답의 client_id 에 의뢰인 이메일이 들어 있다 — 저장하지 않는다.
  elancer     : 이랜서 sitemap.xml → 상세 /project_detail/{id} 의 JSON-LD JobPosting
                목록 API(api.elancer.co.kr)는 robots 가 막으므로 부르지 않는다.
  jobkorea    : 검색 ?stext=개발자&jobtype=6(프리랜서) — Next.js __next_f 에 실린 목록 JSON
  saramin     : 직무 목록 cat_mcls=2(IT)&job_type=9(프리랜서) HTML. 광고 정규직은 근무형태로 거른다
  imjob       : SI 에이전시 공고판 /work/employ_list.html (EUC-KR). 상태·기간·단가가 목록에 있다
  sism        : SI/SM 상주 게시판 /bbs/ajax_board.php?bo_table=guin. 약관에 복제 금지 조항이
                있어 **목록 요약 칸과 링크만** 두고 본문·상세는 받지 않는다(SISM_PAGES 로 적게).
뺀 곳: 위시켓(약관이 크롤링을 명시적으로 금지), OKKY 구인(robots 전면 Disallow),
      크몽(스크래핑 금지 문구 + robots), 숨고(요청서 비공개), 인크루트·피플앤잡(robots 전면 차단).

누적 규칙:
  - 키는 "<site>:<pid>". 처음 본 날(first_seen_at)과 마지막으로 본 날(last_seen_at)을 남긴다.
  - 원본이 모집 종료라고 하면(모집상태·마감일) status=closed.
  - 목록 앞쪽만 훑으므로 '이번에 안 보였다'를 마감으로 보지 않는다. 대신 화면이
    last_seen_at 이 오래된 것을 따로 표시한다(STALE_DAYS).

사용:
    python -m crawlers.crawl_freelance            # 기본 쪽수
    python -m crawlers.crawl_freelance --pages 3  # 소스당 목록 쪽수(이랜서는 상세 건수 = 쪽수×4)
    python -m crawlers.crawl_freelance --only freemoa,elancer
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

from crawlers.jobs_common import USER_AGENT, extract_tech_stack, html_to_text, jitter

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
OUT_PATH = ROOT_DIR / "jd-viewer" / "public" / "freelance.json"

PAGES_DEFAULT = 15          # 원티드 긱스 300건, 프리모아 150건, 이랜서 상세 60건
ELANCER_PER_PAGE = 4        # 이랜서는 상세를 한 건씩 받으므로 쪽수×4 건만
SLEEP_MS = 1200
SUMMARY_MAX = 700
TIMEOUT = 20

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"0\d{1,2}[-\s.]?\d{3,4}[-\s.]?\d{4}")


# ── 공통 ──────────────────────────────────────────────────────────────

def _request(url: str, data: dict | None = None, referer: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9"}
    if referer:
        headers["Referer"] = referer
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _sleep() -> None:
    time.sleep(jitter(SLEEP_MS) / 1000)


def _scrub(text: str | None) -> str:
    """본문 요약. 연락처는 지운다 — 프로젝트 글에 담당자 이메일·전화가 흔하다."""
    t = html_to_text(text) if text and "<" in text else (text or "")
    t = EMAIL_RE.sub("[이메일]", t)
    t = PHONE_RE.sub("[연락처]", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:SUMMARY_MAX]


def _int(v) -> int | None:
    try:
        n = int(float(str(v).replace(",", "")))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _manwon(n: int | None) -> int | None:
    """단가는 만원 단위로 맞춘다. 원 단위로 적힌 것('5,500,000원')을 만원으로 읽으면 월 550억이
    된다 — DB 의 project_budget_sane 가 실제로 이걸 잡았다. 10만 이상이면 원으로 본다."""
    if n is None:
        return None
    return round(n / 10000) if n >= 100000 else n


def _skills(raw, text: str = "") -> list[str]:
    if isinstance(raw, list):
        items = [str(s).strip() for s in raw]
    else:
        items = [s.strip() for s in re.split(r"[,/·]", str(raw or ""))]
    items = [s for s in items if s and len(s) <= 40]
    if not items and text:
        items = extract_tech_stack(text)
    # 표기를 채용 쪽 기술 사전에 맞춘다 — 'JAVA'·'java' 가 'Java' 와 따로 세어지지 않게.
    items = [(c[0] if len(c := extract_tech_stack(s)) == 1 else s) for s in items]
    seen, out = set(), []
    for s in items:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out[:12]


REMOTE_RE = re.compile(r"재택|원격|리모트|remote", re.IGNORECASE)


def _tags(title: str, text: str) -> list[str]:
    # SI/SM 은 제목만 본다. 본문에는 '운영'·'구축'이 너무 흔해서(데이터 구축, 서비스
    # 운영 환경…) 본문까지 보면 거의 모든 프로젝트가 둘 다 달렸다.
    tags = []
    if re.search(r"\bSM\b|유지\s*보수|운영", title, re.IGNORECASE):
        tags.append("SM")
    if re.search(r"\bSI\b|차세대|고도화|시스템\s*구축", title, re.IGNORECASE):
        tags.append("SI")
    if re.search(r"주말|퇴근\s*후|파트\s*타임|part[- ]?time|주\s*\d\s*일", title + " " + text[:500], re.IGNORECASE):
        tags.append("부업 가능")
    return tags


def _project(site: str, pid, **kw) -> dict:
    p = {
        "id": f"{site}:{pid}", "site": site, "pid": str(pid),
        "url": "", "title": "", "category": "", "kind": "", "location": "",
        "budget": None, "duration": "", "start": "", "skills": [], "career": "",
        "posted_date": None, "deadline": None, "applicants": None,
        "summary": "", "tags": [], "status": "active",
    }
    p.update(kw)
    p["title"] = re.sub(r"\s+", " ", p["title"]).strip()
    p["career"] = re.sub(r"\s+", " ", p["career"]).strip()
    # 기간 칸이 없는 곳(잡코리아·사람인)도 제목에 '[프리랜서/6개월]' 처럼 적어 둔다.
    if not p["duration"]:
        m = re.search(r"(\d+)\s*(개월|주)", p["title"])
        if m:
            p["duration"] = f"{m.group(1)}{m.group(2)}"
    return p


# ── 원티드 긱스 ───────────────────────────────────────────────────────

WG_API = "https://www.wanted.co.kr/gigs/api-v2/projects"


WG_DETAIL_LIMIT = 40        # 회차당 상세. 목록엔 경력·업무 내용이 없어 등급을 못 정한다


def _wg_detail(p: dict) -> None:
    """상세 API 로 요구 경력과 업무 내용을 채운다(등급 추정과 '세부 내역'의 재료)."""
    d = json.loads(_request(f"{WG_API}/{p['pid']}", referer="https://www.wanted.co.kr/gigs/projects"))
    lo, hi = _int(d.get("expert_career_year")), _int(d.get("expert_career_end_year"))
    if lo:
        p["career"] = f"경력 {lo}~{hi}년" if hi and hi != lo else f"경력 {lo}년↑"
    parts = [("업무", d.get("work_desc")), ("범위", d.get("work_scope")),
             ("진행", d.get("progress_desc")), ("기타", d.get("etc_desc"))]
    body = "\n".join(f"[{k}] {v.strip()}" for k, v in parts if isinstance(v, str) and v.strip())
    if body:
        p["summary"] = _scrub(body)
    if _int(d.get("expert_number")):
        p["headcount"] = _int(d.get("expert_number"))
    p["detail_at"] = datetime.now().astimezone().isoformat(timespec="seconds")


def fetch_wanted_gigs(pages: int, known: dict | None = None) -> list[dict]:
    known = known or {}
    out = []
    for page in range(1, pages + 1):
        raw = json.loads(_request(f"{WG_API}?page={page}", referer="https://www.wanted.co.kr/gigs/projects"))
        rows = raw.get("rows") or []
        for r in rows:
            sal = r.get("salary") or {}
            term = r.get("term") or {}
            onsite = r.get("work_place") == "office" or "상주" in (r.get("work_place_txt") or "")
            lo, hi = _int(sal.get("start")), _int(sal.get("end"))
            budget = ({"type": "monthly" if sal.get("salary_type") == "monthly" else "total",
                       "min": lo, "max": hi or lo} if lo or hi else None)
            dur = ""
            if term.get("start"):
                dur = f"{term['start']}{'~' + str(term['end']) if term.get('end') else ''}{r.get('text_term_type') or '개월'}"
            jobs = r.get("jobs") or ""
            title = (r.get("title") or "").strip()
            out.append(_project(
                "wanted_gigs", r.get("id"),
                url=f"https://www.wanted.co.kr/gigs/projects/{r.get('id')}",
                title=title,
                category=jobs.split(">")[0].strip() if jobs else "",
                kind="onsite" if onsite else "remote",
                location=(r.get("address") or "").strip(),
                budget=budget, duration=dur, start=r.get("startAt") or "",
                skills=_skills(r.get("skills")),
                applicants=_int(r.get("apply_count")),
                summary=jobs,
                role_hint=jobs,          # '개발 > 자바 개발자' — 직무 분류의 재료(summary 는 상세로 바뀐다)
                tags=_tags(title, jobs),
                status="active" if r.get("is_recruiting") or r.get("recruitingStatus") == "open" else "closed",
            ))
        pages_total = (raw.get("count") or {}).get("pages") or page
        if page >= pages_total or not rows or _all_closed(out[-len(rows):]):
            break
        _sleep()

    # 상세 — 처음 본 모집중부터, 남는 몫으로 예전에 받아 둔 것 중 상세가 없는 것.
    # 이미 받은 상세는 목록 값으로 덮이지 않게 옮겨 둔다.
    need = []
    for p in out:
        old = known.get(p["id"]) or {}
        if old.get("detail_at"):
            for k in ("career", "summary", "headcount", "detail_at"):
                if old.get(k):
                    p[k] = old[k]
        elif p["status"] == "active":
            need.append((0 if p["id"] not in known else 1, p))
    for _, p in sorted(need, key=lambda x: x[0])[:WG_DETAIL_LIMIT]:
        _sleep()
        try:
            _wg_detail(p)
        except Exception as e:                                       # noqa: BLE001
            print(f"  [wanted_gigs] 상세 {p['pid']} 실패: {str(e)[:80]}", flush=True)
    return out


def _all_closed(batch: list[dict]) -> bool:
    """한 쪽이 통째로 마감이면 더 넘기지 않는다. 두 곳 다 목록에 끝난 프로젝트를 섞어
    최신순으로 주므로, 그 뒤는 더 오래된 마감뿐이다(15쪽을 다 받았더니 3/4 가 마감이었다)."""
    return bool(batch) and all(p["status"] == "closed" for p in batch)


# ── 프리모아 ──────────────────────────────────────────────────────────

FM_API = "https://www.freemoa.net/m4a/s41a"


def fetch_freemoa(pages: int) -> list[dict]:
    out = []
    today = date.today().isoformat()
    for page in range(1, pages + 1):
        raw = json.loads(_request(FM_API, data={"page": page}, referer="https://www.freemoa.net/m4/s41"))
        proj = ((raw.get("DATA") or {}).get("PROJECT") or {})
        rows = proj.get("LIST") or []
        for r in rows:
            # client_id(의뢰인 이메일)·cl_idx·picture_url 은 읽지도 옮기지도 않는다.
            # workType 3 이 상주인데, 2 로 올라온 상주도 있다(제목에 [상주]). 셋 다 본다.
            onsite = (str(r.get("workType")) in ("2", "3") or str(r.get("is_stay")) == "1"
                      or "[상주]" in (r.get("title") or ""))
            lo, hi = _int(r.get("cost_min")), _int(r.get("cost_max"))
            during = _int(r.get("during"))
            text = r.get("txt") or ""
            edate = (r.get("edate") or "")[:10] or None
            open_ = str(r.get("isopen")) == "1" and str(r.get("isNowApply", "1")) == "1"
            if edate and edate < today:
                open_ = False
            title = r.get("title") or ""
            out.append(_project(
                "freemoa", r.get("proj_idx"),
                url=f"https://www.freemoa.net/m4/s41?first_pno={r.get('proj_idx')}",
                title=title,
                category=(r.get("proj_filed_new") or r.get("fld") or "").strip(),
                kind="onsite" if onsite else "remote",
                location=(r.get("pv_smallnm") or "").strip(),
                # 상주는 월 단가, 도급은 총액으로 받는다(프리모아 화면 표기와 같다).
                budget=({"type": "monthly" if onsite else "total", "min": lo, "max": hi or lo}
                        if lo or hi else None),
                duration=f"{during}일" if during else "",
                start=(r.get("BEGIN_EXPECT") or "").strip(),
                skills=_skills(r.get("proj_language"), text),
                posted_date=(r.get("INS_TIME") or "")[:10] or None,
                deadline=edate,
                applicants=_int(r.get("ALL_APPLY_COUNT")),
                summary=_scrub(text),
                tags=_tags(title, text),
                status="active" if open_ else "closed",
            ))
        # PAGINATION 에는 전체 쪽수가 없다(totalRows 뿐). 빈 쪽이 오면 끝이다.
        if not rows or _all_closed(out[-len(rows):]):
            break
        _sleep()
    return out


# ── 이랜서 ────────────────────────────────────────────────────────────

EL_SITEMAP = "https://www.elancer.co.kr/sitemap.xml"
JSONLD_RE = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)
EL_PAY_RE = re.compile(r"월\s*단가\s*[:：]?\s*([\d,]+)\s*(?:만\s*원|만)?(?:\s*[~\-]\s*([\d,]+)\s*만?)?")
EL_TERM_RE = re.compile(r"(\d+)\s*개월")


def fetch_elancer(limit: int, known: set[str]) -> list[dict]:
    xml = _request(EL_SITEMAP).decode("utf-8", "replace")
    ids = re.findall(r"/project_detail/(\d+)", xml)
    # 사이트맵은 최신순이다. 처음 보는 것부터 받고, 남는 몫으로 아는 것을 다시 본다.
    fresh = [i for i in ids if f"elancer:{i}" not in known]
    seen = [i for i in ids if f"elancer:{i}" in known]
    today = date.today().isoformat()
    out = []
    for pid in (fresh + seen)[:limit]:
        _sleep()
        try:
            html = _request(f"https://www.elancer.co.kr/project_detail/{pid}").decode("utf-8", "replace")
        except Exception as e:                                       # noqa: BLE001
            print(f"  [elancer] {pid} 실패: {e}", flush=True)
            continue
        ld = None
        for m in JSONLD_RE.finditer(html):
            try:
                cand = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            if isinstance(cand, dict) and cand.get("@type") == "JobPosting":
                ld = cand
                break
        if not ld:
            continue
        desc = ld.get("description") or ""
        title = ld.get("title") or ""
        pay = EL_PAY_RE.search(desc)
        lo = _manwon(_int(pay.group(1))) if pay else None
        hi = _manwon(_int(pay.group(2))) if pay and pay.group(2) else lo
        term = EL_TERM_RE.search(title) or EL_TERM_RE.search(desc)
        loc = ""
        for place in ld.get("jobLocation") or []:
            a = (place or {}).get("address") or {}
            loc = " ".join(x for x in (a.get("addressRegion"), a.get("addressLocality"), a.get("streetAddress")) if x)
            if loc:
                break
        valid = (ld.get("validThrough") or "")[:10] or None
        remote = bool(REMOTE_RE.search(title + " " + desc[:400]))
        out.append(_project(
            "elancer", pid,
            url=f"https://www.elancer.co.kr/project_detail/{pid}",
            title=title, category="개발",
            kind="remote" if remote else "onsite",
            location=loc,
            budget={"type": "monthly", "min": lo, "max": hi} if lo else None,
            duration=f"{term.group(1)}개월" if term else "",
            skills=_skills(ld.get("qualifications"), desc),
            career=ld.get("experienceRequirements") or "",
            posted_date=(ld.get("datePosted") or "")[:10] or None,
            deadline=valid,
            summary=_scrub(desc),
            tags=_tags(title, desc),
            status="closed" if valid and valid < today else "active",
        ))
    return out


# ── 잡코리아 프리랜서 ─────────────────────────────────────────────────
# 검색 페이지(Next.js)가 목록 JSON 을 self.__next_f 스트림에 싣는다. jobtype=6 이 프리랜서.
# 채용 크롤러와 같은 공고가 겹칠 수 있다 — 여기는 '프리랜서로 뜬 것'이라는 렌즈다.

JK_SEARCH = "https://www.jobkorea.co.kr/Search/"
NEXT_F_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
PAGE_OBJ_RE = re.compile(r'\{"pageSize"')
AD_RE = re.compile(r"국비|교육생|수강생|훈련생|무료\s*교육|취업\s*연계\s*과정")


def _next_payload(html: str) -> dict | None:
    blob = "".join(json.loads('"' + m + '"') for m in NEXT_F_RE.findall(html))
    dec = json.JSONDecoder()
    for m in PAGE_OBJ_RE.finditer(blob):
        try:
            obj, _ = dec.raw_decode(blob, m.start())
        except json.JSONDecodeError:
            continue
        content = obj.get("content") or []
        if content and "applicationPeriod" in content[0]:
            return obj
    return None


def fetch_jobkorea(pages: int) -> list[dict]:
    out = []
    today = date.today().isoformat()
    for page in range(1, pages + 1):
        q = urllib.parse.urlencode({"stext": "개발자", "jobtype": "6", "tabType": "recruit", "Page_No": page})
        html = _request(f"{JK_SEARCH}?{q}", referer=JK_SEARCH).decode("utf-8", "replace")
        obj = _next_payload(html)
        if not obj:
            break
        rows = obj.get("content") or []
        for r in rows:
            title = r.get("title") or ""
            if AD_RE.search(title):
                continue
            pay = r.get("payRange") or {}
            lo, hi = _int(pay.get("start")), _int(pay.get("end"))
            ptype = str(r.get("payTypeCode"))
            if ptype == "1":                       # 연봉(만원) → 월 단가로 맞춘다
                lo, hi = (round(lo / 12) if lo else None), (round(hi / 12) if hi else None)
            budget = ({"type": "monthly", "min": lo, "max": hi or lo}
                      if ptype in ("1", "2") and lo else None)
            end = ((r.get("applicationPeriod") or {}).get("end") or "")[:10] or None
            kw = r.get("_internal_featureSkillCode") or ""
            loc = ", ".join((r.get("_internal_featureLocationCode") or "").split(",")[:2])
            ctype, crange = str(r.get("careerType")), _int(r.get("careerRange"))
            career = {"1": "신입", "3": "경력무관"}.get(ctype) or (f"경력 {crange}년↑" if crange else "경력")
            remote = bool(REMOTE_RE.search(title))
            out.append(_project(
                "jobkorea", r.get("id"),
                url=f"https://www.jobkorea.co.kr/Recruit/GI_Read/{r.get('id')}",
                title=title, category="개발",
                kind="remote" if remote else "onsite",
                location=loc, budget=budget,
                skills=_skills(None, f"{title} {kw}"),
                career=career,
                posted_date=(r.get("createdAt") or "")[:10] or None,
                deadline=end,
                summary=(r.get("companyName") or "").strip(),
                tags=_tags(title, kw),
                status="closed" if end and end < today else "active",
            ))
        if page >= (obj.get("totalPages") or page) or not rows:
            break
        _sleep()
    return out


# ── 사람인 프리랜서 ───────────────────────────────────────────────────
# IT개발·데이터 직무(cat_mcls=2) 목록에 job_type=9(프리랜서). 상단 광고로 정규직이 섞여
# 들어오므로 근무형태 칸에 '프리랜서'가 적힌 것만 받는다.

SR_LIST = "https://www.saramin.co.kr/zf_user/jobs/list/job-category"
SR_ITEM_RE = re.compile(r'<div id="rec-(\d+)" class="list_item">(.*?)<div class="similar_recruit">', re.S)


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _pick(pattern: str, html: str) -> str:
    m = re.search(pattern, html, re.S)
    return _strip(m.group(1)) if m else ""


def _md_date(text: str, today: date) -> str | None:
    """'~10.17(토)' → 올해/내년 중 가까운 쪽 ISO. job_status 와 같은 규칙."""
    m = re.search(r"(\d{1,2})\s*[./]\s*(\d{1,2})", text or "")
    if not m:
        return None
    mm, dd = int(m.group(1)), int(m.group(2))
    cands = []
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            cands.append(date(y, mm, dd))
        except ValueError:
            pass
    return min(cands, key=lambda c: abs((c - today).days)).isoformat() if cands else None


def fetch_saramin(pages: int) -> list[dict]:
    out = []
    today = date.today()
    for page in range(1, pages + 1):
        q = urllib.parse.urlencode({"cat_mcls": 2, "job_type": 9, "page_count": 50, "page": page})
        html = _request(f"{SR_LIST}?{q}", referer=SR_LIST).decode("utf-8", "replace")
        items = SR_ITEM_RE.findall(html)
        if not items:
            break
        kept = 0
        for rec, body in items:
            career = _pick(r'<p class="career">(.*?)</p>', body)
            if "프리랜서" not in career:
                continue
            kept += 1
            title = _pick(r'class="job_tit">.*?<span>(.*?)</span>', body)
            sectors = re.findall(r"<span>([^<]+)</span>", _pick_raw(r'<span class="job_sector">(.*?)</span>\s*</div>', body))
            due = _pick(r'<span class="date">(.*?)</span>', body)
            deadline = None if re.search(r"상시|채용시", due) else _md_date(due, today)
            out.append(_project(
                "saramin", rec,
                url=f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={rec}",
                title=title, category="개발",
                kind="remote" if REMOTE_RE.search(title) else "onsite",
                location=_pick(r'<p class="work_place">(.*?)</p>', body),
                skills=_skills(None, title + " " + " ".join(sectors)),
                career=career.replace("·", "").strip(),
                deadline=deadline,
                summary=_pick(r'class="col company_nm">.*?<a[^>]*>(.*?)</a>', body),
                tags=_tags(title, ""),
                status="closed" if deadline and deadline < today.isoformat() else "active",
            ))
        if not kept:
            break
        _sleep()
    return out


def _pick_raw(pattern: str, html: str) -> str:
    m = re.search(pattern, html, re.S)
    return m.group(1) if m else ""


# ── 아임잡 ────────────────────────────────────────────────────────────
# SI 에이전시 한 곳의 공고판(EUC-KR). 목록에 상태·기간·근무형태·단가가 다 있다.

IM_LIST = "https://www.imjob.co.kr/work/employ_list.html"
# ?page=N 으로 부르면 상세 링크에도 page=N& 가 끼어든다.
IM_ITEM_RE = re.compile(r'<a href="/work/employ_detail\.html\?(?:page=\d+&(?:amp;)?)?no=(\d+)"[^>]*>(.*?)</a>', re.S)


def _won_range(text: str) -> tuple[int | None, int | None]:
    nums = [_manwon(_int(n)) for n in re.findall(r"[\d,]+", text or "")]
    nums = [n for n in nums if n]
    if not nums or "협의" in (text or ""):
        return None, None
    return min(nums), max(nums)


def fetch_imjob(pages: int) -> list[dict]:
    out = []
    for page in range(1, pages + 1):
        html = _request(f"{IM_LIST}?page={page}", referer=IM_LIST).decode("cp949", "replace")
        items = IM_ITEM_RE.findall(html)
        if not items:
            break
        for no, body in items:
            title = _pick(r'<span class="pr-subject">(.*?)</span>', body)
            if not title:
                continue
            state = _pick(r'<div class="work-ing">(.*?)</div>', body)
            tags_raw = re.findall(r'<span class="field-tags">(.*?)</span>', body)
            period = _pick(r'<span class="pr-date">(.*?)</span>', body).replace("기간", "").strip()
            info = dict(re.findall(r'<span class="title">(.*?)</span><span class="info">(.*?)</span>', body))
            mode = info.get("근무형태", "")
            remote = "재택" in mode or bool(REMOTE_RE.search(title))
            lo, hi = _won_range(info.get("단가", ""))
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", period)
            dur = ""
            if len(dates) == 2:
                days = (date.fromisoformat(dates[1]) - date.fromisoformat(dates[0])).days + 1
                dur = f"{days}일" if days < 60 else f"{round(days / 30)}개월"
            out.append(_project(
                "imjob", no,
                url=f"https://www.imjob.co.kr/work/employ_detail.html?no={no}",
                title=title,
                category="개발" if any(t in ("개발", "운영(SM)") for t in tags_raw) else (tags_raw[0] if tags_raw else ""),
                kind="remote" if remote else "onsite",
                location=info.get("근무지", ""),
                # 상주(프리)는 월 단가, 재택 단건은 총액으로 올라온다.
                budget={"type": "total" if remote else "monthly", "min": lo, "max": hi} if lo else None,
                duration=dur, start=dates[0] if dates else "",
                skills=_skills([t for t in tags_raw if t not in ("개발", "운영(SM)", "기타", "기획", "디자인")]),
                tags=_tags(title, "") + (["SM"] if "운영(SM)" in tags_raw and "SM" not in _tags(title, "") else []),
                status="active" if "모집" in state else "closed",
            ))
        if _all_closed(out[-len(items):]):
            break
        _sleep()
    return out


# ── SISM ──────────────────────────────────────────────────────────────
# SI/SM 상주 구인 게시판(그누보드). 목록은 비어 있고 AJAX 조각으로 채운다.
# 약관에 "복제·제3자 제공 금지"가 있어 **본문·상세는 받지 않는다** — 목록에 보이는
# 요약 칸과 원문 링크만 두고, 쪽수도 따로 낮게 잡는다(SISM_PAGES).

SISM_AJAX = "https://sism.co.kr/bbs/ajax_board.php"
SISM_PAGES = 3
SISM_ITEM_RE = re.compile(r'<a href="https://sism\.co\.kr/bbs/board\.php\?bo_table=guin&amp;wr_id=(\d+)[^"]*">(.*?)</a>', re.S)


def fetch_sism(pages: int) -> list[dict]:
    out = []
    for page in range(1, min(pages, SISM_PAGES) + 1):
        q = urllib.parse.urlencode({"bo_table": "guin", "sca": "개발", "page": page})
        html = _request(f"{SISM_AJAX}?{q}", referer="https://sism.co.kr/bbs/board.php?bo_table=guin").decode("utf-8", "replace")
        items = SISM_ITEM_RE.findall(html)
        if not items:
            break
        for wr, body in items:
            title = _pick(r"<h3>(.*?)</h3>", body)
            if not title:
                continue
            kind_badge = _pick(r'<span class="badge outline[^"]*"[^>]*>(.*?)</span>', body)
            level = _pick(r'<span class="badge small lev\d">(.*?)</span>', body)
            role = _pick(r'<span class="ico-txt">(.*?)</span>', body)
            local = [_strip(s) for s in re.findall(r"<span>(.*?)</span>", _pick_raw(r'<div class="list-local">(.*?)</div>', body), re.S)]
            left = _pick(r'<div class="list-comment">\s*<span>(.*?)</span>', body)
            start = next((s for s in local if re.match(r"\d{4}-\d{2}-\d{2}", s)), "")
            dur = next((s for s in local if re.search(r"\d+\s*(개월|일|주)", s)), "")
            loc = next((s for s in local if s and s not in (start, dur)), "")
            tags = [t for t in (kind_badge if kind_badge in ("SI", "SM") else "",) if t]
            out.append(_project(
                "sism", wr,
                url=f"https://sism.co.kr/bbs/board.php?bo_table=guin&wr_id={wr}",
                title=title, category="개발",
                kind="remote" if REMOTE_RE.search(title) else "onsite",
                location=loc, duration=dur, start=start,
                skills=_skills(None, title),
                career=f"{level}급" if level else "",
                summary=role,
                tags=tags,
                status="active" if "남음" in left else "closed",
            ))
        if _all_closed(out[-len(items):]):
            break
        _sleep()
    return out


# ── 누적·저장 ─────────────────────────────────────────────────────────

SOURCES = {
    "wanted_gigs": lambda pages, known: fetch_wanted_gigs(pages, known),
    "freemoa": lambda pages, known: fetch_freemoa(pages),
    "elancer": lambda pages, known: fetch_elancer(pages * ELANCER_PER_PAGE, known),
    "jobkorea": lambda pages, known: fetch_jobkorea(pages),
    "saramin": lambda pages, known: fetch_saramin(max(1, pages // 3)),   # 쪽당 50건
    "imjob": lambda pages, known: fetch_imjob(pages),
    "sism": lambda pages, known: fetch_sism(pages),
}


def _load() -> dict:
    try:
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"projects": []}


# ── 이력 — 단가가 얼마나 내려갔나 ─────────────────────────────────────
# 프로젝트마다 '바뀐 순간'만 남긴다(매 회차 쌓으면 같은 말이 수백 줄). 단가·모집 상태·
# 기간이 바뀌면 한 줄. 지원자 수는 계속 오르니 기준에서 빼고 그 순간 값만 싣는다.
HISTORY_MAX = 30


def _snap(p: dict, at: str) -> dict:
    return {"at": at, "budget": p.get("budget"), "status": p.get("status"),
            "duration": p.get("duration"), "applicants": p.get("applicants")}


def _history(old: dict | None, new: dict, now: str) -> list[dict]:
    if old is None:
        return [_snap(new, now)]
    hist = list(old.get("history") or []) or [_snap(old, old.get("first_seen_at") or now)]
    last = hist[-1]
    if (last.get("budget") != new.get("budget") or last.get("status") != new.get("status")
            or last.get("duration") != new.get("duration")):
        hist.append(_snap(new, now))
    return hist[-HISTORY_MAX:]


# ── 재확인 — 목록에서 빠진 모집중 프로젝트를 원본에 묻는다 ─────────────
RECHECK_LIMIT = 60          # 회차당. 요청 간격(SLEEP_MS)을 지키면 1~2분
SISM_GONE_DAYS = 2          # SISM 은 상세를 받지 않는다 — 게재 기간이 끝나면 목록에서 빠진다


def _check(p: dict, today: date, cache: dict) -> tuple[str, str] | None:
    """(status, 근거) — 모르면 None(모집중 유지)."""
    site, pid = p["site"], p["pid"]
    if site == "wanted_gigs":
        try:
            d = json.loads(_request(f"{WG_API}/{pid}", referer="https://www.wanted.co.kr/gigs/projects"))
        except urllib.error.HTTPError as e:
            return ("closed", f"원본 삭제(HTTP {e.code})") if e.code in (404, 410) else None
        p["applicants"] = _int(d.get("apply_count")) or p.get("applicants")
        if d.get("recruitingStatus") != "open" and not d.get("is_recruiting"):
            return "closed", f"원본 상태 {d.get('recruitingStatus') or 'closed'}"
        return "active", "원본 확인: 모집중"
    if site == "elancer":
        html = _request(p["url"]).decode("utf-8", "replace")
        if "JobPosting" not in html:
            return "closed", "원본 삭제(상세 없음)"
        m = re.search(r'"validThrough"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
        if m and m.group(1) < today.isoformat():
            return "closed", f"마감일 경과({m.group(1)})"
        return "active", "원본 확인: 모집중"
    if site in ("jobkorea", "saramin"):
        from pipeline.close_check import CHECKERS          # 채용 쪽 판정기를 그대로 쓴다
        v = CHECKERS[site]({"site": site, "pid": pid, "url": p["url"]}, today, cache)
        return (v.status, v.reason) if v.status in ("closed", "active") else None
    if site == "imjob":
        html = _request(p["url"]).decode("cp949", "replace")
        st = _pick(r'<td class="employ-status"[^>]*>(.*?)</td>', html)
        if "마감" in st:
            return "closed", "원본 확인: 접수마감"
        return ("active", "원본 확인: 모집중") if st else None
    if site == "sism":
        seen = datetime.fromisoformat(p["last_seen_at"])
        if (datetime.now().astimezone() - seen).days >= SISM_GONE_DAYS:
            return "closed", f"게재 기간 종료(목록에서 {SISM_GONE_DAYS}일 넘게 안 보임)"
        return None
    return None   # freemoa: 목록에 마감 표시가 같이 나온다 — 오래 안 보이면 화면이 stale 로 가린다


def recheck(candidates: list[dict], now: str) -> list[dict]:
    """오래 안 물어본 것부터 RECHECK_LIMIT 건. 닫힌 것은 status·closed_at·근거를 채운다."""
    today = date.today()
    cache: dict = {}
    todo = sorted(candidates, key=lambda p: p.get("checked_at") or "")[:RECHECK_LIMIT]
    changed, closed = [], 0
    for p in todo:
        try:
            res = _check(p, today, cache)
        except Exception as e:                                       # noqa: BLE001
            res = None
            print(f"  [recheck] {p['id']} 실패: {str(e)[:80]}", flush=True)
        p["checked_at"] = now
        if res and res[0] == "closed":
            old_status = dict(p)
            p["status"], p["closed_reason"], p["closed_at"] = "closed", res[1], now
            p["history"] = _history(old_status, p, now)
            closed += 1
        changed.append(p)
        if p["site"] != "sism":
            _sleep()
    if todo:
        print(f"[freelance] 재확인 {len(todo)}건 → 마감 {closed}건", flush=True)
    return changed


# ── 추이 — 단가 흐름을 화면에 바로 그릴 수 있게 미리 센다 ───────────────
def _median(xs: list[float]) -> float | None:
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _monthly(p: dict, first: bool = False) -> float | None:
    """월 단가(만원). first=True 면 처음 봤을 때의 단가 — 시장 추이는 '올라올 때 값'으로 센다."""
    b = ((p.get("history") or [{}])[0].get("budget") if first else None) or p.get("budget")
    if not b or b.get("type") != "monthly":
        return None
    lo, hi = b.get("min"), b.get("max")
    v = ((lo or hi) + (hi or lo)) / 2 if (lo or hi) else None
    return v if v and 100 <= v <= 3000 else None      # 월 100만~3천만 밖은 표기 사고로 본다


def trend(projects: list[dict], started_at: str = "") -> dict:
    from collections import defaultdict
    weeks: dict = defaultdict(lambda: defaultdict(list))
    for p in projects:
        v = _monthly(p, first=True)
        if v is None:
            continue
        # 등록일이 없는 곳은 '처음 본 날'로 센다. 단 첫 수집 날 한꺼번에 들어온 것은 그 주에
        # 올라온 게 아니라 이미 있던 자리라 뺀다 — 넣으면 첫 주 표본만 300건으로 부푼다.
        if not p.get("posted_date") and (p.get("first_seen_at") or "")[:10] == started_at[:10]:
            continue
        d = (p.get("posted_date") or p.get("first_seen_at") or "")[:10]
        try:
            day = date.fromisoformat(d)
        except ValueError:
            continue
        wk = (day.toordinal() - day.weekday())           # 그 주 월요일
        key = date.fromordinal(wk).isoformat()
        weeks[key]["all"].append(v)
        weeks[key][p.get("kind") or "?"].append(v)
    weekly = [{"week": k, "n": len(v["all"]), "median": _median(v["all"]),
               "onsite": _median(v.get("onsite", [])), "remote": _median(v.get("remote", []))}
              for k, v in sorted(weeks.items())][-16:]

    by_skill: dict = defaultdict(list)
    for p in projects:
        v = _monthly(p)
        if v is None or p.get("status") != "active":
            continue
        for s in set(_skills(p.get("skills") or [])):     # 옛 표기('JAVA')도 여기서 합친다
            by_skill[s].append(v)
    skills = sorted(({"skill": s, "n": len(v), "median": _median(v), "min": min(v), "max": max(v)}
                     for s, v in by_skill.items() if len(v) >= 3), key=lambda x: -x["n"])[:20]

    # 올라온 뒤 단가를 바꾼 프로젝트 — '얼마나 내렸나'의 직접 증거.
    moves = []
    for p in projects:
        hist = [h for h in p.get("history") or [] if (h.get("budget") or {}).get("type") == "monthly"]
        if len(hist) < 2:
            continue
        a, b = _monthly({"budget": hist[0]["budget"]}), _monthly({"budget": hist[-1]["budget"]})
        if a and b and a != b:
            moves.append({"id": p["id"], "title": p["title"], "from": a, "to": b,
                          "pct": round((b - a) / a * 100, 1), "at": hist[-1]["at"]})
    moves.sort(key=lambda m: m["pct"])
    return {"weekly": weekly, "by_skill": skills, "budget_moves": moves[:50]}


def run(pages: int = PAGES_DEFAULT, only: set[str] | None = None) -> dict:
    """모든 소스를 돌려 누적 파일을 갱신한다. 한 소스가 실패해도 나머지는 저장한다."""
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    doc = _load()
    by_id = {p["id"]: p for p in doc.get("projects") or []}
    known = dict(by_id)            # 사이트별 수집기가 예전 값(상세·이력)을 참고한다
    # --only 로 일부만 돌려도 나머지 소스의 직전 기록은 남긴다(화면이 소스별 건수를 보여 준다).
    report: dict = dict(doc.get("sources") or {})
    ran: set[str] = set()
    touched: list[dict] = []       # 이번 회차에 목록에서 본 것 — DB 에는 이것만 보낸다
    new = 0
    for site, fetch in SOURCES.items():
        if only and site not in only:
            continue
        t0 = time.time()
        try:
            rows = fetch(pages, known)
            report[site] = {"ok": True, "fetched": len(rows), "at": now}
            ran.add(site)
        except Exception as e:                                       # noqa: BLE001
            print(f"[freelance] {site} 실패: {e}", flush=True)
            report[site] = {"ok": False, "error": str(e)[:200], "fetched": 0}
            continue
        for p in rows:
            old = by_id.get(p["id"])
            if old is None:
                new += 1
                p["first_seen_at"] = now
            else:
                p["first_seen_at"] = old.get("first_seen_at") or now
                if old.get("status") == "closed" and p["status"] != "closed":
                    p.pop("closed_at", None)
            if p["status"] == "closed":
                p["closed_at"] = (old or {}).get("closed_at") or now
                p.setdefault("closed_reason", (old or {}).get("closed_reason") or "원본 목록: 모집 마감")
            p["last_seen_at"] = now
            p["history"] = _history(old, p, now)
            by_id[p["id"]] = p
            touched.append(p)
        report[site]["elapsed"] = round(time.time() - t0, 1)
        print(f"[freelance] {site}: {report[site]['fetched']}건 ({report[site]['elapsed']}s)", flush=True)

    # 사람을 구하면 목록에서 빠진다. 빠진 채로 두면 '모집중'으로 남으니 원본에 다시 묻는다.
    seen_now = {p["id"] for p in touched}
    rechecked = recheck([p for p in by_id.values()
                         if p["status"] == "active" and p["id"] not in seen_now
                         and (not only or p["site"] in only)], now)
    touched.extend(rechecked)

    projects = sorted(by_id.values(),
                      key=lambda p: (p.get("posted_date") or p.get("first_seen_at") or ""), reverse=True)
    started_at = doc.get("started_at") or min((p.get("first_seen_at") or now for p in projects), default=now)
    # 등급·유형·분야·직무를 달고 그 축으로 단가를 나눠 센다(pipeline/freelance_rates.py).
    from pipeline.freelance_rates import analyze, classify, snapshot
    for p in projects:
        classify(p)
    analysis = analyze(projects, started_at, now[:10])
    # 그날의 현재 단가표를 한 줄씩 쌓는다 — 지난 시장은 다시 계산할 수 없다(목록에서 내려간
    # 자리는 다시 못 본다). 같은 날 여러 번 돌면 마지막 것으로 바꾼다.
    snap = snapshot(analysis["current"])
    rate_history = [h for h in doc.get("rate_history") or [] if h.get("date") != snap["date"]]
    rate_history = sorted(rate_history + [snap], key=lambda h: h["date"])[-1000:]
    out = {"updated_at": now, "started_at": started_at, "sources": report,
           "trend": trend(projects, started_at), "analysis": analysis,
           "rate_history": rate_history, "projects": projects}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    tmp.replace(OUT_PATH)
    active = sum(1 for p in projects if p["status"] == "active")
    stats = {"total": len(projects), "active": active, "new": new,
             "sources": len(ran), "report": report}

    # 정본 DB 이중 쓰기(store/freelance.py). 드라이버가 없거나 DB 가 꺼져 있어도 크롤은 산다.
    try:
        from store import freelance as _db
        db = _db.dual_write(touched)
        if db is not None:
            _db.dual_write_snapshot(snap)
    except ImportError as e:
        db = None
        print(f"  [freelance] DB 모듈 없음 — JSON 만 씁니다: {e}", flush=True)
    if db:
        stats["db"] = db
        print(f"[freelance] DB {db['upserted']}건 (신규 {db['inserted']}, 상태 변화 {db['checks']})", flush=True)
    print(f"[freelance] 누적 {len(projects)}건 (모집중 {active}, 신규 {new}) → {OUT_PATH}", flush=True)
    return stats


def main() -> None:
    args = _sys.argv[1:]
    pages = PAGES_DEFAULT
    only = None
    if "--pages" in args:
        pages = int(args[args.index("--pages") + 1])
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))
    stats = run(pages, only)
    _sys.exit(0 if stats["sources"] else 1)


if __name__ == "__main__":
    main()
