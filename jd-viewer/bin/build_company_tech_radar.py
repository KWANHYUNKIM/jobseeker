#!/usr/bin/env python3
"""기술 스택 레이더 — 글로벌 IT 대기업의 기술 스택, 아키텍처 다이어그램, 공개 GitHub
코드, 그리고 '왜 이 아키텍처/언어인지'를 큐레이션 시드 + 로컬 ``claude`` CLI 리파인
루프로 유지하는 빌더.

데이터 원본이자 산출물은 ``jd-viewer/public/company_tech_radar.json`` 하나다.
크롤 데이터에서 파생되는 company_stacks.json 과 달리 이 파일은 사람이 큐레이션한
시드를 in-place 로 갱신한다(추가 API 키 없이 로컬 claude 구독으로 리서치).

회사 객체에는 ``diagram``(Mermaid flowchart — 노드별 기술스택 라벨)과 ``github``
(org + 검증된 공개 repo) 필드가 포함된다. 리파인 루프가 이 둘을 매 사이클 발전시킨다.

사용 예::

    # 시드(JSON 배열 파일들)를 병합해 최초 생성
    python build_company_tech_radar.py --init a.json b.json c.json

    # {key, diagram, github, ...} 부분필드 배열을 key 매칭으로 병합(다이어그램 시드)
    python build_company_tech_radar.py --patch patch_0.json patch_1.json

    # github repo 미검증 N개사를 GitHub API 로 검증·보강(star/lang, 환각 repo 제거)
    GITHUB_TOKEN=$(gh auth token) python build_company_tech_radar.py --github 100

    # 집계(국가/도메인/total/generated_at)만 재계산 후 저장
    python build_company_tech_radar.py

    # 가장 오래 갱신 안 된 5개사를 claude CLI 로 리서치·갱신(다이어그램·github 포함, 1회)
    python build_company_tech_radar.py --refine 5

    # 무한 루프로 회사들의 '이유'·다이어그램을 계속 발전(증분, 30분 간격)
    python build_company_tech_radar.py --refine 5 --loop --interval 1800

claude CLI 가 없거나 비대화형 인증이 안 되면 --refine 는 조용히 건너뛴다.
GitHub 검증은 GITHUB_TOKEN(또는 gh auth token) 이 있으면 한도가 5000/h 로 올라간다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # jd-viewer/
DATA = ROOT / "public" / "company_tech_radar.json"

# 국가 표기 순서(뷰어 사이드바와 동일한 우선순위)
COUNTRY_ORDER = ["US", "KR", "IN", "JP", "GB", "DE", "SG", "CN"]

# 상위 산업 도메인 정규화 — 서브도메인(핀테크/결제 등)을 상위로 합치되,
# '/'가 이름의 일부인 복합 도메인은 그대로 보존한다.
DOMAIN_COMPOUND = {"데이터/AI", "스트리밍/미디어", "검색/광고", "IoT/디바이스", "여행/숙박"}
DOMAIN_OVERRIDE = {"메시징 API/SaaS": "SaaS", "지역 커뮤니티/중고거래": "지역 커뮤니티"}

# 도메인별 공통 스택 집계 시 카테고리별로 노출할 상위 기술 개수
DOMAIN_TOP_N = {"languages": 8, "stack": 10, "architecture": 6}

# 같은 기술의 다른 표기를 한 토큰으로 합치기 위한 별칭(집계 정확도 향상)
TECH_ALIASES = {
    "apache kafka": "Kafka",
    "google cloud platform": "GCP",
    "google cloud": "GCP",
    "amazon web services": "AWS",
    "node": "Node.js",
    "nodejs": "Node.js",
    "postgres": "PostgreSQL",
    "k8s": "Kubernetes",
    "spring": "Spring Boot",
}


def normalize_domain(d: str) -> str:
    """서브도메인을 상위 산업 도메인으로 정규화한다(핀테크/결제 → 핀테크)."""
    d = (d or "기타").strip()
    if d in DOMAIN_OVERRIDE:
        return DOMAIN_OVERRIDE[d]
    if d in DOMAIN_COMPOUND:
        return d
    return d.split("/", 1)[0].strip()


def _clean_tech(t: str) -> str:
    """집계용으로 기술 토큰을 정리한다 — 괄호 주석(예: 'MySQL (Vitess)') 제거 후 공백 정규화."""
    t = re.sub(r"\s*\([^)]*\)\s*", " ", t or "")
    t = re.sub(r"\s+", " ", t).strip()
    return TECH_ALIASES.get(t.lower(), t)


def _top(counter: Counter, n: int) -> list[dict]:
    """빈도 내림차순(동률은 이름 오름차순)으로 상위 n개를 {name,count} 배열로."""
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return [{"name": k, "count": v} for k, v in items[:n]]


def domain_groups(companies: list[dict]) -> list[dict]:
    """회사들을 상위 산업 도메인으로 묶고, 도메인별 공통 기술스택을 집계한다.

    각 회사의 stack/languages/architecture 토큰을 도메인 단위로 빈도 집계해
    '그 도메인이 어떤 기술스택으로 이루어지는지'를 대표 스택으로 요약한다."""
    groups: dict[str, dict] = {}
    for c in companies:
        dom = normalize_domain(c.get("domain", "기타"))
        g = groups.setdefault(dom, {
            "name": dom,
            "companies": [],
            "subdomains": set(),
            "_lang": Counter(),
            "_stack": {k: Counter() for k in ("backend", "frontend", "data", "infra")},
            "_arch": Counter(),
        })
        g["companies"].append(c.get("name", ""))
        raw_dom = (c.get("domain") or "").strip()
        if raw_dom and raw_dom != dom:
            g["subdomains"].add(raw_dom)
        for lang in c.get("languages", []):
            cl = _clean_tech(lang)
            if cl:
                g["_lang"][cl] += 1
        stack = c.get("stack") or {}
        for cat in ("backend", "frontend", "data", "infra"):
            for t in stack.get(cat, []) or []:
                ct = _clean_tech(t)
                if ct:
                    g["_stack"][cat][ct] += 1
        for a in c.get("architecture", []):
            ca = _clean_tech(a)
            if ca:
                g["_arch"][ca] += 1

    out = []
    for g in groups.values():
        out.append({
            "name": g["name"],
            "count": len(g["companies"]),
            "companies": sorted(g["companies"]),
            "subdomains": sorted(g["subdomains"]),
            "languages": _top(g["_lang"], DOMAIN_TOP_N["languages"]),
            "stack": {cat: _top(g["_stack"][cat], DOMAIN_TOP_N["stack"])
                      for cat in ("backend", "frontend", "data", "infra")},
            "architecture": _top(g["_arch"], DOMAIN_TOP_N["architecture"]),
        })
    # 회사 수 내림차순 → 이름 오름차순
    out.sort(key=lambda d: (-d["count"], d["name"]))
    return out

# 회사 객체 필드 순서(가독성 위해 직렬화 시 강제)
FIELD_ORDER = [
    "key", "name", "country", "domain", "languages", "stack",
    "architecture", "diagram", "why_language", "why_architecture", "summary",
    "deep_dive", "debate", "interview", "github", "sources", "research_status", "updated_at",
]


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def merge_deep_dive(company: dict, new_sections: list) -> int:
    """deep_dive 를 누적 병합한다 — 기존 토픽은 보존, 새 토픽만 덧붙인다(절대 줄이지 않음).
    동일 토픽이 더 긴 본문으로 오면 더 긴 쪽을 채택(내용을 늘리는 방향만 허용)."""
    existing = company.get("deep_dive") or []
    by_topic = {s.get("topic", "").strip().lower(): s for s in existing}
    added = 0
    for s in new_sections or []:
        topic = (s.get("topic") or "").strip()
        body = (s.get("body") or "").strip()
        if not topic or not body:
            continue
        key = topic.lower()
        if key in by_topic:
            # 더 길고 풍부한 본문이면 갱신(축소 금지)
            if len(body) > len(by_topic[key].get("body", "")):
                by_topic[key]["body"] = body
        else:
            sec = {"topic": topic, "body": body}
            existing.append(sec)
            by_topic[key] = sec
            added += 1
    company["deep_dive"] = existing
    return added


def _ordered(company: dict) -> dict:
    """알려진 필드 순서로 정렬하고 나머지는 뒤에 붙인다."""
    out = {k: company[k] for k in FIELD_ORDER if k in company}
    for k, v in company.items():
        if k not in out:
            out[k] = v
    return out


def _country_rank(code: str) -> int:
    return COUNTRY_ORDER.index(code) if code in COUNTRY_ORDER else len(COUNTRY_ORDER)


# ── 로드/저장 ──────────────────────────────────────────────────────────

def load() -> list[dict]:
    if not DATA.exists():
        return []
    doc = json.loads(DATA.read_text(encoding="utf-8"))
    return doc.get("companies", [])


def save(companies: list[dict]) -> dict:
    """집계를 재계산하고 정렬해 파일에 쓴다. 작성한 문서를 반환."""
    # 국가 정렬 → 도메인 → 이름
    companies = sorted(
        companies,
        key=lambda c: (_country_rank(c.get("country", "")), c.get("domain", ""), c.get("name", "")),
    )
    companies = [_ordered(c) for c in companies]

    # 집계
    countries: dict[str, int] = {}
    domains: dict[str, int] = {}
    for c in companies:
        countries[c.get("country", "?")] = countries.get(c.get("country", "?"), 0) + 1
        d = c.get("domain", "기타")
        domains[d] = domains.get(d, 0) + 1

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(companies),
        "countries": [
            {"code": code, "count": n}
            for code, n in sorted(countries.items(), key=lambda kv: (_country_rank(kv[0]), -kv[1]))
        ],
        "domains": [
            {"name": name, "count": n}
            for name, n in sorted(domains.items(), key=lambda kv: -kv[1])
        ],
        "refined": sum(1 for c in companies if c.get("research_status") == "llm-refined"),
        "domain_groups": domain_groups(companies),
        "companies": companies,
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


# ── 시드 병합(--init) ──────────────────────────────────────────────────

def cmd_init(seed_paths: list[str]) -> None:
    merged: dict[str, dict] = {}
    # 기존 데이터가 있으면 보존(이미 리파인된 항목을 시드로 덮어쓰지 않음)
    for c in load():
        merged[c["key"]] = c
    for p in seed_paths:
        arr = json.loads(Path(p).read_text(encoding="utf-8"))
        for c in arr:
            key = c["key"]
            if key in merged and merged[key].get("research_status") == "llm-refined":
                continue  # 리파인 결과 보존
            c.setdefault("research_status", "seed")
            c.setdefault("updated_at", _today())
            merged[key] = c
    doc = save(list(merged.values()))
    print(f"[init] {doc['total']}개사 저장 → {DATA}")
    print(f"       국가: {', '.join(f'{x['code']} {x['count']}' for x in doc['countries'])}")
    print(f"       도메인: {len(doc['domains'])}종 / 리파인됨 {doc['refined']}개")


# ── claude CLI 리파인(--refine) ────────────────────────────────────────

REFINE_PROMPT = """You are a senior software-architecture analyst. Research the REAL engineering \
stack and system architecture of the company below using publicly known practices (their \
engineering blog, conference talks, job posts, open source). Be specific and accurate — no \
generic filler.

