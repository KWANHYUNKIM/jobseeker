"""에이전트용 MCP 서버의 데이터 계층 — 뷰어 API(backend, 8771)를 읽기만 한다.

출처(뷰어 화면과 같다. API 가 없으면 같은 이름의 jd-viewer/public/ 파일로 물러선다)
  /api/jobs/all            공고 전량     → 필요한 칸만 남겨 메모리에 든다(본문은 잘라 둔다)
  /api/docs/guide/…        취업 브리핑   (guide-engine)
  /api/docs/reveng/…       기술 역설계   (engine)
  /api/companies           기업 기술스택(목록 요약)
  /api/freelance           외주·프리 프로젝트와 단가 분석
공고 검색은 정본 DB 의 하이브리드 검색(FTS+pgvector)을 먼저 쓰고, DB 가 없으면
제목·회사·기술 키워드 검색으로 물러선다.

재배포 원칙: 공고 원문은 원 사이트의 것이다. 여기서는 **우리가 만든 것**(브리핑·역설계·단가 통계·
기술 태그)을 온전히 주고, 공고 본문은 칸마다 앞부분만 잘라 원문 링크와 함께 준다.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

SITE_URL = os.environ.get("AGENT_SITE_URL", "http://localhost:5173").rstrip("/")

SECTION_MAX = 400      # 공고 칸(주요업무·자격요건·우대) 하나당 글자 — 원문은 링크로
JOB_FIELDS = ("site", "pid", "company", "title", "url", "career", "location", "tech_stack",
              "status", "deadline_date", "posted_date", "company_size")
TEXT_FIELDS = ("main_tasks", "qualifications", "preferences")

# public 파일 이름 → 같은 내용을 주는 뷰어 API 경로. 나머지(guide/·reveng/ …)는 /api/docs/<이름>.
API_PATHS = {
    "all_jobs_enriched.json": "/api/jobs/all",     # 공고 전량(읽는 순간의 모집 상태)
    "company_stacks.json": "/api/companies",       # 회사 목록 요약 — 여기서 쓰는 필드는 다 있다
    "freelance.json": "/api/freelance",
}


def _load(name: str, build=None):
    """뷰어 API 로 읽는다(안 되면 같은 이름의 public 파일). build 가 있으면 가공한 결과를 캐시한다.

    뷰어 화면과 같은 출처를 보게 하려고 API 가 먼저다 — 파일은 크롤 회차마다 구운 사본이라
    마감이 늦다. 캐시·ETag·파일 대체는 core.api 가 맡는다.
    """
    from core import api
    # 같은 원본을 원본으로도, 가공본으로도 읽는다(company_stacks → 회사 기술 / 회사 규모 표).
    # 키에 build 를 넣지 않으면 먼저 읽은 쪽이 다른 쪽 자리를 차지한다.
    key = f"{name}#{build.__qualname__}" if build else name
    path = API_PATHS.get(name) or f"/api/docs/{name}"
    return api.get(path, file=name, build=build, key=f"agent_mcp:{key}")


def norm(name: str | None) -> str:
    """회사 이름 비교용 — (주)·㈜·주식회사·공백·대소문자를 걷어 낸다."""
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|\(재\)|\s+", "", name or "")
    return s.lower()


def job_key(j: dict) -> str:
    return f"{j['site']}-{j['pid']}"


# ── 공고 ──────────────────────────────────────────────────────────────

# ── 학력 관문 ────────────────────────────────────────────────────────
# 2년제 졸업자가 '학부 4학년 이상'·'4년제 졸업' 공고에 넣지 않게 하려고 판정한다. 데모에서
# 자동 대조가 통과시킨 두 곳(에너자이 '학부 4학년 이상', 로봇웨어에이아이 '대학교졸업(4년)이상')이
# 원문을 보니 막혀 있었다 — 요건 칸이 잘리기 전(적재 시점의 전문)으로 판정한다.
EDU_LEVELS = ["무관", "고졸", "전문학사", "학사", "석사", "박사"]
EDU_PATTERNS = [   # (단계, 정규식) — 한 줄에서 찾는다. '우대' 줄은 건너뛴다.
    (5, r"박사\s*(?:학위)?\s*(?:이상|소지|취득|졸업|과정|님)"),
    (4, r"석사\s*(?:학위)?\s*(?:이상|소지|취득|졸업|연구원)|석사\s*\(?전공"),
    (3, r"학사\s*(?:학위)?\s*(?:이상|소지|졸업)|4\s*년제|학부\s*4\s*학년|대학교?\s*졸업\s*\(?\s*4\s*년|대졸\s*\(?\s*4|"
        r"대졸\s*이상|대학교\s*졸업\s*이상|4년\s*대졸"),
    (2, r"초대졸|전문\s*학사|전문대|전졸|대학\s*\(?\s*2\s*,?\s*3\s*년|2\s*,\s*3\s*년제|대학졸업\s*\(\s*2"),
    (1, r"고졸|고등학교\s*졸업"),
]
EDU_RX = [(lv, re.compile(p)) for lv, p in EDU_PATTERNS]
EDU_ANY = re.compile(r"학력\s*(?:무관|제한\s*없)|학력\s*:\s*무관")
EDU_SKIP = re.compile(r"우대|preferred|plus|가산")


def edu_gate(*texts: str) -> tuple[int | None, str]:
    """(요구 최소 학력 단계, 근거 문구). 모르면 (None, '')."""
    lines = [ln.strip() for t in texts for ln in re.split(r"[\n•·]", t or "") if ln.strip()]
    for ln in lines:
        if EDU_ANY.search(ln):
            return 0, ln[:80]
    for ln in lines:
        if EDU_SKIP.search(ln):
            continue
        # 한 줄에 여러 단계가 있으면('초대졸 이상, 4년제 우대') 가장 낮은 것이 관문이다.
        hits = [lv for lv, rx in EDU_RX if rx.search(ln)]
        if hits:
            return min(hits), ln[:80]
    return None, ""


def edu_level(label: str) -> int | None:
    label = (label or "").strip()
    aliases = {"고졸": 1, "고등학교": 1, "전문학사": 2, "초대졸": 2, "2년제": 2, "3년제": 2, "전문대": 2,
               "학사": 3, "대졸": 3, "4년제": 3, "석사": 4, "박사": 5}
    return next((v for k, v in aliases.items() if k in label), None)


# 직군 — 공고 제목으로 가른다(첫 번째로 맞는 것). 현실 점검(market_check)이 직군끼리 견준다.
ROLE_FAMILIES = [
    ("AI/ML", r"(?<![a-z])ai(?![a-z])|인공지능|머신\s*러닝|딥\s*러닝|(?<![a-z])ml(?![a-z])|llm|컴퓨터\s*비전|vision"),
    ("데이터", r"데이터|data|빅데이터|(?<![a-z])dba(?![a-z])"),
    ("임베디드/펌웨어", r"임베디드|펌웨어|firmware|embedded|(?<![a-z])mcu(?![a-z])|제어|회로|fpga|하드웨어|반도체"),
    ("모바일", r"안드로이드|android|모바일|(?<![a-z])ios(?![a-z])|flutter|앱\s*개발"),
    ("프론트엔드", r"프론트|front|퍼블리|react|vue"),
    ("백엔드", r"백엔드|back-?end|서버|java|spring|node|(?<![a-z])api(?![a-z])"),
    ("풀스택/웹", r"풀스택|full-?stack|웹|web"),
    ("DevOps/인프라", r"devops|인프라|클라우드|cloud|(?<![a-z])sre(?![a-z])|네트워크|보안"),
    ("QA/테스트", r"(?<![a-z])qa(?![a-z])|테스트|품질"),
    ("SI/유지보수·운영", r"(?<![a-z])si(?![a-z])|(?<![a-z])sm(?![a-z])|유지\s*보수|운영|전산|솔루션|erp|mes"),
]
ROLE_RX = [(n, re.compile(p, re.I)) for n, p in ROLE_FAMILIES]
ENTRY_RX = re.compile(r"신입|무관")
# 경력란이 '경력무관'이어도 제목이 시니어·리드면 신입 자리가 아니다(퓨텍 '(시니어)… ' 가 신입 표본에 섞였다).
SENIOR_RX = re.compile(r"시니어|senior|(?<![a-z])lead(?![a-z])|리드|팀장|파트장|책임|수석|principal|staff|head of", re.I)
GRAD_RX = re.compile(r"석사|박사")

# 시·도 — 사이트마다 '서울 강남구'·'서울강남구'·'전남광주북구'·'[대전/IT]…' 처럼 제각각이다.
REGIONS = ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종", "강원",
           "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
REGION_ALIAS = {"충청북": "충북", "충청남": "충남", "전라북": "전북", "전북특별": "전북", "전라남": "전남",
                "경상북": "경북", "경상남": "경남", "강원특별": "강원", "제주특별": "제주", "Seoul": "서울"}
FOREIGN_RX = re.compile(r"[A-Za-z]{3,}")


def region_of(location: str | None) -> str:
    loc = (location or "").strip()
    if not loc:
        return "지역 표기 없음"
    if re.search(r"원격|재택|remote|anywhere", loc, re.I):
        return "원격"
    for k, v in REGION_ALIAS.items():
        if k in loc:
            return v
    if loc.startswith("전남광주") or loc.startswith("광주"):
        return "광주"          # 사람인은 광주광역시를 '전남광주…' 로 적는다
    hit = [(loc.find(r), r) for r in REGIONS if r in loc]
    if hit:
        return min(hit)[1]
    return "해외" if FOREIGN_RX.search(loc) else "기타"


def role_family(title: str) -> str | None:
    return next((n for n, rx in ROLE_RX if rx.search(title)), None)


def _slim_jobs(raw: list[dict]) -> dict:
    """10만 줄짜리 원본에서 필요한 칸만 — 본문(full_jd)은 버리고 세 칸만 잘라 둔다."""
    by_key: dict[str, dict] = {}
    by_url: dict[str, str] = {}
    for j in raw:
        if not j.get("site") or not j.get("pid"):
            continue
        s = {k: j.get(k) for k in JOB_FIELDS}
        edu = j.get("education") if len(j.get("education") or "") <= 40 else ""
        s["edu_min"], s["edu_evidence"] = edu_gate(edu or "", j.get("qualifications") or "")
        for k in TEXT_FIELDS:
            t = (j.get(k) or "").strip()
            s[k] = t[:SECTION_MAX] + ("…" if len(t) > SECTION_MAX else "")
        s["id"] = job_key(j)
        s["family"] = role_family(j.get("title") or "")
        s["entry"] = bool(ENTRY_RX.search(j.get("career") or "")) and not SENIOR_RX.search(j.get("title") or "")
        s["region"] = region_of(j.get("location"))
        s["pay"] = parse_pay(j.get("full_jd") or "", j.get("benefits") or "")
        s["grad_mention"] = bool(GRAD_RX.search((j.get("qualifications") or "") + (j.get("preferences") or "")))
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
    out["family"] = s.get("family")                                       # 직군(market_check 와 같은 분류)
    lv = s.get("edu_min")
    out["education_min"] = EDU_LEVELS[lv] if lv is not None else None     # None = 공고에서 못 찾음
    out["education_evidence"] = s.get("edu_evidence") or None
    if full:
        out.update({k: s.get(k) for k in TEXT_FIELDS})
    return out


def _semantic(query: str, limit: int) -> list[str] | None:
    """정본 DB 하이브리드 검색(FTS + pgvector) → 공고 id 목록. DB 가 없으면 None.

    뷰어 검색(backend /api/search)과 같은 DB 함수(search_jobs)를 쓴다 — 예전에는 여기만
    SQLite(semantic.db)를 봐서 같은 질문에 뷰어와 다른 답이 나올 수 있었다.
    Ollama 가 없으면 search 가 알아서 FTS 만으로 답한다.
    """
    try:
        from store.vectors.search import search as pg_search
        out = pg_search(query, limit * 3, include_closed=False, use_vector=True)
    except Exception:                                                # noqa: BLE001
        return None
    by_url = jobs()["by_url"]
    ids = [by_url.get(r.get("url")) for r in out]
    return [i for i in ids if i]


def _neg(iso: str) -> str:
    """날짜 문자열을 내림차순 정렬용으로 뒤집는다('2026-09-28' → 큰 날짜가 앞)."""
    return "".join(chr(0x7f - ord(c)) for c in iso)


def search_jobs(query: str, *, limit: int = 10, open_only: bool = True,
                location: str = "", career: str = "", education: str = "") -> dict:
    everything = jobs()["by_key"]
    my_edu = edu_level(education)       # 지원자 최종학력 — 주면 넘을 수 없는 학력 관문을 뺀다

    def keep(s: dict) -> bool:
        if open_only and s.get("status") == "closed":
            return False
        if my_edu is not None and s.get("edu_min") is not None and s["edu_min"] > my_edu:
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


MARKET_CAVEATS = [
    "공고에 '적힌' 학력 관문만 센다. 적히지 않은 서류 심사(학벌·전공·경력 선호)는 이 숫자에 안 보인다 — "
    "실제 문은 이보다 좁다고 보고 말할 것.",
    "색인은 개발 직군 검색어로 모은 것이라 임베디드·제조·SI 처럼 IT 채용 사이트 밖에서 많이 뽑는 직군은 "
    "적게 잡힌다. 표본이 작은 직군(open < 10)은 '데이터 부족'이지 '자리가 없다'가 아니다.",
    "지금 모집중인 공고만 센다(계절·시점에 따라 흔들린다). 합격률·경쟁률은 이 데이터로 알 수 없다.",
    "지역 칸이 빈 공고가 많다(주로 원티드). passable_by_region 의 '지역 표기 없음'은 어디든 될 수 있다.",
]


def market_check(*, education: str = "", location: str = "", entry_only: bool = True,
                 families: list[str] | None = None, top_tech: int = 12, samples: int = 3) -> dict:
    """직군별로 '이 학력·지역·연차로 문을 두드릴 수 있는 공고가 몇 개인가'를 센다.

    지원자의 기술 목록은 받지 않는다(이력서가 서버에 오지 않는 원칙). 직군마다 자주 요구되는 기술을
    비율로 돌려주니, 겹침은 에이전트가 자기 쪽 프로필로 센다.
    """
    my_edu = edu_level(education)
    want = set(families or [])
    by: dict[str, dict] = {}
    for s in jobs()["by_key"].values():
        fam = s.get("family")
        if not fam or s.get("status") == "closed" or (want and fam not in want):
            continue
        if entry_only and not s.get("entry"):
            continue
        b = by.setdefault(fam, {"open": 0, "gated": 0, "unknown_edu": 0, "grad": 0, "tech": {},
                                "local_open": 0, "pass": [], "regions": {}})
        b["open"] += 1
        lv = s.get("edu_min")
        gated = my_edu is not None and lv is not None and lv > my_edu
        b["gated"] += gated
        b["unknown_edu"] += lv is None
        b["grad"] += bool(s.get("grad_mention"))
        for t in s.get("tech_stack") or []:
            b["tech"][t] = b["tech"].get(t, 0) + 1
        local = bool(location) and (location in (s.get("location") or "") or location == s.get("region"))
        b["local_open"] += local
        if not gated:
            b["regions"][s["region"]] = b["regions"].get(s["region"], 0) + 1
            if local or not location:
                b["pass"].append(s)

    pct = lambda n, d: round(100 * n / d) if d else None   # noqa: E731
    out = []
    for fam, b in by.items():
        n = b["open"]
        picks = sorted(b["pass"], key=lambda s: _neg(s.get("posted_date") or ""))
        out.append({
            "family": fam,
            "open": n,
            "passable": n - b["gated"],
            "education_gate_pct": pct(b["gated"], n) if my_edu is not None else None,
            "education_unknown_pct": pct(b["unknown_edu"], n),
            "grad_degree_mention_pct": pct(b["grad"], n),
            "local_open": b["local_open"] if location else None,
            "local_passable": len(picks) if location else None,
            # 넘을 수 있는 공고가 어느 시·도에 있나(전국). '지역 표기 없음'은 주로 원티드 — 원문에서 확인.
            "passable_by_region": [{"region": r, "count": c} for r, c in
                                   sorted(b["regions"].items(), key=lambda kv: -kv[1])],
            "top_tech": [{"name": t, "pct": pct(c, n)} for t, c in
                         sorted(b["tech"].items(), key=lambda kv: -kv[1])[:top_tech]],
            "samples": [job_card(s) for s in picks[:samples]],   # location 을 주면 그 지역 안, 아니면 전국 최신
            "thin_sample": n < 10,
        })
    out.sort(key=lambda r: (-(r["local_passable"] or 0), -r["passable"]))
    return {
        "filters": {"education": education or None, "location": location or None, "entry_only": entry_only},
        "families": out,
        "caveats": MARKET_CAVEATS,
        "how_to_use": "목표 직군과 다른 직군을 나란히 놓고 본다: passable(넘을 수 있는 공고 수)·local_passable·"
                      "education_gate_pct·grad_degree_mention_pct, 그리고 top_tech 를 지원자 프로필과 에이전트 쪽에서 "
                      "겹쳐 본 비율. 목표 직군이 다른 직군보다 문이 뚜렷이 좁으면 서류를 쓰기 전에 그 사실을 먼저 말한다.",
    }


def resolve_id(job_id_or_url: str) -> str | None:
    """공고 id('wanted-12345') 또는 원문 URL → id. /apply 는 사용자가 붙여 넣은 URL 로 시작하기도 한다."""
    j = jobs()
    x = (job_id_or_url or "").strip()
    if x in j["by_key"]:
        return x
    return j["by_url"].get(x) or j["by_url"].get(x.rstrip("/"))


def get_job(job_id: str) -> dict | None:
    k = resolve_id(job_id)
    return job_card(jobs()["by_key"][k], full=True) if k else None


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


# ── 연봉 ─────────────────────────────────────────────────────────────
# 국내 공고는 대부분 '회사 내규에 따름'·'면접 후 결정'이다. 숫자를 적은 공고는 4% 남짓이고 사람인·작은
# 회사 쪽에 쏠려 있다 — 그래서 시세표는 '적어 둔 곳들의 값'이지 시장 전체가 아니다(caveats 로 늘 같이 준다).
# 회사 단위 값은 취업 브리핑(guide-engine)의 연봉 밴드가 우선이다(출처·확신도가 붙어 있다).
PAY_LINE = re.compile(r"연봉|초봉|급여|월급|기본급|보수|salary", re.I)
PAY_SKIP = re.compile(r"급여\s*외|별도|인센티브|성과급|보너스|상여|식대|교통비|지원금|포인트|퇴직|복지|수당\s*지급|"
                      r"연간\s*\d+\s*만\s*원\s*\)")
PAY_RANGE = re.compile(r"(\d[\d,]{2,6})\s*(?:만\s*원?)?\s*[~\-–]\s*(\d[\d,]{2,6})\s*만")
# 금액 한 개: '3,500만'·'5천만'·'1억'·'1.2억'
PAY_AMT = re.compile(r"(\d+(?:\.\d)?)\s*억(?:\s*(\d[\d,]*)\s*만)?|(\d)\s*천\s*(?:\d{1,3}\s*백\s*)?만|(\d[\d,]{2,6})\s*만")
PAY_NOISE = re.compile(r"자본금|매출|투자|설립|\d,\s+\d")     # 회사 소개 줄, OCR 로 깨진 숫자
PAY_MONTH = re.compile(r"월\s*급|월\s*급여|월\s*\d|월\s*평균|\(월\)|/\s*월")


def _num(x: str) -> int:
    return int(x.replace(",", ""))


def _amounts(ln: str) -> list[int]:
    out = []
    for m in PAY_AMT.finditer(ln):
        if m.group(1):
            out.append(int(float(m.group(1)) * 10000) + (_num(m.group(2)) if m.group(2) else 0))
        elif m.group(3):
            out.append(int(m.group(3)) * 1000)
        else:
            out.append(_num(m.group(4)))
    return out


def parse_pay(*texts: str) -> dict | None:
    """공고 본문에서 적힌 연봉(만원/년)을 한 줄 찾는다. 수당·성과급·복지·회사 소개 줄은 건너뛴다."""
    for t in texts:
        for ln in (t or "").split("\n"):
            ln = ln.strip()
            if not PAY_LINE.search(ln) or PAY_SKIP.search(ln) or PAY_NOISE.search(ln):
                continue
            lo = hi = None
            if (m := PAY_RANGE.search(ln)):              # '4000~5500만원' — 앞 숫자에 단위가 없다
                lo, hi = _num(m.group(1)), _num(m.group(2))
            else:
                amts = _amounts(ln)
                if not amts:
                    continue
                lo = amts[0]
                if len(amts) > 1 and re.search(r"[~\-–]", ln):
                    hi = amts[1]
            monthly = bool(PAY_MONTH.search(ln)) and lo < 1000
            k = 12 if monthly else 1
            lo, hi = lo * k, (hi * k if hi else None)
            if hi and hi < lo:
                lo, hi = hi, lo
            if not 1800 <= lo <= 30000 or (hi and hi > 40000):
                continue                      # 연봉으로 보기 어려운 숫자
            return {"low": lo, "high": hi, "monthly": monthly, "text": ln[:90]}
    return None


def career_bucket(career: str | None) -> str:
    c = career or ""
    if re.search(r"신입", c):
        return "신입"
    m = re.search(r"(\d+)", c)
    if m:
        n = int(m.group(1))
        return "1~3년" if n <= 3 else "4~6년" if n <= 6 else "7년+"
    return "무관" if "무관" in c else "미상"


def _sizes() -> dict[str, str]:
    """회사 규모(중소·중견·대기업…) — 공고에는 없고 company_stacks 에 있다."""
    def build(raw):
        return {norm(c.get("name")): c.get("size") for c in raw.get("companies") or [] if c.get("size")}
    return _load("company_stacks.json", build) or {}


def _pct(vals: list[int], q: float) -> int:
    v = sorted(vals)
    i = (len(v) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (i - lo))


SALARY_CAVEATS = [
    "공고에 연봉 숫자를 적는 곳은 4% 남짓이고 사람인·작은 회사 쪽에 쏠려 있다 — market 은 '적어 둔 곳들'의 값이다. "
    "숫자를 안 적는 큰 회사들이 빠져 있으니 시장 전체 중앙값으로 말하지 말 것.",
    "범위로 적힌 공고는 가운데 값을 쓴다. '이상'만 적힌 공고는 그 하한을 쓴다. 월급으로 적힌 것은 ×12 했다.",
    "회사 브리핑의 밴드는 국민연금 가입자 평균처럼 '전 직군 평균'인 경우가 많다 — 신입 초봉이 아니다(basis·note 확인).",
    "표본이 5건 미만인 칸은 숫자를 주지 않는다.",
]


def salary_benchmark(company: str = "", career: str = "", family: str = "") -> dict:
    """회사 연봉(브리핑 밴드 + 그 회사 공고에 적힌 값)과, 비슷한 자리의 시세(공고에 적힌 값으로 센 것)."""
    sizes = _sizes()
    want_bucket = career_bucket(career) if career else ""
    rows: dict[tuple, list[int]] = {}
    mine: list[dict] = []
    n_company = norm(company) if company else ""
    for s in jobs()["by_key"].values():
        p = s.get("pay")
        if not p:
            continue
        mid = (p["low"] + p["high"]) // 2 if p.get("high") else p["low"]
        size = sizes.get(norm(s.get("company"))) or "규모 미상"
        b = career_bucket(s.get("career"))
        if not family or s.get("family") == family:
            rows.setdefault((b, size), []).append(mid)
            rows.setdefault((b, "전체"), []).append(mid)
        if n_company and (norm(s.get("company")) == n_company):
            mine.append({"id": s["id"], "title": s.get("title"), "career": s.get("career"),
                         "status": s.get("status"), **p})

    my_size = None
    if company:
        hit = _find((_load("company_stacks.json") or {}).get("companies") or [], company)
        my_size = (hit or {}).get("size")
    market = []
    for (b, size), vals in sorted(rows.items()):
        if want_bucket and b != want_bucket:
            continue
        if size not in ("전체", my_size) and my_size:
            continue
        if len(vals) < 5:
            continue
        market.append({"career": b, "size": size, "n": len(vals), "p25": _pct(vals, .25),
                       "median": _pct(vals, .5), "p75": _pct(vals, .75)})

    brief = company_brief(company) if company else None
    return {
        "unit": "만원/년",
        "company": ({"name": (brief or {}).get("company") or company, "size": my_size,
                     "brief_salary": (brief or {}).get("salary"),
                     "posted": mine[:10]} if company else None),
        "market": market,
        "filters": {"career_bucket": want_bucket or None, "family": family or None},
        "caveats": SALARY_CAVEATS,
    }


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

# 요건은 **줄(항목) 단위**로 자른다. 예전엔 / - ( 로도 잘라 'MCP (Multi-Party Computation)' 이
# 'Multi' 'Party Computation' 로, '설계/운영 경험' 이 '운영 경험을 보유한 분' 조각으로 흩어졌다.
KW_LINE = re.compile(r"\n+|(?:^|\s)[•·▪■●◦\-*]\s+|\s+\d+[.)]\s+")
# 꼬리 걷기 — '…경험을 보유한 분' → '…경험', '…이해가 있는 분' → '…이해', '…5년 이상인 분' → '…5년 이상'
KW_TAIL = [
    re.compile(r"\s*(?:을|를)\s*(?:보유|갖추|갖춘|가진|가지)\S*\s*(?:분|자|사람)\s*$"),
    re.compile(r"\s*(?:이|가)\s*(?:있는|있으신|계신)\s*(?:분|자|사람)\s*$"),
    re.compile(r"\s*(?:인|한|하신|이신|있는|된)\s*(?:분|자|사람)\s*$"),
]
KW_BULLET = re.compile(r"^[\s•·▪■●◦\-*]+")


def job_keywords(job_id: str) -> dict | None:
    """공고가 요구하는 말 — 지원서가 이 말들을 담았는지 **사용자 쪽에서** 대조하게 준다.
    지원서 본문을 이 서버로 받지 않으려고 대조는 하지 않는다(개인정보가 우리를 거치지 않게)."""
    k = resolve_id(job_id)
    if not k:
        return None
    s = jobs()["by_key"][k]
    job_id = k
    tech = list(s.get("tech_stack") or [])
    phrases = []
    required, preferred = [], []
    for k, bucket in (("qualifications", required), ("preferences", preferred)):
        for part in KW_LINE.split(s.get(k) or ""):
            part = KW_BULLET.sub("", (part or "").strip(" .:;…"))
            for rx in KW_TAIL:
                part = rx.sub("", part)
            part = part.strip(" .:;")
            if 4 <= len(part) <= 120:
                bucket.append(part)
    phrases = required + preferred
    lv = s.get("edu_min")
    return {"job_id": job_id, "must_tech": tech, "required": required[:20], "preferred": preferred[:15],
            "education_min": EDU_LEVELS[lv] if lv is not None else None,
            "education_evidence": s.get("edu_evidence") or None,
            "phrases": phrases[:35],
            "how_to_use": "지원서 본문에 must_tech 가 몇 개 들어갔는지, phrases 의 요구를 어느 문장이 "
                          "받치는지 에이전트 쪽에서 세어 보라. 없는 경력을 지어내서 채우지 말 것."}
