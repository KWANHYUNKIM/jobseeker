"""합격자가 가진 것 ↔ 공고가 요구한 것 — 매칭.

두 겹이다.
1. 글쓴이가 밝힌 '그때 공고' — application.jd_requirements / jd_matching (예전 시기는 이것만 근거다).
2. 지금 공고와 대조 — 같은 회사·같은 직무의 공고(all_jobs_enriched)의 기술(tech_stack + 자격요건 본문)과
   역량(core.classifier.extract_competencies)을 합격자의 기술·역량과 견준다.
   공고 데이터는 수집을 시작한 뒤의 것뿐이라, 경험담의 시기가 다르면 'time_gap' 으로 표시한다.

기술 이름은 공고 쪽 사전(tech_stack 에 실제로 나온 이름)으로 맞춘다 — 같은 말로 세야 겹침이 보인다.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from careers import store
from core.classifier import classify_dev_roles, extract_competencies
from core.normalize import company as norm

ROLE_OK = {"백엔드", "프론트엔드", "풀스택", "iOS", "안드로이드", "데이터엔지니어", "데이터분석", "ML/AI", "DevOps/SRE",
           "보안", "게임", "임베디드", "QA"}
ROLE_BY_TECH = [("프론트엔드", {"React", "Vue", "Next.js", "Angular", "Svelte"}),
                ("안드로이드", {"Android", "Kotlin"}), ("iOS", {"iOS", "Swift", "Objective-C"}),
                ("ML/AI", {"PyTorch", "TensorFlow", "Scikit-learn"}),
                ("DevOps/SRE", {"Kubernetes", "Terraform"}),
                ("백엔드", {"Spring", "Spring Boot", "Django", "FastAPI", "Node.js", "NestJS", "JPA", "Go"})]
REQ_SHARE = 0.3          # 그 회사·직무 공고의 30% 이상이 요구하면 '요구 기술'로 본다
MIN_JOBS = 3             # 비교 공고가 이보다 적으면 맞춘 비율을 내지 않는다
ALIAS = {"springboot": "Spring Boot", "spring boot": "Spring Boot", "스프링부트": "Spring Boot", "스프링": "Spring",
         "react.js": "React", "reactjs": "React", "리액트": "React", "vue.js": "Vue", "vuejs": "Vue", "뷰": "Vue",
         "node": "Node.js", "nodejs": "Node.js", "노드": "Node.js", "k8s": "Kubernetes", "쿠버네티스": "Kubernetes",
         "js": "JavaScript", "자바스크립트": "JavaScript", "ts": "TypeScript", "타입스크립트": "TypeScript",
         "golang": "Go", "자바": "Java", "파이썬": "Python", "코틀린": "Kotlin", "도커": "Docker", "레디스": "Redis",
         "카프카": "Kafka", "nextjs": "Next.js", "next": "Next.js", "postgres": "PostgreSQL", "mariadb": "MySQL",
         "jpa": "JPA", "aws ec2": "AWS", "ec2": "AWS", "s3": "AWS", "rds": "AWS", "gcp": "GCP", "elastic search": "Elasticsearch",
         "es": "Elasticsearch", "rn": "React Native", "swiftui": "Swift", "objective-c": "Objective-C"}
_YEARS = re.compile(r"(\d+)\s*년")


def _vocab(jobs: list[dict]) -> dict[str, str]:
    v = {}
    for j in jobs:
        for t in j.get("tech_stack") or []:
            v[t.lower()] = t
    v.update({k: x for k, x in ALIAS.items()})
    return v


def _scan(text: str, vocab: dict[str, str]) -> set[str]:
    """본문에서 기술 이름 찾기 — 짧은 이름(Go·C·R…)은 오탐이 많아 본문에서는 찾지 않는다."""
    rx = _RX.get(id(vocab))
    if rx is None:                                  # 이름들을 정규식 하나로(긴 이름부터) — 2만 건 공고를 빨리 훑는다
        keys = sorted((k for k in vocab if len(k) >= 4), key=len, reverse=True)
        rx = _RX[id(vocab)] = re.compile(r"(?<![a-z0-9])(" + "|".join(map(re.escape, keys)) + r")(?![a-z0-9])")
    return {vocab[m] for m in rx.findall((text or "").lower())}


_RX: dict[int, re.Pattern] = {}


IMPLY = {"Spring Boot": "Spring", "Next.js": "React", "TypeScript": "JavaScript", "React Native": "React",
         "Nuxt.js": "Vue", "JPA": "Java", "Spring": "Java"}       # 앞을 쓰면 뒤도 가진 걸로 본다


def _imply(ts: set[str]) -> set[str]:
    out = set(ts)
    for _ in range(2):
        out |= {IMPLY[t] for t in out if t in IMPLY}
    return out


def _norm_techs(xs, vocab: dict[str, str]) -> set[str]:
    return _imply(_norm_techs0(xs, vocab))


def _norm_techs0(xs, vocab: dict[str, str]) -> set[str]:
    out = set()
    for x in xs or []:
        if not isinstance(x, str):
            continue
        k = x.strip().lower()
        if k in vocab:
            out.add(vocab[k])
        else:
            out |= _scan(x, vocab)
    return out


def _min_years(career: str) -> int | None:
    if not career:
        return None
    if "신입" in career and "경력" not in career:
        return 0
    m = _YEARS.search(career)
    return int(m.group(1)) if m else None


def story_side(r: dict, vocab: dict[str, str]) -> dict:
    a = r.get("application") or {}
    techs = _norm_techs(r.get("stack"), vocab)
    for p in a.get("portfolio_detail") or []:
        if isinstance(p, dict):
            techs |= _norm_techs(p.get("tech"), vocab)
    blob = " ".join([*(r.get("key_factors") or []), *(r.get("advice") or []), *(r.get("prep_methods") or []),
                     *[s.get("step", "") for s in r.get("path") or [] if isinstance(s, dict)],
                     *(a.get("portfolio_points") or []), *(a.get("resume_points") or []), *(a.get("portfolio_projects") or []),
                     *[str(p.get("problem") or "") + " " + str(p.get("solution") or "") for p in a.get("portfolio_detail") or [] if isinstance(p, dict)],
                     *[str(m.get("shown_by") or "") for m in a.get("jd_matching") or [] if isinstance(m, dict)]])
    comps = set(extract_competencies(blob))
    edu = (r.get("background") or {}).get("education") or ""
    if any(x in edu for x in ("4년제", "대학원")):
        comps.add("학사 이상")
    if "대학원" in edu:
        comps.add("석박사 우대")
    return {"techs": techs, "comps": comps}


class JobIndex:
    def __init__(self, jobs: list[dict]):
        self.vocab = _vocab(jobs)
        self.by: dict[tuple[str, str], list[dict]] = defaultdict(list)
        self.by_role: dict[str, list[dict]] = defaultdict(list)
        for j in jobs:
            req_text = str(j.get("qualifications") or "")
            pref_text = str(j.get("preferences") or "")
            rec = {"techs": _norm_techs(j.get("tech_stack"), self.vocab) | _scan(req_text + " " + pref_text, self.vocab),
                   "req_comps": set(extract_competencies(req_text)), "pref_comps": set(extract_competencies(pref_text)),
                   "min_years": _min_years(str(j.get("career") or "")), "title": j.get("title"), "url": j.get("url"),
                   "seen": (j.get("posted_date") or j.get("seen_first") or j.get("first_seen_at") or "")[:10]}
            roles = classify_dev_roles(j.get("title") or "", tech_stack=j.get("tech_stack") or [])
            for role in roles:
                self.by[(norm(j.get("company") or ""), role)].append(rec)
            if len(roles) == 1 and roles[0] != "기타":          # 시장 기준은 직무가 하나로 갈린 공고만(풀스택이 섞이면 흐려진다)
                self.by_role[roles[0]].append(rec)

    def demand(self, recs: list[dict]) -> dict:
        n = len(recs)
        t = Counter(x for r in recs for x in r["techs"])
        rc = Counter(x for r in recs for x in r["req_comps"])
        pc = Counter(x for r in recs for x in r["pref_comps"])
        yrs = sorted(r["min_years"] for r in recs if r["min_years"] is not None)
        return {"n": n, "techs": [[k, v, round(100 * v / n)] for k, v in t.most_common(15)],
                "req_comps": [[k, v, round(100 * v / n)] for k, v in rc.most_common(10)],
                "pref_comps": [[k, v, round(100 * v / n)] for k, v in pc.most_common(10)],
                "min_years": yrs, "seen": max((r["seen"] for r in recs), default=""),
                "seen_from": min((r["seen"] for r in recs if r["seen"]), default=""),
                "samples": [{"title": r["title"], "url": r["url"]} for r in recs[:5]]}

    @staticmethod
    def near(recs: list[dict], year: int | None) -> tuple[list[dict], int | None]:
        """경험담 해에 가장 가까운 해의 공고만 — 그 해 공고가 MIN_JOBS 보다 적으면 다음으로 가까운 해까지 넓힌다."""
        if not year:
            return recs, None
        by_y: dict[int, list] = defaultdict(list)
        for r in recs:
            if r["seen"][:4].isdigit():
                by_y[int(r["seen"][:4])].append(r)
        out, used = [], None
        for y in sorted(by_y, key=lambda y: (abs(y - year), y)):
            out += by_y[y]
            used = y if used is None else used
            if len(out) >= MIN_JOBS:
                break
        return (out or recs), used

    def pick(self, company: str | None, role: str | None) -> tuple[str, list[dict]]:
        """같은 회사·같은 직무 → 같은 회사 아무 개발 직무 → 시장 전체 같은 직무 순으로 비교 대상을 고른다."""
        k = norm(company or "")
        if k and role and self.by.get((k, role)):
            return "회사·직무", self.by[(k, role)]
        if k:
            same = [x for (c, _), v in self.by.items() if c == k for x in v]
            if same:
                return "회사", same
        if role and role != "기타" and self.by_role.get(role):
            return "시장 직무", self.by_role[role]
        return "", []


def match_story(r: dict, idx: JobIndex) -> dict | None:
    if r.get("kind") == "교육과정":
        return None
    role = r.get("role") if r.get("role") in ROLE_OK else None
    if not role:                                     # 직무를 안 밝힌 글 — 기술로 가늠한다
        ts = story_side(r, idx.vocab)["techs"]
        role = next((ro for ro, keys in ROLE_BY_TECH if ts & keys), None)
    scope, recs = idx.pick(r.get("company"), role)
    year = r.get("year") if isinstance(r.get("year"), int) else None
    recs, used_year = idx.near(recs, year)
    a = r.get("application") or {}
    reported = [x for x in (a.get("jd_requirements") or []) if isinstance(x, str)]
    shown = [m for m in (a.get("jd_matching") or []) if isinstance(m, dict) and m.get("requirement")]
    if not recs and not reported and not shown:
        return None
    me = story_side(r, idx.vocab)
    out = {"scope": scope, "reported": reported, "shown": shown}
    if recs:
        d = idx.demand(recs)
        need = {k for k, _, pct in d["techs"] if pct >= REQ_SHARE * 100}
        need_c = {k for k, _, pct in d["req_comps"] if pct >= REQ_SHARE * 100}
        have, have_c = me["techs"] & need, me["comps"] & need_c
        yrs = d["min_years"]
        thin = d["n"] < MIN_JOBS                 # 공고가 적으면 그 몇 건의 기술이 전부 '요구'가 된다 — 비율을 내지 않는다
        told = bool(me["techs"])                 # 글에 기술이 하나도 안 나오면 '없다'가 아니라 '안 썼다'
        out.update(
            thin=thin, told_tech=told,
            jobs=d["n"], jobs_seen=d["seen"],
            tech_need=sorted(need), tech_have=sorted(have), tech_missing=sorted(need - me["techs"]),
            tech_extra=sorted(me["techs"] - need)[:12],
            comp_need=sorted(need_c), comp_have=sorted(have_c), comp_missing=sorted(need_c - me["comps"]),
            coverage=(round(100 * len(have) / len(need)) if need and told and not thin else None),
            years_before=r.get("years_before"), job_min_years=yrs[len(yrs) // 2] if yrs else None,
            role_used=role, jobs_from=d["seen_from"],
            time_gap=(used_year - year) if (year and used_year) else None,
        )
    return out


def company_table(rs: list[dict], company: str, idx: JobIndex) -> dict | None:
    """회사 단위: 공고 요구율 vs 합격자 보유율 — 기술·역량 칸마다."""
    k = norm(company)
    recs = [x for (c, _), v in idx.by.items() if c == k for x in v]
    if not recs:
        return None
    d = idx.demand(recs)
    sides = [story_side(r, idx.vocab) for r in rs]
    with_t = [s for s in sides if s["techs"]]
    rows_t = [[t, pct, round(100 * sum(t in s["techs"] for s in with_t) / len(with_t)) if with_t else None] for t, _, pct in d["techs"]]
    rows_c = [[c, pct, round(100 * sum(c in s["comps"] for s in sides) / len(sides)) if sides else None] for c, _, pct in d["req_comps"]]
    return {"jobs": d["n"], "seen": d["seen"], "stories_with_tech": len(with_t), "stories": len(sides),
            "tech": rows_t, "comps": rows_c, "pref_comps": d["pref_comps"], "min_years": d["min_years"], "samples": d["samples"]}


def build_index() -> JobIndex:
    from careers import job_history
    return JobIndex(job_history.load())         # 쌓인 공고 이력 전부(git 판 + 회차마다 더한 것)