Company: {name} ({country}, 도메인: {domain})
Current known stack (may be improved or corrected): {current}

Return STRICT JSON ONLY (no markdown fences, no prose) with EXACTLY these keys:
{{
  "languages": ["..."],            // primary languages, most-used first, 3-6
  "stack": {{"backend": ["..."], "frontend": ["..."], "data": ["..."], "infra": ["..."]}},
  "architecture": ["..."],         // 2-4 architectural patterns
  "diagram": "flowchart TD ...",   // see DIAGRAM RULES below
  "why_language": "왜 이 언어들을 쓰는지 도메인·규모 맥락에서 2-3문장 한국어",
  "why_architecture": "왜 이 아키텍처를 택했는지 2-3문장 한국어",
  "summary": "기술 선택 한 줄 헤드라인 한국어",
  "github": {{"org": "https://github.com/<org>", "repos": [
      {{"name": "<org>/<repo>", "url": "https://github.com/<org>/<repo>", "desc": "한 줄 설명(한국어)", "lang": "Go"}}
  ]}},
  "deep_dive_add": [               // 아래 DEEP DIVE 규칙 — 새 토픽을 '추가'한다
      {{"topic": "토픽 제목(한국어)", "body": "마크다운 장문 해설(한국어)"}}
  ],
  "sources": ["https://..."]       // 1-3 real public source URLs
}}

