#!/usr/bin/env python3
"""취업 브리핑 검증 — 뷰어가 읽기 전에 형식이 깨졌는지 본다.

    python3 guide-engine/validate.py             # 전체 검사
    python3 guide-engine/validate.py <slug>      # 회사 하나만
    python3 guide-engine/validate.py --gaps      # 이번 사이클의 대상 (사다리 그대로)
    python3 guide-engine/validate.py --gaps-all  # 보강 후보 전량

역설계 엔진의 validate.py 와 같은 자리를 지키지만 검사 대상이 다르다. 여기서 제일
중요한 검사는 **study[].quote 가 공고 원문에 글자 그대로 있는가**이다 — 뷰어는 그
문자열로 JD 본문을 하이라이트하므로, 한 글자만 달라도 화면에서 조용히 사라진다.
조용히 사라지는 실패는 다음 사이클이 알아채지 못하므로 여기서 잡는다.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "jd-viewer" / "public" / "guide"
INDEX = GUIDE / "index.json"
COMPANIES = GUIDE / "companies"
JOBS = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
STATE = Path(__file__).resolve().parent / "state"
QUEUE = STATE / "QUEUE.md"
CACHE = STATE / ".jobs_cache.json"

STATUSES = {"in_progress", "done"}
CONFIDENCE = {"confirmed", "inferred", "unknown"}
FROM = {"qualification", "preference", "task"}
PRIORITY = {"core", "high", "nice"}
BASIS = {"posting", "public_data", "market"}
SITES = {"wanted", "jumpit", "jobkorea", "saramin", "dev", "remote", "ats"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MIN_STUDY = 3          # 공고 하나가 이 아래면 아직 안 채운 것으로 본다
QUEUE_TARGET = 3       # 대기열이 이 아래로 떨어지면 후보 조사를 돈다
STALE_DAYS = 60        # 이만큼 지난 회사는 재방문 대상
EXPAND_CAP = 12        # 확장이 사다리 2순위를 쥘 수 있는 공고 수 상한.
#                        한 회사를 완주할 때까지 안 넘어가는 규칙은 얕은 브리핑을
#                        막지만, 모집중 67건짜리 회사가 걸리면 대기열이 하루 넘게
#                        멈춘다(공고는 그동안 마감된다). 12건이면 얕지 않으므로
#                        그 뒤로는 신규에 자리를 내주고, 남은 공고는 보강에서 잇는다.
SHOW_NEXT = 5          # --gaps 가 대상 말고 더 보여줄 건수 (루프의 맥락을 아낀다)


# ── 회사명 정규화 ────────────────────────────────────────────────────────
# jd-viewer/src/lib/companyMark.ts 의 normalizeCompany() 와 **같은 규칙**이어야 한다.
# 여기서 만든 aliases 로 뷰어가 공고와 브리핑을 잇기 때문에, 두 구현이 어긋나면
# 데이터는 멀쩡한데 화면에만 아무것도 안 뜨는 상태가 된다.
def norm_company(name: str) -> str:
    s = re.sub(r"\((주|유|재|사)\)", "", name or "")
    s = re.sub(r"(주식회사|유한회사)", "", s)
    s = re.sub(r"\s*\([^)]*\)\s*", "", s)
    return re.sub(r"\s+", "", s).strip()


# ── 공고 캐시 ────────────────────────────────────────────────────────────
# all_jobs_enriched.json 은 60MB 다. 매 사이클 통째로 읽으면 8GB 머신에서 다른 일을
# 방해하므로, 필요한 것만 뽑아 캐시한다. 본문(JD 원문)은 **브리핑이 있는 회사와
# 대기열에 오른 회사만** 담는다 — quote 검사는 그 회사들에만 필요하다.
def load_jobs(tracked: set[str]) -> dict:
    if not JOBS.exists():
        return {"mtime": 0, "tracked": [], "by_url": {}, "counts": {}, "names": {}}
    mtime = JOBS.stat().st_mtime
    if CACHE.exists():
        try:
            c = json.loads(CACHE.read_text(encoding="utf-8"))
            if c.get("mtime") == mtime and tracked.issubset(set(c.get("tracked", []))):
                return c
        except Exception:
            pass

    by_url: dict[str, dict] = {}
    counts: dict[str, int] = {}
    names: dict[str, str] = {}
    with JOBS.open(encoding="utf-8") as f:
        data = json.load(f)
    for j in data:
        n = norm_company(j.get("company", ""))
        if not n:
            continue
        names.setdefault(n, j.get("company", ""))
        if j.get("status") != "closed":
            counts[n] = counts.get(n, 0) + 1
        if n in tracked:
            by_url[j.get("url", "")] = {
                "company": j.get("company", ""),
                "norm": n,
                "title": j.get("title", ""),
                "site": j.get("site", ""),
                "career": j.get("career", ""),
                "status": j.get("status", "active"),
                # quote 검사에 쓰는 세 절. full_jd 는 안 담는다 — 캐시가 몇 배로 붓는다.
                "text": "\n".join([
                    j.get("main_tasks", "") or "",
                    j.get("qualifications", "") or "",
                    j.get("preferences", "") or "",
                ]),
            }
    cache = {"mtime": mtime, "tracked": sorted(tracked), "by_url": by_url,
             "counts": counts, "names": names}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def norm_text(s: str) -> str:
    """quote 대조용. 공백만 접는다 — 그 이상 손대면 '있는 셈 치는' 검사가 된다."""
    return re.sub(r"\s+", " ", (s or "")).strip()


# ── 검사 ────────────────────────────────────────────────────────────────
class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)


def check_claim(r: Report, where: str, obj: dict, conf_key: str = "confidence",
                src_key: str = "sources") -> None:
    conf = obj.get(conf_key)
    if conf is None:
        return
    if conf not in CONFIDENCE:
        r.err(f"{where}: {conf_key}={conf!r} 는 허용되지 않는 값")
        return
    if conf == "confirmed" and not obj.get(src_key):
        r.err(f"{where}: confirmed 인데 {src_key} 가 비었다 (PROMPT.md 5단계)")


def check_sources(r: Report, where: str, sources) -> None:
    for i, s in enumerate(sources or []):
        if not isinstance(s, dict):
            r.err(f"{where}.sources[{i}]: 객체가 아니다")
            continue
        if not s.get("url"):
            r.err(f"{where}.sources[{i}]: url 이 없다")
        if not s.get("title"):
            r.warn(f"{where}.sources[{i}]: title 이 없다")


def check_company(r: Report, path: Path, doc: dict, jobs: dict) -> dict:
    """회사 파일 하나. 돌려주는 것은 --gaps 가 쓸 요약이다."""
    w = path.name
    slug = doc.get("slug", "")
    if not SLUG_RE.match(slug or ""):
        r.err(f"{w}: slug 가 없거나 형식이 아니다 ({slug!r})")
    if slug and path.stem != slug:
        r.err(f"{w}: 파일명과 slug 가 다르다 ({path.stem} vs {slug})")
    if not doc.get("name"):
        r.err(f"{w}: name 이 없다")
    if doc.get("status") not in STATUSES:
        r.err(f"{w}: status={doc.get('status')!r}")
    if not DATE_RE.match(doc.get("updated_at", "") or ""):
        r.err(f"{w}: updated_at 이 YYYY-MM-DD 가 아니다")
    aliases = doc.get("aliases") or []
    if not aliases:
        r.err(f"{w}: aliases 가 비었다 — 뷰어가 이 브리핑을 영영 못 찾는다")
    for a in aliases:
        if a != norm_company(a):
            r.err(f"{w}: aliases 의 {a!r} 가 정규화되지 않았다 (→ {norm_company(a)!r})")

    co = doc.get("company") or {}
    check_claim(r, f"{w}.company.business", co, "business_confidence", "business_sources")
    check_sources(r, f"{w}.company.business", co.get("business_sources"))
    for i, s in enumerate(co.get("scale") or []):
        check_claim(r, f"{w}.company.scale[{i}]", s)
        check_sources(r, f"{w}.company.scale[{i}]", s.get("sources"))
    domain_names = set()
    for i, d in enumerate(co.get("domains") or []):
        if not d.get("name"):
            r.err(f"{w}.company.domains[{i}]: name 이 없다")
        domain_names.add(d.get("name"))
        check_claim(r, f"{w}.company.domains[{i}]", d)
        check_sources(r, f"{w}.company.domains[{i}]", d.get("sources"))

    # 수익원 → 도메인. 이 연결이 끊기면 도메인 목록은 기술 나열로 읽히고, 지원자는
    # 자기가 만질 코드가 어느 돈에 붙어 있는지 알 수 없다 (PROMPT.md 3단계).
    linked_domains = set()
    no_domain: list[str] = []
    for i, rv in enumerate(co.get("revenue") or []):
        where = f"{w}.company.revenue[{i}]"
        if not rv.get("name") or not rv.get("how"):
            r.err(f"{where}: name/how 가 있어야 한다")
        names = rv.get("domains") or []
        if not names:
            no_domain.append(rv.get("name", f"#{i}"))
        for n in names:
            if n not in domain_names:
                r.err(f"{where}: domains 의 {n!r} 가 company.domains 에 없다 — 오타이거나 "
                      f"안 쓴 도메인이다")
            else:
                linked_domains.add(n)
        check_claim(r, where, rv)
        check_sources(r, where, rv.get("sources"))
    for n in domain_names - linked_domains:
        if co.get("revenue"):
            r.warn(f"{w}.company.domains: {n!r} 는 어느 수익원도 가리키지 않는다 — "
                   f"신사업이면 why 에 그렇게 쓰고, 아니면 도메인을 다시 나눈다")
    for i, s in enumerate(co.get("signals") or []):
        if not s.get("reading") or not s.get("evidence"):
            r.err(f"{w}.company.signals[{i}]: reading/evidence 가 있어야 한다")
        if s.get("confidence") not in (None, "inferred"):
            r.err(f"{w}.company.signals[{i}]: signals 는 전부 inferred 다 (PROMPT.md 3단계)")

    sal = doc.get("salary")
    if sal:
        for i, b in enumerate(sal.get("bands") or []):
            where = f"{w}.salary.bands[{i}]"
            lo, hi = b.get("low"), b.get("high")
            if not isinstance(lo, int) or not isinstance(hi, int):
                r.err(f"{where}: low/high 는 만원 단위 정수다 ({lo!r}, {hi!r})")
            elif lo > hi:
                r.err(f"{where}: low({lo}) > high({hi})")
            elif hi > 100000:
                r.warn(f"{where}: high={hi} — 만원 단위가 맞는지 확인 (원 단위로 쓴 듯)")
            if b.get("basis") not in BASIS:
                r.err(f"{where}: basis={b.get('basis')!r}")
            if b.get("basis") == "market" and b.get("confidence") != "inferred":
                r.err(f"{where}: basis=market 은 반드시 inferred 다 (PROMPT.md 2°단계)")
            check_claim(r, where, b)
            check_sources(r, where, b.get("sources"))
        if not sal.get("note"):
            r.warn(f"{w}.salary: note 가 없다 — 이 숫자를 어떻게 읽어야 하는지")

    for i, p in enumerate(doc.get("people") or []):
        where = f"{w}.people[{i}]"
        if not p.get("name") or not p.get("role"):
            r.err(f"{where}: name/role 이 있어야 한다")
        works = p.get("public_work") or []
        if not works:
            r.err(f"{where}: public_work 가 없다 — 링크 없는 사람은 넣지 않는다 (PROMPT.md 2″단계)")
        for k, pw in enumerate(works):
            if not pw.get("url"):
                r.err(f"{where}.public_work[{k}]: url 이 없다")
        check_claim(r, where, p)
        check_sources(r, where, p.get("sources"))

    # ── 공고 ──
    thin: list[str] = []
    no_edge: list[str] = []
    study_total = 0
    seen_urls: set[str] = set()
    for i, p in enumerate(doc.get("postings") or []):
        where = f"{w}.postings[{i}]"
        url = p.get("url", "")
        if not url:
            r.err(f"{where}: url 이 없다")
            continue
        if url in seen_urls:
            r.err(f"{where}: url 이 중복이다 ({url})")
        seen_urls.add(url)
        if p.get("site") not in SITES:
            r.err(f"{where}: site={p.get('site')!r}")
        if not p.get("verdict"):
            r.err(f"{where}: verdict 가 없다")

        job = jobs.get("by_url", {}).get(url)
        if job is None:
            # 공고 데이터가 캐시보다 새 브리핑일 수도, 정말 없는 URL 일 수도 있다.
            # 지우라고 하지 않는다 — 마감된 공고를 남기는 것이 이 엔진의 규칙이다.
            r.warn(f"{where}: 공고 데이터에서 이 url 을 못 찾았다 (마감·재크롤 전이면 정상)")
        elif job["status"] == "closed" and not p.get("closed"):
            r.warn(f"{where}: 공고가 마감됐다 — closed: true 를 단다")

        study = p.get("study") or []
        study_total += len(study)
        if len(study) < MIN_STUDY:
            thin.append(url)
        for k, s in enumerate(study):
            sw = f"{where}.study[{k}]"
            for f in ("topic", "why", "gap_check", "drill"):
                if not s.get(f):
                    r.err(f"{sw}: {f} 가 비었다")
            if s.get("from") not in FROM:
                r.err(f"{sw}: from={s.get('from')!r}")
            if s.get("priority") not in PRIORITY:
                r.err(f"{sw}: priority={s.get('priority')!r}")
            q = s.get("quote") or ""
            if not q:
                r.err(f"{sw}: quote 가 비었다 — 뷰어가 하이라이트할 문장이다")
            elif job is not None and norm_text(q) not in norm_text(job["text"]):
                r.err(f"{sw}: quote 가 공고 원문에 없다 — 하이라이트가 조용히 사라진다\n"
                      f"      {q[:60]!r}")
            for m, res in enumerate(s.get("resources") or []):
                if not res.get("url"):
                    r.err(f"{sw}.resources[{m}]: url 이 없다")
        if not (p.get("edge") or []):
            no_edge.append(url)

    return {
        "slug": slug,
        "name": doc.get("name", ""),
        "status": doc.get("status"),
        "hold_reason": doc.get("hold_reason"),
        "aliases": aliases,
        "updated_at": doc.get("updated_at", ""),
        "postings": len(doc.get("postings") or []),
        "study_items": study_total,
        "thin": thin,
        "no_edge": no_edge,
        "no_salary": not bool(sal and (sal.get("bands") or [])),
        "no_revenue": not bool(co.get("revenue")),
        "revenue_no_domain": no_domain,
        "no_domains": not bool(co.get("domains")),
        "no_business": not bool(co.get("business")),
    }


def load_all(r: Report) -> tuple[dict, list[dict], dict]:
    index = {}
    if not INDEX.exists():
        r.err(f"{INDEX} 가 없다")
    else:
        try:
            index = json.loads(INDEX.read_text(encoding="utf-8"))
        except Exception as e:
            r.err(f"index.json 파싱 실패: {e}")

    docs: list[tuple[Path, dict]] = []
    for p in sorted(COMPANIES.glob("*.json")) if COMPANIES.exists() else []:
        try:
            docs.append((p, json.loads(p.read_text(encoding="utf-8"))))
        except Exception as e:
            r.err(f"{p.name} 파싱 실패: {e}")

    tracked = set()
    for _, d in docs:
        tracked |= set(d.get("aliases") or [])
    tracked |= queue_aliases()
    jobs = load_jobs(tracked)

    summaries = [check_company(r, p, d, jobs) for p, d in docs]

    # 같은 회사를 두 슬러그로 쓴 경우. 뷰어는 aliases 로 첫 번째 것만 찾으므로
    # (useGuide.ts 의 `find`), 나중에 쓴 쪽은 다 써 놓고도 화면에 영영 안 뜬다.
    # 엔진은 사이클마다 기억이 없어서 이 실수를 스스로 못 잡는다 — 여기서 잡는다.
    owner: dict[str, str] = {}
    for s in summaries:
        for a in s["aliases"]:
            if a in owner:
                r.err(f"aliases 충돌: {a!r} 를 {owner[a]} 와 {s['slug']} 가 함께 쓴다 "
                      f"— 뷰어는 앞의 하나만 찾는다. 한 슬러그로 합쳐라")
            else:
                owner[a] = s["slug"]

    # index 와 회사 파일의 불일치. 뷰어는 index 만 보고 "브리핑이 있다/없다"를 정하므로
    # 여기가 어긋나면 다 써 놓고도 화면에 안 뜬다.
    by_slug = {s["slug"]: s for s in summaries}
    listed = {c.get("slug"): c for c in (index.get("companies") or [])}
    for slug in by_slug.keys() - listed.keys():
        r.err(f"index.json: {slug} 이 목록에 없다 — 뷰어가 못 찾는다")
    for slug in listed.keys() - by_slug.keys():
        r.err(f"index.json: {slug} 은 목록에만 있고 파일이 없다")
    for slug, c in listed.items():
        s = by_slug.get(slug)
        if not s:
            continue
        for f in ("name", "status", "updated_at"):
            if c.get(f) != s[f]:
                r.err(f"index.json[{slug}].{f} 가 회사 파일과 다르다 ({c.get(f)!r} vs {s[f]!r})")
        if set(c.get("aliases") or []) != set(s["aliases"]):
            r.err(f"index.json[{slug}].aliases 가 회사 파일과 다르다")
        if c.get("postings") != s["postings"] or c.get("study_items") != s["study_items"]:
            r.err(f"index.json[{slug}]: postings/study_items 카운트가 어긋난다 "
                  f"({c.get('postings')}/{c.get('study_items')} vs {s['postings']}/{s['study_items']})")

    return index, summaries, jobs


# ── 대기열 ──────────────────────────────────────────────────────────────
def queue_rows() -> list[str]:
    """QUEUE.md 의 `## 대기` 표에서 회사명 열만 뽑는다."""
    if not QUEUE.exists():
        return []
    rows, on = [], False
    for line in QUEUE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            on = line.strip().startswith("## 대기")
            continue
        if on and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells or not cells[0] or set(cells[0]) <= set("-: "):
                continue
            if cells[0] in ("회사", "회사명"):
                continue
            rows.append(cells[0])
    return rows


def queue_aliases() -> set[str]:
    return {norm_company(x) for x in queue_rows()}


def days_since(d: str) -> int:
    try:
        return (date.today() - datetime.strptime(d, "%Y-%m-%d").date()).days
    except Exception:
        return 9999


# ── --gaps ──────────────────────────────────────────────────────────────
def gaps(index: dict, summaries: list[dict], jobs: dict, errors: list[str], show_all: bool) -> None:
    print("# 취업 브리핑 — 다음 사이클")
    print()

    if errors:
        print("### 이번 사이클의 대상 — 보수 (사다리 1순위)")
        print(f"오류 {len(errors)}건. 새 내용을 쓰지 말고 이것부터 고친다.")
        print()
        for e in errors[:SHOW_NEXT if not show_all else len(errors)]:
            print(f"  ✗ {e}")
        if not show_all and len(errors) > SHOW_NEXT:
            print(f"  … 외 {len(errors) - SHOW_NEXT}건. 전량은 --gaps-all.")
        return

    counts = jobs.get("counts", {})
    names = jobs.get("names", {})
    tracked = {a for s in summaries for a in s["aliases"]}

    # 2순위 — 진행 중인 회사의 안 채운 공고
    queued = queue_rows()
    deferred: list[str] = []
    for s in summaries:
        if s["status"] != "in_progress" or s["hold_reason"]:
            continue
        # 이미 깊이 쓴 회사가 대기열을 계속 막는 것을 끊는다. 대기열이 비어 있으면
        # 양보할 곳이 없으므로 그대로 확장을 이어간다.
        if s["postings"] >= EXPAND_CAP and queued:
            deferred.append(f"{s['name']}({s['postings']}건)")
            continue
        open_urls = [u for u, j in jobs.get("by_url", {}).items()
                     if j["norm"] in s["aliases"] and j["status"] != "closed"]
        done_urls = set()
        doc = json.loads((COMPANIES / f"{s['slug']}.json").read_text(encoding="utf-8"))
        for p in doc.get("postings") or []:
            if len(p.get("study") or []) >= MIN_STUDY:
                done_urls.add(p["url"])
        todo = [u for u in open_urls if u not in done_urls]
        if todo or s["no_business"]:
            print("### 이번 사이클의 대상 — 확장 (사다리 2순위)")
            print(f"**{s['name']}** (`{s['slug']}`) · 모집중 {len(open_urls)}건 중 {len(todo)}건 미완")
            print()
            if s["no_business"]:
                print("  · company.business 부터 (PROMPT.md 3단계)")
            for u in todo[:SHOW_NEXT]:
                j = jobs["by_url"][u]
                print(f"  · {j['title']} — {u}")
            if len(todo) > SHOW_NEXT:
                print(f"  … 외 {len(todo) - SHOW_NEXT}건")
            return
        print(f"※ {s['name']} 은 모집중 공고를 다 채웠다 — status: done 으로 바꿀 때다.")
        print()

    # 3순위 — 대기열
    q = queued
    if q:
        print("### 이번 사이클의 대상 — 신규 (사다리 3순위)")
        if deferred:
            print(f"※ 확장 {', '.join(deferred)} 은 {EXPAND_CAP}건을 넘겨 뒤로 미뤘다 — "
                  f"남은 공고는 보강(4순위)에서 잇는다.")
        print(f"**{q[0]}** — QUEUE.md 맨 위. in_progress 로 바꾸고 PROMPT.md 3단계부터.")
        print()
        n = norm_company(q[0])
        if n in counts:
            print(f"  · 모집중 공고 {counts[n]}건")
        if len(q) > 1:
            print(f"  · 대기 {len(q)}곳: {', '.join(q[1:])}")
        return

    # 4순위 — 보강
    cand: list[tuple[int, str]] = []
    for s in summaries:
        for u in s["thin"]:
            cand.append((1, f"[study<{MIN_STUDY}] {s['name']} — {u}"))
        if s["no_salary"]:
            cand.append((2, f"[salary 없음] {s['name']} (`{s['slug']}`)"))
        if s["no_revenue"]:
            cand.append((3, f"[revenue 없음] {s['name']} (`{s['slug']}`)"))
        for n in s["revenue_no_domain"]:
            cand.append((3, f"[수익원이 도메인과 안 이어짐] {s['name']} — {n}"))
        if s["no_domains"]:
            cand.append((4, f"[domains 없음] {s['name']} (`{s['slug']}`)"))
        for u in s["no_edge"]:
            cand.append((5, f"[edge 없음] {s['name']} — {u}"))
    cand.sort(key=lambda x: x[0])
    if cand:
        print("### 이번 사이클의 대상 — 보강 (사다리 4순위)")
        print(f"  → {cand[0][1]}")
        print()
        rest = cand[1:] if show_all else cand[1:1 + SHOW_NEXT]
        for _, c in rest:
            print(f"  · {c}")
        if not show_all and len(cand) - 1 > SHOW_NEXT:
            print(f"  … 외 {len(cand) - 1 - SHOW_NEXT}건. 전량은 --gaps-all.")
        return

    # 5순위 — 재방문
    stale = sorted((s for s in summaries if days_since(s["updated_at"]) > STALE_DAYS),
                   key=lambda s: s["updated_at"])
    if stale:
        s = stale[0]
        print("### 이번 사이클의 대상 — 재방문 (사다리 5순위)")
        print(f"**{s['name']}** (`{s['slug']}`) — {days_since(s['updated_at'])}일 전 갱신")
        return

    # 6순위 — 후보 조사
    print("### 이번 사이클의 대상 — 후보 조사 (사다리 6순위)")
    print(f"대기열 {len(q)}곳 (목표 {QUEUE_TARGET}). 아래는 브리핑이 없는 회사를 "
          f"모집중 공고 수로 줄 세운 것이다. **그대로 옮기지 말고** PROMPT.md 2⁗단계로 거른다.")
    print()
    pool = sorted(((c, n) for n, c in counts.items() if n not in tracked),
                  reverse=True)[:15 if show_all else 10]
    for c, n in pool:
        print(f"  · {names.get(n, n)} — 모집중 {c}건")


# ── main ────────────────────────────────────────────────────────────────
def main() -> int:
    args = sys.argv[1:]
    want_gaps = "--gaps" in args or "--gaps-all" in args
    show_all = "--gaps-all" in args
    only = [a for a in args if not a.startswith("--")]

    r = Report()
    index, summaries, jobs = load_all(r)
    if only:
        summaries = [s for s in summaries if s["slug"] in only]

    if want_gaps:
        gaps(index, summaries, jobs, r.errors, show_all)
        return 0

    for e in r.errors:
        print(f"✗ {e}")
    for w in r.warns:
        print(f"! {w}")
    n_post = sum(s["postings"] for s in summaries)
    n_study = sum(s["study_items"] for s in summaries)
    print(f"\n회사 {len(summaries)}곳 · 공고 {n_post}건 · 학습 항목 {n_study}개 "
          f"· 오류 {len(r.errors)} · 경고 {len(r.warns)}")
    return 1 if r.errors else 0


if __name__ == "__main__":
    sys.exit(main())
