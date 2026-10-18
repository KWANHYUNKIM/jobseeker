"""메인 화면 — 공고를 회사별로 묶고, 규모·업종으로 가르고, 신입·경력 구간으로 나눈다.

캐치 첫 화면처럼 '회사 카드 → 그 회사 공고' 순으로 본다. 공고 목록(`/api/jobs`)은 공고
하나가 한 줄이라 같은 회사의 공고 열 건이 열 줄을 차지한다 — 여기서는 회사 하나가 카드 한 장이다.
"""
from __future__ import annotations

import html
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from app.core.exceptions import NotFound
from app.features.home import repository
from app.features.home.industry import INDUSTRIES, classify
from app.utils.cache import cached

SIZES = ("대기업", "중견기업", "중소기업", "해외 기업")
# 주목순에서 큰 회사가 먼저. 해외 기업(OpenAI·SpaceX…)은 국내 규모 잣대가 안 맞아 따로 두되 중소보다 앞.
SIZE_RANK = {"대기업": 0, "중견기업": 1, "해외 기업": 2, "중소기업": 3}
OVERSEAS = "해외·원격"
EXP_BUCKETS = ("1-2년", "3-4년", "5-7년", "8년+")
ENTRY = "신입/무관"
CAREER_ORDER = (ENTRY,) + EXP_BUCKETS


_CORP = re.compile(r"^\s*(\(?(주|유|재|사)\)|주식회사|㈜)\s*|\s*(\(?(주|유|재|사)\)|주식회사|㈜)\s*$")


def display_name(name: str) -> str:
    """카드에 쓰는 이름 — '(주)', '주식회사' 를 뗀다. 영문 병기 '쿠팡 (Coupang)' 은 둔다."""
    n = html.unescape(name or "").strip()
    for _ in range(2):
        n = _CORP.sub("", n).strip()
    return n or (name or "")


# 같은 법인의 다른 표기(한글/영문 표기·옛 이름). 계열사·자회사는 법인이 달라 합치지 않는다
# (토스 ≠ 토스뱅크 ≠ 비바리퍼블리카 채용 브랜드라도 회사 카드는 나눈다 — 공고를 낸 법인이 다르다).
_ALIASES = {
    "당근마켓": "당근", "nhn": "엔에이치엔", "naver": "네이버", "navercloud": "네이버클라우드",
    "nhncloud": "엔에이치엔클라우드", "nhn클라우드": "엔에이치엔클라우드", "nhnpayco": "엔에이치엔페이코",
    "nhn페이코": "엔에이치엔페이코", "nhnlink": "엔에이치엔링크", "nhnace": "엔에이치엔에이스",
    "nhnkcp": "엔에이치엔케이씨피", "nhncommerce": "엔에이치엔커머스", "씨제이올리브영": "cj올리브영",
    "씨제이이엔엠": "cjenm", "cj포디플렉스": "cj4dplex", "신세계아이앤씨": "신세계ic",
    "컬리채용": "컬리", "naverwebtoon": "네이버웹툰", "naverlabs": "네이버랩스",
}


def company_key(name: str) -> str:
    """같은 회사 판정 키 — 법인 표기·괄호 병기·공백·기호를 뗀 소문자, 그리고 같은 법인의 다른 표기."""
    n = re.sub(r"\(.*?\)", "", display_name(name))
    k = re.sub(r"\W+", "", n).lower() or (name or "")
    return _ALIASES.get(k, k)


def _title(t: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(t or "")).strip()


# 바깥에서 긁어 온 로고 주소는 확인한 호스트의 https 만 내보낸다(수집기 crawl_logos.LOGO_HOSTS 와 같다).
LOGO_HOSTS = {"board.catch.co.kr", "cdn.jumpit.co.kr", "static.wanted.co.kr"}


def safe_logo(url: str | None) -> str | None:
    if not url or len(url) > 500:
        return None
    from urllib.parse import urlsplit
    try:
        u = urlsplit(url)
    except ValueError:
        return None
    return url if u.scheme == "https" and u.hostname in LOGO_HOSTS and not u.username else None


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _job(r: dict, industry: str) -> dict:
    return {
        "site": r["site"], "pid": r["pid"], "url": r["url"], "title": _title(r["title"]),
        "company": display_name(r["company"]), "company_slug": r["company_slug"], "logo": safe_logo(r["logo_url"]),
        "size": r["company_size"], "industry": industry,
        "career": r["career_text"], "career_bucket": r["career_bucket"],
        "region": r["region"], "district": r["district"],
        "dday": r["dday"], "deadline": _iso(r["effective_deadline"]),
        "first_seen_at": _iso(r["first_seen_at"]),
        "roles": [x for x in (r["roles"] or []) if x != "기타"], "stacks": (r["stacks"] or [])[:5],
    }


