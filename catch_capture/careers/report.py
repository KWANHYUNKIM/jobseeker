"""paths.jsonl → 집계(report.json) + 혼자 보는 보고서(report.html).

  python -m careers.report

표본이 3건 미만인 칸은 '비율'을 내지 않는다(건수만). 회사는 core.normalize 로 공고 데이터의 회사와 잇는다.
gaps 는 루프 에이전트가 다음 검색어를 고르는 데 쓴다(공고는 많은데 후기가 없는 회사, 얇은 직무·전환).
"""
from __future__ import annotations

import html
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from careers import checks, store
from careers.checks import UNKNOWN
from core.normalize import company as norm

MIN_N = 3
STEP_TAGS = [
    ("부트캠프·교육과정", r"부트캠프|국비|KDT|SSAFY|싸피|우테코|우아한테크코스|부스트캠프|42|소마|마에스트로|교육"),
    ("인턴", r"인턴"), ("SI·SM", r"\bSI\b|\bSM\b|SI\s|에스아이|파견"), ("스타트업", r"스타트업"),
    ("대기업·빅테크", r"대기업|네이버|카카오|라인|쿠팡|배민|우아한|토스|삼성|LG|SK|현대"),
    ("대학원", r"대학원|석사|박사"), ("독학", r"독학|혼자"), ("병역특례·군", r"병역|산업기능|전문연|군"),
    ("비개발 직장", r"비개발|영업|디자이너|공무원|마케팅|회계|교사|간호"), ("전공 졸업", r"졸업|학부|전공"),
]


_CLUB = re.compile(r"에이블스쿨|CEOS|YAPP|DND|SOPT|넥스터즈|디프만|SSAFY|싸피|우테코|부스트캠프|42\s?서울|마에스트로|멋쟁이사자|멋사|GDSC|항해99|코드스테이츠|이어드림|동아리|부트캠프|KDT|국비|아카데미|교육")
# 회사가 아닌 곳 — 교육과정·부트캠프·동아리·학교. 버리지 않고 '교육과정' 칸에 따로 모은다(선발 후기도 쓸모가 있다).
_PROGRAM = re.compile(r"(?i)aivle|에이블\s?스쿨|bootcamp|academy|아카데미|사관학교|테크\s?캠퍼스|테크\s?캠프|멀티캠퍼스|패스트\s?캠퍼스|"
                      r"data\s?school|화이트햇|구름톤|멋쟁이\s?사자|kusitms|큐시즘|경영학회|\bUMC\b|해커톤|새싹|sesac|softeer|aimers|"
                      r"트랙|과정|프로그램|학회")
_SCHOOL = re.compile(r"대학교|대학원|고등학교|마이스터고|사이버대학|대학$")
_EDU_CO = {norm(x) for x in ("엘리스", "위코드", "멀티캠퍼스", "패스트캠퍼스", "코드스테이츠", "제로베이스", "이어드림")}
_EDU_TITLE = re.compile(r"트랙|\d+\s?기|수료|부트캠프|과정|교육생|선발")   # 교육 회사는 '그 과정 합격' 글일 때만 교육과정(직원으로 간 글은 회사)
_PROG_ALIAS = [(r"(?i)aivle|에이블\s?스쿨", "KT 에이블스쿨"), (r"(?i)apple developer academy", "Apple Developer Academy"),
               (r"엘리스", "엘리스 트랙"), (r"구름톤", "구름톤"), (r"멋쟁이\s?사자|멋사", "멋쟁이사자처럼"),
               (r"(?i)kusitms|큐시즘|한국대학생\s?IT\s?경영학회", "KUSITMS"), (r"화이트햇", "화이트햇 스쿨"),
               (r"패스트\s?캠퍼스", "패스트캠퍼스"), (r"SSAFY|싸피", "SSAFY"), (r"우테코|우아한테크코스", "우아한테크코스"),
               (r"부스트캠프", "부스트캠프"), (r"정글", "크래프톤 정글"), (r"카카오\s?테크\s?캠퍼스", "카카오테크캠퍼스"),
               (r"소프트웨어\s?마에스트로|소마", "소프트웨어 마에스트로"), (r"(?i)data\s?school", "MS Data School")]


