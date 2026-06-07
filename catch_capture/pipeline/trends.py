"""채용 트렌드 일일 스냅샷 + 다이제스트 생성.

health.py 패턴을 본떠 매 aggregate 사이클마다 record()가 호출되지만,
"하루 1회"만 스냅샷을 남긴다(같은 날·같은 키워드면 skip). 적재 결과로:
  - trends_history.jsonl : 하루 한 줄씩 누적(직무·경력·기술스택·키워드 집계)
  - trends_latest.json   : 최신 스냅샷
  - trends_reports/trends_<keyword>_<YYYY-MM-DD>.md : 사람이 읽는 일일 리포트
  - trends_reports/trends_<keyword>_latest.md       : 최신 리포트 사본

분석 축:
  - 직무(role)  : 제목 + tech_stack + 자격/JD 텍스트를 가중 점수로 분류
  - 경력(band)  : '경력 3~10년'·'경력3년↑'·'신입' 등 제각각 표기를 밴드로 정규화
  - 직무×경력별 선호 기술스택 Top N  (= 무엇을 공부하면 좋은가)
  - 우대/자격 키워드 빈도              (= 무엇을 선호하는가)
  - 전일 스냅샷이 있으면 '상승 기술스택' 델타까지

CLI:
    python -m pipeline.trends run [keyword] [--force]   # 현재 데이터로 스냅샷 적재(+리포트)
    python -m pipeline.trends digest [keyword]          # 최신 스냅샷을 터미널에 출력
    python -m pipeline.trends report [n]                # 최근 n일 추이 요약
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.resolve()
HISTORY = BASE / "trends_history.jsonl"
LATEST = BASE / "trends_latest.json"
REPORTS_DIR = BASE / "trends_reports"
SCREENSHOTS_DIR = BASE / "screenshots"

TOP_N = 12  # 직무별 기술스택/키워드 상위 개수

# ── 직무 분류 사전 ──────────────────────────────────────────────
# (정규식 목록) — title 매칭 ×3, tech_stack ×2, 텍스트 ×1 로 누적
ROLE_PATTERNS: dict[str, list[str]] = {
    "프론트엔드": [r"프론트", r"front[- ]?end", r"\breact\b", r"\bvue\b", r"angular",
                r"svelte", r"next\.?js", r"nuxt", r"웹\s*퍼블", r"퍼블리셔", r"redux"],
    "백엔드": [r"백[- ]?엔드", r"back[- ]?end", r"서버\s*개발", r"\bspring\b", r"django",
            r"flask", r"fastapi", r"\bnode\.?js\b", r"express", r"\bnest\b", r"\blaravel\b",
            r"\brails\b", r"\bapi\b", r"\bmsa\b", r"마이크로서비스"],
    "풀스택": [r"풀스택", r"full[- ]?stack"],
    "안드로이드": [r"안드로이드", r"android"],
    "iOS": [r"\bios\b", r"\bswift\b", r"objective[- ]?c"],
    "데이터/AI": [r"데이터\s*엔지니어", r"데이터\s*분석", r"\bdata\b", r"머신\s*러닝",
               r"machine\s*learning", r"\bml\b", r"딥러닝", r"\bai\b", r"인공지능",
               r"\bllm\b", r"tensorflow", r"pytorch", r"\bspark\b", r"airflow", r"\betl\b"],
    "데브옵스/인프라": [r"devops", r"데브옵스", r"\bsre\b", r"kubernetes", r"\bk8s\b",
                  r"인프라", r"클라우드\s*엔지니어", r"플랫폼\s*엔지니어", r"terraform"],
    "게임": [r"게임", r"\bgame\b", r"\bunity\b", r"unreal", r"언리얼"],
    "임베디드/펌웨어": [r"임베디드", r"embedded", r"펌웨어", r"firmware", r"\brtos\b",
                 r"제어\s*소프트웨어", r"디바이스\s*드라이버"],
}

# tech_stack 정규화: 소문자 변형 → 표준 표기
TECH_CANON: dict[str, str] = {
    "react": "React", "react.js": "React", "reactjs": "React", "next": "Next.js",
    "next.js": "Next.js", "nextjs": "Next.js", "vue": "Vue", "vue.js": "Vue",
    "nuxt": "Nuxt", "angular": "Angular", "svelte": "Svelte", "typescript": "TypeScript",
    "ts": "TypeScript", "javascript": "JavaScript", "js": "JavaScript",
    "node": "Node.js", "node.js": "Node.js", "nodejs": "Node.js",
    "spring": "Spring", "spring boot": "Spring Boot", "springboot": "Spring Boot",
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI", "express": "Express",
    "nestjs": "NestJS", "nest.js": "NestJS", "java": "Java", "kotlin": "Kotlin",
    "python": "Python", "go": "Go", "golang": "Go", "php": "PHP", "laravel": "Laravel",
    "ruby": "Ruby", "rails": "Ruby on Rails", "c++": "C++", "c#": "C#", "c": "C",
    "rust": "Rust", "scala": "Scala", "swift": "Swift",
    "mysql": "MySQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mongodb": "MongoDB", "redis": "Redis", "elasticsearch": "Elasticsearch",
    "kafka": "Kafka", "rabbitmq": "RabbitMQ", "oracle": "Oracle", "mariadb": "MariaDB",
    "aws": "AWS", "gcp": "GCP", "azure": "Azure", "docker": "Docker",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes", "terraform": "Terraform",
    "jenkins": "Jenkins", "git": "Git", "linux": "Linux", "msa": "MSA",
    "graphql": "GraphQL", "grpc": "gRPC", "tensorflow": "TensorFlow",
    "pytorch": "PyTorch", "spark": "Spark", "hadoop": "Hadoop", "airflow": "Airflow",
    "unity": "Unity", "unreal": "Unreal",
}

# 우대/자격 텍스트에서 잡아낼 개념 키워드 (표기 → 정규식)
CONCEPT_KEYWORDS: dict[str, str] = {
    "대용량/트래픽": r"대용량|대규모\s*트래픽|트래픽|대규모\s*시스템",
    "MSA/마이크로서비스": r"\bmsa\b|마이크로\s*서비스",
    "클라우드": r"클라우드|\baws\b|\bgcp\b|azure",
    "컨테이너/쿠버네티스": r"도커|docker|쿠버네티스|kubernetes|\bk8s\b|컨테이너",
    "CI/CD": r"ci/?cd|지속적\s*통합|배포\s*자동화|jenkins",
    "테스트/TDD": r"테스트\s*코드|\btdd\b|단위\s*테스트|테스트\s*자동화",
    "코드리뷰": r"코드\s*리뷰|code\s*review",
    "성능 최적화": r"성능\s*최적화|쿼리\s*최적화|튜닝",
    "분산/동시성": r"분산\s*(시스템|처리)|동시성|병렬\s*처리",
    "메시지큐/이벤트": r"메시지\s*큐|message\s*queue|이벤트\s*기반|카프카|kafka",
    "협업/커뮤니케이션": r"협업|커뮤니케이션|소통",
    "오너십/주도성": r"오너십|주도적|주도성|능동적",
    "영어": r"영어\s*(능력|회화|가능|커뮤니케이션)|english",
    "학위(석/박사)": r"석사|박사|대학원",
    "CS기초(알고리즘/자료구조)": r"알고리즘|자료\s*구조|컴퓨터\s*공학|cs\s*지식",
    "오픈소스": r"오픈\s*소스|open\s*source",
    "애자일/스크럼": r"애자일|agile|스크럼|scrum",
    "객체지향/설계": r"객체\s*지향|\boop\b|디자인\s*패턴|설계\s*경험",
}


# ── 정규화 헬퍼 ────────────────────────────────────────────────
def _txt(job: dict, *fields: str) -> str:
    """여러 필드를 합친 소문자 텍스트."""
    parts = []
    for f in fields:
        v = job.get(f)
        if isinstance(v, list):
            parts.append(" ".join(str(x) for x in v))
        elif v:
            parts.append(str(v))
    return " ".join(parts).lower()


def classify_role(job: dict) -> str:
    """제목(×3) + tech_stack(×2) + 자격/JD(×1) 가중 점수로 직무 분류."""
    title = (job.get("title") or "").lower()
    stack = _txt(job, "tech_stack")
    body = _txt(job, "qualifications", "main_tasks", "full_jd")
    scores: dict[str, int] = {}
    for role, pats in ROLE_PATTERNS.items():
        s = 0
        for p in pats:
            if re.search(p, title):
                s += 3
            if re.search(p, stack):
                s += 2
            if re.search(p, body):
                s += 1
        if s:
            scores[role] = s
    if not scores:
        return "기타"
    best = max(scores.values())
    # 동점이면 ROLE_PATTERNS 선언 순서가 빠른 직무 우선
    for role in ROLE_PATTERNS:
        if scores.get(role) == best:
            return role
    return "기타"


def career_band(career: str | None) -> str:
    """경력 표기를 밴드로 정규화."""
    c = (career or "").strip()
    if not c:
        return "미상"
    low = c.replace(" ", "")
    has_sin = "신입" in low
    has_gyeong = "경력" in low
    if "경력무관" in low or "무관" in low:
        return "경력무관"
    nums = [int(n) for n in re.findall(r"\d+", low)]
    if has_sin and not nums and not has_gyeong:
        return "신입"
    if has_sin and (has_gyeong or nums):
        return "신입~"  # '신입·경력' 류
    if nums:
        mn = min(nums)
        if mn <= 0:
            return "신입"
        if mn <= 2:
            return "1~3년"
        if mn <= 4:
            return "3~5년"
        if mn <= 9:
            return "5~10년"
        return "10년+"
    if has_gyeong:
        return "경력(연차미상)"
    return "기타"


# 경력 밴드 표시 순서
BAND_ORDER = ["신입", "신입~", "1~3년", "3~5년", "5~10년", "10년+",
              "경력무관", "경력(연차미상)", "미상", "기타"]


def _canon_tech(item: str) -> str | None:
    k = str(item).strip().lower()
    if not k:
        return None
    return TECH_CANON.get(k, str(item).strip())


def _tech_counter(jobs: list[dict]) -> Counter:
    c: Counter = Counter()
    for j in jobs:
        ts = j.get("tech_stack")
        if not isinstance(ts, list):
            continue
        for t in ts:
            ct = _canon_tech(t)
            if ct:
                c[ct] += 1
    return c


def _concept_counter(jobs: list[dict]) -> Counter:
    c: Counter = Counter()
    for j in jobs:
        text = _txt(j, "preferences", "qualifications")
        if not text:
            continue
        for label, pat in CONCEPT_KEYWORDS.items():
            if re.search(pat, text):
                c[label] += 1
    return c


def _band_counter(jobs: list[dict]) -> Counter:
    c: Counter = Counter()
    for j in jobs:
        c[career_band(j.get("career"))] += 1
    return c


def _ordered_bands(counter: Counter) -> list:
    items = dict(counter)
    out = [(b, items.pop(b)) for b in BAND_ORDER if b in items]
    out += sorted(items.items(), key=lambda kv: -kv[1])
    return out


# ── 분석 ──────────────────────────────────────────────────────
def analyze(jobs: list[dict]) -> dict:
    """모집중 jobs 리스트 → 트렌드 스냅샷(dict)."""
    for j in jobs:
        j["_role"] = classify_role(j)

    roles = Counter(j["_role"] for j in jobs)
    by_role: dict[str, dict] = {}
    for role in roles:
        rjobs = [j for j in jobs if j["_role"] == role]
        by_role[role] = {
            "count": len(rjobs),
            "bands": _ordered_bands(_band_counter(rjobs)),
            "tech": _tech_counter(rjobs).most_common(TOP_N),
            "concepts": _concept_counter(rjobs).most_common(TOP_N),
        }

    return {
        "total": len(jobs),
        "by_role": dict(sorted(roles.items(), key=lambda kv: -kv[1])),
        "bands": _ordered_bands(_band_counter(jobs)),
        "tech_overall": _tech_counter(jobs).most_common(TOP_N * 2),
        "concepts_overall": _concept_counter(jobs).most_common(TOP_N),
        "roles": by_role,
    }


def _today() -> str:
    return datetime.now().date().isoformat()


def _load_history() -> list:
    if not HISTORY.exists():
        return []
    out = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _prev_snapshot(keyword: str, before_date: str) -> dict | None:
    prev = None
    for r in _load_history():
        if r.get("keyword") == keyword and r.get("date", "") < before_date:
            prev = r
    return prev


def _rising_tech(cur: dict, prev: dict | None) -> list:
    """전일 대비 증가한 기술스택 (이름, 현재, 증가량)."""
    if not prev:
        return []
    pc = {t: n for t, n in prev.get("tech_overall", [])}
    out = []
    for t, n in cur.get("tech_overall", []):
        delta = n - pc.get(t, 0)
        if delta > 0:
            out.append((t, n, delta))
    out.sort(key=lambda x: -x[2])
    return out[:TOP_N]


# ── 적재(하루 1회) + 리포트 ─────────────────────────────────────
def record(keyword: str, active_jobs: list, force: bool = False) -> dict | None:
    """오늘 첫 호출에만 스냅샷 적재 + 리포트 생성. 이미 있으면 None."""
    today = _today()
    history = _load_history()
    todays = [r for r in history if r.get("keyword") == keyword and r.get("date") == today]
    if todays and not force:
        return None  # 오늘 이미 기록됨 — skip

    snap = analyze(active_jobs)
    snap["date"] = today
    snap["ts"] = datetime.now().isoformat(timespec="seconds")
    snap["keyword"] = keyword

    prev = _prev_snapshot(keyword, today)
    snap["rising_tech"] = _rising_tech(snap, prev)

    # history 갱신: --force 로 같은 날 재기록 시 그 날 항목을 교체
    history = [r for r in history if not (r.get("keyword") == keyword and r.get("date") == today)]
    history.append(snap)
    with open(HISTORY, "w", encoding="utf-8") as f:
        for r in history:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    LATEST.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

    write_report(snap, prev)
    return snap


def _fmt_counts(items: list, sep: str = " · ", limit: int | None = None) -> str:
    items = items[:limit] if limit else items
    return sep.join(f"{name} {cnt}" for name, cnt in items) or "—"


def build_report_md(snap: dict, prev: dict | None) -> str:
    total = snap["total"] or 1
    L = []
    L.append(f"# 📊 채용 트렌드 다이제스트 — {snap['date']}")
    head = f"> 키워드 `{snap['keyword']}` · 모집중 {snap['total']}건"
    if prev:
        head += f" · (전일 {prev['date']} {prev['total']}건 대비 {snap['total'] - prev['total']:+d})"
    L.append(head)
    L.append("")

    L.append("## 1. 직무 분포")
    L.append("| 직무 | 공고수 | 비중 |")
    L.append("|---|---:|---:|")
    for role, cnt in snap["by_role"].items():
        L.append(f"| {role} | {cnt} | {100*cnt//total}% |")
    L.append("")

    L.append("## 2. 경력 수요 (전체)")
    L.append("| 경력밴드 | 공고수 | 비중 |")
    L.append("|---|---:|---:|")
    for band, cnt in snap["bands"]:
        L.append(f"| {band} | {cnt} | {100*cnt//total}% |")
    L.append("")

    L.append("## 3. 직무별 선호 기술스택 · 경력 · 우대조건")
    for role, cnt in snap["by_role"].items():
        info = snap["roles"][role]
        if info["count"] < 3:
            continue
        L.append(f"### {role} ({info['count']}건)")
        L.append(f"- **주력 경력**: {_fmt_counts(info['bands'], limit=4)}")
        L.append(f"- **기술스택 Top**: {_fmt_counts(info['tech'])}")
        L.append(f"- **우대/자격 키워드**: {_fmt_counts(info['concepts'])}")
        L.append("")

    L.append("## 4. 전체 기술스택 Top")
    L.append(_fmt_counts(snap["tech_overall"], sep="  ·  "))
    L.append("")

    L.append("## 5. 전체 우대/자격 키워드 Top")
    L.append(_fmt_counts(snap["concepts_overall"], sep="  ·  "))
    L.append("")

    L.append("## 6. 지금 공부하면 좋은 것")
    if snap.get("rising_tech"):
        L.append("**전일 대비 수요 상승 ↑**")
        for name, cnt, delta in snap["rising_tech"]:
            L.append(f"- {name} (현재 {cnt}건, +{delta})")
        L.append("")
    L.append("**현재 가장 많이 요구되는 스택**")
    for name, cnt in snap["tech_overall"][:8]:
        L.append(f"- {name} — {cnt}건 ({100*cnt//total}% 공고)")
    L.append("")
    L.append(f"<sub>생성 {snap['ts']} · 직무 분류는 제목+스택+JD 휴리스틱이라 ±오차 있음</sub>")
    return "\n".join(L)


def write_report(snap: dict, prev: dict | None) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    md = build_report_md(snap, prev)
    dated = REPORTS_DIR / f"trends_{snap['keyword']}_{snap['date']}.md"
    dated.write_text(md, encoding="utf-8")
    (REPORTS_DIR / f"trends_{snap['keyword']}_latest.md").write_text(md, encoding="utf-8")
    return dated


# ── 데이터 로더(standalone) ────────────────────────────────────
def _load_active(keyword: str) -> list:
    """최신 통합 폴더의 all_jobs.json(모집중)을 읽는다."""
    if not SCREENSHOTS_DIR.exists():
        return []
    cands = sorted(SCREENSHOTS_DIR.glob(f"all_{keyword}_*"),
                   key=lambda p: p.name, reverse=True)
    cands += sorted(SCREENSHOTS_DIR.glob("all_통합_*"),
                    key=lambda p: p.name, reverse=True)
    for d in cands:
        f = d / "all_jobs.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
    return []


# ── CLI ───────────────────────────────────────────────────────
def _print_digest(snap: dict) -> None:
    total = snap["total"] or 1
    print(f"\n📊 채용 트렌드 — {snap['date']} · 키워드 '{snap['keyword']}' · 모집중 {snap['total']}건\n")
    print("[직무 분포]")
    for role, cnt in snap["by_role"].items():
        print(f"  {role:<14} {cnt:>4}건 ({100*cnt//total:>2}%)")
    print("\n[경력 수요]")
    for band, cnt in snap["bands"]:
        print(f"  {band:<14} {cnt:>4}건 ({100*cnt//total:>2}%)")
    print("\n[전체 기술스택 Top]")
    print("  " + _fmt_counts(snap["tech_overall"][:15], sep=" · "))
    print("\n[우대/자격 키워드 Top]")
    print("  " + _fmt_counts(snap["concepts_overall"][:12], sep=" · "))
    if snap.get("rising_tech"):
        print("\n[전일 대비 상승 ↑]")
        print("  " + " · ".join(f"{n}(+{d})" for n, _, d in snap["rising_tech"]))
    rpt = REPORTS_DIR / f"trends_{snap['keyword']}_latest.md"
    print(f"\n  → 리포트: {rpt}")


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "digest"

    if cmd == "run":
        kw = args[1] if len(args) > 1 and not args[1].startswith("-") else "개발자"
        force = "--force" in args
        jobs = _load_active(kw)
        if not jobs:
            print(f"(통합 데이터 없음 — screenshots/all_{kw}_* 또는 all_통합_* 폴더를 찾을 수 없음)")
            return
        snap = record(kw, jobs, force=force)
        if snap is None:
            print(f"(오늘({_today()}) '{kw}' 스냅샷이 이미 있음 — --force 로 재생성 가능)")
            if LATEST.exists():
                _print_digest(json.loads(LATEST.read_text(encoding="utf-8")))
            return
        _print_digest(snap)

    elif cmd == "report":
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 14
        hist = _load_history()[-n:]
        if not hist:
            print("(트렌드 기록 없음 — 아직 적재 안 됨. 'run' 으로 첫 스냅샷 생성)")
            return
        print(f"{'날짜':12}  {'모집중':>5}  | 직무 분포")
        for r in hist:
            roles = " ".join(f"{k}={v}" for k, v in list(r.get("by_role", {}).items())[:5])
            print(f"{r.get('date',''):12}  {r.get('total',0):>5}  | {roles}")

    else:  # digest
        if not LATEST.exists():
            print("(최신 스냅샷 없음 — 'python -m pipeline.trends run' 으로 먼저 적재)")
            return
        _print_digest(json.loads(LATEST.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
