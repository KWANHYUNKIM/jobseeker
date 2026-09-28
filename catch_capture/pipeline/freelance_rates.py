"""외주·프리 단가 분석 — 등급·유형·분야·직무로 나눠 본 월 단가.

프리랜서 몸값은 '중간값 하나'로 말할 수 없다. SI/SM 시장은 등급(초급·중급·고급·특급)으로
단가를 부르고, 같은 등급이어도 어떤 프로젝트냐(금융 차세대인지 공공 유지보수인지)에 따라
값이 갈린다. 여기서는 프로젝트마다 네 가지를 붙이고(classify), 월 단가를 그 축으로 나눠
센다(analyze). crawl_freelance 가 매 회차 부르고 결과는 freelance.json 의 analysis 에 실린다.

등급을 정하는 법
  · 표기 — 제목·경력·본문에 '고급' '중급' 같은 말이 있으면 그것(grade_basis='표기').
    여럿이 함께 적혀 있으면('중급고급', '초/중급') 한 등급으로 못 정하므로 '혼합'.
  · 경력 추정 — 표기가 없고 '경력 N년'이 있으면 연수로 가른다(grade_basis='경력 추정').
    초급 <3년, 중급 3~6년, 고급 7~9년, 특급 10년 이상. 시장에서 흔히 쓰는 구분이고
    공식 기준(KOSA 등급)은 학력·자격에 따라 달라 그대로 옮길 수 없다. 화면은 추정을 따로 센다.
  · 둘 다 없으면 None — 등급 분석에서 빠진다.

단가는 '올라올 때 값'(history 첫 줄)을 쓴다. 뒤에 내린 값은 따로(budget_moves) 센다.
월 단가만 비교한다 — 도급 총액은 기간이 제각각이라 같은 줄에 놓을 수 없다.
"""
from __future__ import annotations

import re
from collections import defaultdict

GRADES = ("초급", "중급", "고급", "특급")
GRADE_RE = re.compile(r"(특급|고급|중급|초급)")
# 범위('8~20년')는 하한을 읽는다 — '년' 바로 앞 숫자만 보면 20년이 되어 전부 특급이 됐다.
YEARS_RE = re.compile(r"(\d{1,2})\s*(?:[~\-]\s*(\d{1,2})\s*)?년")

# 순서가 우선순위다 — 앞에서 먼저 걸리는 것을 쓴다.
DOMAINS = [
    ("금융", r"은행|카드|증권|보험|생보|손보|캐피탈|금융|저축|자산운용|계정계|여신|수신|신탁|핀테크|[WMH]TS|농협|신한|국민|하나|우리|NH|KB"),
    ("공공", r"공단|공사(?!원)|정부|시청|구청|도청|공공|국토|국방|교육청|행정|조달|관리원|진흥원|연구원|청$|부처|지자체|한국\w{1,8}원"),
    ("통신", r"통신|SKT|\bKT\b|유플러스|LG\s?U\+"),
    ("제조", r"제조|공장|MES|SCM|SRM|ERP|SAP|화학|제철|반도체|자동차|건설기계|중공업|철강|PLM"),
    ("유통·커머스", r"커머스|쇼핑|유통|리테일|마트|물류|배송|이커머스|패션|의류"),
    ("의료", r"병원|의료|헬스|제약|EMR|바이오"),
    ("게임·미디어", r"게임|방송|미디어|OTT|콘텐츠|엔터"),
]
DOMAIN_RES = [(n, re.compile(p, re.IGNORECASE)) for n, p in DOMAINS]

ROLES = [
    ("PM·PL", r"\bPM\b|\bPL\b|PMO|프로젝트\s*관리|기획자|\bPO\b"),
    ("QA", r"\bQA\b|테스트|테스터"),
    ("디자인", r"디자인|디자이너|UI/?UX|Figma|퍼블리"),
    ("DBA·인프라", r"\bDBA\b|\bTA\b|\bAA\b|인프라|네트워크|서버\s*엔지니어|클라우드|AWS|Azure|DevOps|SRE|보안|OP\b|시스템\s*엔지니어|리눅스"),
    ("데이터·AI", r"데이터|\bDW\b|EDW|ETL|\bAI\b|머신러닝|딥러닝|\bML\b|LLM|RAG|분석가|빅데이터"),
    ("모바일", r"안드로이드|Android|iOS|모바일|Flutter|React\s*Native|리액트\s*네이티브|Kotlin|Swift"),
    ("프론트엔드", r"프론트|Front|React|Vue|리액트|Angular|웹스퀘어|WebSquare|Nexacro|넥사크로|JavaScript|TypeScript"),
    ("백엔드", r"백엔드|벡앤드|Back|서버|Java|자바|Spring|\.NET|C#|Node|Python|파이썬|Go\b|PHP|Proframe|계정계|C\+\+|\bC\b"),
]
ROLE_RES = [(n, re.compile(p, re.IGNORECASE)) for n, p in ROLES]