def _board() -> dict:
    """회사 묶음 전체. 1분 캐시 — 공고는 회차(1시간)마다 바뀐다."""
    rows = repository.active_it_rows()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    # 회사 id 가 아니라 이름으로 묶는다 — 같은 회사가 표기만 달리해 두 줄로 갈라져 있다
    # ('(주)스마일게이트' / '스마일게이트', '쿠팡' / '쿠팡 (Coupang)').
    by_co: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        r["company_id"] = company_key(r["company"])
        by_co[r["company_id"]].append(r)

    companies, jobs = [], []
    for cid, rs in by_co.items():
        rs.sort(key=lambda r: r["first_seen_at"], reverse=True)
        # 같은 공고가 사이트만 달리해 두 번 실린 것(쿠팡 채용페이지 + 사람인)을 하나로 — 새 것을 남긴다.
        # 회사 단위로 묶을 때 처음 드러나는 중복이라(job_dup 은 같은 사이트 안·같은 제목을 본다) 여기서 거른다.
        seen_t: set[str] = set()
        rs[:] = [r for r in rs if not (_tkey(r["title"]) in seen_t or seen_t.add(_tkey(r["title"])))]
        # 대표 표기·슬러그는 공고가 가장 많은 쪽
        top = Counter((r["company"], r["company_slug"], r["logo_url"]) for r in rs).most_common()
        name = display_name(top[0][0][0])
        slugs = list(dict.fromkeys(t[0][1] for t in top))
        logo = next((safe_logo(t[0][2]) for t in top if safe_logo(t[0][2])), None)
        industry = classify(name)
        size = Counter(r["company_size"] for r in rs if r["company_size"]).most_common(1)
        size = size[0][0] if size else "중소기업"
        # 해외 보드(Greenhouse·Ashby…)로 들어온 글로벌 회사는 직원 수를 모르니 규모 판정이 '중소'로
        # 떨어진다(OpenAI·SpaceX 가 중소기업이었다). 공고 절반 이상이 해외 근무면 '해외 기업' 으로 둔다.
        # 헤드헌팅 회사는 이름이 큰 회사 명단 앞부분에 걸려(라인서치 → '라인') 대기업으로 잡히곤 한다
        if industry == AGENCY:
            size = "중소기업"
        if size != "대기업" and sum(r["region"] == OVERSEAS for r in rs) * 2 >= len(rs):
            size = "해외 기업"
            # 해외 ATS 보드로 오는 회사는 거의 소프트웨어 회사다(이름 규칙에 안 걸린 것만)
            if industry == "기타":
                industry = "IT·소프트웨어"
        careers = Counter(r["career_bucket"] for r in rs)
        present = [b for b in CAREER_ORDER if careers.get(b)]
        ddays = [r["dday"] for r in rs if r["dday"] is not None and r["dday"] >= 0]
        roles = Counter(x for r in rs for x in (r["roles"] or []) if x != "기타")
        companies.append({
            "id": cid, "name": name, "slug": slugs[0], "slugs": slugs, "logo": logo,
            "size": size, "industry": industry,
            "active": len(rs),
            "entry": careers.get(ENTRY, 0),
            "experienced": sum(careers.get(b, 0) for b in EXP_BUCKETS),
            "career_from": present[0] if present else None,
            "career_to": present[-1] if present else None,
            "new_7d": sum(1 for r in rs if r["first_seen_at"] >= week_ago),
            "latest_at": _iso(rs[0]["first_seen_at"]),
            "soonest_dday": min(ddays) if ddays else None,
            "roles": [k for k, _ in roles.most_common(3)],
            "titles": [{"title": _title(r["title"]), "site": r["site"], "pid": r["pid"],
                        "career_bucket": r["career_bucket"], "dday": r["dday"]} for r in rs[:3]],
        })
        new_7d = companies[-1]["new_7d"]
        for r in rs:
            r["_size"], r["_industry"] = size, industry
            r["_score"] = _score(r, size, new_7d, industry)
            jobs.append(r)
    return {"companies": companies, "jobs": jobs, "by_slug": {c["slug"]: c for c in companies},
            "rows_by_co": by_co,
            "by_any_slug": {sl: c for c in companies for sl in c["slugs"]}, "generated_at": datetime.now().isoformat(timespec="seconds")}