DEEP DIVE RULES (이 회사의 기술이 '실제로 어떻게 작동하는지' 깊고 길게 설명 — 핵심):
- 이미 다룬 토픽: {covered}
- 위에서 다루지 않은 NEW 토픽을 2~4개 골라 `deep_dive_add` 에 넣는다(가능한 토픽: 요청 처리 흐름 end-to-end, 핵심 컴포넌트별 동작 원리, 데이터 저장·일관성·샤딩 전략, 캐싱 계층, 비동기·이벤트·스트리밍 처리, 확장성·오토스케일링 기법, 장애 대응·복원력(서킷브레이커·페일오버), 배포·CI/CD·카나리, 관측성(로깅·트레이싱·메트릭), 보안·인증, 검색·랭킹·추천, ML/추천 파이프라인, 특이한 엔지니어링 결정과 트레이드오프, 대표 트래픽 이벤트 사례, 마이그레이션 히스토리 등 — 이 회사에 맞는 것).
- 각 body 는 **길고 구체적으로**. 마크다운 사용(소제목 ###, 글머리표, `코드/기술명`, 표 가능). 실제 동작 메커니즘·수치·트레이드오프·왜 그렇게 했는지를 풍부하게. 짧게 줄이지 말 것 — 길수록 좋다.
- 한국어로 쓰되 기술/제품/컴포넌트 이름은 영문 그대로.

The why_language / why_architecture / summary / desc / deep_dive body fields MUST be Korean. Tech/node names in English.

DIAGRAM RULES (this is the most important field — it is rendered as a visual architecture map):
- Valid Mermaid `flowchart TD` (or LR) syntax. 8-16 nodes covering the END-TO-END system for THIS company's domain.
- Group nodes into `subgraph` layers that fit the domain, e.g.: Client/Edge, API/Gateway, Core Services, Data/Storage, Streaming/Async, Infra/Platform. Use the layers that actually matter for this company.
- EVERY node label MUST name the concrete tech in that box using a <br/> line. ALWAYS wrap labels in double quotes. Example node: `GW["API Gateway<br/>Zuul + Envoy"]`.
- Show real data flow with arrows; label key edges where useful: `GW -->|gRPC| SVC`.
- Use ONLY ascii node ids (letters/digits). NEVER put parentheses, quotes, or unescaped special chars inside labels — use <br/> for line breaks. Keep it parseable.
- Make it specific to this company's actual architecture (e.g. Netflix: Zuul→microservices→EVCache/Cassandra, Kafka, Spinnaker on AWS; Discord: WebSocket Gateway→Elixir sessions→ScyllaDB, Rust hot paths).

The why_language / why_architecture / summary / desc fields MUST be Korean. Tech/node names in English.
For github.repos give 2-5 FLAGSHIP, REAL, well-known public repos for this company (omit if the company has none). Do not invent repo names."""


def _extract_json(text: str) -> dict | None:
    """모델 응답에서 첫 번째 JSON 오브젝트를 안전하게 추출."""
    text = text.strip()
    if text.startswith("```"):
        # ```json ... ``` 펜스 제거
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _call_claude(prompt: str, timeout: int = 300, extra: list | None = None) -> str | None:
    """로컬 claude CLI 를 headless 로 호출해 결과 텍스트를 반환. 실패 시 None.
    extra 로 추가 CLI 인자를 넘길 수 있다(예: 웹검색 허용 --allowedTools)."""
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json", *(extra or [])],
            capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        print("[refine] claude CLI 를 찾을 수 없습니다. 건너뜀.", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("[refine] claude 호출 타임아웃.", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(f"[refine] claude 종료코드 {proc.returncode}: {proc.stderr[:200]}", file=sys.stderr)
        return None
    try:
        wrapper = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout  # --output-format json 미지원 빌드 대비
    return wrapper.get("result", "")


# ── GitHub API 검증/보강 ───────────────────────────────────────────────
# LLM 이 준 repo 가 실존하는지 확인하고 star/lang/설명을 보강한다. 환각 repo 는 제거.
# 인증 없이도 동작(시간당 60회 제한). GITHUB_TOKEN 이 있으면 헤더에 실어 한도를 늘린다.

_REPO_RE = re.compile(r"github\.com/([^/\s]+)/([^/\s#?]+)")


def _gh_api(path: str) -> dict | None:
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"User-Agent": "jobseeker-radar", "Accept": "application/vnd.github+json"},
    )
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 403:  # rate limit
            print("[github] API rate limit — 보강 생략(GITHUB_TOKEN 설정 권장)", file=sys.stderr)
            raise
        return None  # 404 등 → repo 없음
    except Exception:
        return None


def enrich_github(company: dict) -> None:
    """company['github'].repos 의 각 repo 를 GitHub API 로 검증·보강. 없는 repo 는 버린다."""
    gh = company.get("github")
    if not gh or not gh.get("repos"):
        return
    kept = []
    for repo in gh["repos"]:
        m = _REPO_RE.search(repo.get("url", "") or repo.get("name", ""))
        if not m:
            continue
        owner, name = m.group(1), m.group(2).removesuffix(".git")
        try:
            meta = _gh_api(f"/repos/{owner}/{name}")
        except Exception:
            kept.append(repo)  # rate limit → 검증 못 함, 일단 보존
            continue
        if not meta:
            continue  # 실존하지 않음 → 제거
        repo["name"] = meta["full_name"]
        repo["url"] = meta["html_url"]
        repo["stars"] = meta.get("stargazers_count", 0)
        repo["lang"] = meta.get("language") or repo.get("lang", "")
        if meta.get("description") and not repo.get("desc"):
            repo["desc"] = meta["description"]
        kept.append(repo)
        time.sleep(0.7)  # 미인증 한도(60/h) 배려
    gh["repos"] = sorted(kept, key=lambda r: -(r.get("stars") or 0))


def _refine_one(company: dict, with_github: bool = True) -> bool:
    cur = {
        "languages": company.get("languages", []),
        "stack": company.get("stack", {}),
        "architecture": company.get("architecture", []),
    }
    covered = [s.get("topic", "") for s in (company.get("deep_dive") or [])]
    prompt = REFINE_PROMPT.format(
        name=company["name"], country=company.get("country", ""),
        domain=company.get("domain", ""),
        current=json.dumps(cur, ensure_ascii=False),
        covered=", ".join(covered) if covered else "(없음)",
    )
    text = _call_claude(prompt)
    if not text:
        return False
    data = _extract_json(text)
    if not data:
        print(f"[refine] {company['name']}: JSON 파싱 실패, 건너뜀.", file=sys.stderr)
        return False
    for fld in ("languages", "stack", "architecture", "diagram", "why_language",
                "why_architecture", "summary", "sources", "github"):
        if data.get(fld):
            company[fld] = data[fld]
    added = merge_deep_dive(company, data.get("deep_dive_add"))   # 누적(절대 축소 X)
    if with_github:
        enrich_github(company)
    company["research_status"] = "llm-refined"
    company["updated_at"] = _today()
    print(f"[refine]   딥다이브 +{added}개 토픽 (누적 {len(company.get('deep_dive') or [])})")
    return True


def _stalest(companies: list[dict], n: int) -> list[dict]:
    """가장 오래 갱신 안 된 n개(seed 우선, 그다음 updated_at 오름차순)."""
    return sorted(
        companies,
        key=lambda c: (c.get("research_status") == "llm-refined", c.get("updated_at", "")),
    )[:n]


def cmd_patch(paths: list[str], do_github: bool) -> None:
    """{key, ...부분필드} 배열 파일들을 key 로 매칭해 기존 회사에 병합(다이어그램/깃허브 시드용)."""
    companies = load()
    if not companies:
        print("[patch] 데이터가 없습니다. 먼저 --init 하세요.", file=sys.stderr)
        return
    by_key = {c["key"]: c for c in companies}
    n = 0
    for p in paths:
        for patch in json.loads(Path(p).read_text(encoding="utf-8")):
            c = by_key.get(patch.get("key"))
            if not c:
                continue
            for fld in ("diagram", "github", "languages", "stack", "architecture",
                        "why_language", "why_architecture", "summary", "sources"):
                if patch.get(fld):
                    c[fld] = patch[fld]
            if patch.get("deep_dive"):          # 누적 병합(덮어쓰기 X)
                merge_deep_dive(c, patch["deep_dive"])
            if patch.get("debate"):             # 아키텍처 토론 결과(Workflow/CLI 산출)
                c["debate"] = patch["debate"]
            if patch.get("interview"):          # 채용 전형 가이드
                c["interview"] = patch["interview"]
            if do_github:
                try:
                    enrich_github(c)
                except Exception:
                    pass
            n += 1
    doc = save(companies)
    print(f"[patch] {n}개사 병합 완료 → {DATA} (다이어그램 보유 "
          f"{sum(1 for c in doc['companies'] if c.get('diagram'))}개)")


def cmd_github(n: int) -> None:
    """github.repos 가 미검증인 회사들을 골라 GitHub API 로 검증·보강."""
    companies = load()
    targets = [c for c in companies if c.get("github", {}).get("repos")
               and any("stars" not in r for r in c["github"]["repos"])][:n]
    for c in targets:
        print(f"[github] {c['name']} repo 검증 중…")
        try:
            enrich_github(c)
        except Exception:
            break
        save(companies)
    print(f"[github] {len(targets)}개사 처리")


def cmd_refine(n: int, loop: bool, interval: int) -> None:
    while True:
        companies = load()
        if not companies:
            print("[refine] 데이터가 없습니다. 먼저 --init 으로 시드를 넣으세요.", file=sys.stderr)
            return
        targets = _stalest(companies, n)
        done = 0
        for c in targets:
            print(f"[refine] {c['name']} ({c['country']}/{c.get('domain','')}) 리서치 중…")
            if _refine_one(c):
                done += 1
                save(companies)  # 매 회사 저장 → 중단돼도 진행분 보존
        doc = save(companies)
        print(f"[refine] {done}/{len(targets)}개사 갱신 완료. 누적 리파인 {doc['refined']}/{doc['total']}")
        if not loop:
            return
        print(f"[refine] {interval}s 대기 후 다음 사이클…")
        time.sleep(interval)


# ── 아키텍처 토론(멀티 에이전트: 설계자↔검토자 + 정리자) ─────────────────
# claude CLI 를 역할별로 여러 번 호출해 '둘이 대화로 설계를 완성'하는 과정을 만든다.
# 설계자가 아키텍처 후보 여러 개 제안 → 검토자가 반박 → 설계자 재반론(N라운드) →
# 정리자가 합의 결론. 전 과정을 transcript 로 남겨 뷰어에서 대화처럼 보여준다.

def _facts(company: dict) -> str:
    keep = {k: company.get(k) for k in ("name", "country", "domain", "languages",
                                        "stack", "architecture", "summary")}
    return json.dumps(keep, ensure_ascii=False)


ARCHITECT_PROMPT = """너는 시니어 소프트웨어 아키텍트(설계자)다. 아래 회사의 도메인·규모에 맞는
시스템 아키텍처를 **서로 다른 2~3개 후보**로 제안하라. 각 후보는 접근이 확연히 달라야 한다
(예: 모놀리식 vs MSA, 동기 vs 이벤트소싱, 자체 인프라 vs 매니지드).

회사 정보: {facts}

STRICT JSON ONLY (펜스/산문 금지):
{{
  "architectures": [
    {{"name": "변형 A: <짧은 이름>", "summary": "한국어 2~3문장",
      "diagram": "flowchart TD ... (Mermaid, 6~12노드, 라벨 더블쿼트+<br/>로 기술명, ascii id, 괄호 금지)",
      "pros": ["한국어 장점"], "cons": ["한국어 단점/리스크"]}}
  ],
  "opening": "설계자로서 왜 이렇게 후보를 나눴는지, 어디에 핵심 트레이드오프가 있는지 여는 발언(한국어 마크다운, 길어도 됨)"
}}"""

CRITIC_PROMPT = """너는 깐깐한 시니어 아키텍트(검토자)다. 아래 설계자의 제안을 비판적으로 검토하라.
이 회사의 도메인·트래픽·실패 모드를 근거로 **구체적으로 반박/질문**하라
("이 트래픽이면 이 DB가 병목 아냐?", "이 일관성 모델로 정산이 맞아?", "이 비용/운영부담은?",
"엣지 케이스/장애 시나리오는?"). 칭찬보다 약점·누락·트레이드오프를 파고들어라.

회사 정보: {facts}
현재까지의 토론:
{transcript}

STRICT JSON ONLY: {{"text": "검토자 발언(한국어 마크다운, 구체적이고 길게)"}}"""

REBUT_PROMPT = """너는 설계자다. 검토자의 지적에 답하라. 인정할 건 인정하고, 설계를 보강/수정하거나
특정 후보로 좁혀라. 필요하면 새 절충안을 제시하라(한국어, 구체적으로).

회사 정보: {facts}
현재까지의 토론:
{transcript}

STRICT JSON ONLY: {{"text": "설계자 재반론(한국어 마크다운, 길게)"}}"""

SYNTH_PROMPT = """너는 중립적인 정리자다. 아래 설계자·검토자의 토론을 종합해 **합의된 결론**을 내려라.
어느 후보(또는 하이브리드)를 택할지, 그 근거, 토론에서 드러난 핵심 인사이트, 아직 열린 질문을 정리하라.

회사 정보: {facts}
아키텍처 후보: {candidates}
전체 토론:
{transcript}

STRICT JSON ONLY:
{{
  "chosen": "택한 후보명 또는 '하이브리드: ...'",
  "rationale": "왜 그렇게 합의했는지(한국어 마크다운, 길게)",
  "key_insights": ["토론에서 나온 핵심 통찰(한국어)"],
  "open_questions": ["더 검증이 필요한 열린 질문(한국어)"]
}}"""


def _fmt_transcript(turns: list[dict]) -> str:
    label = {"architect": "설계자", "critic": "검토자", "synthesizer": "정리자"}
    return "\n\n".join(f"[{label.get(t['role'], t['role'])} R{t['round']}]\n{t['text']}"
                       for t in turns) or "(아직 없음)"


def _debate_one(company: dict, rounds: int = 2) -> bool:
    facts = _facts(company)
    # 1) 설계자: 후보 제안 + 여는 발언
    data = _extract_json(_call_claude(ARCHITECT_PROMPT.format(facts=facts)) or "")
    if not data or not data.get("architectures"):
        print(f"[debate] {company['name']}: 설계자 제안 실패, 건너뜀.", file=sys.stderr)
        return False
    candidates = data["architectures"]
    transcript = [{"round": 1, "role": "architect", "text": data.get("opening", "")}]
    # 2) 검토자 ↔ 설계자 N라운드
    for r in range(1, rounds + 1):
        crit = _extract_json(
            _call_claude(CRITIC_PROMPT.format(facts=facts, transcript=_fmt_transcript(transcript))) or "")
        if crit and crit.get("text"):
            transcript.append({"round": r, "role": "critic", "text": crit["text"]})
        reb = _extract_json(
            _call_claude(REBUT_PROMPT.format(facts=facts, transcript=_fmt_transcript(transcript))) or "")
        if reb and reb.get("text"):
            transcript.append({"round": r + 1, "role": "architect", "text": reb["text"]})
    # 3) 정리자: 합의 결론
    verdict = _extract_json(_call_claude(SYNTH_PROMPT.format(
        facts=facts, candidates=json.dumps(candidates, ensure_ascii=False),
        transcript=_fmt_transcript(transcript))) or "") or {}
    company["debate"] = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "rounds": rounds,
        "architectures": candidates,
        "transcript": transcript,
        "verdict": {
            "chosen": verdict.get("chosen", ""),
            "rationale": verdict.get("rationale", ""),
            "key_insights": verdict.get("key_insights", []),
            "open_questions": verdict.get("open_questions", []),
        },
    }
    company["updated_at"] = _today()
    print(f"[debate]   후보 {len(candidates)}개 · 전사 {len(transcript)}턴 · 합의 '{verdict.get('chosen','?')[:30]}'")
    return True


def cmd_debate(n: int, rounds: int, loop: bool, interval: int) -> None:
    while True:
        companies = load()
        if not companies:
            print("[debate] 데이터가 없습니다. 먼저 --init 하세요.", file=sys.stderr)
            return
        # 토론 없는 회사 우선, 그다음 가장 오래된 것
        targets = sorted(companies, key=lambda c: (bool(c.get("debate")),
                                                   c.get("debate", {}).get("generated_at", "")))[:n]
        done = 0
        for c in targets:
            print(f"[debate] {c['name']} ({c.get('domain','')}) 토론 중… (라운드 {rounds})")
            if _debate_one(c, rounds):
                done += 1
                save(companies)
        doc = save(companies)
        have = sum(1 for c in doc["companies"] if c.get("debate"))
        print(f"[debate] {done}/{len(targets)}개사 토론 완료. 누적 토론 {have}/{doc['total']}")
        if not loop:
            return
        print(f"[debate] {interval}s 대기 후 다음 사이클…")
        time.sleep(interval)


# ── 공개 면접 후기 수집(--reviews) ─────────────────────────────────────
# claude CLI 웹검색으로 공개 블로그/커리어 페이지의 면접 후기를 찾아 링크+요약으로 수집한다.
# 사적 후기 사이트(Blind/잡플래닛/Glassdoor 등)는 차단하고, URL 실존을 HTTP 로 검증해
# 환각 링크를 버린다. interview.reviews 에 URL 기준 중복제거하며 누적(절대 축소 안 함).

BLOCKED_REVIEW_DOMAINS = (
    "teamblind.com", "blind.com", "jobplanet.co.kr", "jobplanet.com",
    "glassdoor.com", "glassdoor.co.kr", "linkedin.com",
)


def _url_alive(url: str) -> bool:
    """공개 URL 이 실제로 살아있는지(<400) 확인하고 차단 도메인을 거른다."""
    if not url.startswith(("http://", "https://")):
        return False
    if any(d in url.lower() for d in BLOCKED_REVIEW_DOMAINS):
        return False
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": "Mozilla/5.0 (compatible; jobseeker-radar/1.0)",
        "Accept": "text/html",
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status < 400
    except urllib.error.HTTPError as e:
        return e.code < 400
    except Exception:
        return False


REVIEWS_PROMPT = """웹검색을 사용해 아래 회사의 '개발자 채용/면접 후기' 를 다룬 **공개 글**을 찾아라.
대상: 개인 블로그(velog, tistory, 브런치, Medium, github.io 등), 회사 공식 채용/기술 블로그.
제외(절대 포함 금지): Blind(teamblind), 잡플래닛(jobplanet), Glassdoor, LinkedIn, 로그인/유료가 가려진 글.

회사: {name} ({country})

실제로 검색해서 찾은 URL 만 사용하라(존재하지 않는 URL 지어내기 금지). 2~5개.
STRICT JSON ONLY(펜스/산문 금지):
{{"reviews": [
  {{"title": "글 제목", "url": "https://...", "summary": "면접 과정·난이도·팁 요약(한국어 2~3문장)", "source": "velog|tistory|브런치|Medium|회사블로그 등", "date": "YYYY-MM 있으면"}}
]}}"""


def merge_reviews(interview: dict, new_reviews: list) -> int:
    existing = interview.get("reviews") or []
    seen = {r.get("url", "").rstrip("/") for r in existing}
    added = 0
    for r in new_reviews or []:
        url = (r.get("url") or "").strip()
        title = (r.get("title") or "").strip()
        if not url or not title or url.rstrip("/") in seen:
            continue
        if not _url_alive(url):
            print(f"[reviews]   드롭(검증 실패/차단): {url[:60]}", file=sys.stderr)
            continue
        rec = {
            "title": title, "url": url,
            "summary": (r.get("summary") or "").strip(),
            "source": (r.get("source") or "").strip(),
        }
        if r.get("date"):
            rec["date"] = str(r["date"]).strip()
        existing.append(rec)
        seen.add(url.rstrip("/"))
        added += 1
    interview["reviews"] = existing
    return added


def _reviews_one(company: dict) -> bool:
    text = _call_claude(
        REVIEWS_PROMPT.format(name=company["name"], country=company.get("country", "")),
        extra=["--allowedTools", "WebSearch,WebFetch"],
    )
    if not text:
        return False
    data = _extract_json(text)
    if not data:
        print(f"[reviews] {company['name']}: JSON 파싱 실패.", file=sys.stderr)
        return False
    iv = company.setdefault("interview", {"process": [], "focus": [], "tips": [], "sources": []})
    added = merge_reviews(iv, data.get("reviews"))
    company["updated_at"] = _today()
    print(f"[reviews]   +{added}개 후기 (누적 {len(iv.get('reviews') or [])})")
    return added > 0


DAY_SECONDS = 86400  # 하루. 적응형 백오프는 이 값을 절대 넘지 않는다.


def cmd_reviews(n: int, loop: bool, interval: int,
                max_interval: int = DAY_SECONDS, backoff: float = 2.0) -> None:
    """공개 후기를 수집한다. --loop 면 적응형 간격으로 돈다:
    - 새 후기를 찾으면 간격을 시작값(interval)으로 리셋해 빠르게 더 담는다.
    - 못 찾으면 간격을 backoff 배씩 늘린다(점점 뜸하게).
    - 단, 어떤 경우에도 하루(86400s)를 넘지 않는다."""
    start = max(60, interval)
    cap = min(max(start, max_interval), DAY_SECONDS)   # 24h 하드 캡
    cur = start
    while True:
        companies = load()
        if not companies:
            print("[reviews] 데이터가 없습니다.", file=sys.stderr)
            return
        # 전형 가이드 있는 회사 우선 → 후기 적은 곳 → updated_at 오래된 순
        targets = sorted(
            companies,
            key=lambda c: (
                not bool(c.get("interview")),
                len((c.get("interview") or {}).get("reviews") or []),
                c.get("updated_at", ""),
            ),
        )[:n]
        done = 0
        for c in targets:
            print(f"[reviews] {c['name']} 공개 후기 검색 중…")
            if _reviews_one(c):
                done += 1
                save(companies)
        doc = save(companies)
        have = sum(1 for c in doc["companies"] if (c.get("interview") or {}).get("reviews"))
        print(f"[reviews] {done}/{len(targets)}개사 수집. 후기 보유 {have}/{doc['total']}")
        if not loop:
            return
        # 적응형 간격: 새 후기 있으면 짧게 리셋, 없으면 늘림(하루 캡)
        if done > 0:
            cur = start
        else:
            cur = min(int(cur * backoff), cap)
        mins = cur / 60
        print(f"[reviews] 다음 사이클까지 {cur}s(~{mins:.0f}분) 대기 "
              f"(새 후기 {done}개 → 간격 {'리셋' if done > 0 else '증가'})")
        time.sleep(cur)


# ── 엔트리포인트 ──────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="기술 스택 레이더 빌더")
    ap.add_argument("--init", nargs="+", metavar="SEED.json",
                    help="시드 JSON 배열 파일들을 병합해 최초 생성")
    ap.add_argument("--patch", nargs="+", metavar="PATCH.json",
                    help="{key,...} 부분필드 배열을 key 매칭으로 병합(다이어그램/깃허브 시드)")
    ap.add_argument("--refine", type=int, metavar="N", default=0,
                    help="가장 오래된 N개사를 claude CLI 로 갱신")
    ap.add_argument("--github", type=int, metavar="N", default=0,
                    help="github repo 미검증 N개사를 GitHub API 로 검증·보강")
    ap.add_argument("--debate", type=int, metavar="N", default=0,
                    help="N개사를 멀티 에이전트 토론(설계자↔검토자+정리자)으로 아키텍처 도출")
    ap.add_argument("--rounds", type=int, default=2, help="토론 라운드 수(기본 2)")
    ap.add_argument("--reviews", type=int, metavar="N", default=0,
                    help="N개사의 공개 면접 후기를 claude 웹검색으로 수집·검증·누적")
    ap.add_argument("--no-github", action="store_true", help="--patch 시 GitHub API 검증 생략")
    ap.add_argument("--loop", action="store_true", help="--refine/--debate/--reviews 를 무한 반복")
    ap.add_argument("--interval", type=int, default=1800,
                    help="루프 간격(초). --reviews 에선 적응형 백오프의 시작/최소 간격")
    ap.add_argument("--max-interval", type=int, default=DAY_SECONDS,
                    help="--reviews 적응형 백오프 상한(초). 하루(86400)로 하드 캡됨")
    ap.add_argument("--backoff", type=float, default=2.0,
                    help="--reviews 후기 못 찾을 때 간격 증가 배수(기본 2.0)")
    args = ap.parse_args()

    if args.init:
        cmd_init(args.init)
    elif args.patch:
        cmd_patch(args.patch, do_github=not args.no_github)
    elif args.github > 0:
        cmd_github(args.github)
    elif args.debate > 0:
        cmd_debate(args.debate, args.rounds, args.loop, args.interval)
    elif args.reviews > 0:
        cmd_reviews(args.reviews, args.loop, args.interval,
                    max_interval=args.max_interval, backoff=args.backoff)
    elif args.refine > 0:
        cmd_refine(args.refine, args.loop, args.interval)
    else:
        doc = save(load())  # 집계만 재계산
        print(f"[build] 집계 재계산 완료 — {doc['total']}개사, 리파인 {doc['refined']}개 → {DATA}")


if __name__ == "__main__":
    main()
