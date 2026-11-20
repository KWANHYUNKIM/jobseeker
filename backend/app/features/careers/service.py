"""커리어 후기 API — 연도·회사·회사 유형으로 잘라 '누가 어떤 스펙으로 어디에 갔나'를 센다.

경험담(career_story)은 4천여 건이라 한 번 읽어 캐시하고, 거르기·세기는 여기서 한다.
표본이 MIN_N 건 미만인 칸은 비율을 내지 않는다(건수만) — careers/report.py 와 같은 규칙.
본문(career_post.body)은 열쇠(settings.careers_key)를 아는 요청에만 붙인다.
"""
from __future__ import annotations

import hmac
import re
from collections import Counter, defaultdict
from statistics import median

from app.core.config import settings
from app.core.exceptions import NotFound
from app.features.careers import repository
from app.utils.cache import cached

MIN_N = 3
UNKNOWN = "확인되지 않음"
FILTERS = ("year", "company", "type", "level", "kind", "role", "origin", "q")
YB_BANDS = [("1년 미만", 0, 1), ("1~3년", 1, 3), ("3~5년", 3, 5), ("5~10년", 5, 10), ("10년 이상", 10, 99)]


# ── 읽기 ───────────────────────────────────────────────────────────────

def _rows() -> list[dict]:
    return cached(("careers", "rows"), repository.stories)


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in ("", "null", "none", "없음", "모름", UNKNOWN.lower()))


def _strs(v) -> list[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if not isinstance(x, (dict, list)) and not _blank(x)]
    return [] if _blank(v) else [str(v).strip()]


def _d(r: dict, *keys):
    cur = r.get("data") or {}
    for k in keys:
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur


def _match(r: dict, f: dict) -> bool:
    if f.get("year") and str(r.get("year")) != str(f["year"]):
        return False
    if f.get("company") and r.get("company_key") != f["company"] and r.get("company") != f["company"]:
        return False
    for k, col in (("type", "company_type"), ("level", "level"), ("kind", "kind"), ("role", "role"), ("origin", "origin")):
        if f.get(k) and (r.get(col) or "") != f[k]:
            return False
    if f.get("q"):
        hay = " ".join(str(x) for x in (r.get("title"), r.get("company"), _d(r, "summary"), r.get("role"),
                                        " ".join(_strs(_d(r, "stack")))) if x)
        if f["q"].lower() not in hay.lower():
            return False
    return True


def _filtered(f: dict) -> list[dict]:
    f = {k: v for k, v in f.items() if v not in (None, "")}
    return [r for r in _rows() if _match(r, f)]


# ── 세기 ───────────────────────────────────────────────────────────────

def _top(c: Counter, n: int = 10) -> list[list]:
    return [[k, v] for k, v in c.most_common(n) if k]


def _share(c: Counter, total: int, n: int = 8) -> list[list]:
    if total < MIN_N:
        return _top(c, n)
    return [[k, v, round(100 * v / total)] for k, v in c.most_common(n) if k]


def _med(xs: list[float]) -> float | None:
    return round(median(xs), 1) if xs else None


_CERT_ALIAS = [(r"정처기|정보처리\s?기사", "정보처리기사"), (r"정보처리\s?산업기사", "정보처리산업기사"),
               (r"(?i)sqld", "SQLD"), (r"(?i)sqlp", "SQLP"), (r"(?i)adsp", "ADsP"), (r"(?i)aws.*saa|solutions?\s?architect", "AWS SAA"),
               (r"(?i)aws.*(clf|practitioner)", "AWS CLF"), (r"(?i)cka", "CKA"), (r"빅데이터\s?분석\s?기사", "빅데이터분석기사"),
               (r"정보보안\s?기사", "정보보안기사"), (r"리눅스\s?마스터\s?1", "리눅스마스터 1급"), (r"리눅스\s?마스터", "리눅스마스터 2급"),
               (r"네트워크\s?관리사", "네트워크관리사"), (r"(?i)topcit", "TOPCIT"), (r"한국사", "한국사능력검정")]
_LANG_ALIAS = [(r"(?i)(?:opic|오픽)\s*(AL|IH|IM\s?[1-3]?|IL)", lambda m: "OPIc " + m.group(1).replace(" ", "").upper()),
               (r"(?i)(?:토익\s?스피킹|toeic\s?speaking)\s*(\S+)?", lambda m: "토익스피킹" + (" " + m.group(1) if m.group(1) else "")),
               (r"(?i)(?:토익|toeic)\s*(\d{3})", lambda m: f"토익 {int(m.group(1)) // 50 * 50}점대"),
               (r"(?i)jlpt\s*(N[1-5])", lambda m: "JLPT " + m.group(1).upper())]