# ── 인기 점수 ─────────────────────────────────────────────────────────
# 캐치의 '인기' 는 열람 수다. 우리 방문 기록은 아직 며칠치(열람 140건)라 그걸로 순위를 못 매긴다.
# 그래서 공고가 들고 있는 신호로 매긴다 — 회사 규모, 그 회사가 이번 주에 낸 공고 수(지금 많이
# 뽑는 중인가), 공고가 얼마나 새것인가, 마감이 가까운가. 화면에 이 기준을 그대로 적는다.
SIZE_WEIGHT = {"대기업": 30, "중견기업": 18, "해외 기업": 14, "중소기업": 4}


AGENCY = "채용대행·헤드헌팅"
AGENCY_PENALTY = 25


def _score(r: dict, size: str, co_new_7d: int, industry: str = "") -> float:
    age_days = (datetime.now(timezone.utc) - r["first_seen_at"]).total_seconds() / 86400
    fresh = max(0.0, 21 - age_days) * 1.2
    soon = 6 if r["dday"] is not None and 0 <= r["dday"] <= 7 else 0
    penalty = AGENCY_PENALTY if industry == AGENCY else 0
    return SIZE_WEIGHT.get(size, 4) + fresh + min(co_new_7d, 15) + soon - penalty


INTERN = re.compile(r"인턴|intern|교육생|아카데미|academy|부트캠프|채용연계|체험형|SSAFY|마에스트로|트레이니|trainee|견습", re.I)
TOP_N = 50
# 업종 구역의 제목 — 칩보다 길게 써도 되는 자리라 사람들이 부르는 말로
SECTION_TITLE = {"금융": "은행·금융", "IT·플랫폼": "IT 플랫폼", "IT·소프트웨어": "IT·소프트웨어",
                 "공공·기관": "공공기관·공기업"}


def _rank(rows: list[dict], n: int = TOP_N) -> list[dict]:
    """점수 순으로 n 건. 먼저 회사마다 가장 높은 한 건씩 줄 세우고, 자리가 남으면 두 번째 공고로
    채운다 — 같은 회사가 1·2위를 연달아 차지하면 순위가 아니라 그 회사 목록처럼 보인다."""
    ordered = sorted(rows, key=lambda r: r["_score"], reverse=True)
    out, per = [], Counter()
    for cap in (1, 2):
        for r in ordered:
            if per[r["company_id"]] >= cap or (cap == 2 and r.get("_taken")):
                continue
            if cap == 1 or not r.get("_taken"):
                per[r["company_id"]] += 1
                r["_taken"] = True
                out.append(_job(r, r["_industry"]))
            if len(out) >= n:
                break
        if len(out) >= n:
            break
    for r in ordered:
        r.pop("_taken", None)
    return out


def _sections() -> list[dict]:
    """아래로 내리며 보는 구역들 — 필터와 무관한 전체 기준. 구역마다 TOP 50."""
    b = cached(("home_board",), _board)
    jobs = b["jobs"]
    now = datetime.now(timezone.utc)
    today = [r for r in jobs if (now - r["first_seen_at"]).total_seconds() < 86400]
    today_title = "오늘 뜬"
    if len(today) < 10:                     # 크롤이 쉬었던 날 — 빈 구역보다 사흘치가 낫다
        today = [r for r in jobs if (now - r["first_seen_at"]).total_seconds() < 3 * 86400]
        today_title = "최근 사흘 새로 뜬"

    def sec(key, title, lead, rows):
        return {"key": key, "title": title, "lead": lead, "total": len(rows), "jobs": _rank(rows)}

    out = [
        sec("entry", "신입", "신입 인기", [r for r in jobs if r["career_bucket"] == ENTRY]),
        sec("experienced", "경력", "경력 인기", [r for r in jobs if r["career_bucket"] in EXP_BUCKETS]),
        sec("today", today_title, f"{today_title} 인기", today),
        sec("intern", "인턴·교육생", "인턴·교육생", [r for r in jobs if INTERN.search(r["title"] or "")]),
        sec("midsmall", "중견·중소", "중견·중소 인기",
            [r for r in jobs if r["_size"] in ("중견기업", "중소기업") and r["_industry"] != AGENCY]),
        sec("overseas", "해외 기업", "해외 기업 인기",
            [r for r in jobs if r["_size"] == "해외 기업" and r["_industry"] != AGENCY]),
    ]
    by_ind: dict[str, list[dict]] = defaultdict(list)
    for r in jobs:
        if r["_industry"] not in ("기타", AGENCY):
            by_ind[r["_industry"]].append(r)
    for ind, rows in sorted(by_ind.items(), key=lambda kv: -len(kv[1])):
        if len(rows) >= 5:
            t = SECTION_TITLE.get(ind, ind)
            out.append(sec(f"ind:{ind}", t, t, rows))
    return [x for x in out if x["total"]]


