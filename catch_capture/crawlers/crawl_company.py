#!/usr/bin/env python3
"""회사 도메인 조사 크롤러 (2차 보강).

build_company_stacks.py 가 만든 회사 목록을 받아, 각 회사의 공식 홈페이지를
DuckDuckGo HTML 검색으로 찾고 → 홈페이지에서 회사 소개·기술 신호·도메인을
추출해 jd-viewer/public/company_profiles.json 에 캐시한다.

브라우저 없이 순수 HTTP(jobs_common.http_get)만 쓴다(DDG HTML 엔드포인트는
JS 없이 결과를 내려줌). 결과는 norm 회사명 키로 누적 저장 → 재실행 시 이미
조사한 회사는 건너뛴다(resumable). 차단되면 block_detect 로 백오프.

사용:
    python -m crawlers.crawl_company            # 미조사 회사 전부
    python -m crawlers.crawl_company --limit 20 # 20개만
    python -m crawlers.crawl_company --force 네이버  # 특정 회사 재조사
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # catch_capture 루트
from crawlers import block_detect  # noqa: E402
from crawlers.jobs_common import (  # noqa: E402
    extract_tech_stack, html_to_text, http_get, jitter,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "catch_capture" / "dashboard"))
from classifier import _norm_company  # noqa: E402

# build_company_stacks 의 도메인 추론 재사용 (단일 소스)
sys.path.insert(0, str(ROOT / "jd-viewer" / "bin"))
from build_company_stacks import infer_domains  # noqa: E402

STACKS = ROOT / "jd-viewer" / "public" / "company_stacks.json"
JOBS = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
OUTPUT = ROOT / "jd-viewer" / "public" / "company_profiles.json"

SITE = "company"  # block_detect 마커 식별자

# 홈페이지 후보에서 제외할 도메인(채용·집계·소셜·백과·뉴스)
_EXCLUDE_HOST = (
    "wanted.co.kr", "jumpit.co.kr", "jobkorea.co.kr", "saramin.co.kr",
    "rocketpunch.com", "jobplanet.co.kr", "catch.co.kr", "incruit.com",
    "linkedin.com", "indeed.com", "namu.wiki", "wikipedia.org",
    "youtube.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "blog.naver.com", "cafe.naver.com", "tistory.com", "brunch.co.kr",
    "news.naver.com", "google.com", "duckduckgo.com", "github.com",
    "play.google.com", "apps.apple.com", "thevc.kr", "innoforest.co.kr",
    "ko.indeed.com", "kr.indeed.com", "saramin.com",
)

_RESULT_A = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                       re.IGNORECASE | re.DOTALL)
_RESULT_SNIP = re.compile(r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
                          re.IGNORECASE | re.DOTALL)
# DDG anomaly/차단 페이지 신호 (결과 0건과 함께 나타남)
_DDG_BLOCK_HINTS = ("anomaly", "/anomaly", "challenge", "blocked your", "rate limit")
_TAG = re.compile(r"<[^>]+>")
_META_DESC = re.compile(
    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _strip(html: str) -> str:
    return urllib.parse.unquote(_TAG.sub("", html or "")).replace("&amp;", "&").strip()


def _real_url(href: str) -> str:
    """DDG 결과 href(리다이렉트 래퍼 가능)에서 실제 목적지 URL 추출."""
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href or "/l/?" in href:
        q = urllib.parse.urlparse(href).query
        params = urllib.parse.parse_qs(q)
        if "uddg" in params:
            return params["uddg"][0]
    return href


def _host(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


class Blocked(RuntimeError):
    """검색 제공자가 레이트리밋/anomaly로 결과를 막음 — 백오프 후 재시도 대상."""


def ddg_search(query: str) -> list[dict]:
    """DuckDuckGo HTML 검색 → [{url, title, snippet}]. 결과 0건/anomaly면 Blocked."""
    q = urllib.parse.urlencode({"q": query, "kl": "kr-kr"})
    url = f"https://html.duckduckgo.com/html/?{q}"
    try:
        raw = http_get(url, timeout=20).decode("utf-8", "ignore")
    except Exception as exc:
        reason, code = block_detect.from_http_error(exc)
        if reason:
            block_detect.report(SITE, reason, code, detail=query)
            raise Blocked(f"ddg {reason}") from exc
        raise
    hrefs = _RESULT_A.findall(raw)
    if not hrefs:
        low = raw.lower()
        if block_detect.looks_blocked_text(raw) or any(h in low for h in _DDG_BLOCK_HINTS):
            raise Blocked("ddg anomaly/captcha")
        raise Blocked("ddg no results")  # 0건도 차단으로 취급(빈 캐시 오염 방지)
    snips = _RESULT_SNIP.findall(raw)
    out: list[dict] = []
    for i, (href, title) in enumerate(hrefs):
        snip = _strip(snips[i]) if i < len(snips) else ""
        out.append({"url": _real_url(href), "title": _strip(title), "snippet": snip})
    return out


def search(query: str) -> list[dict]:
    """검색 진입점. DuckDuckGo HTML 사용. 차단/0건이면 Blocked 전파.

    DDG는 IP당 버스트(~5건) 후 ~10분 레이트리밋을 건다. 호출부는 Blocked를
    만나면 즉시 멈추고 block_detect 쿨다운을 건다. 크롤러가 resumable이라
    쿨다운 해제 후 재실행하면 못 채운 회사부터 이어서 조사한다.
    """
    return ddg_search(query)


def pick_homepage(results: list[dict], company: str) -> dict | None:
    """검색 결과에서 공식 홈페이지로 보이는 첫 후보 선택."""
    for r in results:
        host = _host(r["url"])
        if not host:
            continue
        if any(bad in host for bad in _EXCLUDE_HOST):
            continue
        return r
    return None


def fetch_homepage(url: str) -> dict:
    """홈페이지 HTML → {title, desc, text, tech}."""
    try:
        html = http_get(url, timeout=20).decode("utf-8", "ignore")
    except Exception:
        return {}
    title_m = _TITLE.search(html)
    desc_m = _META_DESC.search(html)
    text = html_to_text(html)
    return {
        "title": _strip(title_m.group(1)) if title_m else "",
        "meta_desc": desc_m.group(1).strip() if desc_m else "",
        "text": text[:1200],
        "tech": extract_tech_stack(html + "\n" + text),
    }


def investigate(company: str) -> dict:
    """회사 1곳 조사 → 프로필 dict. 검색 차단 시 Blocked 전파."""
    results = search(f"{company} 회사")
    home = pick_homepage(results, company)
    snippet = results[0]["snippet"] if results else ""
    prof: dict = {
        "name": company,
        "homepage": None,
        "desc": snippet or None,
        "tech": [],
        "domains": [],
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    text_for_domain = snippet
    if home:
        prof["homepage"] = home["url"]
        page = fetch_homepage(home["url"])
        desc = page.get("meta_desc") or home.get("snippet") or page.get("title")
        if desc:
            prof["desc"] = desc.strip()[:400]
        prof["tech"] = page.get("tech", [])
        text_for_domain = " ".join([
            home.get("snippet", ""), page.get("meta_desc", ""),
            page.get("title", ""), page.get("text", ""),
        ])
    prof["domains"] = [d["name"] for d in infer_domains(text_for_domain, top=2)]
    return prof


def _company_list(min_count: int) -> list[str]:
    """조사 대상 회사명 목록 — company_stacks.json 우선, 없으면 jobs 집계."""
    if STACKS.exists():
        data = json.loads(STACKS.read_text(encoding="utf-8"))
        return [c["name"] for c in data.get("companies", [])]
    from collections import Counter
    jobs = json.loads(JOBS.read_text(encoding="utf-8"))
    cnt = Counter((j.get("company") or "").strip() for j in jobs if j.get("company"))
    return [name for name, n in cnt.most_common() if n >= min_count]


def _load_cache() -> dict[str, dict]:
    if not OUTPUT.exists():
        return {}
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict[str, dict]) -> None:
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUTPUT)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="이번 실행에서 조사할 최대 회사 수(0=전부)")
    ap.add_argument("--min", type=int, default=2, help="(stacks 없을 때) 최소 공고 수")
    ap.add_argument("--delay", type=int, default=5000, help="회사 간 기본 대기(ms), 지터 적용")
    ap.add_argument("--force", type=str, default=None, help="특정 회사명만 강제 재조사")
    args = ap.parse_args()

    cache = _load_cache()

    if args.force:
        targets = [args.force]
    else:
        targets = [c for c in _company_list(args.min) if _norm_company(c) not in cache]
        if args.limit:
            targets = targets[: args.limit]

    print(f"[*] 대상 {len(targets)}개 회사 (캐시 {len(cache)}개 보유)", flush=True)
    done = 0
    for i, company in enumerate(targets, 1):
        nk = _norm_company(company)
        try:
            prof = investigate(company)
        except Blocked as e:
            block_detect.note_block(SITE)
            print(f"  [{i}/{len(targets)}] {company}: {e} → 중단(백오프). 잠시 후 재실행하세요", flush=True)
            break
        except Exception as e:
            print(f"  [{i}/{len(targets)}] {company}: 실패 {e}", flush=True)
            prof = {"name": company, "homepage": None, "desc": None,
                    "tech": [], "domains": [], "ts": datetime.now().isoformat(timespec="seconds")}
        cache[nk] = prof
        done += 1
        hp = prof.get("homepage") or "—"
        doms = ", ".join(prof.get("domains") or []) or "—"
        print(f"  [{i}/{len(targets)}] {company:18s} | {hp[:42]:42s} | {doms}", flush=True)
        if done % 5 == 0:
            _save_cache(cache)
        time.sleep(jitter(args.delay) / 1000)

    _save_cache(cache)
    block_detect.note_success(SITE)
    print(f"[*] {OUTPUT.relative_to(ROOT)} 저장 — 신규 {done}개 / 총 {len(cache)}개", flush=True)


if __name__ == "__main__":
    main()