def _cert(x: str) -> str:
    for rx, name in _CERT_ALIAS:
        if re.search(rx, x):
            return name
    return x


def _lang(x: str) -> str:
    for rx, fn in _LANG_ALIAS:
        m = re.search(rx, x)
        if m:
            return fn(m)
    return x


_GPA = re.compile(r"(\d\.\d+)\s*(?:/\s*(4\.[035]|4|100))?")


def _gpa(s: str) -> float | None:
    """4.5 만점으로 맞춘 학점. 숫자가 없으면('3점 후반') None."""
    m = _GPA.search(s or "")
    if not m:
        return None
    v = float(m.group(1))
    scale = float(m.group(2)) if m.group(2) else 4.5
    if scale == 100 or v > 4.5:
        return None
    return round(v * 4.5 / scale, 2) if scale in (4.0, 4.3) else v if 1.5 <= v <= 4.5 else None


_TIER = [("백준 다이아·루비", r"다이아|루비|diamond|ruby"), ("백준 플래티넘", r"플래|플레|platinum"),
         ("백준 골드", r"골드|골\d|gold"), ("백준 실버", r"실버|silver"), ("백준 브론즈", r"브론즈|bronze"),
         ("프로그래머스 Lv3 이상", r"(?:lv|level|레벨|단계)\s*\.?\s*[3-5]|[3-5]\s*단계"),
         ("프로그래머스 Lv1~2", r"(?:lv|level|레벨)\s*\.?\s*[12]|[12]\s*단계"), ("리트코드", r"(?i)leetcode|리트코드"),
         ("SWEA", r"(?i)swea|sw\s?역량"), ("코딩테스트 준비", r"코테|코딩\s?테스트")]


def _tier(s: str) -> str | None:
    for name, rx in _TIER:
        if re.search(rx, s or "", re.I):
            return name
    return None


def _yb_band(y) -> str | None:
    if not isinstance(y, (int, float)):
        return None
    for name, lo, hi in YB_BANDS:
        if lo <= y < hi:
            return name
    return None


def _spec(rs: list[dict]) -> dict:
    """스펙 묶음 — 학력·학점·자격증·어학·대외활동·수상·인턴·알고리즘·나이·경력."""
    n = len(rs)
    spec = [(_d(r, "spec") or {}) for r in rs]
    with_spec = sum(1 for s in spec if any(_strs(v) for v in s.values()))
    gpas = [g for s in spec if (g := _gpa(str(s.get("gpa") or "")))]
    ages = [r["age"] for r in rs if isinstance(r.get("age"), int)]
    ybs = [r["years_before"] for r in rs if isinstance(r.get("years_before"), (int, float)) and r["years_before"] > 0]
    return {
        "n": n, "with_spec": with_spec,
        "levels": _share(Counter(r.get("level") for r in rs), n),
        "education": _share(Counter(r.get("education") or UNKNOWN for r in rs), n),
        "gpa": {"n": len(gpas), "median": _med(gpas),
                "bands": _top(Counter("4.0 이상" if g >= 4.0 else "3.5~4.0" if g >= 3.5 else "3.0~3.5" if g >= 3.0 else "3.0 미만"
                                      for g in gpas), 4)},
        "certs": _top(Counter(_cert(x) for s in spec for x in {*_strs(s.get("certs"))}), 12),
        "language": _top(Counter(_lang(x) for s in spec for x in _strs(s.get("language"))), 10),
        "activities": _top(Counter(x for s in spec for x in _strs(s.get("activities"))), 12),
        "awards": _top(Counter(x for s in spec for x in _strs(s.get("awards"))), 8),
        "internships": _top(Counter(x for s in spec for x in _strs(s.get("internships"))), 8),
        "algorithm": _top(Counter(t for s in spec if (t := _tier(str(s.get("algorithm") or "")))), 8),
        "age": {"n": len(ages), "median": _med(ages)},
        "years_before": {"n": len(ybs), "median": _med(ybs)},
        "stack": _top(Counter(x for r in rs for x in _strs(_d(r, "stack"))), 14),
        "programs": _top(Counter(r.get("program") for r in rs if r.get("program")), 8),
    }


def _brief(r: dict) -> dict:
    return {"id": r["id"], "title": r.get("title"), "source": r.get("source"), "year": r.get("year"),
            "kind": r.get("kind"), "company": r.get("company"), "company_type": r.get("company_type"),
            "role": r.get("role"), "level": r.get("level"), "years_before": r.get("years_before"),
            "origin": r.get("origin"), "education": r.get("education"), "summary": _d(r, "summary"),
            "steps": [s.get("step") for s in (_d(r, "path") or []) if isinstance(s, dict) and s.get("step")][:8]}


