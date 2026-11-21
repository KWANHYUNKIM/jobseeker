"""사람인 알바 — 직무 목록 IT개발·데이터(2)·디자인(15) 에 근무형태 아르바이트(5)·파트(14).

채용 크롤러(crawl_saramin)·외주 크롤러(crawl_freelance 의 프리랜서 목록)와 같은 길이다 —
robots 는 /zf_user/jobs/list/·/zf_user/jobs/relay/view 를 막지 않는다(/zf_user/recruit/view/ 등은 막는다).
목록 HTML 에 제목·근무지·근무형태·마감 표기(~12.20)·직무 태그가 있다. 급여·등록일은 목록에 없고,
사람인은 원래 등록일을 주지 않는다(close_check 머리말) — 화면은 '처음 본 날'로 대신한다.

상단 광고로 정규직이 섞여 들어오므로 근무형태 칸에 '아르바이트'·'파트'가 적혔거나 제목이 알바라고 하는 것만 받는다.
검색 앞 몇 쪽만 보므로 목록에서 안 보인다고 내려간 게 아니다 — 재확인은 공고 페이지에 묻고
판정은 close_check.verdict_saramin(마감일 표기·'마감된 공고' 문구)을 그대로 쓴다.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
from datetime import date, timedelta

from crawlers.alba.common import Gone, Source, md_date, split_region, today_kst

LIST_URL = "https://www.saramin.co.kr/zf_user/jobs/list/job-category"
VIEW_URL = "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={}"
MAX_PAGES = 6                     # 50건 × 6쪽 — 최신순으로 앞쪽만(알바는 하루 몇십 건 올라온다)
ITEM_RE = re.compile(r'<div id="rec-(\d+)" class="list_item">(.*?)<div class="similar_recruit">', re.S)
ALBA_TYPE = re.compile(r"아르바이트|파트")
ALBA_TITLE = re.compile(r"알바|아르바이트|파트\s*타이?머?|파트\s*타임|단기")


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def _pick(pattern: str, html: str) -> str:
    m = re.search(pattern, html, re.S)
    return _strip(m.group(1)) if m else ""


def _due(text: str, today: date) -> str | None:
    """'~12.20(일)' · 'D-4' · '내일마감' · '오늘마감' · '상시채용' → ISO 마감일(없으면 None)."""
    if re.search(r"상시|채용\s*시", text or ""):
        return None
    m = re.search(r"D-(\d+)", text or "")
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat()
    if "오늘" in (text or ""):
        return today.isoformat()
    if "내일" in (text or ""):
        return (today + timedelta(days=1)).isoformat()
    return md_date(text, today)


def parse_list(html: str, today: date) -> dict[str, dict]:
    """목록 한 쪽 → {rec_idx: entry}. 회사명은 읽지 않는다."""
    out: dict[str, dict] = {}
    for rec, body in ITEM_RE.findall(html):
        title = re.sub(r"\s*스크랩\s*$", "", _pick(r'class="job_tit">(.*?)</div>', body))
        career = _pick(r'<p class="career">(.*?)</p>', body)
        if not title or not (ALBA_TYPE.search(career) or ALBA_TITLE.search(title)):
            continue
        sectors = re.findall(r"<span>([^<]+)</span>",
                             (re.search(r'<span class="job_sector">(.*?)</span>\s*</div>', body, re.S) or [None, ""])[1])
        due = _pick(r'<span class="date">(.*?)</span>', body)
        deadline = _due(due, today)
        sido, sigungu = split_region(_pick(r'<p class="work_place">(.*?)</p>', body))
        etype = "아르바이트" if "아르바이트" in career else ("파트" if "파트" in career else "")
        out[rec] = {"url": VIEW_URL.format(rec), "title": title, "content": " ".join(sectors),
                    "sido": sido, "sigungu": sigungu, "deadline": deadline, "employment": etype,
                    "sort": f"{int(rec):012d}"}
    return out


class Saramin(Source):
    name = "saramin"
    label = "사람인"
    new_limit = 150
    recheck_limit = 60

    def listing(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        today = date.fromisoformat(today_kst())
        for page in range(1, MAX_PAGES + 1):
            q = urllib.parse.urlencode({"cat_mcls": "2,15", "job_type": "5,14", "page_count": 50, "page": page,
                                        "sort": "RD"}, safe=",")
            html = self.http.get(f"{LIST_URL}?{q}", referer=LIST_URL)[2]
            if not ITEM_RE.search(html):
                break
            out.update(parse_list(html, today))
        self.complete = False                  # 앞쪽만 본다 — '사라짐'을 마감으로 쓰지 않는다
        return out

    def detail(self, pid: str, e: dict) -> dict | None:
        """목록이 준 것으로 충분하다(새로 받을 때는 원본에 따로 묻지 않는다)."""
        dl = e.get("deadline")
        return {"title": e.get("title") or "", "content": e.get("content") or "", "pay": None,
                "sido": e.get("sido") or "", "sigungu": e.get("sigungu") or "", "employment": e.get("employment") or "",
                "hours": "", "posted_at": None, "deadline": dl, "opt_out": False,
                "closed_reason": f"마감일 경과({dl})" if dl and dl < today_kst() else None}

    def recheck(self, p: dict) -> dict | None:
        from pipeline.close_check import verdict_saramin
        try:
            status, _final, html = self.http.get(VIEW_URL.format(p["pid"]), referer=LIST_URL)
        except urllib.error.HTTPError as ex:
            if ex.code in (404, 410):
                raise Gone(f"원본 삭제(HTTP {ex.code})") from None
            raise
        v = verdict_saramin(html, date.fromisoformat(today_kst()))
        if v.status == "unknown":
            return None
        return {"deadline": v.deadline, "closed_reason": v.reason if v.status == "closed" else None}
