#!/usr/bin/env python3
"""기술 블로그 크롤러 — LangGraph 파이프라인 버전 (LLM 없음 = 비용 0).

LangGraph는 그래프 오케스트레이션 라이브러리일 뿐이며, 여기 모든 노드는
규칙 기반(결정적)으로 동작한다. LLM API 키도, 호출 비용도 필요 없다.

파이프라인 (StateGraph):
  discover ── 회사 도메인에서 RSS/Atom 피드 URL을 자동 발견(auto-discovery)
     │        + 큐레이션된 FEEDS 병합
  fetch ───── 각 피드 fetch + 파싱 (RSS 2.0 / Atom 1.0)
     │
  enrich ──── 기술스택 추출(정규식) + 언어 추정
     │
  store ───── URL 기준 중복제거/누적 → jd-viewer/public/tech_blogs.json

실행:
  python -m crawlers.crawl_techblog_graph             # 피드당 최신 20개
  python -m crawlers.crawl_techblog_graph 40          # 피드당 40개
  python -m crawlers.crawl_techblog_graph 20 woowahan,netflix
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, TypedDict
from urllib.parse import urljoin

from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobs_common import http_get, jitter  # noqa: E402
from crawl_techblog import (  # noqa: E402
    FEEDS,
    OUT,
    ROOT,
    CONTENT_LIMIT_DEFAULT,
    canonical_url,
    category_meta,
    enrich_post,
    fetch_feed,
    process_content,
    safe_parse_feed,
    _strip_internal,
)

# ── 피드 자동 발견용 시드(피드 URL 미상, 홈페이지만 알고 있는 블로그) ──────
SEED_SITES: list[dict] = [
    {"key": "devsisters", "company": "데브시스터즈", "country": "KR", "site": "https://tech.devsisters.com/"},
    {"key": "kakaopay", "company": "카카오페이", "country": "KR", "site": "https://tech.kakaopay.com/"},
    {"key": "yogiyo", "company": "요기요", "country": "KR", "site": "https://techblog.yogiyo.co.kr/"},
    {"key": "spotify-r", "company": "Spotify R&D", "country": "US", "site": "https://research.atspotify.com/"},
    {"key": "stackoverflow", "company": "Stack Overflow", "country": "US", "site": "https://stackoverflow.blog/"},
]

# <link rel="alternate" type="application/rss+xml" href="...">
_FEED_LINK = re.compile(
    r"""<link[^>]+type=["']application/(?:rss|atom)\+xml["'][^>]*>""", re.I
)
_HREF = re.compile(r"""href=["']([^"']+)["']""", re.I)
_COMMON_PATHS = ["/rss.xml", "/feed.xml", "/atom.xml", "/index.xml", "/feed/", "/feed", "/rss"]


def discover_feed(site_url: str) -> Optional[str]:
    """홈페이지 HTML의 <link rel=alternate> 또는 흔한 경로로 RSS/Atom 피드 URL을 추정."""
    try:
        html = http_get(site_url, timeout=20).decode("utf-8", "ignore")
    except Exception:
        html = ""
    m = _FEED_LINK.search(html)
    if m:
        h = _HREF.search(m.group(0))
        if h:
            return urljoin(site_url, h.group(1))
    for p in _COMMON_PATHS:
        url = urljoin(site_url, p)
        try:
            head = http_get(url, timeout=12)[:600].lower()
            if b"<rss" in head or b"<feed" in head:
                return url
        except Exception:
            continue
    return None


# ── LangGraph 상태 ────────────────────────────────────────────────────
class GraphState(TypedDict):
    per_feed: int
    only: Optional[set]
    content_limit: int       # 회차당 신규 본문 수집/번역 상한
    feeds: list[dict]        # 해석된 피드 목록 (key, company, country, feed)
    raw_posts: list[dict]
    posts: list[dict]        # 누적 병합된 전체 글
    new_count: int
    content_stats: dict
    stats: dict


# ── 노드 ──────────────────────────────────────────────────────────────
def node_discover(state: GraphState) -> dict:
    only = state.get("only")
    feeds: list[dict] = [
        {k: f[k] for k in ("key", "company", "country", "feed")}
        for f in FEEDS
        if not only or f["key"] in only
    ]
    print(f"[discover] 큐레이션 피드 {len(feeds)}개", flush=True)

    seeds = [s for s in SEED_SITES if not only or s["key"] in only]
    found = 0
    for s in seeds:
        feed = discover_feed(s["site"])
        if feed:
            feeds.append({"key": s["key"], "company": s["company"], "country": s["country"], "feed": feed})
            found += 1
            print(f"[discover]  + {s['company']:14s} → {feed}", flush=True)
        else:
            print(f"[discover]  - {s['company']:14s} 피드 못 찾음", flush=True)
        time.sleep(jitter(500) / 1000)
    print(f"[discover] 자동 발견 {found}개 / 총 {len(feeds)}개 피드", flush=True)
    return {"feeds": feeds}


