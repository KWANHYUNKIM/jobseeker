"""알바천국(www.alba.co.kr) — 업직종 'IT·인터넷'·'디자인' 목록에서 컴퓨터로 하는 일만.

수집 경로 (2026-11-21 조사):
  robots.txt  : `User-agent: *` 에 `Disallow: /` 를 깔고 `Allow:` 로 /job/·/recruit/·/search/·/sitemap/ 등만 연다.
                **매 회차 robots 를 다시 읽고** 부를 주소가 허용되는지 본다(`allowed`) — 바뀌면 그 회차는 쉰다.
  목록        : /job/occupation/List?jobKind=18000000(IT·인터넷, 1,185건)·20000000(디자인, 530건), 50건씩.
                회사명·제목·근무지(시/군/구)·근무시간·급여가 줄마다 있다. 상담·QA·사무 광고가 많이 섞인다 —
                제목 규칙이 거른다(콜센터 '단순 상담', 체험단, 국비 과정).
                사이트맵(/sitemap/sitemapN.xml, 31개·17만 건)은 adid 와 lastmod 뿐이라 제목으로 거를 수 없어 안 쓴다.
  상세        : /job/Detail?adid=N — JSON-LD JobPosting(datePosted·validThrough·baseSalary·jobLocation·
                description 의 '모집직종')과 화면 상태(`init('진행' | '마감' …)`). 상호·번지는 버린다.
  마감        : 여기서는 validThrough 가 **진짜 접수 마감일**이다(당근과 다르다) — 지나면 닫는다.
                화면 상태가 '진행'이 아니거나, '삭제된 공고입니다' 안내·첫 화면으로 넘어가면 닫는다.
                두 분류 목록을 끝까지 보므로 목록에서 빠진 모집중 공고는 그 회차에 바로 다시 묻는다.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse

from crawlers.alba.common import (PAY_UNIT_EN, Gone, Robots, Source, ld_posting, pay_obj, sido_name, split_region,
                                  strip_tags)

BASE = "https://www.alba.co.kr"
JOB_KINDS = {"18000000": "IT·인터넷", "20000000": "디자인"}
PAGE_SIZE = 50
MAX_PAGES = 60                 # 분류 하나에 50건 × 60쪽 = 3,000건까지(지금 1,185·530)

ROW_RE = re.compile(r"<tr class=\"[^\"]*\" data-imid='(\d+)'>(.*?)</tr>", re.S)
PAGING_RE = re.compile(r"getWnSearchPaging\('(\d+)', '(\d+)', (\d+)")
STATE_RE = re.compile(r"""onload="init\('([^']*)'""")
LIST_PAY = {"hour": "시급", "day": "일급", "week": "주급", "month": "월급", "year": "연봉", "case": "건별"}
EMPLOYMENT = {"PART_TIME": "알바", "CONTRACTOR": "계약직", "TEMPORARY": "단기", "FULL_TIME": "풀타임",
              "INTERN": "인턴", "OTHER": ""}