SM_RE = re.compile(r"\bSM\b|유지\s*보수|운영", re.IGNORECASE)
SI_RE = re.compile(r"\bSI\b|구축|차세대|고도화|개발\s*사업|신규\s*개발", re.IGNORECASE)


FLOOR_RE = re.compile(r"(초급|중급|고급)\s*(이상|가능|부터)")


def _grade(text: str, career: str) -> tuple[str | None, str | None]:
    # '초급이상' '초급 가능' 은 하한을 말할 뿐 이 자리의 등급이 아니다 — 지우고 센다.
    found = set(GRADE_RE.findall(FLOOR_RE.sub(" ", text)))
    if len(found) == 1:
        return found.pop(), "표기"
    if len(found) > 1:
        return "혼합", "표기"
    m = YEARS_RE.search(career or "")
    if m:
        y = int(m.group(1))
        top = int(m.group(2)) if m.group(2) else None
        # '1 ~ 20년' 은 사실상 경력 무관이다 — 하한만 보면 전부 초급이 된다.
        if top is not None and y <= 1 and top >= 10:
            return None, None
        if 0 < y <= 40:                     # '경력 100년↑' 같은 표기 사고는 버린다
            g = "초급" if y < 3 else "중급" if y < 7 else "고급" if y < 10 else "특급"
            return g, "경력 추정"
    return None, None


def classify(p: dict) -> dict:
    """프로젝트 하나에 grade·grade_basis·domain·work_type·role 을 단다(제자리 수정, 반환도 한다)."""
    title = p.get("title") or ""
    body = f"{title} {p.get('summary') or ''}"[:600]
    grade, basis = _grade(f"{title} {p.get('career') or ''} {(p.get('summary') or '')[:300]}", p.get("career") or "")
    domain = next((n for n, rx in DOMAIN_RES if rx.search(body)), "기타")
    work_type = "SM" if SM_RE.search(title) else "SI" if SI_RE.search(title) else None
    # 직무는 제목 → 원본의 직무 분류(원티드 긱스 '개발 > 자바 개발자') → 기술 순. 본문은 보지 않는다 —
    # 긴 상세에는 '리눅스 배포 경험' 같은 말이 섞여 서버 개발자가 인프라로 잡혔다.
    role = next((n for n, rx in ROLE_RES if rx.search(title)), None) \
        or next((n for n, rx in ROLE_RES if rx.search(p.get("role_hint") or "")), None) \
        or next((n for n, rx in ROLE_RES if rx.search(" ".join(p.get("skills") or []))), None)
    p.update({"grade": grade, "grade_basis": basis, "domain": domain, "work_type": work_type, "role": role})
    return p


# ── 분석 ──────────────────────────────────────────────────────────────