def _program(r: dict) -> str | None:
    """이 경험담이 회사가 아니라 교육과정·동아리·학교 이야기면 그 이름(같은 곳은 한 이름으로), 아니면 None."""
    co = (r.get("company") or "").strip()
    bc = str((r.get("background") or {}).get("bootcamp") or "").strip()
    if bc.lower() in ("null", "none", "없음", "모름", UNKNOWN):     # 로컬 모델이 빈칸을 글자로 적어 둔 것
        bc = ""
    name = None
    if co:
        if _CLUB.search(co) or _PROGRAM.search(co) or _SCHOOL.search(co):
            name = co
        elif norm(co) in _EDU_CO and _EDU_TITLE.search(r.get("title") or ""):
            name = co
        elif r.get("kind") == "교육과정":
            name = co
    elif r.get("kind") == "교육과정":
        name = bc or "과정 이름 모름"
    if not name:
        return None
    for pat, canon in _PROG_ALIAS:
        if re.search(pat, name):
            return canon
    return name


_TRANS = [("비개발→개발", r"비개발|비전공|문과|인문|영업|디자이너|공무원|교사|간호|마케팅|반도체|공정|생산|군인|서비스직|→\s*개발"),
          ("SI→서비스", r"SI|SM|에이전시|외주"), ("스타트업→대기업", r"스타트업\s*→\s*(대기업|빅테크|네카라)"),
          ("대기업→스타트업", r"(대기업|빅테크)\s*→\s*스타트업"), ("직무 전환(개발 안에서)", r"(프론트|백엔드|앱|iOS|안드로이드|데이터|QA|퍼블리셔)\S*\s*→"),
          ("국내→해외", r"해외|미국|일본|캐나다|독일|싱가포르|유럽"), ("학생→개발", r"학생|졸업|취준"), ("공백기 후 재취업", r"공백|권고사직|퇴사|휴직|경력\s*단절")]


def _transition(t: str) -> str:
    t = t.strip()
    if not t or t in ("없음", "null", "None"):
        return ""
    for name, rx in _TRANS:
        if re.search(rx, t):
            return name
    return "그 밖의 전환"


def _tags(step: str) -> list[str]:
    return [t for t, rx in STEP_TAGS if re.search(rx, step or "")]


def _top(c: Counter, n: int = 8) -> list[list]:
    return [[k, v] for k, v in c.most_common(n) if k]


def _share(c: Counter, total: int, n: int = 6) -> list[list]:
    if total < MIN_N:
        return _top(c, n)
    return [[k, v, round(100 * v / total)] for k, v in c.most_common(n) if k]


def _clean(r: dict) -> dict:
    """모델이 가끔 모양을 틀리게 낸다(path 를 문자열 목록으로, spec 을 문자열로) — 읽을 때 맞춘다."""
    r["path"] = [s if isinstance(s, dict) else {"step": str(s)} for s in (r.get("path") or []) if s]
    for k in ("background", "spec", "selection"):
        if not isinstance(r.get(k), dict):
            r[k] = {}
    for k in ("stack", "prep_methods", "key_factors", "advice", "other_companies"):
        v = r.get(k)
        r[k] = [str(x) for x in v if x and not isinstance(x, (dict, list))] if isinstance(v, list) else ([v] if isinstance(v, str) and v else [])
    if r.get("company") is not None and not isinstance(r["company"], str):
        r["company"] = None
    return r


def _edu(r: dict) -> str:
    """학력 — 원문에 근거가 없어 지운 값(null)은 '확인되지 않음'."""
    v = (r.get("background") or {}).get("education")
    return UNKNOWN if checks.blank(v) else v


def _src(rs: list[dict], pick, n: int) -> list[dict]:
    """글에서 뽑은 문장마다 원문 주소를 같이 단다 — {t, url, title}."""
    out = []
    for r in rs:
        for x in pick(r) or []:
            if x and isinstance(x, (str, int)):
                out.append({"t": str(x), "url": r.get("url"), "title": r.get("title")})
                if len(out) >= n:
                    return out
    return out