def _txt(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def parse_list(html: str) -> tuple[dict[str, dict], int]:
    """목록 한 쪽 → ({adid: entry}, 전체 건수). 상호(company)는 읽지 않는다."""
    out: dict[str, dict] = {}
    for adid, body in ROW_RE.findall(html):
        title = _txt((re.search(r"<span class='title'>(.*?)</span>", body, re.S) or [None, ""])[1])
        if not title:
            continue
        local = _txt((re.search(r"<td class='local[^']*'[^>]*>(.*?)</td>", body, re.S) or [None, ""])[1])
        hours = _txt((re.search(r"<td class='data'>(.*?)</td>", body, re.S) or [None, ""])[1])
        hours = "" if hours.strip() in ("-", "") else hours
        pm = re.search(r"<span class='payIcon (\w+)'>([^<]*)</span><span class='number'>([\d,]+)</span>", body)
        sido, sigungu = split_region(local)
        out[adid] = {
            "url": f"{BASE}/job/Detail?adid={adid}", "title": title,
            "sido": sido, "sigungu": sigungu, "hours": hours.replace(" ", ""),
            "pay": pay_obj(pm.group(3), LIST_PAY.get(pm.group(1), pm.group(2).strip())) if pm else None,
            "sort": f"{int(adid):012d}",
        }
    m = PAGING_RE.search(html)
    return out, int(m.group(2)) if m else 0


def parse_detail(html: str, today: str) -> dict | None:
    """상세 → 요약 칸 + 판정용(content·parts·closed_reason). 공고 데이터가 없으면 None. 삭제 안내면 Gone."""
    if re.search(r"<title>\s*삭제된\s*공고", html) or "alert(\"삭제된 공고입니다" in html:
        raise Gone("원본 삭제(삭제된 공고 안내)")
    ld = ld_posting(html)
    state = (STATE_RE.search(html) or [None, ""])[1]
    if not ld:
        # JSON-LD 가 없는 공고가 있다(2026-11-21 첫 수집에서 IT·인터넷 후보의 일부). 그때는 <title> 의
        # '<상호> 채용정보 : <제목> - 알바천국' 에서 제목만, 화면의 '모집마감 2026.11.26(목)' 에서 마감일만 읽는다.
        # 급여·지역·근무 시간은 목록 줄이 준다. 화면 상태도 못 읽으면 모양을 모르는 것이다.
        tm = re.search(r"<title>[^<]*?채용정보\s*:\s*(.*?)\s*-\s*알바천국\s*</title>", html, re.S)
        if not tm or not state:
            return None
        dm = re.search(r"모집마감</dt>\s*<dd[^>]*>.*?(\d{4})\.(\d{2})\.(\d{2})", html, re.S)
        deadline = "-".join(dm.groups()) if dm else None
        return {"title": tm.group(1).strip(), "content": "", "parts": [], "pay": None, "sido": "", "sigungu": "",
                "employment": "", "posted_at": None, "deadline": deadline, "opt_out": False,
                "closed_reason": f"원본 확인: {state}" if state != "진행" else (
                    f"원본 확인: 마감일 경과({deadline})" if deadline and deadline < today else None)}
    addr = ((ld.get("jobLocation") or {}).get("address") or {})
    val = (ld.get("baseSalary") or {}).get("value") or {}
    desc = strip_tags(ld.get("description") or "")
    kinds = re.search(r"\[모집직종\]\s*(.+)", desc)
    parts = []
    if kinds:                       # 'IT·인터넷 > 프로그래머, QA·테스터·검증' — '>' 뒤가 세부 직종
        for grp in kinds.group(1).split("\n")[0].split("/"):
            parts += [x.strip() for x in grp.split(">")[-1].split(",") if x.strip()]
    etypes = ld.get("employmentType") or []
    etypes = etypes if isinstance(etypes, list) else [etypes]
    deadline = (ld.get("validThrough") or "")[:10] or None
    reason = None
    if state and state != "진행":
        reason = f"원본 확인: {state}"
    elif deadline and deadline < today:
        reason = f"원본 확인: 마감일 경과({deadline})"
    return {
        "title": (ld.get("title") or "").strip(),
        "content": desc, "parts": parts,
        "pay": pay_obj(val.get("value"), PAY_UNIT_EN.get(val.get("unitText") or "", "")),
        "sido": sido_name(addr.get("addressRegion") or ""), "sigungu": addr.get("addressLocality") or "",
        "employment": next((EMPLOYMENT[e] for e in etypes if EMPLOYMENT.get(e)), ""),
        "posted_at": ld.get("datePosted") or None, "deadline": deadline,
        "opt_out": False, "closed_reason": reason,
    }


class AlbaCheonguk(Source):
    name = "albacheonguk"
    label = "알바천국"
    new_limit = 150
    recheck_limit = 100
    listing_open_only = True

    def __init__(self):
        super().__init__()
        self._robots: Robots | None = None

    def allowed(self, url: str) -> bool:
        """robots.txt 를 회차마다 한 번 다시 읽는다. `Disallow: /` 위의 Allow 목록이 바뀌면 그대로 따른다."""
        if self._robots is None:
            self._robots = Robots(self.http.get(f"{BASE}/robots.txt", accept="text/plain")[2])
        return self._robots.allowed(url)

    def _get(self, url: str) -> tuple[int, str, str]:
        if not self.allowed(url):
            raise RuntimeError(f"robots.txt 가 막는다: {url}")
        return self.http.get(url, referer=f"{BASE}/")

    def listing(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        complete = True
        for kind in JOB_KINDS:
            total = None
            for page in range(1, MAX_PAGES + 1):
                q = urllib.parse.urlencode({"jobKind": kind, "page": page, "pagesize": PAGE_SIZE})
                rows, total_n = parse_list(self._get(f"{BASE}/job/occupation/List?{q}")[2])
                total = total_n if total is None else total
                out.update(rows)
                if not rows or page * PAGE_SIZE >= (total or 0):
                    break
            else:
                complete = False                         # 쪽 상한에 걸렸다 — 끝까지 못 봤다
            if not total:
                complete = False
        self.complete = complete
        return out

    def detail(self, pid: str, e: dict) -> dict | None:
        try:
            _status, final, html = self._get(e["url"])
        except urllib.error.HTTPError as ex:
            if ex.code in (404, 410):
                raise Gone(f"원본 삭제(HTTP {ex.code})") from None
            raise
        if f"adid={pid}" not in final:
            raise Gone("원본에서 내려감(첫 화면으로 넘어감)")
        d = parse_detail(html, _today())
        if d is None:
            return None
        # 목록이 준 지역(시/군/구까지)·근무 시간·급여 표기가 상세 JSON-LD 보다 낫다 — 있으면 그것을 쓴다.
        for k in ("sido", "sigungu", "hours"):
            if e.get(k):
                d[k] = e[k]
        if e.get("pay") and not d.get("pay"):
            d["pay"] = e["pay"]
        return d

    def recheck(self, p: dict) -> dict | None:
        d = self.detail(p["pid"], {"url": p["url"]})
        if d:
            for k in ("sido", "sigungu"):                # 처음에 목록에서 받은 지역을 JSON-LD 로 덮지 않는다
                d.pop(k, None)
        return d


def _today() -> str:
    from crawlers.alba.common import today_kst
    return today_kst()
