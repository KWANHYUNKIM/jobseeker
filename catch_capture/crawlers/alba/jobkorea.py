"""잡코리아 알바 — 통합검색에 고용형태 아르바이트(jobtype=7)를 걸고 컴퓨터 일 낱말로 찾는다.

외주 크롤러(crawl_freelance, jobtype=6 프리랜서)와 같은 길이다 — 검색 페이지(Next.js)가 목록 JSON 을
self.__next_f 스트림에 싣고, 그 해석기(_next_payload)를 그대로 빌려 쓴다. robots 는 `*` 에 /Search/ 를
막지 않는다(소셜 미리보기 봇만 막는다). AI 학습 수집기(ClaudeBot 등)는 통째로 막혀 있다 — 이 크롤러는
채용 크롤러와 같은 브라우저 UA 로 `*` 규칙을 따른다.

목록 줄에는 제목·마감(applicationPeriod.end)·급여(payRange·payTypeCode)가 있다. 근무지는 역 이름이 섞인
낱말 묶음이라, 1차 후보만 상세(/Recruit/GI_Read/<번호>)를 받아 JSON-LD 의 주소에서 시/도·시/군/구를 뗀다.
JSON-LD 의 baseSalary 는 금액이 만 배로 부풀어 있어(시급 10,320 → 103,200,000) 단위만 쓰고 금액은 목록 것을 쓴다.
마감 판정은 close_check.verdict_jobkorea(JSON-LD validThrough·'마감된 공고' 문구)를 그대로 쓴다.
검색 앞 몇 쪽만 보므로 '목록에서 사라짐'은 마감 신호로 쓰지 않는다.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
from datetime import date

from crawlers.alba.common import Gone, Source, ld_posting, pay_obj, split_region, today_kst

SEARCH = "https://www.jobkorea.co.kr/Search/"
VIEW_URL = "https://www.jobkorea.co.kr/Recruit/GI_Read/{}"
# 분류 규칙의 큰 갈래마다 한두 낱말. 검색어가 많을수록 요청이 는다 — 낱말당 최신 MAX_PAGES 쪽.
KEYWORDS = ("개발", "프로그래머", "웹디자인", "디자인", "영상편집", "포토샵", "홈페이지", "코딩", "엑셀",
            "데이터", "컴퓨터", "CAD", "3D", "쇼핑몰", "QA")
MAX_PAGES = 3
# payTypeCode → (단위, 만원 단위인가). 0 은 협의.
PAY_TYPE = {"5": ("시급", False), "4": ("일급", False), "3": ("주급", False), "2": ("월급", True), "1": ("연봉", True)}


def list_entry(r: dict) -> tuple[str, dict] | None:
    """검색 결과 한 줄 → (번호, entry). 아르바이트(고용형태 7)가 안 붙은 광고 줄은 None."""
    rid = str(r.get("id") or "")
    codes = [str(c) for c in r.get("employmentTypeCodeList") or []]
    if not rid or not any(c.split("/")[0] == "7" for c in codes):
        return None
    pay = r.get("payRange") or {}
    unit, manwon = PAY_TYPE.get(str(r.get("payTypeCode")), ("", False))
    amt = pay.get("start")
    try:
        amt = int(float(amt)) * (10000 if manwon else 1) if amt not in (None, "", "0") else None
    except ValueError:
        amt = None
    end = ((r.get("applicationPeriod") or {}).get("end") or "")[:10] or None
    return rid, {"url": VIEW_URL.format(rid), "title": (r.get("title") or "").strip(),
                 "content": (r.get("jobClassificationOrIndustry") or "").strip(","),
                 "pay": pay_obj(amt, unit) if unit else None, "deadline": end,
                 "posted_at": r.get("createdAt") or None, "sort": r.get("createdAt") or ""}


def parse_detail(html: str, today: date) -> dict:
    """상세 → 지역·고용 형태·마감 판정. 요약 칸의 나머지(제목·급여)는 목록 것을 쓴다."""
    from pipeline.close_check import verdict_jobkorea
    ld = ld_posting(html) or {}
    addr = ((ld.get("jobLocation") or {}).get("address") or {}) if isinstance(ld.get("jobLocation"), dict) else {}
    sido, sigungu = split_region(addr.get("streetAddress") or "")
    v = verdict_jobkorea(html, today)
    return {"title": (ld.get("title") or "").strip(), "sido": sido, "sigungu": sigungu,
            "employment": {"PART_TIME": "아르바이트", "CONTRACTOR": "계약직", "FULL_TIME": "정규직",
                           "INTERN": "인턴"}.get(str(ld.get("employmentType") or ""), ""),
            "posted_at": ld.get("datePosted") or None, "deadline": v.deadline,
            "verdict": v.status,
            "opt_out": False, "closed_reason": v.reason if v.status == "closed" else None}


class JobKorea(Source):
    name = "jobkorea"
    label = "잡코리아"
    new_limit = 150
    recheck_limit = 60

    def listing(self) -> dict[str, dict]:
        from crawlers.crawl_freelance import _next_payload
        out: dict[str, dict] = {}
        for kw in KEYWORDS:
            for page in range(1, MAX_PAGES + 1):
                q = urllib.parse.urlencode({"stext": kw, "jobtype": "7", "tabType": "recruit", "Page_No": page})
                obj = _next_payload(self.http.get(f"{SEARCH}?{q}", referer=SEARCH)[2])
                if not obj:
                    break
                for r in obj.get("content") or []:
                    ent = list_entry(r)
                    if ent:
                        out[ent[0]] = ent[1]
                if page >= (obj.get("totalPages") or page):
                    break
        self.complete = False
        return out

    def _fetch(self, pid: str) -> str:
        try:
            return self.http.get(VIEW_URL.format(pid), referer=SEARCH)[2]
        except urllib.error.HTTPError as ex:
            if ex.code in (404, 410):
                raise Gone(f"원본 삭제(HTTP {ex.code})") from None
            raise

    def detail(self, pid: str, e: dict) -> dict | None:
        d = parse_detail(self._fetch(pid), date.fromisoformat(today_kst()))
        d.pop("verdict", None)
        return {**d, "title": e.get("title") or d.get("title"), "content": e.get("content") or "",
                "pay": e.get("pay"), "deadline": d.get("deadline") or e.get("deadline"),
                "posted_at": d.get("posted_at") or e.get("posted_at"), "hours": ""}

    def recheck(self, p: dict) -> dict | None:
        d = parse_detail(self._fetch(p["pid"]), date.fromisoformat(today_kst()))
        if d["verdict"] == "unknown" and not d["title"]:
            return None
        return {"deadline": d["deadline"], "closed_reason": d["closed_reason"], "opt_out": False}
