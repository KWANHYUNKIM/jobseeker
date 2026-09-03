#!/usr/bin/env python3
"""기술 백과사전 검증 — 뷰어가 읽기 전에 형식이 깨졌는지 본다.

    python3 study-engine/validate.py             # 전체 검사
    python3 study-engine/validate.py <slug>      # 문서 하나만
    python3 study-engine/validate.py --gaps      # 이번 사이클의 대상 (사다리 그대로)
    python3 study-engine/validate.py --gaps-all  # 보강 후보 전량

역설계·브리핑 엔진의 validate.py 와 같은 자리를 지키지만 검사 대상이 다르다.
여기서 제일 중요한 검사는 셋이다.

  1. **aliases 가 tech_relations.json 의 name 과 글자 그대로 맞는가** — 기술 관계 화면에서
     이 문서로 들어오는 유일한 열쇠다. 어긋나면 다 써 놓고도 링크가 안 뜬다.
  2. **끊긴 related 링크** — 백과사전은 링크로 자라므로 끊긴 링크는 버그가 아니라 대기열이다.
     오류로 세지 않고 --gaps 가 큐 후보로 올린다.
  3. **표의 열/셀 개수** — 어긋나면 화면에서 표가 조용히 밀린다.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = ROOT / "jd-viewer" / "public" / "study"
INDEX = STUDY / "index.json"
ARTICLES = STUDY / "articles"
RELATIONS = ROOT / "jd-viewer" / "public" / "tech_relations.json"
STATE = Path(__file__).resolve().parent / "state"
QUEUE = STATE / "QUEUE.md"

CATEGORIES = {"language", "framework", "runtime", "infra", "data", "ai",
              "firmware", "hardware", "term", "domain", "practice"}
LEVELS = {"basic", "core", "deep"}
STATUSES = {"in_progress", "done"}
CONFIDENCE = {"confirmed", "inferred", "unknown"}
SECTION_KINDS = {"what", "why", "how", "limits", "extra"}
TABLE_KINDS = {"pinmap", "register", "spec", "compare", "glossary"}
EVIDENCE_FROM = {"posting", "blog", "docs", "standard"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MIN_SECTIONS = 4       # 이 아래면 뼈대만 있고 살이 없다 (PROMPT.md 4단계)
MIN_CHECKS = 3
MIN_DRILLS = 2
MIN_WHEN = 2
QUEUE_TARGET = 5       # 대기열이 이 아래로 떨어지면 후보 조사를 돈다
STALE_DAYS = 120       # 이만큼 지난 문서는 재방문 대상 (기술 문서는 조용히 낡는다)
SHOW_NEXT = 6          # --gaps 가 대상 말고 더 보여줄 건수 (루프의 맥락을 아낀다)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)


def check_sources(r: Report, where: str, sources) -> None:
    for i, s in enumerate(sources or []):
        if not isinstance(s, dict):
            r.err(f"{where}.sources[{i}]: 객체가 아니다")
            continue
        if not s.get("url"):
            r.err(f"{where}.sources[{i}]: url 이 없다")
        if not s.get("title"):
            r.warn(f"{where}.sources[{i}]: title 이 없다")


def check_claim(r: Report, where: str, obj: dict) -> None:
    conf = obj.get("confidence")
    if conf is None:
        return
    if conf not in CONFIDENCE:
        r.err(f"{where}: confidence={conf!r} 는 허용되지 않는 값")
        return
    if conf == "confirmed" and not obj.get("sources"):
        r.err(f"{where}: confirmed 인데 sources 가 비었다 (PROMPT.md 5단계)")


def load_relations() -> dict:
    """tech_relations.json 을 {name: tech} 로. 없으면 빈 dict — 이 엔진은 그것 없이도 돈다."""
    if not RELATIONS.exists():
        return {"by_name": {}, "generated_at": "", "total_jobs": 0}
    try:
        d = json.loads(RELATIONS.read_text(encoding="utf-8"))
    except Exception:
        return {"by_name": {}, "generated_at": "", "total_jobs": 0}
    return {
        "by_name": {t.get("name"): t for t in d.get("techs") or []},
        "generated_at": (d.get("generated_at") or "")[:10],
        "total_jobs": d.get("total_jobs", 0),
    }


def check_article(r: Report, path: Path, doc: dict, rel: dict) -> dict:
    """문서 하나. 돌려주는 것은 --gaps 가 쓸 요약이다."""
    w = path.name
    slug = doc.get("slug", "")
    if not SLUG_RE.match(slug or ""):
        r.err(f"{w}: slug 가 없거나 형식이 아니다 ({slug!r})")
    if slug and path.stem != slug:
        r.err(f"{w}: 파일명과 slug 가 다르다 ({path.stem} vs {slug})")
    for f in ("title", "one_liner", "summary"):
        if not doc.get(f):
            r.err(f"{w}: {f} 가 비었다")
    if doc.get("category") not in CATEGORIES:
        r.err(f"{w}: category={doc.get('category')!r}")
    if doc.get("level") not in LEVELS:
        r.err(f"{w}: level={doc.get('level')!r}")
    if doc.get("status") not in STATUSES:
        r.err(f"{w}: status={doc.get('status')!r}")
    if not DATE_RE.match(doc.get("updated_at", "") or ""):
        r.err(f"{w}: updated_at 이 YYYY-MM-DD 가 아니다")

    aliases = doc.get("aliases") or []
    if not aliases:
        r.err(f"{w}: aliases 가 비었다 — 기술 관계 화면에서 이 문서로 들어올 길이 없다")

    # ── market ──
    # 이 엔진의 축이다. 숫자는 tech_relations.json 것을 그대로 옮기기로 했으므로,
    # 어긋나면 옮기다 틀렸거나 데이터가 갱신된 것이다(재방문 대상).
    mk = doc.get("market")
    market_stale = False
    if mk:
        tech = mk.get("tech")
        src = rel["by_name"].get(tech)
        if not tech:
            r.err(f"{w}.market: tech 가 없다")
        elif src is None:
            if rel["by_name"]:
                r.err(f"{w}.market: tech={tech!r} 가 tech_relations.json 에 없다 — "
                      f"이름을 글자 그대로 맞춘다")
        else:
            if tech not in aliases:
                r.err(f"{w}: market.tech({tech!r}) 가 aliases 에 없다 — 관계 화면이 못 잇는다")
            for f, key in (("postings", "count"), ("pct_jobs", "pct_jobs")):
                if mk.get(f) != src.get(key):
                    r.warn(f"{w}.market.{f} 가 tech_relations 와 다르다 "
                           f"({mk.get(f)} vs {src.get(key)}) — 재방문 대상")
                    market_stale = True
        if not DATE_RE.match(mk.get("as_of", "") or ""):
            r.err(f"{w}.market: as_of 가 YYYY-MM-DD 가 아니다 (tech_relations 의 generated_at)")

    # ── sections ──
    sec_ids: set[str] = set()
    kinds: set[str] = set()
    for i, s in enumerate(doc.get("sections") or []):
        where = f"{w}.sections[{i}]"
        sid = s.get("id", "")
        if not ID_RE.match(sid or ""):
            r.err(f"{where}: id 가 없거나 형식이 아니다 ({sid!r}) — 앵커로 쓰인다")
        elif sid in sec_ids:
            r.err(f"{where}: id 가 중복이다 ({sid})")
        sec_ids.add(sid)
        if not s.get("heading") or not s.get("body"):
            r.err(f"{where}: heading/body 가 있어야 한다")
        if s.get("kind") not in SECTION_KINDS:
            r.err(f"{where}: kind={s.get('kind')!r}")
        kinds.add(s.get("kind"))
        check_claim(r, where, s)
        check_sources(r, where, s.get("sources"))

    # ── tables ──
    for i, t in enumerate(doc.get("tables") or []):
        where = f"{w}.tables[{i}]"
        if t.get("kind") not in TABLE_KINDS:
            r.err(f"{where}: kind={t.get('kind')!r}")
        if not t.get("caption"):
            r.err(f"{where}: caption 이 없다")
        cols = t.get("columns") or []
        if not cols:
            r.err(f"{where}: columns 가 비었다")
        for k, row in enumerate(t.get("rows") or []):
            if not isinstance(row, list) or len(row) != len(cols):
                r.err(f"{where}.rows[{k}]: 셀 {len(row) if isinstance(row, list) else '?'}개 "
                      f"— 열은 {len(cols)}개다. 화면에서 표가 밀린다")
        # 핀 번호는 패키지마다 다르다. 패키지를 안 밝힌 핀맵은 틀린 정보다.
        if t.get("kind") == "pinmap" and not t.get("note"):
            r.err(f"{where}: pinmap 은 note 에 패키지를 밝혀야 한다 (PROMPT.md 4단계)")
        if t.get("kind") in ("pinmap", "register", "spec") and not t.get("sources"):
            r.warn(f"{where}: 숫자가 든 표인데 sources 가 없다 — 데이터시트를 단다")
        check_claim(r, where, t)
        check_sources(r, where, t.get("sources"))

    # ── when_to_use ──
    for i, u in enumerate(doc.get("when_to_use") or []):
        where = f"{w}.when_to_use[{i}]"
        for f in ("situation", "pick", "why", "tradeoff"):
            if not u.get(f):
                r.err(f"{where}: {f} 가 비었다")
        if not u.get("over"):
            r.err(f"{where}: over 가 비었다 — 비교 대상 없는 '이럴 땐 이걸'은 "
                  f"고르는 데 도움이 안 된다 (PROMPT.md 4단계)")
        check_claim(r, where, u)
        check_sources(r, where, u.get("sources"))

    # ── pitfalls ──
    for i, p in enumerate(doc.get("pitfalls") or []):
        where = f"{w}.pitfalls[{i}]"
        for f in ("trap", "why"):
            if not p.get(f):
                r.err(f"{where}: {f} 가 비었다")
        if not p.get("fix"):
            r.err(f"{where}: fix 가 없다 — 그건 경고가 아니라 겁주기다 (PROMPT.md 4단계)")
        check_sources(r, where, p.get("sources"))

    # ── terms ──
    for i, t in enumerate(doc.get("terms") or []):
        if not t.get("term") or not t.get("what"):
            r.err(f"{w}.terms[{i}]: term/what 이 있어야 한다")

    # ── drills ──
    for i, d in enumerate(doc.get("drills") or []):
        where = f"{w}.drills[{i}]"
        for f in ("task", "done_when", "why"):
            if not d.get(f):
                r.err(f"{where}: {f} 가 비었다")
        # 장비가 필요한 실습은 대부분의 독자에게 아무 일도 일으키지 않는다.
        if d.get("needs") and not d.get("no_hardware"):
            r.warn(f"{where}: needs 가 있는데 no_hardware(장비 없을 때의 대안)가 없다")

    # ── evidence ──
    for i, e in enumerate(doc.get("evidence") or []):
        where = f"{w}.evidence[{i}]"
        if not e.get("quote") or not e.get("what_it_shows"):
            r.err(f"{where}: quote/what_it_shows 가 있어야 한다")
        if not e.get("url"):
            r.err(f"{where}: url 이 없다 — 인용은 출처와 함께만 쓴다")
        if e.get("from") not in EVIDENCE_FROM:
            r.err(f"{where}: from={e.get('from')!r}")

    check_sources(r, f"{w}", doc.get("sources"))

    return {
        "slug": slug,
        "title": doc.get("title", ""),
        "category": doc.get("category"),
        "level": doc.get("level"),
        "status": doc.get("status"),
        "one_liner": doc.get("one_liner", ""),
        "aliases": aliases,
        "updated_at": doc.get("updated_at", ""),
        "sections": len(doc.get("sections") or []),
        "kinds": kinds,
        "tables": len(doc.get("tables") or []),
        "when_to_use": len(doc.get("when_to_use") or []),
        "pitfalls": len(doc.get("pitfalls") or []),
        "drills": len(doc.get("drills") or []),
        "checks": len(doc.get("checks") or []),
        "evidence": len(doc.get("evidence") or []),
        "related": [(x.get("slug"), x.get("how")) for x in (doc.get("related") or [])],
        "no_market": not bool(mk),
        "market_stale": market_stale,
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

    rel = load_relations()
    docs: list[tuple[Path, dict]] = []
    for p in sorted(ARTICLES.glob("*.json")) if ARTICLES.exists() else []:
        try:
            docs.append((p, json.loads(p.read_text(encoding="utf-8"))))
        except Exception as e:
            r.err(f"{p.name} 파싱 실패: {e}")

    summaries = [check_article(r, p, d, rel) for p, d in docs]

    # 같은 낱말을 두 슬러그로 쓴 경우. 관계 화면은 alias 로 첫 번째 것만 찾으므로
    # 나중에 쓴 쪽은 다 써 놓고도 영영 안 뜬다.
    owner: dict[str, str] = {}
    for s in summaries:
        for a in s["aliases"]:
            key = a.lower()
            if key in owner and owner[key] != s["slug"]:
                r.err(f"aliases 충돌: {a!r} 를 {owner[key]} 와 {s['slug']} 가 함께 쓴다 "
                      f"— 한 문서로 합치거나 한쪽에서 뺀다")
            else:
                owner[key] = s["slug"]

    # index 와 문서의 불일치. 뷰어는 index 만 보고 목록을 그린다.
    by_slug = {s["slug"]: s for s in summaries}
    listed = {a.get("slug"): a for a in (index.get("articles") or [])}
    for slug in by_slug.keys() - listed.keys():
        r.err(f"index.json: {slug} 이 목록에 없다 — 뷰어가 못 찾는다")
    for slug in listed.keys() - by_slug.keys():
        r.err(f"index.json: {slug} 은 목록에만 있고 파일이 없다")
    for slug, a in listed.items():
        s = by_slug.get(slug)
        if not s:
            continue
        for f in ("title", "category", "level", "status", "one_liner", "updated_at"):
            if a.get(f) != s[f]:
                r.err(f"index.json[{slug}].{f} 가 문서와 다르다 ({a.get(f)!r} vs {s[f]!r})")
        if set(a.get("aliases") or []) != set(s["aliases"]):
            r.err(f"index.json[{slug}].aliases 가 문서와 다르다")
        if a.get("sections") != s["sections"] or a.get("drills") != s["drills"]:
            r.err(f"index.json[{slug}]: sections/drills 카운트가 어긋난다 "
                  f"({a.get('sections')}/{a.get('drills')} vs {s['sections']}/{s['drills']})")

    # done 의 조건 (PROMPT.md 완주 기준). in_progress 는 아직 쓰는 중이므로 안 건다.
    for s in summaries:
        if s["status"] != "done":
            continue
        w = f"{s['slug']}.json"
        if s["sections"] < MIN_SECTIONS:
            r.err(f"{w}: done 인데 sections 가 {s['sections']}개다 (최소 {MIN_SECTIONS})")
        if "why" not in s["kinds"]:
            r.err(f"{w}: done 인데 kind=why 인 절이 없다 — 왜 생겼는지 없는 문서는 "
                  f"공식 문서 요약본이다 (PROMPT.md 4단계)")
        if s["when_to_use"] < MIN_WHEN:
            r.err(f"{w}: done 인데 when_to_use 가 {s['when_to_use']}개다 (최소 {MIN_WHEN})")
        if s["drills"] < MIN_DRILLS:
            r.err(f"{w}: done 인데 drills 가 {s['drills']}개다 (최소 {MIN_DRILLS})")
        if s["checks"] < MIN_CHECKS:
            r.err(f"{w}: done 인데 checks 가 {s['checks']}개다 (최소 {MIN_CHECKS})")

    return index, summaries, rel


# ── 대기열 ──────────────────────────────────────────────────────────────
def queue_rows() -> list[str]:
    """QUEUE.md 의 `## 대기` 표에서 낱말 열만 뽑는다."""
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
            if cells[0] in ("낱말", "주제", "제목"):
                continue
            rows.append(cells[0])
    return rows


def days_since(d: str) -> int:
    try:
        return (date.today() - datetime.strptime(d, "%Y-%m-%d").date()).days
    except Exception:
        return 9999


# ── --gaps ──────────────────────────────────────────────────────────────
def gaps(summaries: list[dict], rel: dict, errors: list[str], show_all: bool) -> None:
    print("# 기술 백과사전 — 다음 사이클")
    print()

    # 1순위 — 보수
    if errors:
        print("### 이번 사이클의 대상 — 보수 (사다리 1순위)")
        print(f"오류 {len(errors)}건. 새 문서를 쓰지 말고 이것부터 고친다.")
        print()
        for e in errors[: len(errors) if show_all else SHOW_NEXT]:
            print(f"  ✗ {e}")
        if not show_all and len(errors) > SHOW_NEXT:
            print(f"  … 외 {len(errors) - SHOW_NEXT}건. 전량은 --gaps-all.")
        return

    by_slug = {s["slug"] for s in summaries}
    queued = queue_rows()

    # 2순위 — 쓰다 만 문서
    for s in sorted((x for x in summaries if x["status"] == "in_progress"),
                    key=lambda x: x["updated_at"]):
        print("### 이번 사이클의 대상 — 완성 (사다리 2순위)")
        print(f"**{s['title']}** (`{s['slug']}`) · {s['updated_at']} 갱신")
        print()
        todo = []
        if s["sections"] < MIN_SECTIONS:
            todo.append(f"sections {s['sections']}/{MIN_SECTIONS}")
        if "why" not in s["kinds"]:
            todo.append("kind=why 인 절이 없다 (왜 생겼나)")
        if s["when_to_use"] < MIN_WHEN:
            todo.append(f"when_to_use {s['when_to_use']}/{MIN_WHEN}")
        if s["drills"] < MIN_DRILLS:
            todo.append(f"drills {s['drills']}/{MIN_DRILLS}")
        if s["checks"] < MIN_CHECKS:
            todo.append(f"checks {s['checks']}/{MIN_CHECKS}")
        if not s["evidence"]:
            todo.append("evidence 가 비었다 (실제 공고·블로그 문장)")
        if not todo:
            print("  · 완주 기준을 다 채웠다 — **status: done 으로 바꿀 때다.**")
        for t in todo:
            print(f"  · {t}")
        return

    # 3순위 — 대기열
    if queued:
        print("### 이번 사이클의 대상 — 신규 (사다리 3순위)")
        print(f"**{queued[0]}** — QUEUE.md 맨 위. PROMPT.md 3단계부터.")
        print()
        if len(queued) > 1:
            print(f"  · 대기 {len(queued)}개: {', '.join(queued[1:])}")
        return

    # 4순위 — 보강
    cand: list[tuple[int, str]] = []
    broken: list[str] = []
    for s in summaries:
        if s["sections"] < MIN_SECTIONS:
            cand.append((1, f"[sections {s['sections']}/{MIN_SECTIONS}] {s['title']} (`{s['slug']}`)"))
        if s["drills"] < MIN_DRILLS:
            cand.append((2, f"[drills {s['drills']}/{MIN_DRILLS}] {s['title']} (`{s['slug']}`)"))
        if s["when_to_use"] < MIN_WHEN:
            cand.append((3, f"[when_to_use 없음] {s['title']} (`{s['slug']}`)"))
        if not s["pitfalls"]:
            cand.append((4, f"[pitfalls 없음] {s['title']} (`{s['slug']}`)"))
        if not s["evidence"]:
            cand.append((5, f"[evidence 없음] {s['title']} (`{s['slug']}`)"))
        for slug, how in s["related"]:
            if slug not in by_slug:
                broken.append(f"{slug} ← {s['title']} 이 가리킨다 ({how})")
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
        if broken:
            print()
            print(f"※ 끊긴 링크 {len(broken)}개 — 오류가 아니라 **다음 대기열**이다:")
            for b in broken[:SHOW_NEXT]:
                print(f"  · {b}")
        return

    # 5순위 — 재방문
    stale = sorted((s for s in summaries
                    if s["market_stale"] or days_since(s["updated_at"]) > STALE_DAYS),
                   key=lambda s: s["updated_at"])
    if stale:
        s = stale[0]
        print("### 이번 사이클의 대상 — 재방문 (사다리 5순위)")
        why = "market 이 tech_relations 와 어긋난다" if s["market_stale"] \
            else f"{days_since(s['updated_at'])}일 전 갱신"
        print(f"**{s['title']}** (`{s['slug']}`) — {why}")
        return

    # 6순위 — 후보 조사
    print("### 이번 사이클의 대상 — 후보 조사 (사다리 6순위)")
    print(f"대기열 {len(queued)}개 (목표 {QUEUE_TARGET}). 아래는 **문서가 없는 기술**을 "
          f"공고 수로 줄 세운 것이다. **그대로 옮기지 말고** PROMPT.md 2⁗단계로 거른다.")
    print()
    covered = {a.lower() for s in summaries for a in s["aliases"]}
    pool = [t for name, t in rel["by_name"].items() if (name or "").lower() not in covered]
    pool.sort(key=lambda t: -(t.get("count") or 0))
    for t in pool[: 20 if show_all else 12]:
        print(f"  · {t['name']} — 공고 {t.get('count', 0):,}건 ({t.get('pct_jobs', 0)}%) · {t.get('layer', '')}")
    if broken := [f"{slug} ← {s['title']}" for s in summaries for slug, _ in s["related"]
                  if slug not in by_slug]:
        print()
        print(f"※ 끊긴 링크 {len(broken)}개 — 여기가 큐의 1순위다:")
        for b in broken[:SHOW_NEXT]:
            print(f"  · {b}")


# ── main ────────────────────────────────────────────────────────────────
def main() -> int:
    args = sys.argv[1:]
    want_gaps = "--gaps" in args or "--gaps-all" in args
    show_all = "--gaps-all" in args
    only = [a for a in args if not a.startswith("--")]

    r = Report()
    _index, summaries, rel = load_all(r)
    if only:
        summaries = [s for s in summaries if s["slug"] in only]

    if want_gaps:
        gaps(summaries, rel, r.errors, show_all)
        return 0

    for e in r.errors:
        print(f"✗ {e}")
    for w in r.warns:
        print(f"! {w}")
    n_sec = sum(s["sections"] for s in summaries)
    n_drill = sum(s["drills"] for s in summaries)
    n_done = sum(1 for s in summaries if s["status"] == "done")
    print(f"\n문서 {len(summaries)}개(완성 {n_done}) · 절 {n_sec}개 · 실습 {n_drill}개 "
          f"· 오류 {len(r.errors)} · 경고 {len(r.warns)}")
    return 1 if r.errors else 0


if __name__ == "__main__":
    sys.exit(main())