def _moves(rs: list[dict]) -> dict:
    """경력직 — 어디서(출발지 갈래) 어디로(회사 유형·회사) 몇 년 차에 갔나."""
    mv = [r for r in rs if r.get("origin")]
    n = len(mv)
    matrix = Counter((r["origin"], r.get("company_type") or "미분류") for r in mv)
    dest = Counter((r["company"], r.get("company_type")) for r in mv if r.get("company") and not r.get("program"))
    by_band: dict[str, Counter] = defaultdict(Counter)
    for r in mv:
        if (b := _yb_band(r.get("years_before"))):
            by_band[b][r.get("company_type") or "미분류"] += 1
    return {
        "n": n,
        "origins": _share(Counter(r["origin"] for r in mv), n, 14),
        "matrix": [{"origin": o, "type": t, "n": c} for (o, t), c in matrix.most_common()],
        "years": [{"band": b, "n": sum(by_band[b].values()), "types": _top(by_band[b], 6)} for b, _, _ in YB_BANDS],
        "destinations": [{"company": c, "type": t, "n": k} for (c, t), k in dest.most_common(30)],
        "transitions": _share(Counter(r.get("transition_cat") for r in rs if r.get("transition_cat")), len(rs), 10),
        "examples": [_brief(r) for r in mv if r.get("company") and len(_d(r, "path") or []) >= 2][:80],
    }


def _paths(rs: list[dict]) -> dict:
    """어떤 길로 왔나 — 경로 단계의 갈래·준비 방법·전형."""
    n = len(rs)
    pm = [m for r in rs if isinstance((m := _d(r, "prep_months")), (int, float)) and 0 < m < 120]
    return {
        "tags": _share(Counter(t for r in rs for t in (_d(r, "path_tags") or [])), n, 10),
        "prep": _top(Counter(x for r in rs for x in _strs(_d(r, "prep_methods"))), 12),
        "prep_months": {"n": len(pm), "median": _med(pm)},
        "interviews": _top(Counter(x for r in rs for x in _strs(_d(r, "selection", "interviews"))), 10),
        "coding_test": _top(Counter(x for r in rs for x in _strs(_d(r, "selection", "coding_test"))), 8),
    }


def _applied(rs: list[dict]) -> list[dict]:
    """같이 지원한 회사들 — 어디서 붙고 어느 단계에서 떨어졌나(other_companies)."""
    agg: dict[str, dict] = {}
    for r in rs:
        for o in _d(r, "other_companies") or []:
            co = o.get("company") if isinstance(o, dict) else None
            if _blank(co):
                continue
            res = str(o.get("result") or "")
            a = agg.setdefault(co.strip(), {"company": co.strip(), "pass": 0, "fail": 0, "stages": Counter()})
            if "불" in res or "탈락" in res:
                a["fail"] += 1
                if not _blank(o.get("stage")):
                    a["stages"][str(o["stage"])] += 1
            elif "합격" in res:
                a["pass"] += 1
    out = sorted(agg.values(), key=lambda a: -(a["pass"] + a["fail"]))[:40]
    return [a | {"stages": _top(a["stages"], 4)} for a in out]


def _voices(rs: list[dict], key: tuple[str, ...], n: int = 30) -> list[dict]:
    out = []
    for r in rs:
        for t in _strs(_d(r, *key)):
            out.append({"t": t, "id": r["id"], "company": r.get("company"), "year": r.get("year")})
            break                                       # 한 글에서 하나씩 — 한 사람 말이 칸을 채우지 않게
        if len(out) >= n:
            break
    return out


def _docs(rs: list[dict]) -> dict:
    ap = [(_d(r, "application") or {}) for r in rs]
    return {k: _top(Counter(x for a in ap for x in _strs(a.get(k))), 12)
            for k in ("resume_points", "portfolio_points", "portfolio_projects", "cover_letter_points", "cover_letter_questions")}


# ── 응답 ───────────────────────────────────────────────────────────────

def overview(f: dict) -> dict:
    key = tuple(f.get(k) for k in FILTERS)
    return cached(("careers", "overview", key), lambda: _overview(f))


