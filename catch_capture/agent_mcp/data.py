"""에이전트용 MCP 서버의 데이터 계층 — 뷰어가 이미 서빙하는 산출물을 읽기만 한다.

원본(전부 jd-viewer/public/ 아래, 크롤·엔진이 만든다)
  all_jobs_enriched.json   공고         → 필요한 칸만 남겨 메모리에 든다(본문은 잘라 둔다)
  guide/                   취업 브리핑   (guide-engine)
  reveng/                  기술 역설계   (engine)
  company_stacks.json      기업 기술스택
  freelance.json           외주·프리 프로젝트와 단가 분석
공고 검색은 semantic.db 의 하이브리드 검색(FTS+벡터)을 먼저 쓰고, 색인이나 Ollama 가 없으면
제목·회사·기술 키워드 검색으로 물러선다.

재배포 원칙: 공고 원문은 원 사이트의 것이다. 여기서는 **우리가 만든 것**(브리핑·역설계·단가 통계·
기술 태그)을 온전히 주고, 공고 본문은 칸마다 앞부분만 잘라 원문 링크와 함께 준다.
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
PUBLIC = ROOT / "jd-viewer" / "public"
SITE_URL = os.environ.get("AGENT_SITE_URL", "http://localhost:5173").rstrip("/")

SECTION_MAX = 400      # 공고 칸(주요업무·자격요건·우대) 하나당 글자 — 원문은 링크로
JOB_FIELDS = ("site", "pid", "company", "title", "url", "career", "location", "tech_stack",
              "status", "deadline_date", "posted_date", "company_size")
TEXT_FIELDS = ("main_tasks", "qualifications", "preferences")

_lock = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}


def _load(name: str, build=None):
    """파일을 읽어 두고 수정 시각이 바뀌면 다시 읽는다. build 가 있으면 가공한 결과를 캐시한다."""
    path = PUBLIC / name
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    with _lock:
        hit = _cache.get(name)
        if hit and hit[0] == mtime:
            return hit[1]
    raw = json.loads(path.read_text(encoding="utf-8"))
    value = build(raw) if build else raw
    with _lock:
        _cache[name] = (mtime, value)
    return value


def norm(name: str | None) -> str:
    """회사 이름 비교용 — (주)·㈜·주식회사·공백·대소문자를 걷어 낸다."""
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|\(재\)|\s+", "", name or "")
    return s.lower()


def job_key(j: dict) -> str:
    return f"{j['site']}-{j['pid']}"


# ── 공고 ──────────────────────────────────────────────────────────────

def _slim_jobs(raw: list[dict]) -> dict:
    """10만 줄짜리 원본에서 필요한 칸만 — 본문(full_jd)은 버리고 세 칸만 잘라 둔다."""
    by_key: dict[str, dict] = {}
    by_url: dict[str, str] = {}
    for j in raw:
        if not j.get("site") or not j.get("pid"):
            continue
        s = {k: j.get(k) for k in JOB_FIELDS}
        for k in TEXT_FIELDS:
            t = (j.get(k) or "").strip()
            s[k] = t[:SECTION_MAX] + ("…" if len(t) > SECTION_MAX else "")
        s["id"] = job_key(j)
        s["_hay"] = " ".join([j.get("company") or "", j.get("title") or "", " ".join(j.get("tech_stack") or []),
                              s["main_tasks"], s["qualifications"]]).lower()
        by_key[s["id"]] = s
        if j.get("url"):
            by_url[j["url"]] = s["id"]
    return {"by_key": by_key, "by_url": by_url}


def jobs() -> dict:
    return _load("all_jobs_enriched.json", _slim_jobs) or {"by_key": {}, "by_url": {}}


def job_card(s: dict, *, full: bool = False) -> dict:
    out = {k: s.get(k) for k in ("id", "company", "title", "career", "location", "tech_stack",
                                 "status", "deadline_date", "posted_date", "company_size", "url")}
    out["viewer_url"] = f"{SITE_URL}/jobs/{s['id']}"
    if full:
        out.update({k: s.get(k) for k in TEXT_FIELDS})
    return out


def _semantic(query: str, limit: int) -> list[str] | None:
    """semantic.db 하이브리드 검색 → 공고 id 목록. 색인·Ollama 가 없으면 None."""
    try:
        from semantic import db as sdb, search as ssearch
        conn = sdb.connect()
        try:
            out = ssearch.search(conn, query, kind="job", limit=limit * 3)
        finally:
            conn.close()
    except Exception:                                                # noqa: BLE001
        return None
    by_url = jobs()["by_url"]
    ids = [by_url.get(r.get("url")) for r in out.get("results") or []]
    return [i for i in ids if i]


def _neg(iso: str) -> str:
    """날짜 문자열을 내림차순 정렬용으로 뒤집는다('2026-09-28' → 큰 날짜가 앞)."""
    return "".join(chr(0x7f - ord(c)) for c in iso)


def search_jobs(query: str, *, limit: int = 10, open_only: bool = True,
                location: str = "", career: str = "") -> dict:
    everything = jobs()["by_key"]

    def keep(s: dict) -> bool:
        if open_only and s.get("status") == "closed":
            return False
        if location and location not in (s.get("location") or ""):
            return False
        return not career or career in (s.get("career") or "")

    # 거르기를 먼저 한다 — 뒤에서 거르면 '전부 맞는 3건'이 다 마감이라 0건이 되는 일이 생겼다.
    data = {k: s for k, s in everything.items() if keep(s)}
    q = (query or "").strip()
    engine = "semantic"
    ids = [i for i in (_semantic(q, limit) or []) if i in data] if q else None
    if not ids:                     # 색인이 없거나 비었거나(Ollama 꺼짐 등) 결과가 없으면 키워드로
        engine = "keyword"
        toks = [t for t in q.lower().split() if t]
        hits = {k: sum(t in s["_hay"] for t in toks) for k, s in data.items()} if toks else {}
        need = len(toks)
        # 에이전트는 문장으로 묻는다('재택 되는 React'). 전부 맞는 것이 모자라면 절반 이상 맞는 것으로 채운다.
        ids = [k for k, n in hits.items() if n == need] if toks else list(data)
        if toks and len(ids) < limit and need > 1:
            ids += [k for k, n in hits.items() if need / 2 <= n < need]

        # 많이 맞은 것 → 회사명 → 제목 → 본문 순(뷰어 검색과 같은 규칙), 같은 자리끼리는 최근 등록 먼저.
        def rank(k: str) -> tuple:
            s = data[k]
            co, ti = norm(s["company"]), (s["title"] or "").lower()
            where = 0 if any(t in co for t in toks) else 1 if any(t in ti for t in toks) else 2
            return (-hits.get(k, 0), where, "" if s.get("posted_date") else "1", _neg(s.get("posted_date") or ""))
        ids.sort(key=rank)
    out = [job_card(data[k]) for k in ids[:limit] if k in data]
    return {"engine": engine, "count": len(out), "jobs": out}


def get_job(job_id: str) -> dict | None:
    s = jobs()["by_key"].get(job_id)
    return job_card(s, full=True) if s else None


# ── 회사 ──────────────────────────────────────────────────────────────

def _find(items: list[dict], company: str, keys=("name", "name_en", "norm")) -> dict | None:
    n = norm(company)
    for it in items:
        names = [it.get(k) for k in keys] + list(it.get("aliases") or [])
        if any(norm(x) == n for x in names if x):
            return it
    for it in items:                                              # 한쪽이 다른 쪽을 품는 경우
        names = [it.get(k) for k in keys] + list(it.get("aliases") or [])
        if any(n and norm(x) and (n in norm(x) or norm(x) in n) for x in names if x):
            return it
    return None


def company_brief(company: str) -> dict | None:
    """취업 브리핑 — 사업·연봉 밴드·공고별 판단(무엇을 공부하고 면접에서 무엇을 물을지)."""
    idx = _load("guide/index.json") or {}
    hit = _find(idx.get("companies") or [], company)
    if not hit:
        return None
    doc = _load(f"guide/companies/{hit['slug']}.json") or {}
    # 공개 인물(people)은 넣지 않는다 — 실명 목록을 남의 에이전트에 넘길 이유가 없다.
    return {
        "company": doc.get("name"), "site": doc.get("site"), "one_liner": doc.get("one_liner"),
        "business": doc.get("company"), "salary": doc.get("salary"),
        "postings": [{k: p.get(k) for k in ("title", "url", "verdict", "fit", "study", "edge", "interview")}
                     for p in doc.get("postings") or []],
        "open_questions": doc.get("open_questions"),
        "updated_at": doc.get("updated_at"),
        "viewer_url": f"{SITE_URL}/companies",
    }


def company_tech(company: str) -> dict | None:
    """기업 기술스택(공고에서 센 것) + 기술 역설계(공개 자료로 재구성한 것)."""
    stacks = (_load("company_stacks.json") or {}).get("companies") or []
    st = _find(stacks, company)
    rv_idx = (_load("reveng/index.json") or {}).get("companies") or []
    rv = _find(rv_idx, company)
    if not st and not rv:
        return None
    out: dict = {}
    if st:
        out["from_postings"] = {k: st.get(k) for k in ("name", "size", "posting_count", "roles", "top_tech")}
    if rv:
        d = _load(f"reveng/companies/{rv['slug']}.json") or {}
        out["reverse_engineered"] = {k: d.get(k) for k in ("name", "country", "category", "one_liner",
                                                            "business_model", "products", "domains")}
        # 기능마다 '왜 그렇게 만들었나'(business.why)까지만 — 본문 전체는 뷰어에서 읽게 한다.
        out["reverse_engineered"]["features"] = [
            {"name": f.get("name"), "domain": f.get("domain"),
             "why": ((f.get("business") or {}).get("why") or "")[:300]}
            for f in (d.get("features") or [])[:12]
        ]
        out["reverse_engineered"]["viewer_url"] = f"{SITE_URL}/reveng/{rv['slug']}"
    return out


# ── 외주·프리 ────────────────────────────────────────────────────────

def freelance_rates() -> dict | None:
    doc = _load("freelance.json") or {}
    a = doc.get("analysis")
    if not a:
        return None
    cur = a.get("current") or {}
    table = {g: {c: ({k: s[k] for k in ("n", "p25", "median", "p75")} if s else None)
                 for c, s in (row or {}).items()}
             for g, row in (cur.get("table") or {}).items()}
    return {
        "unit": "만원/월 (올라올 때 단가)",
        "window": {"since": cur.get("since"), "until": cur.get("until")},
        "current_table": table,
        "by_domain": a.get("by_domain"), "by_role": a.get("by_role"), "by_type": a.get("by_type"),
        "insights": a.get("insights"),
        "method": "등급은 원본 표기 우선, 없으면 경력으로 추정(초급<3년·중급 3~6·고급 7~9·특급 10+). "
                  "개발 프로젝트의 월 단가만 센다.",
        "viewer_url": f"{SITE_URL}/freelance/rates",
    }


def search_freelance(query: str = "", *, grade: str = "", kind: str = "", limit: int = 10) -> dict:
    doc = _load("freelance.json") or {}
    toks = [t for t in (query or "").lower().split() if t]
    out = []
    for p in doc.get("projects") or []:
        if p.get("status") != "active":
            continue
        if grade and p.get("grade") != grade:
            continue
        if kind and p.get("kind") != kind:
            continue
        hay = f"{p.get('title')} {' '.join(p.get('skills') or [])} {p.get('location')} {p.get('domain')}".lower()
        if not all(t in hay for t in toks):
            continue
        out.append({k: p.get(k) for k in ("id", "title", "site", "kind", "grade", "grade_basis", "domain",
                                          "work_type", "role", "budget", "duration", "location", "skills",
                                          "career", "deadline", "url")})
        if len(out) >= limit:
            break
    return {"count": len(out), "projects": out}


# ── ATS 키워드 ───────────────────────────────────────────────────────

KW_SPLIT = re.compile(r"[,\n/·•\-()\[\]]+")


def job_keywords(job_id: str) -> dict | None:
    """공고가 요구하는 말 — 지원서가 이 말들을 담았는지 **사용자 쪽에서** 대조하게 준다.
    지원서 본문을 이 서버로 받지 않으려고 대조는 하지 않는다(개인정보가 우리를 거치지 않게)."""
    s = jobs()["by_key"].get(job_id)
    if not s:
        return None
    tech = list(s.get("tech_stack") or [])
    phrases = []
    for k in ("qualifications", "preferences"):
        for part in KW_SPLIT.split(s.get(k) or ""):
            part = part.strip(" .:;")
            if 2 <= len(part) <= 40:
                phrases.append(part)
    return {"job_id": job_id, "must_tech": tech, "phrases": phrases[:40],
            "how_to_use": "지원서 본문에 must_tech 가 몇 개 들어갔는지, phrases 의 요구를 어느 문장이 "
                          "받치는지 에이전트 쪽에서 세어 보라. 없는 경력을 지어내서 채우지 말 것."}