def _story(r: dict, match: bool = True) -> dict:
    return {"kind": r.get("kind"), "year": r.get("year"), "period": r.get("period"), "role": r.get("role"), "level": r.get("level"),
            "summary": r.get("summary"), "url": r.get("url"), "title": r.get("title"), "source": r.get("source"),
            "company": r.get("company"), "education": _edu(r), "transition": r.get("transition"),
            "years_before": r.get("years_before"), "age": r.get("age"), "match": r.get("match") if match else None}


def _lst(a: dict, k: str) -> list[str]:
    v = (a or {}).get(k)
    return [str(x) for x in v if x and isinstance(x, (str, int))] if isinstance(v, list) else []


def _val(a: dict, k: str) -> str | None:
    v = (a or {}).get(k)
    return v if isinstance(v, str) and v.strip() and v.strip().lower() not in ("null", "none", "없음") else None


def _docs(rs: list[dict]) -> dict:
    """서류(이력서·포트폴리오·자소서)를 어떻게 짰나 — 집계."""
    ap = [r.get("application") or {} for r in rs]
    with_docs = [a for a in ap if any(_val(a, k) or _lst(a, k) for k in
                                      ("resume", "portfolio", "resume_points", "portfolio_points", "cover_letter_points"))]
    return {
        "n": len(with_docs),
        "resume": _top(Counter(_val(a, "resume") for a in ap), 10),
        "portfolio": _top(Counter(_val(a, "portfolio") for a in ap), 10),
        "resume_points": _top(Counter(x for a in ap for x in _lst(a, "resume_points")), 15),
        "portfolio_points": _top(Counter(x for a in ap for x in _lst(a, "portfolio_points")), 15),
        "portfolio_projects": _top(Counter(x for a in ap for x in _lst(a, "portfolio_projects")), 12),
        "cover_letter_points": _top(Counter(x for a in ap for x in _lst(a, "cover_letter_points")), 15),
        "cover_letter_questions": _top(Counter(x for a in ap for x in _lst(a, "cover_letter_questions")), 15),
        "doc_results": [x for a in ap if (x := _val(a, "doc_result"))][:30],
    }


def _doc_examples(rows: list[dict]) -> list[dict]:
    """서류 이야기가 있는 경험담 — 최근 것부터. 화면의 '서류' 탭이 읽는다."""
    out = []
    for r in rows:
        a = r.get("application") or {}
        pts = _lst(a, "resume_points") + _lst(a, "portfolio_points") + _lst(a, "cover_letter_points")
        if not (pts or _val(a, "portfolio") or _val(a, "resume")):
            continue
        out.append({"year": r.get("year"), "period": r.get("period"), "level": r.get("level"), "role": r.get("role"),
                    "company": r.get("company"), "kind": r.get("kind"), "years_before": r.get("years_before"),
                    "resume": _val(a, "resume"), "portfolio": _val(a, "portfolio"),
                    "resume_points": _lst(a, "resume_points"), "portfolio_points": _lst(a, "portfolio_points"),
                    "portfolio_projects": _lst(a, "portfolio_projects"),
                    "cover_letter_points": _lst(a, "cover_letter_points"),
                    "cover_letter_questions": _lst(a, "cover_letter_questions"),
                    "doc_result": _val(a, "doc_result"), "url": r.get("url"), "title": r.get("title")})
    out.sort(key=lambda x: -(x["year"] if isinstance(x.get("year"), int) else 0))
    return out[:400]


