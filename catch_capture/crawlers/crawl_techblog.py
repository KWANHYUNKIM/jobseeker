#!/usr/bin/env python3
"""기술 블로그 크롤러 — 한국/미국 엔지니어링 블로그 RSS/Atom 피드 수집.

각 회사 엔지니어링 블로그의 RSS/Atom 피드를 큐레이션 목록(FEEDS)으로 받아
글 단위로 제목·블로그명·국가·URL·발행일·요약·기술스택·태그를 추출한다.
의존성 없이 stdlib(xml.etree)로 RSS 2.0/Atom 1.0 모두 파싱한다.

출력: jd-viewer/public/tech_blogs.json (URL 기준 누적/중복제거)
형식: {generated_at, total, sources:[{company,country,count}], posts:[...]}

실행:
  python -m crawlers.crawl_techblog            # 전체 피드, 피드당 최신 20개
  python -m crawlers.crawl_techblog 40         # 피드당 최신 40개
  python -m crawlers.crawl_techblog 20 woowahan,netflix  # 일부 회사만
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobs_common import USER_AGENT, html_to_text, jitter  # noqa: E402
from tech_taxonomy import CATEGORIES, CATEGORY_OF, categories_of, extract_tech_tags  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent          # jobseeker/
OUT = ROOT / "jd-viewer" / "public" / "tech_blogs.json"

# ── 큐레이션 피드 목록 ────────────────────────────────────────────────
# key: 회사 식별자(필터/중복제거용), company: 표시명, country: 국가, feed: RSS/Atom URL
FEEDS: list[dict] = [
    # 대한민국
    {"key": "woowahan", "company": "우아한형제들", "country": "KR", "feed": "https://techblog.woowahan.com/feed/"},
    {"key": "kakao", "company": "카카오", "country": "KR", "feed": "https://tech.kakao.com/feed/"},
    {"key": "naver-d2", "company": "네이버 D2", "country": "KR", "feed": "https://d2.naver.com/d2.atom"},
    {"key": "toss", "company": "토스", "country": "KR", "feed": "https://toss.tech/rss.xml"},
    {"key": "daangn", "company": "당근", "country": "KR", "feed": "https://medium.com/feed/daangn"},
    {"key": "kurly", "company": "컬리", "country": "KR", "feed": "https://helloworld.kurly.com/rss.xml"},
    {"key": "banksalad", "company": "뱅크샐러드", "country": "KR", "feed": "https://blog.banksalad.com/rss.xml"},
    {"key": "socar", "company": "쏘카", "country": "KR", "feed": "https://tech.socarcorp.kr/feed.xml"},
    {"key": "hyperconnect", "company": "하이퍼커넥트", "country": "KR", "feed": "https://hyperconnect.github.io/feed.xml"},
    {"key": "coupang", "company": "쿠팡", "country": "KR", "feed": "https://medium.com/feed/coupang-engineering"},
    {"key": "zigbang", "company": "직방", "country": "KR", "feed": "https://medium.com/feed/zigbang"},
    {"key": "watcha", "company": "왓챠", "country": "KR", "feed": "https://medium.com/feed/watcha"},
    {"key": "29cm", "company": "29CM", "country": "KR", "feed": "https://medium.com/feed/29cm"},
    {"key": "line", "company": "LINE", "country": "KR", "feed": "https://techblog.lycorp.co.jp/ko/feed/index.xml"},

    # 미국 / 글로벌
    {"key": "netflix", "company": "Netflix", "country": "US", "feed": "https://netflixtechblog.com/feed"},
    {"key": "lyft", "company": "Lyft", "country": "US", "feed": "https://eng.lyft.com/feed"},
    {"key": "airbnb", "company": "Airbnb", "country": "US", "feed": "https://medium.com/feed/airbnb-engineering"},
    {"key": "stripe", "company": "Stripe", "country": "US", "feed": "https://stripe.com/blog/feed.rss"},
    {"key": "cloudflare", "company": "Cloudflare", "country": "US", "feed": "https://blog.cloudflare.com/rss/"},
    {"key": "github", "company": "GitHub", "country": "US", "feed": "https://github.blog/feed/"},
    {"key": "dropbox", "company": "Dropbox", "country": "US", "feed": "https://dropbox.tech/feed"},
    {"key": "slack", "company": "Slack", "country": "US", "feed": "https://slack.engineering/feed/"},
    {"key": "grab", "company": "Grab", "country": "SG", "feed": "https://engineering.grab.com/feed.xml"},
    {"key": "spotify", "company": "Spotify", "country": "US", "feed": "https://engineering.atspotify.com/feed/"},
    {"key": "pinterest", "company": "Pinterest", "country": "US", "feed": "https://medium.com/feed/pinterest-engineering"},
    {"key": "meta", "company": "Meta", "country": "US", "feed": "https://engineering.fb.com/feed/"},
    {"key": "aws", "company": "AWS", "country": "US", "feed": "https://aws.amazon.com/blogs/aws/feed/"},
    {"key": "discord", "company": "Discord", "country": "US", "feed": "https://discord.com/blog/rss.xml"},
    {"key": "etsy", "company": "Etsy", "country": "US", "feed": "https://www.etsy.com/codeascraft/rss"},

    # 일본
    {"key": "mercari", "company": "Mercari", "country": "JP", "feed": "https://engineering.mercari.com/en/blog/feed.xml"},
    {"key": "cookpad", "company": "Cookpad", "country": "JP", "feed": "https://techlife.cookpad.com/feed"},
    {"key": "cyberagent", "company": "CyberAgent", "country": "JP", "feed": "https://developers.cyberagent.co.jp/blog/feed/"},
    {"key": "dena", "company": "DeNA", "country": "JP", "feed": "https://engineering.dena.com/index.xml"},

    # 유럽
    {"key": "zalando", "company": "Zalando", "country": "DE", "feed": "https://engineering.zalando.com/atom.xml"},
    {"key": "soundcloud", "company": "SoundCloud", "country": "DE", "feed": "https://developers.soundcloud.com/blog/blog.rss"},
    {"key": "ft", "company": "Financial Times", "country": "GB", "feed": "https://medium.com/feed/ft-product-technology"},

    # 인도
    {"key": "swiggy", "company": "Swiggy", "country": "IN", "feed": "https://bytes.swiggy.com/feed"},
    {"key": "flipkart", "company": "Flipkart", "country": "IN", "feed": "https://blog.flipkart.tech/feed"},
    {"key": "razorpay", "company": "Razorpay", "country": "IN", "feed": "https://engineering.razorpay.com/feed"},
]

# Atom 네임스페이스
ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"

SUMMARY_MAX = 600


# 글 식별과 무관한 추적/유입 파라미터 (제거 대상). utm_* 는 접두사로 별도 처리.
_TRACKING_PARAMS = {
    "source", "ref", "ref_src", "referer", "referrer", "fbclid", "gclid", "gi",
    "mc_cid", "mc_eid", "_branch_match_id", "spm", "from", "yclid", "igshid",
}


def canonical_url(url: str) -> str:
    """중복 판정용 정규 URL. 추적 파라미터·프래그먼트·끝 슬래시 제거, scheme/host 소문자.

    Medium 피드의 `?source=rss----xxx---4` 처럼 시간에 따라 바뀌는 토큰을 떼어
    같은 글이 다른 URL로 중복 저장되는 것을 막는다. 글 식별자는 경로에 있으므로
    서로 다른 글을 잘못 합치지 않는다.
    """
    url = (url or "").strip()
    try:
        sp = urlsplit(url)
    except ValueError:
        return url
    if not sp.scheme or not sp.netloc:
        return url
    q = [
        (k, v) for k, v in parse_qsl(sp.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    q.sort()
    path = sp.path.rstrip("/") or "/"
    return urlunsplit((sp.scheme.lower(), sp.netloc.lower(), path, urlencode(q), ""))


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _parse_date(raw: str) -> tuple[str, float]:
    """RFC822(RSS) 또는 ISO8601(Atom) 날짜 → (YYYY-MM-DD, epoch초). 실패 시 ('', 0)."""
    raw = (raw or "").strip()
    if not raw:
        return "", 0.0
    # RSS: "Tue, 10 Jun 2025 09:00:00 +0900"
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            return dt.date().isoformat(), dt.timestamp()
    except (TypeError, ValueError):
        pass
    # Atom: "2025-06-10T09:00:00Z" / "2025-06-10T09:00:00+09:00"
    try:
        iso = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat(), dt.timestamp()
    except ValueError:
        return "", 0.0


def _summarize(html: str) -> str:
    text = html_to_text(html or "")
    if len(text) > SUMMARY_MAX:
        text = text[:SUMMARY_MAX].rstrip() + "…"
    return text


# XML 1.0 에서 허용되지 않는 제어문자 (일부 Medium 피드가 섞어 보냄)
_BAD_XML_CHARS = re.compile(
    "[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]"
)
# 엔티티가 아닌 맨 & (well-formed 위반) → &amp;
_BARE_AMP = re.compile(r"&(?!#?\w+;)")
_FEED_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
}


def fetch_feed(url: str, timeout: int = 30) -> bytes:
    """피드 fetch. Accept 헤더로 406 회피, 인증서 실패 시 미검증 컨텍스트로 폴백."""
    req = urllib.request.Request(url, headers=_FEED_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), ssl.SSLError):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read()
        raise


def safe_parse_feed(data: bytes, src: dict) -> list[dict]:
    """parse_feed_raw 래퍼. ParseError 시 잘못된 문자/엔티티를 정리해 1회 재시도."""
    try:
        return parse_feed_raw(data, src)
    except ET.ParseError:
        text = data.decode("utf-8", "ignore")
        text = _BAD_XML_CHARS.sub("", text)
        text = _BARE_AMP.sub("&amp;", text)
        return parse_feed_raw(text.encode("utf-8"), src)


def parse_feed_raw(xml_bytes: bytes, src: dict) -> list[dict]:
    """RSS 2.0 또는 Atom 1.0 XML → 글 레코드 리스트 (tech_stack 미포함, enrich 전 단계)."""
    root = ET.fromstring(xml_bytes)
    tag = root.tag.lower()
    posts: list[dict] = []

    if tag.endswith("rss") or root.find("channel") is not None:
        items = root.findall(".//item")
        for it in items:
            link = _text(it.find("link"))
            title = _text(it.find("title"))
            if not link or not title:
                continue
            desc = _text(it.find("description"))
            content = _text(it.find(f"{CONTENT}encoded")) or desc
            pub, ts = _parse_date(_text(it.find("pubDate")))
            tags = [_text(c) for c in it.findall("category") if _text(c)]
            posts.append(_raw_post(src, title, link, content, desc, pub, ts, tags))
    else:  # Atom
        entries = root.findall(f"{ATOM}entry")
        for en in entries:
            title = _text(en.find(f"{ATOM}title"))
            link = ""
            for ln in en.findall(f"{ATOM}link"):
                rel = ln.get("rel", "alternate")
                if rel == "alternate" or not link:
                    link = ln.get("href", "") or link
            if not link or not title:
                continue
            content = _text(en.find(f"{ATOM}content")) or _text(en.find(f"{ATOM}summary"))
            summary = _text(en.find(f"{ATOM}summary")) or content
            pub, ts = _parse_date(
                _text(en.find(f"{ATOM}published")) or _text(en.find(f"{ATOM}updated"))
            )
            tags = [c.get("term", "") for c in en.findall(f"{ATOM}category") if c.get("term")]
            posts.append(_raw_post(src, title, link, content, summary, pub, ts, tags))
    return posts


def _raw_post(src, title, link, content, summary, pub, ts, tags) -> dict:
    return {
        "key": src["key"],
        "company": src["company"],
        "country": src["country"],
        "title": title.strip(),
        "url": canonical_url(link),
        "published": pub,
        "published_ts": ts,
        "summary": _summarize(summary or content),
        "_blob": f"{title}\n{html_to_text(content or summary or '')}",  # enrich용 임시 본문
        "tags": [t.strip() for t in tags][:8],
    }


def enrich_post(post: dict) -> dict:
    """규칙 기반 보강: 세분화 택소노미로 기술 태그·카테고리 추출 + 언어 추정.

    LLM 없이 결정적으로 동작. tech_stack 은 뷰어 호환을 위해 그대로 두고,
    categories 에 등장 카테고리(언어/AI·ML/LLM·생성형/펌웨어·임베디드 등)를 담는다.
    """
    blob = post.pop("_blob", "") or (post.get("title", "") + "\n" + post.get("summary", ""))
    tags = extract_tech_tags(blob)
    post["tech_stack"] = tags
    post["categories"] = categories_of(tags)
    hangul = sum(1 for ch in blob if "가" <= ch <= "힣")
    post["lang"] = "ko" if hangul >= 10 else "en"
    return post


def parse_feed(xml_bytes: bytes, src: dict) -> list[dict]:
    """파싱 + 보강을 한 번에 (standalone 크롤러용)."""
    return [enrich_post(p) for p in parse_feed_raw(xml_bytes, src)]


def category_meta(posts: list[dict]) -> dict:
    """수집된 글에 실제 등장한 태그→카테고리 맵 + 카테고리 순서(표시용)."""
    present_tags = {t for p in posts for t in p.get("tech_stack", [])}
    tag_categories = {t: CATEGORY_OF[t] for t in present_tags if t in CATEGORY_OF}
    cats_present = {c for c in tag_categories.values()}
    return {
        "categories": [c for c in CATEGORIES if c in cats_present],
        "tag_categories": tag_categories,
    }


def load_existing() -> dict[str, dict]:
    """기존 tech_blogs.json → {url: post} 맵 (누적/중복제거용)."""
    if not OUT.exists():
        return {}
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return {}
    by_url: dict[str, dict] = {}
    for p in data.get("posts", []):
        if not p.get("url"):
            continue
        p["url"] = canonical_url(p["url"])   # 기존 데이터도 정규화해 합침
        by_url[p["url"]] = p
    return by_url


def crawl(per_feed: int, only: set[str] | None) -> None:
    by_url = load_existing()
    print(f"[*] 기존 글 {len(by_url)}건 로드", flush=True)

    feeds = [f for f in FEEDS if not only or f["key"] in only]
    new_count = 0
    for src in feeds:
        try:
            raw = fetch_feed(src["feed"], timeout=30)
            posts = [enrich_post(p) for p in safe_parse_feed(raw, src)[:per_feed]]
        except Exception as e:  # 피드 실패는 건너뛰고 계속
            print(f"  [!] {src['company']:14s} 실패: {type(e).__name__}: {str(e)[:80]}", flush=True)
            continue
        added = 0
        for p in posts:
            if p["url"] not in by_url:
                added += 1
            by_url[p["url"]] = p          # 갱신(요약/태그 최신화)
        new_count += added
        print(f"  [+] {src['company']:14s} {len(posts):3d}건 (신규 {added})", flush=True)
        time.sleep(jitter(700) / 1000)

    posts = sorted(by_url.values(), key=lambda p: p.get("published_ts") or 0, reverse=True)

    # 출처별 집계
    src_counts: dict[str, dict] = {}
    for p in posts:
        s = src_counts.setdefault(p["key"], {"company": p["company"], "country": p["country"], "count": 0})
        s["count"] += 1
    sources = sorted(src_counts.values(), key=lambda s: s["count"], reverse=True)

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(posts),
        "sources": sources,
        **category_meta(posts),
        "posts": posts,
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)
    print(f"[*] 총 {len(posts)}건 (신규 {new_count}) → {OUT.relative_to(ROOT)}", flush=True)


def main() -> None:
    per_feed = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 20
    only = None
    if len(sys.argv) > 2:
        only = {s.strip() for s in sys.argv[2].split(",") if s.strip()}
    crawl(per_feed, only)


if __name__ == "__main__":
    main()