def _q(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    i = (len(xs) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def _stat(xs: list[float]) -> dict | None:
    if not xs:
        return None
    return {"n": len(xs), "p25": round(_q(xs, 0.25)), "median": round(_q(xs, 0.5)),
            "p75": round(_q(xs, 0.75)), "min": round(min(xs)), "max": round(max(xs))}


def _is_dev(p: dict) -> bool:
    """개발 프로젝트인가. 원티드 긱스·프리모아는 디자인·기획·마케팅 자리도 올린다 —
    섞으면 '고급 개발자 단가' 칸에 브랜드 디자인 프로젝트가 들어간다(실제로 들어갔다)."""
    cat = p.get("category") or ""
    return not cat or any(c.strip() == "개발" for c in cat.split(","))


def _first_monthly(p: dict) -> float | None:
    if not _is_dev(p):
        return None
    b = ((p.get("history") or [{}])[0].get("budget")) or p.get("budget")
    if not b or b.get("type") != "monthly":
        return None
    lo, hi = b.get("min"), b.get("max")
    v = ((lo or hi) + (hi or lo)) / 2 if (lo or hi) else None
    return v if v and 150 <= v <= 3000 else None


def _matrix(rows: list[tuple[str, str, float]], row_order: list[str]) -> list[dict]:
    """(행, 등급, 값) → [{key, total:{…}, grades:{등급: stat}}], 표본 많은 순."""
    cells: dict = defaultdict(lambda: defaultdict(list))
    for k, g, v in rows:
        cells[k][g].append(v)
        cells[k]["_all"].append(v)
    out = [{"key": k, "total": _stat(c["_all"]), "grades": {g: _stat(c[g]) for g in GRADES if c.get(g)}}
           for k, c in cells.items()]
    order = {k: i for i, k in enumerate(row_order)}
    out.sort(key=lambda r: (-r["total"]["n"], order.get(r["key"], 99)))
    return out


# ── 현재 단가표 · 월별 추이 · 일별 스냅숏 ──────────────────────────────
# '현재' = 최근 CURRENT_DAYS 안에 목록에서 본 자리. 마감된 것도 넣는다 — 단가는 올라올 때
# 정해지고 사람을 구했다고 바뀌지 않는다. 칸마다 그 숫자를 만든 프로젝트 id 를 같이 싣는다
# (화면이 '이 숫자의 근거'로 그대로 보여 준다 — 표와 근거가 따로 계산되면 어긋난다).
CURRENT_DAYS = 90
CURRENT_COLS = ("전체", "SI", "SM")


def _day(s: str | None) -> str:
    return (s or "")[:10]


def current_table(projects: list[dict], today: str) -> dict:
    from datetime import date, timedelta
    since = (date.fromisoformat(today) - timedelta(days=CURRENT_DAYS)).isoformat()
    cells: dict = {g: {c: [] for c in CURRENT_COLS} for g in GRADES}
    for p in projects:
        v = _first_monthly(p)
        if v is None or p.get("grade") not in GRADES or _day(p.get("last_seen_at")) < since:
            continue
        for c in ("전체", p.get("work_type")):
            if c in CURRENT_COLS:
                cells[p["grade"]][c].append((v, p["id"]))
    table = {}
    for g in GRADES:
        table[g] = {}
        for c in CURRENT_COLS:
            vs = cells[g][c]
            st = _stat([v for v, _ in vs])
            if st:
                st["ids"] = [i for _, i in sorted(vs)]
            table[g][c] = st
    return {"since": since, "until": today, "days": CURRENT_DAYS, "cols": list(CURRENT_COLS), "table": table}


def monthly(projects: list[dict], started_at: str) -> list[dict]:
    """월별 코호트 — 그 달에 올라온 자리의 '올라올 때 단가'. 첫 수집 날 한꺼번에 들어온
    것(등록일 없음)은 그 달에 올라온 게 아니라 이미 있던 자리라 뺀다."""
    months: dict = defaultdict(lambda: defaultdict(list))
    for p in projects:
        v = _first_monthly(p)
        if v is None or p.get("grade") not in GRADES:
            continue
        if not p.get("posted_date") and _day(p.get("first_seen_at")) == _day(started_at):
            continue
        m = (p.get("posted_date") or _day(p.get("first_seen_at")))[:7]
        if len(m) == 7:
            months[m][p["grade"]].append(v)
            months[m]["_all"].append(v)
    return [{"month": m, "n": len(v["_all"]), "grades": {g: _stat(v[g]) for g in GRADES if v.get(g)}}
            for m, v in sorted(months.items())]


def snapshot(cur: dict) -> dict:
    """그날의 현재 단가표 한 줄(id 는 빼고 숫자만). 크롤러가 날짜별로 한 줄씩 쌓는다."""
    return {"date": cur["until"],
            "cells": {g: {c: {k: s[k] for k in ("n", "p25", "median", "p75")}
                          for c, s in row.items() if s}
                      for g, row in cur["table"].items()}}


def analyze(projects: list[dict], started_at: str = "", today: str | None = None) -> dict:
    from datetime import date
    today = today or date.today().isoformat()
    data = []
    for p in projects:
        v = _first_monthly(p)
        if v is not None:
            data.append((classify(p), v))
    graded = [(p, v) for p, v in data if p["grade"] in GRADES]

    grades = {g: _stat([v for p, v in graded if p["grade"] == g]) for g in GRADES}
    grades_explicit = {g: _stat([v for p, v in graded if p["grade"] == g and p["grade_basis"] == "표기"])
                       for g in GRADES}
    by_type = _matrix([(p["work_type"], p["grade"], v) for p, v in graded if p["work_type"]], ["SI", "SM"])
    by_domain = _matrix([(p["domain"], p["grade"], v) for p, v in graded], [n for n, _ in DOMAINS] + ["기타"])
    by_role = _matrix([(p["role"], p["grade"], v) for p, v in graded if p["role"]], [n for n, _ in ROLES])
    by_mode = _matrix([({"onsite": "상주", "remote": "원격"}.get(p.get("kind"), "?"), p["grade"], v)
                       for p, v in graded], ["상주", "원격"])

    meta = {
        "monthly": len(data), "graded": len(graded),
        "explicit": sum(1 for p, _ in graded if p["grade_basis"] == "표기"),
        "inferred": sum(1 for p, _ in graded if p["grade_basis"] == "경력 추정"),
        "mixed": sum(1 for p, _ in data if p["grade"] == "혼합"),
        "ungraded": sum(1 for p, _ in data if p["grade"] is None),
        "sites": dict(sorted(((s, sum(1 for p, _ in data if p["site"] == s))
                              for s in {p["site"] for p, _ in data}), key=lambda x: -x[1])),
    }
    result = {"meta": meta, "grades": grades, "grades_explicit": grades_explicit,
              "by_type": by_type, "by_domain": by_domain, "by_role": by_role, "by_mode": by_mode,
              "current": current_table(projects, today), "monthly": monthly(projects, started_at)}
    result["insights"] = insights(result)
    return result


def _gap(row: dict, base: dict, g: str) -> int | None:
    a, b = (row["grades"].get(g) or {}), (base.get(g) or {})
    if a.get("n", 0) >= 3 and b.get("n", 0) >= 3:
        return a["median"] - b["median"]
    return None


def insights(a: dict) -> list[str]:
    """표에서 읽어 낼 말을 문장으로. 표본이 3건 미만인 칸은 말하지 않는다."""
    out: list[str] = []
    g = a["grades"]
    ladder = [(k, g[k]) for k in GRADES if g.get(k) and g[k]["n"] >= 3]
    if ladder:
        out.append("등급별 월 단가 중앙값은 " + " → ".join(f"{k} {s['median']:,}만원" for k, s in ladder)
                   + " 입니다.")
    if len(ladder) >= 2:
        steps = [f"{ladder[i][0]}→{ladder[i + 1][0]} +{ladder[i + 1][1]['median'] - ladder[i][1]['median']:,}만원"
                 for i in range(len(ladder) - 1)]
        out.append("등급이 한 칸 오를 때 중앙값 차이: " + ", ".join(steps) + ".")
    for k, s in ladder:
        spread = s["p75"] - s["p25"]
        if spread >= 150:
            out.append(f"{k}은 같은 등급 안에서도 편차가 큽니다 — 가운데 절반이 {s['p25']:,}~{s['p75']:,}만원"
                       f"({spread:,}만원 폭). 프로젝트 성격을 같이 봐야 합니다.")
    si = next((r for r in a["by_type"] if r["key"] == "SI"), None)
    sm = next((r for r in a["by_type"] if r["key"] == "SM"), None)
    if si and sm:
        for k in ("고급", "중급"):
            d = _gap(si, sm["grades"], k)
            if d is not None and abs(d) >= 30:
                out.append(f"{k} 기준 SI(구축)가 SM(운영)보다 월 {abs(d):,}만원 {'높습니다' if d > 0 else '낮습니다'}.")
    base = a["grades"]
    for row in a["by_domain"]:
        if row["key"] == "기타":
            continue
        for k in ("고급", "중급"):
            d = _gap(row, base, k)
            if d is not None and abs(d) >= 40:
                out.append(f"{row['key']} 분야 {k}은 전체 {k}보다 월 {abs(d):,}만원 "
                           f"{'높게' if d > 0 else '낮게'} 부릅니다(표본 {row['grades'][k]['n']}건).")
    top_roles = sorted((r for r in a["by_role"] if r["total"]["n"] >= 5),
                       key=lambda r: -r["total"]["median"])
    if len(top_roles) >= 2:
        hi, lo = top_roles[0], top_roles[-1]
        out.append(f"직무별로는 가장 높은 곳이 {hi['key']} {hi['total']['median']:,}만원, "
                   f"가장 낮은 곳이 {lo['key']} {lo['total']['median']:,}만원입니다(등급을 섞은 값).")
    m = a["meta"]
    out.append(f"월 단가가 있는 {m['monthly']:,}건 중 등급을 정한 것은 {m['graded']:,}건"
               f"(표기 {m['explicit']:,} · 경력 추정 {m['inferred']:,}), 혼합 표기 {m['mixed']:,}건과 "
               f"등급 모름 {m['ungraded']:,}건은 등급 표에서 뺐습니다.")
    return out
