"""회사 로고 수집 — 메인 화면(`/`) 회사 카드의 로고를 `company.logo_url`(DB 014)에 채운다.

새로 긁는 곳은 없다. 우리가 이미 받는 **공고 원문 페이지**(마감 재확인도 같은 페이지를 묻는다)에
회사 로고 주소가 실려 있어서 그 주소만 읽는다. 이미지는 받지 않는다 — 뷰어가 원본 주소로 띄운다.

  dev(캐치) : JSON-LD JobPosting.hiringOrganization.logo        (board.catch.co.kr/…/CI/…)
  jumpit    : 페이지 데이터의 "companyName" 옆 "logo"            (cdn.jumpit.co.kr/…)
  원티드    : 공고 페이지·회사 API 모두 큰 회사에도 기본 그림(/images/wdes/)만 주고, robots.txt 가
              CloudFront 403 이라 허용 범위를 확인할 수 없어 쓰지 않는다(파서는 남겨 둔다).
  사람인·잡코리아: 공고 페이지에 추천 회사 로고가 여럿 섞여 이 회사 것을 가를 수 없어 아직 안 쓴다.

모집중인 공고가 있는 회사 중 로고가 없는 곳을, 공고가 많은 회사부터 묻는다. 못 찾아도
`logo_checked_at` 을 찍어 30일 동안은 다시 묻지 않는다.

    python -m crawlers.crawl_logos --limit 200          # 크롤 회차 끝(run_extras)이 부르는 것과 같다
    python -m crawlers.crawl_logos --limit 3000         # 처음 한 번 백필
    python -m crawlers.crawl_logos --dry-run --limit 20
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import html
import json
import re
import time
import urllib.request

from crawlers.jobs_common import USER_AGENT, jitter

SLEEP_MS = 1500
TIMEOUT = 15
RECHECK_DAYS = 30
SITE_ORDER = ("dev", "jumpit")   # 로고가 확실한 곳만. 원티드는 기본 그림만 주고 robots 를 못 읽어(403) 뺐다

_CANDIDATES = """
    SELECT co.id, co.display_name,
           array_agg(j.url ORDER BY array_position(%(order)s::text[], j.site::text), j.first_seen_at DESC)
               FILTER (WHERE j.site::text = ANY(%(order)s::text[]))             AS urls,
           array_agg(j.site::text ORDER BY array_position(%(order)s::text[], j.site::text), j.first_seen_at DESC)
               FILTER (WHERE j.site::text = ANY(%(order)s::text[]))             AS sites,
           count(*) AS active
      FROM company co
      JOIN job j       ON j.company_id = co.id
      JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
     WHERE co.logo_url IS NULL
       AND (co.logo_checked_at IS NULL OR co.logo_checked_at < now() - make_interval(days => %(days)s))
     GROUP BY co.id
    HAVING count(*) FILTER (WHERE j.site::text = ANY(%(order)s::text[])) > 0
     ORDER BY count(*) DESC
     LIMIT %(limit)s
"""


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def _from_dev(page: str) -> str | None:
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            d = json.loads(block)
        except ValueError:
            continue
        for x in d if isinstance(d, list) else [d]:
            org = x.get("hiringOrganization") if isinstance(x, dict) else None
            logo = org.get("logo") if isinstance(org, dict) else None
            if isinstance(logo, dict):
                logo = logo.get("url")
            if isinstance(logo, str) and logo.startswith("http"):
                return logo
    return None


def _from_jumpit(page: str) -> str | None:
    # 페이지 데이터가 문자열 안에 한 번 더 JSON 으로 들어 있어 따옴표가 \" 로 온다
    t = page.replace('\\"', '"').replace("\\/", "/")
    m = re.search(r'"companyName":"[^"]*","logo":"(https://cdn\.jumpit\.co\.kr/[^"]+)"', t)
    return m.group(1) if m else None


def _from_wanted(page: str) -> str | None:
    m = re.search(r'"company":\{"company_id":\d+.{0,2000}?"logo_image":"(https://static\.wanted\.co\.kr/[^"]+)"', page, re.S)
    if not m or "/images/wdes/" in m.group(1):
        return None
    return m.group(1)


PARSERS = {"dev": _from_dev, "jumpit": _from_jumpit, "wanted": _from_wanted}


def find_logo(urls: list[str], sites: list[str]) -> tuple[str | None, str | None]:
    """사이트마다 공고 하나씩만 묻는다(같은 사이트 공고는 같은 회사 로고를 준다)."""
    tried = set()
    for url, site in zip(urls, sites):
        if site in tried:
            continue
        tried.add(site)
        try:
            logo = PARSERS[site](_get(url))
        except Exception:                                   # noqa: BLE001 — 한 회사 실패가 회차를 죽이지 않게
            logo = None
        time.sleep(jitter(SLEEP_MS) / 1000)
        if logo:
            return html.unescape(logo), site
    return None, None


def run(limit: int = 200, dry_run: bool = False) -> dict:
    from store.db.conn import cursor
    with cursor() as cur:
        cur.execute(_CANDIDATES, {"order": list(SITE_ORDER), "days": RECHECK_DAYS, "limit": limit})
        rows = cur.fetchall()
    found = 0
    for i, r in enumerate(rows, 1):
        logo, site = find_logo(r["urls"] or [], r["sites"] or [])
        found += bool(logo)
        print(f"  [{i}/{len(rows)}] {r['display_name'][:24]:24s} {site or '-':7s} {logo or '없음'}", flush=True)
        if dry_run:
            continue
        with cursor() as cur:
            cur.execute("UPDATE company SET logo_url = COALESCE(%s, logo_url), logo_source = COALESCE(%s, logo_source),"
                        " logo_checked_at = now() WHERE id = %s", (logo, site, r["id"]))
    print(f"[logos] {len(rows)}곳 확인 → 로고 {found}곳", flush=True)
    return {"checked": len(rows), "found": found}


if __name__ == "__main__":
    args = _sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 200
    run(limit, dry_run="--dry-run" in args)