def _sort_key(sort: str):
    if sort == "new":
        return lambda c: (c["latest_at"] or "",)
    if sort == "count":
        return lambda c: (c["active"],)
    # 주목(기본): 큰 회사 먼저, 같은 규모면 공고가 많은 곳
    return lambda c: (-SIZE_RANK.get(c["size"], 9), c["active"], c["new_7d"])


def home(size: str = "", industry: str = "", sort: str = "popular", limit: int = 48, offset: int = 0) -> dict:
    b = cached(("home_board",), _board)
    cos = b["companies"]

    def ok(c, skip=""):
        return ((skip == "size" or not size or c["size"] == size) and
                (skip == "industry" or not industry or c["industry"] == industry))

    size_counts = Counter(c["size"] for c in cos if ok(c, "size"))
    ind_counts = Counter(c["industry"] for c in cos if ok(c, "industry"))
    picked = sorted((c for c in cos if ok(c)), key=_sort_key(sort), reverse=True)

    ids = {c["id"] for c in picked}
    jobs = [r for r in b["jobs"] if r["company_id"] in ids]
    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for r in jobs:
        by_bucket[r["career_bucket"]].append(r)

    # 첫 화면 로고 띠 — 필터와 무관하게 지금 공고가 많은 큰 회사들
    spotlight = sorted(cos, key=_sort_key("popular"), reverse=True)[:80]
    return {
        "generated_at": b["generated_at"],
        "spotlight": [{"name": c["name"], "slug": c["slug"], "logo": c["logo"], "size": c["size"],
                       "active": c["active"]} for c in spotlight],
        "totals": {"companies": len(picked), "jobs": len(jobs),
                   "entry": len(by_bucket[ENTRY]),
                   "experienced": sum(len(by_bucket[x]) for x in EXP_BUCKETS)},
        "facets": {
            "sizes": [{"name": s, "n": size_counts.get(s, 0)} for s in SIZES],
            "industries": [{"name": i, "n": ind_counts[i]} for i in INDUSTRIES if ind_counts.get(i)],
        },
        "companies": [{k: v for k, v in c.items() if k not in ("id", "slugs")} for c in picked[offset:offset + limit]],
        # 구역마다 앞 10건만 싣는다(첫 화면 무게). 더보기는 /api/home/section/{key} 가 50건.
        "sections": [{**x, "jobs": x["jobs"][:10]} for x in cached(("home_sections",), _sections)],
    }


def section(key: str) -> dict:
    for x in cached(("home_sections",), _sections):
        if x["key"] == key:
            return x
    raise NotFound(f"구역 {key} 이(가) 없습니다")


def _tkey(title: str) -> str:
    return re.sub(r"\W+", "", _title(title).lower())[:20]


def _dedupe(jobs: list[dict]) -> list[dict]:
    """같은 공고가 사이트만 달리해 두 번 실린 것을 하나로 — 먼저 온(새) 것을 남긴다."""
    seen, out = set(), []
    for j in jobs:
        key = _tkey(j["title"])
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def company(slug: str) -> dict:
    b = cached(("home_board",), _board)
    c = b["by_any_slug"].get(slug)
    if not c:
        raise NotFound(f"모집중인 IT 공고가 있는 회사 중에 {slug} 가 없습니다")
    rows = b["rows_by_co"][c["id"]]
    careers = Counter(r["career_bucket"] for r in rows)
    return {
        "company": {k: v for k, v in c.items() if k not in ("id", "slugs")},
        "careers": [{"bucket": x, "n": careers.get(x, 0)} for x in CAREER_ORDER + ("정보없음",) if careers.get(x)],
        "jobs": _dedupe([_job(r, c["industry"]) for r in rows]),
    }