def _matching(rows: list[dict]) -> dict:
    """직무별: 합격자가 지금 공고 요구를 얼마나 채웠나, 자주 빠진 것, 글쓴이가 밝힌 그때 공고 요구."""
    by_role: dict[str, list] = defaultdict(list)
    for r in rows:
        if r.get("match"):
            by_role[r["match"].get("role_used") or r.get("role") or "기타"].append(r)
    out = []
    for role, rs in sorted(by_role.items(), key=lambda kv: -len(kv[1])):
        ms = [r["match"] for r in rs]
        solid = [m for m in ms if m.get("told_tech") and not m.get("thin")]     # 빠진 것은 기술을 밝힌 글·공고 3건 이상만 센다
        cov = [m["coverage"] for m in ms if m.get("coverage") is not None]
        out.append({
            "role": role, "n": len(rs),
            "coverage_median": sorted(cov)[len(cov) // 2] if cov else None, "coverage_n": len(cov), "solid": len(solid),
            "missing_tech": _top(Counter(t for m in solid for t in m.get("tech_missing") or []), 10),
            "missing_comp": _top(Counter(t for m in solid for t in m.get("comp_missing") or []), 8),
            "had_tech": _top(Counter(t for m in solid for t in m.get("tech_have") or []), 10),
            "extra_tech": _top(Counter(t for m in solid for t in m.get("tech_extra") or []), 10),
            "reported": _top(Counter(x for m in ms for x in m.get("reported") or []), 15),
            "shown": [{"requirement": s.get("requirement"), "shown_by": s.get("shown_by")} for m in ms for s in m.get("shown") or []][:30],
            "examples": [{"year": r.get("year"), "period": r.get("period"), "company": r.get("company"), "level": r.get("level"),
                          "years_before": r.get("years_before"), "title": r.get("title"), "url": r.get("url"), "match": r["match"]}
                         for r in sorted(rs, key=lambda r: -(r["year"] if isinstance(r.get("year"), int) else 0))[:60]],
        })
    return {"roles": out, "note": "지금 공고 = 수집을 시작한 뒤 본 공고. 경험담 시기와 다르면 time_gap(년)으로 표시."}


def _ages(rows: list[dict]) -> dict:
    """합격 당시 나이 — 글쓴이가 밝힌 것만. 무엇과 같이 갈리나(신입·경력·학력·전환·직무·회사)."""
    from careers import age as ag
    rs = [r for r in rows if r.get("age")]

    def by(key, min_n=3):
        g = defaultdict(list)
        for r in rs:
            k = key(r)
            if k:
                g[k].append(r["age"])
        return sorted(([k, ag.stats(v)] for k, v in g.items() if len(v) >= min_n), key=lambda kv: -kv[1]["n"])

    late = [r for r in rs if r["age"] >= 30 and r.get("level") in ("신입", "인턴")]
    return {"all": ag.stats([r["age"] for r in rs]), "of": len(rows),
            "level": by(lambda r: r.get("level")), "kind": by(lambda r: r.get("kind")),
            "education": by(_edu),
            "bootcamp": by(lambda r: "부트캠프·교육과정 거침" if (r.get("background") or {}).get("bootcamp") else "안 거침/모름"),
            "prior": by(lambda r: "개발 전 다른 일" if (r.get("background") or {}).get("prior_non_dev_career") else None, 1),
            "role": by(lambda r: r.get("role")),
            "company": by(lambda r: r.get("company") if r.get("kind") != "교육과정" else None, 2),
            "late_entry": [{"age": r["age"], "company": r.get("company"), "role": r.get("role"), "year": r.get("year"),
                            "education": _edu(r),
                            "prior": (r.get("background") or {}).get("prior_non_dev_career"),
                            "bootcamp": (r.get("background") or {}).get("bootcamp"),
                            "summary": r.get("summary"), "url": r.get("url")} for r in sorted(late, key=lambda r: -r["age"])][:80]}


def _roster() -> dict | None:
    try:
        from careers import roster
        return roster.summary()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def build() -> dict:
    from careers.extract import read_apps
    apps = read_apps()
    raw = {r["id"]: r for r in store.raw_items() if r.get("id")}
    rows = []
    for r in store.read_paths():                     # 읽을 때마다 원문으로 다시 본다 — 예전에 뽑은 줄도 같은 규칙을 받는다
        if not r.get("is_story"):
            continue
        b = raw.get(r["id"]) or {}
        text = f"{b.get('title') or r.get('title') or ''}\n{b.get('body') or ''}"
        if b and not checks.is_it_item(r.get("source") or b.get("source"), text):             # IT 이야기가 아닌 글(체대입시 명단 등)은 빼고 센다
            continue
        rows.append(checks.check_background(_clean(r), text) if b else _clean(r))
    for r in rows:                                   # 나중에 덧붙인 서류 항목(application.jsonl)을 합친다
        if not isinstance(r.get("application"), dict) or not any(r["application"].values()):
            r["application"] = apps.get(r["id"]) if isinstance(apps.get(r["id"]), dict) else {}
    jobs = store.load_json(store.JOBS, [])
    open_by = Counter(norm(j.get("company", "")) for j in jobs if j.get("status") in (None, "active", "모집중", "open"))
    names = {norm(c): c for c in store.companies()}

    from careers import age as ag
    ages = ag.read_ages()
    for r in rows:
        r["age"] = ag.of(r, ages)

    from careers import match as mt
    idx = mt.build_index()
    for r in rows:
        try:
            r["match"] = mt.match_story(r, idx)
        except Exception:  # noqa: BLE001 — 한 건 모양이 이상해도 보고서는 만든다
            r["match"] = None

    by_co: dict[str, list] = defaultdict(list)
    by_prog: dict[str, list] = defaultdict(list)
    for r in rows:
        prog = _program(r)
        if prog:
            by_prog[prog].append(r)
        elif r.get("company") and r.get("kind") != "교육과정":
            by_co[norm(r["company"])].append(r)

    def profile(rs: list[dict]) -> dict:
        rs = sorted(rs, key=lambda r: -(r["year"] if isinstance(r.get("year"), int) else 0))   # 최근 일부터
        n = len(rs)
        bg = Counter(_edu(r) for r in rs)
        return {
            "n": n,
            "kinds": _top(Counter(r.get("kind") for r in rs)),
            "years": sorted(([str(k), v] for k, v in Counter(r.get("year") for r in rs).items() if k), reverse=True),
            "recent": sum(1 for r in rs if isinstance(r.get("year"), int) and r["year"] >= 2025),
            "spec_gpa": [r["spec"]["gpa"] for r in rs if (r.get("spec") or {}).get("gpa")][:30],
            "spec_lang": _top(Counter(x for r in rs for x in ((r.get("spec") or {}).get("language") or [])), 10),
            "spec_certs": _top(Counter(x for r in rs for x in ((r.get("spec") or {}).get("certs") or [])), 10),
            "spec_acts": _top(Counter(x for r in rs for x in ((r.get("spec") or {}).get("activities") or [])), 10),
            "spec_algo": [r["spec"]["algorithm"] for r in rs if (r.get("spec") or {}).get("algorithm")][:20],
            "roles": _share(Counter(r.get("role") for r in rs), n),
            "levels": _share(Counter(r.get("level") for r in rs), n),
            "education": _share(bg, n),
            "years_before": sorted(r["years_before"] for r in rs if isinstance(r.get("years_before"), (int, float))),
            "stack": _top(Counter(s for r in rs for s in (r.get("stack") or [])), 12),
            "prep": _top(Counter(s for r in rs for s in (r.get("prep_methods") or [])), 10),
            "path_tags": _share(Counter(t for r in rs for t in {t for s in (r.get("path") or []) for t in _tags(s.get("step", ""))}), n, 10),
            "interviews": _top(Counter(s for r in rs for s in ((r.get("selection") or {}).get("interviews") or [])), 8),
            "questions": _src(rs, lambda r: (r.get("selection") or {}).get("notable_questions"), 30),
            "factors": _src(rs, lambda r: r.get("key_factors"), 40),
            "advice": _src(rs, lambda r: r.get("advice"), 30),
            "docs": _docs(rs),
            "age": ag.stats([r["age"] for r in rs if r.get("age")]),
            "stories": [_story(r) for r in rs],
        }

    gh = {k: v for k, v in store.load_json(store.DIR / "github_orgs.json", {}).items() if v.get("verified")}
    companies = []
    for k in set(by_co) | set(gh):
        rs = by_co.get(k, [])
        p = profile(rs) if rs else {"n": 0, "stories": []}
        p.update(company=names.get(k) or (rs[0]["company"] if rs else gh[k]["company"]), norm=k,
                 open_jobs=open_by.get(k, 0), github=gh.get(k), match=mt.company_table(rs, names.get(k) or k, idx) if rs else None)
        companies.append(p)
    companies.sort(key=lambda p: (-p["n"], -bool(p.get("github")), -p["open_jobs"]))
    programs = sorted((profile(rs) | {"company": k, "norm": k, "open_jobs": 0, "github": None, "match": None}
                       for k, rs in by_prog.items()), key=lambda p: -p["n"])

    trans = defaultdict(list)
    for r in rows:
        t = _transition(r.get("transition") or "")
        if t and t not in ("없음", "null"):
            trans[t].append(r)
    transitions = sorted(({"transition": t, **profile(rs)} for t, rs in trans.items()), key=lambda x: -x["n"])

    edu = defaultdict(list)
    for r in rows:
        edu[_edu(r)].append(r)
    backgrounds = []
    for e, rs in sorted(edu.items(), key=lambda kv: -len(kv[1])):
        backgrounds.append({"education": e, "n": len(rs), "companies": _top(Counter(r.get("company") for r in rs), 12),
                            "roles": _share(Counter(r.get("role") for r in rs), len(rs)),
                            "path_tags": _share(Counter(t for r in rs for t in {t for s in (r.get("path") or []) for t in _tags(s.get("step", ""))}), len(rs), 10),
                            "stories": [_story(r, False) for r in sorted(rs, key=lambda r: -(r["year"] if isinstance(r.get("year"), int) else 0))]})

    market = defaultdict(list)
    for r in rows:
        if r.get("market_note"):
            market[r.get("year") or UNKNOWN].append({"t": r["market_note"], "url": r.get("url"), "title": r.get("title")})

    have = set(by_co)
    gaps = {
        "companies_without_stories": [names[k] for k, n in open_by.most_common() if k in names and k not in have][:80],
        "thin_roles": [k for k, v in Counter(r.get("role") for r in rows).items() if v < 10],
    }
    rep = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw": len(list(store.RAW.glob("*.json"))), "extracted": len(store.read_paths()), "stories": len(rows),
        "overall": profile(rows) | {"stories": [_story(r, False) for r in sorted(rows, key=lambda r: -(r["year"] if isinstance(r.get("year"), int) else 0))]},   # 경험담 전부(원문 주소) — '전체 경험담' 이 읽는다
        "companies": companies, "programs": programs, "transitions": transitions, "backgrounds": backgrounds,
        "market_by_year": {str(k): v for k, v in sorted(market.items(), key=lambda kv: str(kv[0]))},
        "gaps": gaps,
        "documents": _doc_examples(rows),
        "matching": _matching(rows),
        "ages": _ages(rows),
        "roster": _roster(),
    }
    store.save_json(store.REPORT_JSON, rep)
    store.REPORT_HTML.write_text(_html(rep), encoding="utf-8")
    print(f"보고서: 경험담 {len(rows)} · 회사 {len(companies)} · 교육과정 {len(programs)} · 전환 {len(transitions)} → {store.REPORT_HTML}")
    return rep


