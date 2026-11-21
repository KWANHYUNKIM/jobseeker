"""알바몬(www.albamon.com, 잡코리아 계열) — 업직종 IT·기술 전체와 디자인·영상 세부 직종.

수집 경로 (2026-11-21 조사):
  robots.txt  : `User-agent: *` 는 /jobs/detail/*?*keyword·/jobs/detail-content·/jobs/detail/content·
                /jobs/apply/ 등만 막고 나머지(/jobs/part·/jobs/detail/<번호>)는 연다. AI 학습 수집기
                (GPTBot·ClaudeBot…)와 Scrapy 는 통째로 막는다 — 이 크롤러는 다른 채용 크롤러와 같은 브라우저 UA 로
                `*` 규칙을 따르고, 회차마다 robots 를 다시 읽어 부를 주소를 대조한다.
  목록        : /jobs/part?parts=<코드,…>&sortType=POSTED_DATE&size=50&page=N — Next.js 가 서버에서 그린
                `__NEXT_DATA__` 의 base.normal.collection. 제목·parts(업직종 이름)·급여·근무 시간·근무지(시/군/구)·
                closingDate·postStatusType 이 있다. **managerPhoneNumber(담당자 휴대폰)도 실려 오는데 읽지 않는다.**
                코드: 9000 IT·기술 전체(946) · B010 웹·모바일디자인 · B020 그래픽·영상·편집디자인 ·
                B040 CAD·CAM·인테리어디자인 · B050 캐릭터·애니메이션디자인 · C030 동영상촬영·편집 · 6082 데이터수집·가공.
  상세        : /jobs/detail/<번호> 의 viewData — postStatus·closeStat·deleted·deadlineDate·registDateTime·
                crawlingBlock. 없는 번호는 pageProps.fetchError("조회된 결과가 없습니다").
  마감        : postStatus 가 OPEN 이 아니거나 closeStat·deleted 이거나 deadlineDate 가 지나면 닫는다.
                `crawlingBlock` 이 켜진 공고는 수집 거부로 보고 싣지 않는다(당근의 webCrawlNotAllowed 와 같게).
                목록을 끝까지 보므로 목록에서 빠진 모집중 공고는 그 회차에 바로 다시 묻는다.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse

from crawlers.alba.common import Gone, Robots, Source, pay_obj, split_region, strip_tags

BASE = "https://www.albamon.com"
PARTS = ("9000", "B010", "B020", "B040", "B050", "C030", "6082")
PAGE_SIZE = 50
MAX_PAGES = 150

NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
PAY_UNIT = {"HOURLY_WAGE": "시급", "DAILY_WAGE": "일급", "WEEKLY_WAGE": "주급", "MONTHLY_SALARY": "월급",
            "YEARLY_SALARY": "연봉", "PER_CASE": "건별", "HOURLY": "시급", "DAILY": "일급", "WEEKLY": "주급",
            "MONTHLY": "월급", "YEARLY": "연봉"}


def next_data(html: str) -> dict | None:
    m = NEXT_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _hours(week: str, time_: str) -> str:
    return " ".join(x for x in ((week or "").strip(), (time_ or "").strip()) if x)


def list_entry(c: dict) -> tuple[str, dict]:
    """목록 한 줄 → (번호, entry). **필요한 칸만 이름으로 집어 온다** — 담당자 전화·좌표·주소는 닿지 않는다."""
    no = str(c.get("recruitNo") or "")
    pay_t = (c.get("payType") or {})
    sido, sigungu = split_region(c.get("workplaceArea") or "")
    status = (c.get("postStatusType") or {}).get("key") or ""
    return no, {
        "url": f"{BASE}/jobs/detail/{no}", "title": (c.get("recruitTitle") or "").strip(),
        "parts": [p for p in c.get("parts") or [] if isinstance(p, str)],
        "sido": sido, "sigungu": sigungu,
        "hours": _hours(c.get("workingWeek") or "", c.get("workingTime") or ""),
        "pay": None if c.get("negoPay") else pay_obj(re.sub(r"[^\d]", "", c.get("pay") or ""),
                                                      PAY_UNIT.get(pay_t.get("key") or "", pay_t.get("description") or "")),
        "deadline": (c.get("closingDate") or "")[:10] or None,
        "list_status": status,
        "sort": f"{int(no):012d}" if no.isdigit() else "",
    }


def parse_list(html: str) -> tuple[dict[str, dict], int]:
    d = next_data(html)
    if not d:
        raise RuntimeError("목록에 __NEXT_DATA__ 가 없다")
    data = d["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]
    base = data.get("base") or {}
    out = dict(list_entry(c) for c in (base.get("normal") or {}).get("collection") or [])
    out.pop("", None)
    return out, int((base.get("pagination") or {}).get("totalCount") or 0)


def _kst(s: str | None) -> str | None:
    """'2026-11-20 18:09:26' → '2026-11-20T18:09:26+09:00'."""
    if not s:
        return None
    return s.strip().replace(" ", "T") + ("+09:00" if re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d", s.replace(" ", "T")) else "")


def parse_detail(html: str, today: str) -> dict | None:
    """상세 viewData → 요약 칸 + 판정용. 없는 공고면 Gone, 모양을 못 읽으면 None."""
    d = next_data(html)
    if not d:
        return None
    pp = (d.get("props") or {}).get("pageProps") or {}
    if pp.get("fetchError") and not pp.get("data"):
        raise Gone("원본에서 내려감(조회된 공고 없음)")
    v = (pp.get("data") or {}).get("viewData")
    if not v:
        return None
    st = (v.get("postStatus") or {}).get("key") or ""
    deadline = None if v.get("allTime") else ((v.get("deadlineDate") or "")[:10] or None)
    reason = None
    if v.get("deleted"):
        reason = "원본 삭제"
    elif v.get("closeStat") or (st and st != "OPEN"):
        reason = f"원본 확인: {(v.get('postStatus') or {}).get('description') or '모집 마감'}"
    elif deadline and deadline < today:
        reason = f"원본 확인: 마감일 경과({deadline})"
    sal_t = (v.get("salaryType") or {})
    emp = [e.get("description") for e in v.get("employmentType") or [] if isinstance(e, dict)]
    return {
        "title": (v.get("recruitTitle") or "").strip(),
        "content": strip_tags(v.get("content") or "")[:3000],
        "parts": [p.get("description") for p in v.get("part") or [] if isinstance(p, dict)],
        "pay": None if v.get("salaryConsult") else pay_obj(v.get("salary"), PAY_UNIT.get(sal_t.get("key") or "",
                                                                                         sal_t.get("description") or "")),
        "hours": _hours((v.get("workDays") or {}).get("description") or "", v.get("workTimeDetail") or ""),
        "employment": "·".join(x for x in emp if x),
        "posted_at": _kst(v.get("firstPostDateTime") or v.get("registDateTime")),
        "deadline": deadline,
        "opt_out": bool(v.get("crawlingBlock")),
        "closed_reason": reason,
    }


class Albamon(Source):
    name = "albamon"
    label = "알바몬"
    new_limit = 150
    recheck_limit = 100
    listing_open_only = True

    def __init__(self):
        super().__init__()
        self._robots: Robots | None = None

    def _get(self, url: str) -> tuple[int, str, str]:
        if self._robots is None:
            self._robots = Robots(self.http.get(f"{BASE}/robots.txt", accept="text/plain")[2])
        if not self._robots.allowed(url):
            raise RuntimeError(f"robots.txt 가 막는다: {url}")
        return self.http.get(url, referer=f"{BASE}/jobs/part")

    def listing(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        total = 0
        self.complete = False
        for page in range(1, MAX_PAGES + 1):
            q = urllib.parse.urlencode({"parts": ",".join(PARTS), "sortType": "POSTED_DATE",
                                        "size": PAGE_SIZE, "page": page}, safe=",")
            rows, total = parse_list(self._get(f"{BASE}/jobs/part?{q}")[2])
            out.update(rows)
            if not rows or page * PAGE_SIZE >= total:
                self.complete = bool(total)
                break
        return out

    def detail(self, pid: str, e: dict) -> dict | None:
        try:
            _status, _final, html = self._get(f"{BASE}/jobs/detail/{pid}")
        except urllib.error.HTTPError as ex:
            if ex.code in (404, 410):
                raise Gone(f"원본 삭제(HTTP {ex.code})") from None
            raise
        d = parse_detail(html, _today())
        if d is None:
            return None
        for k in ("sido", "sigungu"):                    # 목록의 근무지(시/군/구) — 상세에는 번지까지 붙어 있다
            if e.get(k):
                d[k] = e[k]
        return d

    def recheck(self, p: dict) -> dict | None:
        d = self.detail(p["pid"], {})
        if d:
            d.pop("sido", None)
            d.pop("sigungu", None)
        return d


def _today() -> str:
    from crawlers.alba.common import today_kst
    return today_kst()