def _overview(f: dict) -> dict:
    allrows = _rows()
    if not allrows:
        raise NotFound("커리어 후기가 아직 DB 에 없다(python -m store.ingest.careers)")
    rs = _filtered(f)
    n = len(rs)
    years = Counter(r.get("year") for r in rs if r.get("year"))
    by_year = []
    for y in sorted(years, reverse=True):
        yr = [r for r in rs if r.get("year") == y]
        by_year.append({"year": y, "kinds": _top(Counter(r.get("kind") for r in yr), 6),
                        "types": _top(Counter(r.get("company_type") for r in yr), 8)} | _spec(yr))
    by_type = []
    for t, c in Counter(r.get("company_type") for r in rs).most_common():
        tr = [r for r in rs if r.get("company_type") == t]
        by_type.append({"type": t, "companies": _top(Counter(r.get("company") for r in tr if r.get("company")), 10)}
                       | _spec(tr))
    cos = Counter((r["company_key"], r["company"], r.get("company_type")) for r in rs
                  if r.get("company_key") and not r.get("program"))
    progs = Counter((r["company_key"], r["program"]) for r in rs if r.get("program"))
    c = repository.counts()
    return {
        "updated_at": c.get("updated_at"), "total": {k: c.get(k) for k in ("posts", "stories", "counted")},
        "n": n, "filters": {k: f.get(k) for k in FILTERS if f.get(k)},
        "facets": {
            "years": sorted(([y, v] for y, v in Counter(r.get("year") for r in allrows if r.get("year")).items()), reverse=True),
            "types": _top(Counter(r.get("company_type") for r in allrows), 20),
            "levels": _top(Counter(r.get("level") for r in allrows), 10),
            "kinds": _top(Counter(r.get("kind") for r in allrows), 12),
            "roles": _top(Counter(r.get("role") for r in allrows), 16),
            "origins": _top(Counter(r.get("origin") for r in allrows if r.get("origin")), 16),
        },
        "companies": [{"key": k, "name": nm, "type": t, "n": v} for (k, nm, t), v in cos.most_common(80)],
        "programs": [{"key": k, "name": nm, "n": v} for (k, nm), v in progs.most_common(30)],
        "spec": _spec(rs),
        "by_year": by_year,
        "by_type": by_type,
        "moves": _moves(rs),
        "paths": _paths(rs),
        "applied": _applied(rs),
        "docs": _docs(rs),
        "voices": {"factors": _voices(rs, ("key_factors",)), "advice": _voices(rs, ("advice",)),
                   "questions": _voices(rs, ("selection", "notable_questions"))},
    }


def stories(f: dict, offset: int = 0, limit: int = 50) -> dict:
    rs = _filtered(f)
    return {"n": len(rs), "offset": offset, "items": [_brief(r) for r in rs[offset: offset + limit]]}


def _key_ok(key: str | None) -> bool:
    return bool(settings.careers_key) and bool(key) and hmac.compare_digest(settings.careers_key, key)


def story(post_id: str, key: str | None) -> dict:
    r = repository.story(post_id)
    if r is None:
        raise NotFound(f"후기 {post_id} 없음")
    ok = _key_ok(key)
    out = {k: v for k, v in r.items() if k not in ("body", "data")} | (r.get("data") or {})
    out["body"] = r.get("body") if ok else None
    out["body_locked"] = not ok
    out["body_chars"] = len(r.get("body") or "")
    return out


def roster() -> dict:
    return cached(("careers", "roster"), _roster)


def _n(x: dict) -> int:
    """명단 한 줄의 인원 — 모델이 글자('3명')로 적기도 한다."""
    m = re.search(r"\d+", str(x.get("count") or ""))
    return max(1, int(m.group())) if m else 1


def _year(v) -> int | None:
    m = re.search(r"(19|20)\d{2}", str(v or ""))
    return int(m.group()) if m else None


def _roster() -> dict:
    posts = [p for p in repository.roster() if p.get("it")]
    people = [x | {"year": _year(x.get("year"))} for p in posts for x in (p.get("rows") or []) if isinstance(x, dict)]
    orgs: dict[str, list] = defaultdict(list)
    for x in people:
        if not _blank(x.get("org")):
            orgs[x["org"]].append(x)

    def cnt(xs, k):
        c = Counter()
        for x in xs:
            if not _blank(x.get(k)):
                c[x[k]] += _n(x)
        return c

    def total(xs):
        return sum(_n(x) for x in xs)

    return {
        "posts": len(posts), "people": total(people),
        "years": sorted(([y, v] for y, v in cnt(people, "year").items()), reverse=True),
        "orgs": [{"org": o, "n": total(xs), "type": _top(cnt(xs, "org_type"), 1)[0][0] if cnt(xs, "org_type") else None,
                  "schools": _top(cnt(xs, "school"), 8), "majors": _top(cnt(xs, "major"), 6),
                  "cs": sum(_n(x) for x in xs if x.get("major_cs") is True),
                  "years": sorted(([y, v] for y, v in cnt(xs, "year").items()), reverse=True)}
                 for o, xs in sorted(orgs.items(), key=lambda kv: -total(kv[1]))[:60]],
        "schools": _top(cnt(people, "school"), 20),
    }
