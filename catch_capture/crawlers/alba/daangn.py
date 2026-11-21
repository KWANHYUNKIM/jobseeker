"""당근알바(jobs.daangn.com) — 동네 알바 중 컴퓨터로 하는 일.

당근알바에는 동네 단위의 짧은 일거리가 올라온다. 대부분 서빙·포장·청소지만 그 사이에 "홈페이지 수정해
주실 분", "엑셀 자동화 알려 주실 분", "유아 코딩 강사" 같은 일감이 섞여 있다. 그것만 골라 모은다.
약관이 서비스 구성요소의 동의 없는 상업적 복제를 막아서 요약과 링크만 둔다(common 머리말).
작성자가 '웹 수집 허용 안 함'(webCrawlNotAllowed)을 켠 공고는 아예 싣지 않는다(이미 실었으면 지운다).

수집 경로 (2026-11-21 조사):
  robots.txt  : User-agent: * 허용. /api/·/me·/auth/·/job-posts/*/apply 등만 막는다 — /api/ 는 부르지 않는다.
  사이트맵    : /sitemap.xml → sitemaps/job-posts-N.xml (공고 4만여 건, <lastmod> 포함)
  공고 주소   : /job-posts/<제목 슬러그>-<12자 id>. 슬러그가 제목이라 사이트맵만으로 1차로 거른다.
  상세        : 페이지에 실린 공고 데이터(closed·closedAt·hidden·deleted·status·급여·근무 시간·
                workplaceRegion) — JSON-LD JobPosting 은 있는 공고만 있어서 없을 때의 보조로만 쓴다.
                JSON-LD 의 validThrough 는 유료 노출 끝나는 날이지 마감일이 아니다 — 쓰지 않는다.

거르는 법 (두 단계):
  1) 사이트맵 슬러그(= 제목)에 분류 규칙을 돌린다. 슬러그 끝의 id 는 떼고 본다 —
     무작위 12자에 'it'·'ai'·'gpt' 가 자주 들어 있다.
  2) 후보의 상세를 받아 진짜 제목으로 다시 분류한다. 제목만으로 모호하면(‘컴퓨터 잘하시는 분’)
     본문을 메모리에서 같이 본다. 아니라고 판정된 것은 상태 파일에 적어 다시 받지 않는다
     (제목이 바뀌어 슬러그가 달라지면 다시 본다).

마감 규칙:
  - 원본 데이터가 closed 이거나 closedAt 이 있거나 deleted·hidden·비공개(privatizedAt)거나
    status 가 ACCEPTED 가 아니면 마감. 404/410 이거나 다른 주소로 넘어가도 마감.
  - 사이트맵에서 사라진 모집중 공고는 그 회차에 바로 다시 묻는다. 사이트맵이 직전의 절반 밑이면 보류.
  - 사이트맵 lastmod 가 바뀐 공고(마감한 것 포함 — 다시 열 수 있다)도 먼저 묻는다.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse

from crawlers.alba.common import SIDO, Gone, Source, ld_posting

BASE = "https://jobs.daangn.com"
SITEMAP_INDEX = f"{BASE}/sitemap.xml"
ID_RE = re.compile(r"^[0-9a-z]{12}$")
SM_ITEM_RE = re.compile(r"<loc>([^<]+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?")


def split_loc(loc: str) -> tuple[str, str] | None:
    """'…/job-posts/<슬러그>-<id>' → (id, 슬러그 제목). 모양이 다르면 None."""
    tail = urllib.parse.unquote(loc.rstrip("/").rsplit("/", 1)[-1])
    if "/job-posts/" not in loc or "-" not in tail:
        return None
    slug, pid = tail.rsplit("-", 1)
    return (pid, slug) if ID_RE.match(pid) else None


def parse_sitemap(xml: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for loc, lastmod in SM_ITEM_RE.findall(xml):
        loc = loc.strip().replace("&amp;", "&")
        sp = split_loc(loc)
        if sp:
            out[sp[0]] = {"url": loc, "slug": sp[1], "title": sp[1].replace("-", " "),
                          "lastmod": (lastmod or "").strip()}
    return out


_JS_STR = r'"((?:[^"\\]|\\.)*)"'
POST_START = re.compile(r"jobPost:\$R\[\d+\]=\{")


def _js_str(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw


def _scalar(seg: str, name: str):
    m = re.search(r"[{,]" + name + r":(?:" + _JS_STR + r"|(!0|!1|null|-?\d+(?:\.\d+)?))", seg)
    if not m:
        return None
    if m.group(1) is not None:
        return _js_str(m.group(1))
    v = m.group(2)
    return {"!0": True, "!1": False, "null": None}.get(v, None) if not re.match(r"-?\d", v) else (
        float(v) if "." in v else int(v))


def _array(seg: str, name: str) -> list[str]:
    m = re.search(r"[{,]" + name + r":\$R\[\d+\]=\[([^\]]*)\]", seg)
    return re.findall(_JS_STR, m.group(1)) if m else []


def _segment(html: str) -> str | None:
    m = POST_START.search(html)
    if not m:
        return None
    end = html.find("__fragments:", m.end())
    return html[m.end(): end if end > 0 else m.end() + 20000]


PAY_UNIT = {"HOURLY": "시급", "DAILY": "일급", "WEEKLY": "주급", "MONTHLY": "월급",
            "YEARLY": "연봉", "PER_CASE": "건당"}
EMPLOYMENT = {"PART_TIME_JOB": "알바", "PART_TIME": "알바", "STAFF": "정직원", "FULL_TIME": "정직원",
              "CONTRACT": "계약직", "CONTRACTOR": "계약직", "FREELANCER": "프리랜서", "INTERN": "인턴"}
DAYS = {"MON": "월", "TUE": "화", "WED": "수", "THU": "목", "FRI": "금", "SAT": "토", "SUN": "일"}


def _hours(days: list[str], start, end, negotiable) -> str:
    d = "·".join(DAYS.get(x, x) for x in days)
    t = f"{start}~{end}" if start and end and (start, end) != ("00:00", "23:30") else ""
    s = " ".join(x for x in (d, t) if x)
    if negotiable and s:
        s += " (협의)"
    return s or ("시간 협의" if negotiable else "")


def parse_detail(html: str) -> dict | None:
    """상세 페이지 → 저장할 요약 칸 + 판정에 쓰는 것(content·opt_out·closed_reason).

    content 는 분류에만 쓰고 호출부가 버린다. 공고 데이터가 없으면 None.
    """
    seg = _segment(html)
    ld = ld_posting(html)
    if seg is None and ld is None:
        return None
    if seg is None:                                   # 보조 — JSON-LD 만 있는 화면
        addr = ((ld.get("jobLocation") or {}).get("address") or {})
        sal = ld.get("baseSalary") or {}
        val = sal.get("value") if isinstance(sal.get("value"), (int, float)) else (sal.get("value") or {}).get("value")
        return {"title": ld.get("title") or "", "content": ld.get("description") or "",
                "pay": {"amount": val, "unit": {"HOUR": "시급", "DAY": "일급", "MONTH": "월급", "YEAR": "연봉"}.get(
                    (sal.get("value") or {}).get("unitText") if isinstance(sal.get("value"), dict) else sal.get("unitText"), ""),
                        "text": ""} if val else None,
                "sido": SIDO.get(addr.get("addressRegion") or "", addr.get("addressRegion") or ""),
                "sigungu": addr.get("addressLocality") or "",
                "employment": EMPLOYMENT.get(str(ld.get("employmentType") or ""), str(ld.get("employmentType") or "")),
                "hours": str(ld.get("workHours") or ""), "posted_at": ld.get("datePosted"),
                "opt_out": False, "closed_reason": None}

    closed_reason = None
    status = _scalar(seg, "status")
    if _scalar(seg, "deleted"):
        closed_reason = "원본 삭제"
    elif _scalar(seg, "closed") or _scalar(seg, "closedAt"):
        closed_reason = "원본 확인: 모집 마감"
    elif _scalar(seg, "hidden") or _scalar(seg, "privatizedAt"):
        closed_reason = "원본 확인: 숨김·비공개"
    elif status and status != "ACCEPTED":
        closed_reason = f"원본 상태 {status}"
    salary, stype = _scalar(seg, "salary"), _scalar(seg, "salaryType")
    region = seg[seg.find("workplaceRegion:"):] if "workplaceRegion:" in seg else ""
    name1, name2 = _scalar(region, "name1") or "", _scalar(region, "name2") or ""
    etype = _scalar(seg, "employmentType") or ""
    return {
        "title": _scalar(seg, "title") or "",
        "content": _scalar(seg, "content") or "",
        "pay": {"amount": salary, "unit": PAY_UNIT.get(stype or "", stype or ""),
                "text": _scalar(seg, "stringifiedSalary") or ""} if salary else None,
        "sido": SIDO.get(name1, name1), "sigungu": name2,
        "employment": EMPLOYMENT.get(etype, etype),
        "hours": _hours(_array(seg, "workDays"), _scalar(seg, "workTimeStart"), _scalar(seg, "workTimeEnd"),
                        _scalar(seg, "isWorkTimeNegotiable")),
        "posted_at": _scalar(seg, "publishedAt") or _scalar(seg, "createdAt") or (ld or {}).get("datePosted"),
        "opt_out": bool(re.search(r"webCrawlNotAllowed:!0", seg)),
        "closed_reason": closed_reason,
        "closed_at": _scalar(seg, "closedAt"),
    }


class Daangn(Source):
    name = "daangn"
    label = "당근"
    new_limit = 150
    recheck_limit = 100
    check_uses_listing = True        # 사이트맵만 받으면 '사라짐'을 알 수 있다 — 회차 사이 확인도 그대로

    def listing(self) -> dict[str, dict]:
        index = self.http.get(SITEMAP_INDEX)[2]
        maps = [u for u in re.findall(r"<loc>([^<]+)</loc>", index) if re.search(r"/job-posts-\d+\.xml", u)]
        if not maps:
            raise RuntimeError("사이트맵 색인에 job-posts-N.xml 이 없다")
        entries: dict[str, dict] = {}
        for u in maps:
            entries.update(parse_sitemap(self.http.get(u.strip())[2]))
        self.complete = True
        return entries

    def candidate(self, e: dict) -> bool:
        from crawlers.alba.common import is_candidate
        return is_candidate(e.get("slug") or e.get("title") or "")

    def detail(self, pid: str, e: dict) -> dict | None:
        """원본을 받아 parse_detail. 내려간 공고는 Gone. 모양을 못 읽으면 None."""
        try:
            _status, final, html = self.http.get(e["url"])
        except urllib.error.HTTPError as ex:
            if ex.code in (404, 410):
                raise Gone(f"원본 삭제(HTTP {ex.code})") from None
            raise
        if pid not in urllib.parse.unquote(final):
            raise Gone("원본에서 내려감(다른 주소로 넘어감)")
        return parse_detail(html)
