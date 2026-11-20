#!/usr/bin/env python3
"""인프런 강의의 **차례만** 받는다 — 기술도서의 뼈대용.

    python book-engine/curriculum.py show <강의 주소>          # 차례를 화면에 + state/curricula/<id>.json
    python book-engine/curriculum.py queue [--max 40] [--scan 400]   # 데이터 사이언스 강의를 찾아 state/QUEUE.md 를 채운다

**무엇을 받고 무엇을 안 받나.** 강의 상세 페이지(`/course/<슬러그>`)는 robots.txt 가 허용하고, 서버가
페이지에 심어 보내는 `__NEXT_DATA__` 에 차례(섹션·수업 제목·길이)가 들어 있다. 그것만 읽는다.
영상·수업 본문(`/course/lecture`)·내부 API(`/api`)는 robots 가 막고, 유료 강의 내용은 강사의 저작물이라
받지 않는다. 책의 본문·예제·그림은 우리가 직접 쓴다(PROMPT.md).

강의 목록은 카테고리 페이지가 브라우저에서 `/api` 로 채우므로 못 읽는다. 대신 공개 사이트맵의 강의 주소를
슬러그 낱말로 좁히고, 상세 페이지의 분류(categorySlugs)로 확인한다(jd-viewer/bin/build_inflearn.py 와 같은 길).
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse as up
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "state"
CURRICULA = STATE / "curricula"
QUEUE = STATE / "QUEUE.md"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
SITEMAP_INDEX = "https://cdn.inflearn.com/sitemaps/sitemap.xml"
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
KO_COURSE = re.compile(r"^https://www\.inflearn\.com/course/([^/?#]+)\?cid=(\d+)")
SLEEP = 1.0   # 요청 사이 — 사람이 페이지를 넘기는 속도보다 느리게

# 데이터 사이언스 강의를 슬러그로 좁히는 낱말(인프런 슬러그는 한글·영문 낱말을 - 로 잇는다)
DS_WORDS = ["데이터", "파이썬", "python", "pandas", "판다스", "numpy", "머신러닝", "machine-learning", "딥러닝",
            "deep-learning", "통계", "시각화", "sql", "분석", "ai", "llm", "pytorch", "텐서플로", "tensorflow",
            "scikit", "kaggle", "캐글", "추천", "자연어", "nlp", "컴퓨터-비전", "rag", "langchain"]
# 상세 페이지의 분류로 확인한다 — 이 중 하나라도 있으면 데이터 사이언스 강의
DS_CATEGORIES = {"data-science", "data-analysis", "data-engineering", "artificial-intelligence", "ai",
                 "machine-learning", "deep-learning", "data-visualization", "statistics", "ai-ml", "llm"}


def _get(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _queries(html: str) -> list[dict]:
    m = NEXT_DATA.search(html)
    if not m:
        return []
    return json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("dehydratedState", {}).get("queries", [])


def _pick(qs: list[dict], needle: str) -> dict:
    for q in qs:
        if needle in str(q.get("queryKey", "")):
            d = (q.get("state") or {}).get("data")
            if isinstance(d, dict):
                return d.get("data") if isinstance(d.get("data"), dict) else d
    return {}


def course(url: str) -> dict:
    """강의 한 개의 차례와 소개 메타. 본문은 없다."""
    html = _get(url)
    qs = _queries(html)
    info, meta = _pick(qs, "/online/info"), _pick(qs, "/meta")
    contents, cur = _pick(qs, "/contents?lang=ko"), _pick(qs, "/curriculum")
    if not info.get("title"):
        raise RuntimeError(f"강의 정보를 못 읽었다: {url}")
    sections = [{"title": s.get("title", "").strip(),
                 "units": [{"title": u.get("title", "").strip(), "minutes": round((u.get("runtime") or 0) / 60)}
                           for u in s.get("units") or [] if u.get("title")]}
                for s in cur.get("curriculum") or []]
    return {
        "id": info.get("id"), "url": url.split("?")[0], "title": info.get("title"),
        "instructors": [(i.get("nickname") or i.get("name") or "") for i in (contents.get("mainInstructors") or [])][:2],
        "students": info.get("studentCount") or 0,
        "level": str(contents.get("levelCode") or contents.get("level") or ""),
        "categories": [c for c in (meta.get("categorySlugs") or []) if c],
        "skills": [s for s in (meta.get("skillSlugs") or []) if s][:12],
        "abilities": [a for a in (contents.get("abilities") or []) if a][:8],   # 강의가 약속하는 것 — 책의 목표로 쓴다
        "targets": [t for t in (contents.get("targets") or []) if t][:6],
        "prerequisites": [b for b in (contents.get("based") or []) if b][:6],
        "updated_at": str(cur.get("lastUpdatedAt") or contents.get("lastUpdatedAt") or "")[:10],
        "sections": sections,
    }


def show(url: str) -> None:
    c = course(url)
    CURRICULA.mkdir(parents=True, exist_ok=True)
    out = CURRICULA / f"{c['id']}.json"
    out.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{c['title']} — {', '.join(c['instructors'])} · 수강생 {c['students']:,} · 갱신 {c['updated_at']}")
    for i, s in enumerate(c["sections"], 1):
        print(f"  {i:>2}. {s['title']}  ({len(s['units'])}개 · {sum(u['minutes'] for u in s['units'])}분)")
        for u in s["units"]:
            print(f"        - {u['title']}")
    print(f"→ {out}")


def queue(max_n: int = 40, scan: int = 400) -> None:
    """사이트맵 → 슬러그 낱말로 후보 → 상세 페이지 분류로 확인 → 수강생 순 QUEUE.md."""
    idx = _get(SITEMAP_INDEX, 60)
    files = [u for u in re.findall(r"<loc>([^<]+)</loc>", idx) if "courseDetail-" in u]
    cand: list[str] = []
    for f in files:
        for u in re.findall(r"<loc>([^<]+)</loc>", _get(f, 90)):
            u = u.replace("&amp;", "&")
            m = KO_COURSE.match(u)
            if m and any(w in up.unquote(m.group(1)).lower() for w in DS_WORDS):
                cand.append(u)
        time.sleep(SLEEP)
    # 최근 것만 보면 수강생이 거의 없는 새 강의만 남는다 — 전체에서 고르게 scan 개를 본다
    step = max(1, len(cand) // scan)
    picked = cand[::step][:scan]
    print(f"슬러그 후보 {len(cand)}개 중 {len(picked)}개를 상세 페이지로 확인한다(요청 간격 {SLEEP}초)")
    done = _done_ids()
    found: list[dict] = []
    for u in picked:
        try:
            c = course(u)
        except Exception as e:                                       # noqa: BLE001
            print(f"  건너뜀 {u[:70]}: {e}")
            continue
        finally:
            time.sleep(SLEEP)
        if set(c["categories"]) & DS_CATEGORIES and len(c["sections"]) >= 3 and c["id"] not in done:
            found.append(c)
    found.sort(key=lambda c: -c["students"])
    lines = ["# 데이터 사이언스 기술도서 대기열", "",
             "`python book-engine/curriculum.py queue` 가 채운다. 위에서부터 한 권씩 연다(PROMPT.md).",
             "줄 앞의 `[x]` 는 책을 연 강의다 — 엔진이 책을 열 때 고친다.", ""]
    for c in found[:max_n]:
        lines.append(f"- [ ] {c['title']} — 수강생 {c['students']:,} · 섹션 {len(c['sections'])} · {c['url']}  (id {c['id']})")
    old = QUEUE.read_text(encoding="utf-8") if QUEUE.exists() else ""
    kept = [ln for ln in old.splitlines() if ln.startswith("- [x]")]
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE.write_text("\n".join(lines[:5] + kept + lines[5:]) + "\n", encoding="utf-8")
    print(f"대기열 {len(found[:max_n])}권 → {QUEUE}")


def _done_ids() -> set:
    if not QUEUE.exists():
        return set()
    return {int(m) for m in re.findall(r"^- \[x\].*\(id (\d+)\)", QUEUE.read_text(encoding="utf-8"), re.M)}


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "show":
        show(argv[1])
        return 0
    if argv and argv[0] == "queue":
        queue(int(argv[argv.index("--max") + 1]) if "--max" in argv else 40,
              int(argv[argv.index("--scan") + 1]) if "--scan" in argv else 400)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