def _chips(items) -> str:
    out = []
    for it in items or []:
        label = html.escape(str(it[0]))
        val = f"{it[1]}" + (f" · {it[2]}%" if len(it) > 2 else "")
        out.append(f'<span class="chip">{label} <b>{val}</b></span>')
    return "".join(out) or '<span class="muted">—</span>'


def _link(url, label="원문") -> str:
    return f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{label}</a>' if url else '<span class="muted">원문 없음</span>'


def _list(xs, n=8) -> str:
    """문장 목록 — {t, url} 이면 문장 끝에 원문 링크를 단다."""
    out = []
    for x in (xs or [])[:n]:
        if isinstance(x, dict):
            out.append(f"<li>{html.escape(str(x.get('t') or ''))} {_link(x.get('url'))}</li>")
        else:
            out.append(f"<li>{html.escape(str(x))}</li>")
    return "".join(out) or '<li class="muted">—</li>'


def _stories(ss, n=None) -> str:
    e = html.escape
    rows = []
    for s in (ss or [])[:n]:
        tags = " · ".join(str(v) for v in (s.get("year") or s.get("period") or "시기 " + UNKNOWN, s.get("kind"), s.get("company"),
                                            s.get("role"), s.get("level"), "학력 " + (s.get("education") or UNKNOWN)) if v)
        rows.append(f'<li data-q="{e((s.get("title") or "") + " " + (s.get("company") or "") + " " + (s.get("summary") or ""))}">'
                    f'<span class="tag">{e(tags)}</span> {e(s.get("summary") or s.get("title") or "")} {_link(s.get("url"))}</li>')
    return f'<ul class="stories">{"".join(rows)}</ul>' if rows else '<p class="muted">—</p>'


