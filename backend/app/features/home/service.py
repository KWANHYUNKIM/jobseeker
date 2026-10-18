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

SIZES = ("대기업", "중견기업", "중소기업")
SIZE_RANK = {s: i for i, s in enumerate(SIZES)}
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


def company_key(name: str) -> str:
    """같은 회사 판정 키 — 법인 표기·괄호 병기·공백·기호를 뗀 소문자."""
    n = re.sub(r"\(.*?\)", "", display_name(name))
    return re.sub(r"\W+", "", n).lower() or (name or "")


def _title(t: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(t or "")).strip()


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _job(r: dict, industry: str) -> dict:
    return {
        "site": r["site"], "pid": r["pid"], "url": r["url"], "title": _title(r["title"]),
        "company": display_name(r["company"]), "company_slug": r["company_slug"], "logo": r["logo_url"],
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
        # 대표 표기·슬러그는 공고가 가장 많은 쪽
        top = Counter((r["company"], r["company_slug"], r["logo_url"]) for r in rs).most_common()
        name = display_name(top[0][0][0])
        slugs = list(dict.fromkeys(t[0][1] for t in top))
        logo = next((t[0][2] for t in top if t[0][2]), None)
        industry = classify(name)
        size = Counter(r["company_size"] for r in rs if r["company_size"]).most_common(1)
        size = size[0][0] if size else "중소기업"
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
        for r in rs:
            r["_size"], r["_industry"] = size, industry
            jobs.append(r)
    return {"companies": companies, "jobs": jobs, "by_slug": {c["slug"]: c for c in companies},
            "rows_by_co": by_co,
            "by_any_slug": {sl: c for c in companies for sl in c["slugs"]}, "generated_at": datetime.now().isoformat(timespec="seconds")}


def _sort_key(sort: str):
    if sort == "new":
        return lambda c: (c["latest_at"] or "",)
    if sort == "count":
        return lambda c: (c["active"],)
    # 주목(기본): 큰 회사 먼저, 같은 규모면 공고가 많은 곳
    return lambda c: (-SIZE_RANK.get(c["size"], 9), c["active"], c["new_7d"])


def _pick(rows: list[dict], n: int) -> list[dict]:
    """큰 회사·새 공고 순으로 n 건 — 한 회사가 목록을 다 차지하지 않게 회사당 2건까지."""
    rows = sorted(rows, key=lambda r: (SIZE_RANK.get(r["_size"], 9), -r["first_seen_at"].timestamp()))
    out, per, seen = [], Counter(), set()
    for r in rows:
        key = (r["company_id"], re.sub(r"\W+", "", _title(r["title"]).lower())[:20])
        if per[r["company_id"]] >= 2 or key in seen:    # 같은 공고가 사이트만 달리해 두 번 오는 것도 거른다
            continue
        seen.add(key)
        per[r["company_id"]] += 1
        out.append(_job(r, r["_industry"]))
        if len(out) >= n:
            break
    return out


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

    return {
        "generated_at": b["generated_at"],
        "totals": {"companies": len(picked), "jobs": len(jobs),
                   "entry": len(by_bucket[ENTRY]),
                   "experienced": sum(len(by_bucket[x]) for x in EXP_BUCKETS)},
        "facets": {
            "sizes": [{"name": s, "n": size_counts.get(s, 0)} for s in SIZES],
            "industries": [{"name": i, "n": ind_counts[i]} for i in INDUSTRIES if ind_counts.get(i)],
        },
        "companies": [{k: v for k, v in c.items() if k not in ("id", "slugs")} for c in picked[offset:offset + limit]],
        "entry": _pick(by_bucket[ENTRY], 12),
        "experienced": [{"bucket": x, "n": len(by_bucket[x]), "jobs": _pick(by_bucket[x], 8)}
                        for x in EXP_BUCKETS],
    }


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
        "jobs": [_job(r, c["industry"]) for r in rows],
    }
