#!/usr/bin/env python3
"""인프런 유료 강의 수집기 — 수요 있는 기술만, 학습 사다리 형태로.

입력: jd-viewer/public/trends.json  (수요 순위 = 추적 기술)
출력: jd-viewer/public/inflearn_courses.json

**build_learning.py 와의 관계.** 그쪽은 YouTube 무료 영상이다. 무료 영상은 진입에는
좋지만 "이 기술이 지금 어디까지 왔고 실무에서 어떻게 쓰이는지"까지 데려가 주는 경우가
드물다. 유료 강의는 커리큘럼이 설계돼 있어 그 구간을 메운다. 그래서 같은 기술을 두고
무료/유료를 나란히 두고, 유료 쪽은 난이도 사다리로 정렬한다.

**robots.txt 준수 (2026-08-19 확인).** `User-agent: *` 기준 인프런은 `/api` 를 막는다.
내부 JSON 엔드포인트를 직접 부르지 않는다. 대신 (a) 공개 사이트맵으로 강의 URL 을
모으고 (b) 허용된 강의 상세 페이지를 받아 서버가 이미 심어 보낸 `__NEXT_DATA__` 를
읽는다. 막힌 경로(/api, /carts, /orders, /course/*/edit, /course/*/dashboard,
/course/lecture, /challenges, /admin, /auth)는 어느 것도 건드리지 않는다.

**왜 검색 페이지를 안 쓰는가 — 한 번 속았다.**
처음엔 `/ko/search?s=<기술>` 의 `__NEXT_DATA__` 를 읽었다. 200 이 오고, 20건이 파싱되고,
제목·가격·수강생까지 그럴듯하게 채워졌다. 그런데 검색어를 바꿔도 **결과가 완전히
동일**했다(Python·AWS·Java 세 질의의 강의 id 배열이 글자 그대로 같았다). SSR 페이로드는
필터 이전의 기본 목록이고 실제 검색은 클라이언트에서 돈다. `?skill=<슬러그>` 목록도
마찬가지로 서버가 항목을 채워 보내지 않는다. 즉 그 경로로는 조용히 틀린 데이터를
만들게 된다 — 형식이 멀쩡해서 눈으로는 안 걸린다.

그래서 관련도를 검색에 맡기지 않고 이쪽에서 만든다. 사이트맵의 슬러그가 사람이 읽는
문자열(`mysql-강좌`, `spring-boot-...`)이라 기술명이 그대로 박혀 있고, `?cid=` 는 대략
시간순이라 최신을 고르는 데 쓸 수 있다. 후보를 슬러그로 좁힌 뒤 상세 페이지에서만
정확한 메타(skillSlugs, level, 수강생, 가격)를 확인한다.

사용법:
    python3 jd-viewer/bin/build_inflearn.py                # trends 추적 기술 전체
    python3 jd-viewer/bin/build_inflearn.py --limit 3      # 앞 3개 기술만(테스트)
    python3 jd-viewer/bin/build_inflearn.py --candidates 8 # 기술당 후보 수 조절
    python3 jd-viewer/bin/build_inflearn.py --refresh      # 캐시 무시
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse as up
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
TRENDS = ROOT / "jd-viewer" / "public" / "trends.json"
OUTPUT = ROOT / "jd-viewer" / "public" / "inflearn_courses.json"
CACHE_DIR = Path(__file__).resolve().parent / ".inflearn_cache"
SITEMAP_INDEX = "https://cdn.inflearn.com/sitemaps/sitemap.xml"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0 Safari/537.36"
)
DELAY = 1.5           # 상세 페이지 1건당 최소 간격(초)
CANDIDATES = 12       # 기술당 상세를 확인할 후보 수(슬러그 매칭 상위)
KEEP = 8              # 기술당 최종 보관 수
NEXT_DATA_RE = re.compile(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
KO_COURSE_RE = re.compile(r"^https://www\.inflearn\.com/course/([^?]+)\?cid=(\d+)$")

LEVEL_ORDER = {"BASIC": 0, "INTERMEDIATE": 1, "ADVANCED": 2}
LEVEL_KO = {"BASIC": "입문", "INTERMEDIATE": "중급", "ADVANCED": "고급"}

# 슬러그/스킬슬러그에서 그 기술로 볼 표기들. 공고의 기술명과 강의 슬러그의 표기가
# 다른 경우만 적는다(이름이 그대로 쓰이는 기술은 굳이 넣지 않는다).
ALIASES: dict[str, list[str]] = {
    "Node.js": ["nodejs", "node-js", "node"],
    "Spring Boot": ["spring-boot", "springboot", "스프링부트", "스프링-부트"],
    "Spring": ["spring", "스프링"],
    "TypeScript": ["typescript", "타입스크립트", "ts"],
    "JavaScript": ["javascript", "자바스크립트", "js"],
    "Java": ["java", "자바"],
    "Python": ["python", "파이썬"],
    "C++": ["cpp", "c-plus", "c__", "씨쁠쁠"],
    "C#": ["csharp", "c-sharp"],
    "REST API": ["rest-api", "restapi", "rest"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Kubernetes": ["kubernetes", "k8s", "쿠버네티스"],
    "Docker": ["docker", "도커"],
    "React": ["react", "리액트"],
    "Vue": ["vue", "뷰"],
    "Next.js": ["nextjs", "next-js", "넥스트"],
    "Django": ["django", "장고"],
    "FastAPI": ["fastapi", "fast-api"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis", "레디스"],
    "Kafka": ["kafka", "카프카"],
    "Elasticsearch": ["elasticsearch", "elastic-search", "엘라스틱"],
    "AWS": ["aws", "amazon-web"],
    "GCP": ["gcp", "google-cloud"],
    "Azure": ["azure"],
    "Linux": ["linux", "리눅스"],
    "Git": ["git", "깃"],
    "PyTorch": ["pytorch", "파이토치"],
    "TensorFlow": ["tensorflow", "텐서플로"],
    "Android": ["android", "안드로이드"],
    "iOS": ["ios", "swift", "스위프트"],
    "Kotlin": ["kotlin", "코틀린"],
    "Flutter": ["flutter", "플러터"],
    "Go": ["golang", "go-lang"],  # 'go' 단독은 오탐이 너무 많다
}


# 이 단어가 들어 있으면 그 부분은 매칭 근거에서 지운다. 'Java' 의 별칭 '자바'/'java' 가
# '자바스크립트'/'javascript' 안에 그대로 들어 있어, 그냥 두면 자바 칸이 JS 강의로 찬다.
NEGATIVE: dict[str, list[str]] = {
    "Java": ["javascript", "자바스크립트", "java-script", "js"],
}


def aliases_for(tech: str) -> list[str]:
    base = ALIASES.get(tech)
    if base:
        return base
    slug = re.sub(r"[^a-z0-9가-힣]+", "-", tech.lower()).strip("-")
    return [slug] if len(slug) >= 3 else []


def sitemap_course_urls(client: httpx.Client) -> list[tuple[str, str, int]]:
    """(url, slug, cid) — 한국어 강의만. 사이트맵은 공개 크롤 경로다."""
    idx = client.get(SITEMAP_INDEX, timeout=60).text
    files = [u for u in re.findall(r"<loc>([^<]+)</loc>", idx) if "courseDetail-" in u]
    out: list[tuple[str, str, int]] = []
    for f in files:
        xml = client.get(f, timeout=90).text
        for u in re.findall(r"<loc>([^<]+)</loc>", xml):
            m = KO_COURSE_RE.match(u.replace("&amp;", "&"))
            if m:
                out.append((u, up.unquote(m.group(1)).lower(), int(m.group(2))))
        time.sleep(0.5)
    return out


def _queries(html: str) -> list[dict]:
    m = NEXT_DATA_RE.search(html)
    if not m:
        return []
    data = json.loads(m.group(1))
    return data.get("props", {}).get("pageProps", {}).get("dehydratedState", {}).get("queries", [])


def _pick(queries: list[dict], needle: str) -> dict:
    for q in queries:
        if needle in str(q.get("queryKey", "")):
            data = (q.get("state") or {}).get("data")
            if isinstance(data, dict):
                inner = data.get("data")
                return inner if isinstance(inner, dict) else data
    return {}


def fetch_course(client: httpx.Client, url: str) -> dict | None:
    """강의 상세 페이지 → 뷰어가 쓰는 형태. 실패는 None."""
    r = client.get(url, timeout=45)
    r.raise_for_status()
    qs = _queries(r.text)
    if not qs:
        return None
    info = _pick(qs, "/online/info")
    contents = _pick(qs, "/contents?lang=ko")
    meta = _pick(qs, "/meta")
    if not info.get("title"):
        return None

    pay = info.get("paymentInfo") or {}
    level_code = (contents.get("levelCode") or contents.get("level") or "")
    return {
        "id": info.get("id"),
        "slug": info.get("slug"),
        "url": url.split("?")[0],
        "title": info.get("title") or "",
        "description": (info.get("description") or "")[:300],
        "students": info.get("studentCount") or 0,
        "likes": info.get("likeCount") or 0,
        "duration_sec": info.get("duration") or 0,
        "level": str(level_code).upper(),
        "level_ko": LEVEL_KO.get(str(level_code).upper(), ""),
        "skills": [s for s in (meta.get("skillSlugs") or []) if s][:10],
        "categories": [c for c in (meta.get("categorySlugs") or []) if c][:4],
        # 이 세 가지가 "어떻게 배워야 하는가"에 실제로 답하는 필드다.
        "abilities": [a for a in (contents.get("abilities") or []) if a][:6],
        "targets": [t for t in (contents.get("targets") or []) if t][:5],
        "prerequisites": [b for b in (contents.get("based") or []) if b][:5],
        "instructors": [
            (i.get("nickname") or i.get("name") or "")
            for i in (contents.get("mainInstructors") or [])
        ][:2],
        # 키 이름 주의: 결제가는 paymentPrice 가 아니라 krwPaymentPrice/payPrice 다.
        # paymentPrice 로 읽으면 전 강의 가격이 조용히 null 이 된다.
        "price_regular": pay.get("krwRegularPrice", pay.get("regularPrice")),
        "price_pay": pay.get("krwPaymentPrice", pay.get("payPrice")),
        "is_free": pay.get("krwPaymentPrice", pay.get("payPrice")) == 0,
        "published_at": str(contents.get("publishedAt") or "")[:10],
        "updated_at": str(contents.get("lastUpdatedAt") or "")[:10],
        "is_new": bool(info.get("isNew")),
        "is_best": bool(info.get("isBest")),
    }


def relevant(course: dict, tech: str, alias: list[str]) -> bool:
    """상세에서 다시 확인한다. 슬러그 매칭은 후보를 좁히는 용도일 뿐 근거가 아니다.

    **슬러그는 여기 넣으면 안 된다.** 두 가지 이유로 내용과 어긋난다.
      - 20자에서 잘린다. `e-book-learn-javascr` 는 'javascript' 가 중간에서 끊겨
        부정 별칭이 지워내지 못하고 'java' 만 남는다 — 자바 칸이 JS 전자책으로 찬다.
      - 강좌를 갈아끼워도 URL 은 유지된다. `becoming-a-java-back-1` 의 현재 제목은
        "Claude Code, 서브에이전트…" 다. 슬러그는 그 강의가 한때 무엇이었는지를 말할 뿐이다.
    근거로 쓸 수 있는 것은 상세 페이지가 준 title 과 skillSlugs 다.
    """
    hay = " ".join([
        course.get("title") or "",
        " ".join(course.get("skills") or []), course.get("description") or "",
    ]).lower()
    for neg in NEGATIVE.get(tech, []):
        hay = hay.replace(neg, " ")
    return any(a in hay for a in alias)


def clean_skills(course: dict) -> dict:
    """skillSlugs 에는 퍼센트 인코딩된 한글 슬러그가 섞여 온다(`%EC%BD%94%EB%93%9C-...`).
    그대로 두면 화면에 인코딩 문자열이 그대로 찍힌다. 디코딩은 출력 조립 시점에 한다 —
    캐시에는 이미 가공된 형태가 들어 있어 shape() 만 고쳐서는 기존 캐시가 안 고쳐진다."""
    course["skills"] = [
        up.unquote(s).replace("-", " ").strip() if "%" in s else s
        for s in (course.get("skills") or [])
    ]
    return course


def rank(courses: list[dict]) -> list[dict]:
    """난이도 사다리 우선, 같은 칸에서는 '믿을 만한 최신순'.

    수강생 수만으로 줄 세우면 5년 된 베스트셀러가 늘 1등이라 "지금 어떻게 발전했는가"
    라는 질문에는 최악의 답이 된다. 최신순만 쓰면 수강생 0명이 올라온다. 갱신 연도를
    먼저 보고 그 다음 규모를 본다.
    """
    def key(c: dict):
        year = (c.get("updated_at") or c.get("published_at") or "")[:4]
        return (
            LEVEL_ORDER.get(c.get("level") or "", 9),
            -(int(year) if year.isdigit() else 0),
            -(c.get("students") or 0),
        )
    return sorted(courses, key=key)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="앞 N개 기술만")
    ap.add_argument("--candidates", type=int, default=CANDIDATES)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    if not TRENDS.exists():
        raise SystemExit(f"[inflearn] trends.json 이 없습니다: {TRENDS}  (build_trends.py 먼저)")
    trends = json.loads(TRENDS.read_text(encoding="utf-8"))
    techs: list[str] = trends.get("tracked") or []
    if args.limit:
        techs = techs[: args.limit]
    if not techs:
        raise SystemExit("[inflearn] 추적 기술이 비었습니다.")

    latest = (trends.get("days") or [{}])[-1]
    total = latest.get("total") or 0
    demand = {t: round(100 * latest.get("tech", {}).get(t, 0) / total, 2) for t in techs} if total else {}
    movers = {m["tech"]: m["delta"] for m in
              (trends.get("movers", {}).get("up", []) + trends.get("movers", {}).get("down", []))}

    CACHE_DIR.mkdir(exist_ok=True)
    headers = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    with httpx.Client(headers=headers, follow_redirects=True) as client:
        print("[inflearn] 사이트맵에서 강의 목록 수집…", flush=True)
        catalog = sitemap_course_urls(client)
        print(f"[inflearn] 한국어 강의 {len(catalog):,}건", flush=True)

        out: list[dict] = []
        for i, tech in enumerate(techs, 1):
            alias = aliases_for(tech)
            if not alias:
                print(f"  [{i}/{len(techs)}] {tech}: 별칭 없음, 건너뜀")
                continue
            # 슬러그로 후보를 좁힌다. cid 내림차순으로만 자르면 등록된 지 얼마 안 된
            # 수강생 4명짜리만 뽑히고, 그 기술의 대표 강의는 전부 아래에 깔린다.
            # 그래서 절반은 최신에서, 절반은 나머지 구간에서 고르게 뽑는다.
            cand = [c for c in catalog if any(a in c[1] for a in alias)]
            for neg in NEGATIVE.get(tech, []):
                cand = [c for c in cand
                        if any(a in c[1].replace(neg, " ") for a in alias)]
            cand.sort(key=lambda c: -c[2])
            n_new = max(1, args.candidates // 2)
            newest, rest = cand[:n_new], cand[n_new:]
            if rest and len(newest) < args.candidates:
                step = max(1, len(rest) // (args.candidates - len(newest)))
                newest += rest[::step][: args.candidates - len(newest)]
            cand = newest

            got: list[dict] = []
            for url, slug, cid in cand:
                cf = CACHE_DIR / f"{cid}.json"
                if cf.exists() and not args.refresh:
                    try:
                        c = json.loads(cf.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        c = None
                else:
                    try:
                        c = fetch_course(client, url)
                    except Exception as e:                       # noqa: BLE001
                        print(f"      {slug[:40]}: 실패 {e}", file=sys.stderr)
                        c = None
                    cf.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
                    time.sleep(DELAY)
                if c and relevant(c, tech, alias):
                    got.append(c)

            ranked = [clean_skills(c) for c in rank(got)[:KEEP]]
            out.append({
                "tech": tech,
                "demand_pct": demand.get(tech, 0.0),
                "trend_delta": movers.get(tech),
                "candidates": len(cand),
                "courses": ranked,
                "paid_count": sum(1 for c in ranked if not c["is_free"]),
                "levels": [l for l in ["입문", "중급", "고급"]
                           if any(c["level_ko"] == l for c in ranked)],
            })
            print(f"  [{i}/{len(techs)}] {tech}: 후보 {len(cand)} → 관련 {len(got)} → 채택 {len(ranked)}"
                  f" · 수요 {demand.get(tech, 0)}%", flush=True)

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "inflearn.com 사이트맵 + 강의 상세 페이지 SSR (robots 준수 — /api 미사용)",
        "tech_count": len(out),
        "techs": out,
    }
    OUTPUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"[inflearn] 기술 {len(out)}개 → {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