def _html(rep: dict) -> str:
    e = html.escape
    co = []
    for p in rep["companies"]:
        g = p.get("github")
        gh_html = ""
        if g:
            repos = "".join(f'<li><a href="{e(r["url"] or "#")}" target="_blank" rel="noopener">{e(r["name"])}</a> <span class="tag">{e(r.get("lang") or "")} ★{r["stars"]} · {e(r["pushed"])}</span> {e(r["desc"])}</li>' for r in g["top_repos"][:6])
            gh_html = f'''<h4>GitHub <a href="{e(g["url"])}" target="_blank" rel="noopener">{e(g["login"])}</a> · 공개 저장소 {g["public_repos"]} · 최근 1년 활동 {g["active_12m"]}</h4>{_chips(g["languages"])}<div>{_chips(g["topics"][:10])}</div><ul>{repos}</ul>'''
        if not p.get("n"):
            co.append(f"<details><summary><b>{e(p['company'])}</b> <span class='muted'>경험담 0 · 모집중 공고 {p['open_jobs']} · GitHub</span></summary>{gh_html}</details>")
            continue
        co.append(f"""<details><summary><b>{e(p['company'])}</b> <span class="muted">경험담 {p['n']} · 모집중 공고 {p['open_jobs']}</span></summary>
<div class="grid"><div><h4>직무</h4>{_chips(p['roles'])}<h4>단계</h4>{_chips(p['levels'])}<h4>학력</h4>{_chips(p['education'])}</div>
<div><h4>거쳐 온 길</h4>{_chips(p['path_tags'])}<h4>기술</h4>{_chips(p['stack'])}<h4>준비</h4>{_chips(p['prep'])}</div>
<div><h4>합격·탈락 이유로 꼽은 것</h4><ul>{_list(p['factors'])}</ul><h4>면접에서 나온 것</h4><ul>{_list(p['questions'])}</ul><h4>조언</h4><ul>{_list(p['advice'])}</ul></div></div>
{gh_html}<h4>경험담 {p['n']}건 — 전부 원문으로</h4>{_stories(p['stories'])}</details>""")
    tr = "".join(f"<details><summary><b>{e(t['transition'])}</b> <span class='muted'>{t['n']}건</span></summary><h4>거쳐 온 길</h4>{_chips(t['path_tags'])}<h4>학력</h4>{_chips(t['education'])}<h4>준비</h4>{_chips(t['prep'])}<h4>꼽은 이유</h4><ul>{_list(t['factors'])}</ul><h4>조언</h4><ul>{_list(t['advice'])}</ul><h4>경험담 {t['n']}건</h4>{_stories(t['stories'])}</details>" for t in rep["transitions"][:40])
    bg = "".join(f"<details><summary><b>{e(b['education'])}</b> <span class='muted'>{b['n']}건</span></summary><div class='grid'><div><h4>거쳐 온 길</h4>{_chips(b['path_tags'])}</div><div><h4>간 회사</h4>{_chips(b['companies'])}</div></div><h4>경험담 {b['n']}건</h4>{_stories(b.get('stories'))}</details>" for b in rep["backgrounds"])
    mk = "".join(f"<details><summary><b>{e(y)}</b> <span class='muted'>{len(v)}건</span></summary><ul>{_list(v, 200)}</ul></details>" for y, v in rep["market_by_year"].items())
    o = rep["overall"]
    return f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>커리어 경로</title>