def node_fetch(state: GraphState) -> dict:
    per_feed = state["per_feed"]
    raw: list[dict] = []
    ok = fail = 0
    for src in state["feeds"]:
        try:
            data = fetch_feed(src["feed"], timeout=30)
            posts = safe_parse_feed(data, src)[:per_feed]
            raw.extend(posts)
            ok += 1
            print(f"[fetch]  {src['company']:14s} {len(posts):3d}건", flush=True)
        except Exception as e:
            fail += 1
            print(f"[fetch]  {src['company']:14s} 실패: {type(e).__name__}: {str(e)[:70]}", flush=True)
        time.sleep(jitter(700) / 1000)
    print(f"[fetch] 피드 {ok}개 성공 / {fail}개 실패 · 글 {len(raw)}건", flush=True)
    return {"raw_posts": raw}


def node_enrich(state: GraphState) -> dict:
    posts = [enrich_post(p) for p in state["raw_posts"]]
    with_stack = sum(1 for p in posts if p["tech_stack"])
    print(f"[enrich] {len(posts)}건 보강 · 기술스택 추출 {with_stack}건", flush=True)
    return {"posts": posts}


def node_merge(state: GraphState) -> dict:
    """기존 누적본 로드 + 이번 수집분을 URL 정규화 기준으로 병합/중복제거."""
    by_url: dict[str, dict] = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            for p in prev.get("posts", []):
                if p.get("url"):
                    p["url"] = canonical_url(p["url"])   # 기존 데이터도 정규화해 합침
                    by_url[p["url"]] = p
        except (json.JSONDecodeError, KeyError):
            by_url = {}
    before = len(by_url)
    for p in state["posts"]:
        by_url[p["url"]] = p
    posts = sorted(by_url.values(), key=lambda p: p.get("published_ts") or 0, reverse=True)
    new_count = len(posts) - before
    print(f"[merge] 누적 {len(posts)}건 (신규 {new_count})", flush=True)
    return {"posts": posts, "new_count": new_count}


def node_content(state: GraphState) -> dict:
    """본문 파일 없는 글을 상한 내에서 전체 크롤 + 한국어 번역."""
    stats = process_content(state["posts"], limit=state.get("content_limit", CONTENT_LIMIT_DEFAULT))
    return {"content_stats": stats}


def node_store(state: GraphState) -> dict:
    posts = state["posts"]
    src_counts: dict[str, dict] = {}
    for p in posts:
        s = src_counts.setdefault(
            p["key"], {"company": p["company"], "country": p["country"], "count": 0}
        )
        s["count"] += 1
    sources = sorted(src_counts.values(), key=lambda s: s["count"], reverse=True)

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(posts),
        "sources": sources,
        **category_meta(posts),
        "posts": _strip_internal(posts),
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)
    cs = state.get("content_stats", {})
    stats = {"total": len(posts), "new": state.get("new_count", 0), "sources": len(sources),
             "content_built": cs.get("built", 0), "content_pending": cs.get("pending", 0)}
    print(f"[store] 총 {stats['total']}건 (신규 {stats['new']}) · "
          f"본문 신규 {stats['content_built']}건 → {OUT.relative_to(ROOT)}", flush=True)
    return {"stats": stats}


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("discover", node_discover)
    g.add_node("fetch", node_fetch)
    g.add_node("enrich", node_enrich)
    g.add_node("merge", node_merge)
    g.add_node("content", node_content)
    g.add_node("store", node_store)
    g.add_edge(START, "discover")
    g.add_edge("discover", "fetch")
    g.add_edge("fetch", "enrich")
    g.add_edge("enrich", "merge")
    g.add_edge("merge", "content")
    g.add_edge("content", "store")
    g.add_edge("store", END)
    return g.compile()


def run(per_feed: int = 20, only: Optional[set] = None,
        content_limit: int = CONTENT_LIMIT_DEFAULT) -> dict:
    app = build_graph()
    final = app.invoke({"per_feed": per_feed, "only": only, "content_limit": content_limit,
                        "feeds": [], "raw_posts": [], "posts": [],
                        "new_count": 0, "content_stats": {}, "stats": {}})
    return final.get("stats", {})


def main() -> None:
    per_feed = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 20
    only = None
    if len(sys.argv) > 2:
        only = {s.strip() for s in sys.argv[2].split(",") if s.strip()}
    run(per_feed, only)


if __name__ == "__main__":
    main()