<style>:root{{--bg:#f6f7f9;--fg:#1d2233;--muted:#6b7285;--card:#fff;--line:#e3e6ec;--acc:#f45757}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12141a;--fg:#e8eaf0;--muted:#9aa1b3;--card:#1b1e26;--line:#2c303b}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.6 system-ui,"Noto Sans KR",sans-serif;margin:0;padding:24px max(16px,4vw)}}
h1{{margin:0 0 4px}}h2{{margin:28px 0 10px}}h4{{margin:10px 0 4px;font-size:12px;color:var(--muted)}}
details{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:8px 0}}summary{{cursor:pointer}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}.muted{{color:var(--muted)}}
.chip{{display:inline-block;border:1px solid var(--line);border-radius:99px;padding:1px 9px;margin:2px;font-size:12px}}.chip b{{color:var(--acc)}}
.tag{{font-size:12px;color:var(--muted)}}ul{{margin:4px 0;padding-left:18px}}.stories li{{margin:3px 0}}
input[type=search]{{width:100%;max-width:480px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font:inherit}}
a{{color:var(--acc)}}</style>
<h1>커리어 경로</h1><p class="muted">모은 글 {rep['raw']} · 추출 {rep['extracted']} · 경험담 {rep['stories']} · {e(rep['generated_at'])} · 표본 3건 미만은 비율 없이 건수만<br>
학력·전환은 원문에 근거 낱말이 있을 때만 셉니다. 근거가 없으면 '{UNKNOWN}'. 모든 문장·경험담 옆 '원문'을 누르면 그 글로 갑니다.</p>
<h2>전체</h2><div class="grid"><div><h4>직무</h4>{_chips(o['roles'])}</div><div><h4>학력</h4>{_chips(o['education'])}</div><div><h4>거쳐 온 길</h4>{_chips(o['path_tags'])}</div><div><h4>준비 방법</h4>{_chips(o['prep'])}</div></div>
<h2>전체 경험담 {len(o['stories'])}건</h2><details open><summary>검색해서 원문 찾기</summary><input type="search" id="q" placeholder="회사·제목·요약으로 찾기" aria-label="경험담 검색"><p class="muted" id="qn"></p><div id="all">{_stories(o['stories'])}</div></details>
<h2>회사별</h2>{''.join(co)}
<h2>교육과정·동아리·학교 (회사가 아닌 곳)</h2>{''.join(f"<details><summary><b>{e(p['company'])}</b> <span class='muted'>{p['n']}건</span></summary><h4>꼽은 이유</h4><ul>{_list(p['factors'])}</ul><h4>면접·선발에서 나온 것</h4><ul>{_list(p['questions'])}</ul>{_stories(p['stories'])}</details>" for p in rep.get('programs', []))}
<h2>커리어 전환</h2>{tr}
<h2>배경별로 어디에 갔나</h2>{bg}
<h2>그때 시장 (글쓴이가 묘사한 것)</h2>{mk or '<p class="muted">아직 없다</p>'}
<h2>빈칸 (다음 수집 대상)</h2><p class="muted">공고는 있는데 후기가 없는 회사: {e(', '.join(rep['gaps']['companies_without_stories'][:40]))}</p>
<script>
const items=[...document.querySelectorAll('#all li')],q=document.getElementById('q'),qn=document.getElementById('qn');
q.oninput=()=>{{const s=q.value.trim().toLowerCase();let n=0;for(const li of items){{const ok=!s||li.dataset.q.toLowerCase().includes(s);li.hidden=!ok;n+=ok}}qn.textContent=s?n+'건':''}};
</script>"""


if __name__ == "__main__":
    build()
