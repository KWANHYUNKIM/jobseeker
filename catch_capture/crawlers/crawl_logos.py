"""회사 로고 수집 — 메인 화면(`/`) 회사 카드의 로고를 **우리 서버에** 둔다(company.logo_url, DB 014·015).

로고 주소는 우리가 이미 받는 **공고 원문 페이지**(마감 재확인도 같은 페이지를 묻는다)에서 읽는다.
그다음 이미지를 한 번 받아 확인·재인코딩해 `jd-viewer/public/logos/` 에 둔다 — 방문자 브라우저가
원본 서버(캐치·점핏·구글)에 직접 가지 않는다. 그쪽 서버 상태·접근 기록에 묶이지 않고, 원본이
그림을 바꾸거나 내려도 카드가 깨지지 않는다.

  dev(캐치) : JSON-LD JobPosting.hiringOrganization.logo        (board.catch.co.kr/…/CI/…)
  jumpit    : 페이지 데이터의 "companyName" 옆 "logo"            (cdn.jumpit.co.kr/…)
  원티드    : 공고 페이지·회사 API 모두 큰 회사에도 기본 그림(/images/wdes/)만 주고, robots.txt 가
              CloudFront 403 이라 허용 범위를 확인할 수 없어 쓰지 않는다(파서는 남겨 둔다).
  랠릿(boards): 공고 상세 공개 JSON 의 companyLogo                     (cdn.rallit.com/…)
  사람인    : 위에서 못 찾은 국내 회사는 어느 사이트에서 왔든 사람인 회사 검색 → 기업정보 페이지
              (robots Allow: /zf_user/company-info/)의 og:image 를 쓴다. 검색 결과에서 이름(norm)이
              똑같은 회사가 **하나일 때만** 받는다(clogo.saramin.co.kr/…). 공고 페이지의 logo_src 는
              추천 공고 회사 것이 섞여 쓰지 않는다.
  잡코리아  : 공고 페이지 JSON-LD 에 회사명만 있고 로고가 없다.
  파비콘    : 뷰어의 도메인 표(src/utils/companyMark.ts DOMAIN)에 적은 큰 회사는 구글 파비콘을 한 번
              받아 logos/d/<도메인>.png 로 둔다(--favicons). 뷰어는 이 파일을 먼저 찾는다. 같은 그림을
              DB(company.logo_url, logo_source='favicon')에도 적는다 — API·통계·에이전트 서버는 DB 만 본다.

받은 이미지는 그대로 두지 않는다 — Pillow 로 열어 형식(PNG·JPEG·GIF·WEBP·ICO·BMP)을 확인하고
128px PNG 로 다시 그려 저장한다. SVG 는 받지 않는다(스크립트를 품을 수 있다). 다시 그리면 이미지 안에
덧붙은 다른 내용(폴리글랏)과 메타데이터가 떨어지고, 512KB 넘는 파일·4천만 화소 넘는 그림은 버린다.

모집중인 공고가 있는 회사 중 로고가 없는 곳을, 공고가 많은 회사부터 묻는다. 못 찾아도
`logo_checked_at` 을 찍어 30일 동안은 다시 묻지 않는다.

    python -m crawlers.crawl_logos --limit 200          # 크롤 회차 끝(run_extras)이 부르는 것과 같다
    python -m crawlers.crawl_logos --mirror             # 원본 주소로 남아 있던 로고를 우리 서버로 옮긴다
    python -m crawlers.crawl_logos --favicons           # 도메인 표의 파비콘을 받아 둔다(없는 것만)
    python -m crawlers.crawl_logos --dry-run --limit 20
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import hashlib
import html
import io
import json
import re
import time
import urllib.request

from core.paths import JD_VIEWER_DIR, VIEWER_PUBLIC

from crawlers.jobs_common import USER_AGENT, jitter

SLEEP_MS = 1500
TIMEOUT = 15
RECHECK_DAYS = 30
# 로고가 확실한 곳만. 원티드는 기본 그림만 주고 robots 를 못 읽어(403) 뺐다.
# 그래도 못 찾으면 사람인 기업정보에서 이름이 똑같은 회사의 로고를 쓴다(saramin_logo) — 사이트 무관.
# 기타 보드는 랠릿 공고만 — 공고 상세 JSON 의 companyLogo(_boards_logo).
SITE_ORDER = ("dev", "jumpit", "boards")

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


_HANGUL = re.compile(r"[가-힣]")   # 외국 회사 이름으로 사람인을 뒤지면 동명 국내 회사가 걸릴 수 있다
SARAMIN_SEARCH = "https://www.saramin.co.kr/zf_user/search/company?searchword={q}"
SARAMIN_COMPANY = "https://www.saramin.co.kr/zf_user/company-info/view?csn={csn}"   # robots 가 Allow 로 적은 곳
_SARAMIN_HIT = re.compile(r'<a href="/zf_user/company-info/view\?csn=([A-Za-z0-9%=+/]+)" title="([^"]+)"[^>]*class="company_popup"')
_OG_IMAGE = re.compile(r'<meta[^>]+property="og:image"[^>]+content="(https://clogo\.saramin\.co\.kr/company/logo/[^"]+)"')


def saramin_logo(name: str) -> str | None:
    """사람인 기업정보의 로고 — 어느 사이트에서 온 회사든 쓴다(국내 회사는 대개 사람인에 기업정보가 있다).

    회사 검색 결과에서 **이름(norm)이 똑같은** 회사만 고르고, 그 회사 기업정보 페이지의 og:image 가
    사람인 로고 서버(clogo)일 때만 받는다. 이름이 다르거나 동명 회사가 여럿이면 받지 않는다 —
    남의 로고를 붙이느니 글자 마크가 낫다. (공고 페이지에도 logo_src 가 있지만 추천 공고 회사 것이
    섞여 있고, 본문 요청은 따로 불러오는 내부 경로라 쓰지 않는다.)
    """
    from urllib.parse import quote
    from core.normalize import company as norm
    want = norm(name)
    if not want or len(want) < 2:
        return None
    page = _get(SARAMIN_SEARCH.format(q=quote(name)))
    csns = {csn for csn, title in _SARAMIN_HIT.findall(page) if norm(html.unescape(title)) == want}
    if len(csns) != 1:
        return None
    time.sleep(jitter(SLEEP_MS) / 1000)
    m = _OG_IMAGE.search(_get(SARAMIN_COMPANY.format(csn=csns.pop())))
    return html.unescape(m.group(1)) if m else None


RALLIT_DETAIL = "https://www.rallit.com/client/api/v1/position/{id}"   # crawl_boards 가 쓰는 공개 JSON(robots 허용)


def _boards_logo(url: str, name: str) -> str | None:
    """기타 보드(boards) 공고 — 지금은 랠릿만. 공고 상세 JSON 의 companyLogo 를 쓴다
    (목록의 companyRepresentativeImage 는 로고가 아니라 사무실·서비스 배너 사진이다).
    상세의 회사명이 우리 회사명과 같을 때만 받는다."""
    from core.normalize import company as norm
    m = re.match(r"https://www\.rallit\.com/positions/(\d+)", url or "")
    if not m:
        return None
    req = urllib.request.Request(RALLIT_DETAIL.format(id=m.group(1)),
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        d = json.loads(r.read().decode("utf-8", "replace")).get("data") or {}
    if name and norm(d.get("companyName") or "") != norm(name):
        return None
    logo = d.get("companyLogo")
    return logo if isinstance(logo, str) and logo.startswith("https://cdn.rallit.com/") else None


PARSERS = {"dev": _from_dev, "jumpit": _from_jumpit, "wanted": _from_wanted}
URL_PARSERS = {"boards": _boards_logo}   # 페이지가 아니라 공고 주소로 원본 API 를 묻는 곳

# 저장해도 되는 로고 주소 — 확인한 이미지 서버의 https 만. 원본 페이지가 바뀌거나 이상한 값을 줘도
# 엉뚱한 주소(다른 호스트·javascript:·http)가 DB 를 거쳐 화면의 <img> 로 가지 않게 여기서 막는다.
# 뷰어(utils/companyMark.ts safeLogoUrl)와 API(home/service.py safe_logo)도 같은 목록으로 한 번 더 거른다.
LOGO_HOSTS = {"board.catch.co.kr", "cdn.jumpit.co.kr", "static.wanted.co.kr", "clogo.saramin.co.kr", "cdn.rallit.com"}


def _safe(url: str | None) -> str | None:
    from urllib.parse import urlsplit
    if not url or len(url) > 500:
        return None
    try:
        u = urlsplit(url)
    except ValueError:
        return None
    return url if u.scheme == "https" and u.hostname in LOGO_HOSTS and not u.username else None


# ── 우리 서버에 두기 ────────────────────────────────────────────────────
LOGO_DIR = VIEWER_PUBLIC / "logos"
MAX_BYTES = 512 * 1024
SIZE = 128
FORMATS = {"PNG", "JPEG", "GIF", "WEBP", "ICO", "BMP"}


def _download(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if not (r.headers.get("Content-Type") or "").lower().startswith("image/"):
            return None
        if "svg" in (r.headers.get("Content-Type") or "").lower():
            return None
        data = r.read(MAX_BYTES + 1)
    return data if len(data) <= MAX_BYTES else None


def store_image(data: bytes, sub: str, name: str) -> str | None:
    """확인·재인코딩해 logos/<sub>/<name>.png 로 둔다. 뷰어가 쓸 경로를 돌려준다(못 쓰면 None)."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 40_000_000           # 압축 폭탄 — 넘으면 열 때 예외
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in FORMATS:
                return None
            probe.verify()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if max(im.size) <= 16:                # 구글이 모르는 도메인에 주는 16px 지구본 따위
                return None
            im = im.convert("RGBA")
            im.thumbnail((SIZE, SIZE), Image.LANCZOS)
            out = LOGO_DIR / sub / f"{name}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".tmp")
            im.save(tmp, "PNG", optimize=True)
            tmp.replace(out)
    except Exception:                                   # noqa: BLE001 — 깨진 그림 하나가 회차를 죽이지 않게
        return None
    return f"/logos/{sub}/{name}.png"


def mirror(origin: str) -> str | None:
    """원본 로고 주소 → 우리 서버 경로. 허용 호스트의 https 가 아니면 받지도 않는다."""
    if not _safe(origin):
        return None
    try:
        data = _download(origin)
    except Exception:                                   # noqa: BLE001
        return None
    name = hashlib.sha1(origin.encode()).hexdigest()[:16]
    return store_image(data, "c", name) if data else None


def find_logo(urls: list[str], sites: list[str], name: str = "") -> tuple[str | None, str | None]:
    """사이트마다 공고 하나씩만 묻는다(같은 사이트 공고는 같은 회사 로고를 준다)."""
    tried = set()
    for url, site in zip(urls, sites):
        if site in URL_PARSERS:
            if site in tried or not re.match(r"https://www\.rallit\.com/", url or ""):
                continue        # boards 는 출처가 여럿이다 — 로고를 주는 출처(랠릿) 공고를 고른다
        elif site in tried:
            continue
        tried.add(site)
        try:
            if site in URL_PARSERS:
                logo = URL_PARSERS[site](url, name)
            else:
                page = _get(url)
                logo = PARSERS[site](page)
        except Exception:                                   # noqa: BLE001 — 한 회사 실패가 회차를 죽이지 않게
            logo = None
        time.sleep(jitter(SLEEP_MS) / 1000)
        logo = _safe(html.unescape(logo)) if logo else None
        if logo:
            return logo, site
    return None, None


def run(limit: int = 200, dry_run: bool = False) -> dict:
    from store.db.conn import cursor
    with cursor() as cur:
        cur.execute(_CANDIDATES, {"order": list(SITE_ORDER), "days": RECHECK_DAYS, "limit": limit})
        rows = cur.fetchall()
    found = 0
    for i, r in enumerate(rows, 1):
        origin, site = find_logo(r["urls"] or [], r["sites"] or [], r["display_name"])
        if not origin and _HANGUL.search(r["display_name"] or ""):
            try:                    # 공고 원문이 로고를 안 주면 사람인 기업정보(이름이 똑같은 회사만)
                origin = _safe(saramin_logo(r["display_name"]))
                site = "saramin" if origin else None
            except Exception:                               # noqa: BLE001
                origin = None
            time.sleep(jitter(SLEEP_MS) / 1000)
        local = mirror(origin) if origin and not dry_run else None
        found += bool(local)
        print(f"  [{i}/{len(rows)}] {r['display_name'][:24]:24s} {site or '-':7s} {local or origin or '없음'}", flush=True)
        if dry_run:
            continue
        with cursor() as cur:
            cur.execute("UPDATE company SET logo_url = COALESCE(%s, logo_url), logo_origin = COALESCE(%s, logo_origin),"
                        " logo_source = COALESCE(%s, logo_source), logo_checked_at = now() WHERE id = %s",
                        (local, origin if local else None, site if local else None, r["id"]))
    print(f"[logos] {len(rows)}곳 확인 → 로고 {found}곳", flush=True)
    return {"checked": len(rows), "found": found}


def mirror_existing() -> dict:
    """014 때 원본 주소로 저장한 로고를 우리 서버로 옮긴다. 못 받으면 비워서 다음 회차가 다시 찾게 한다."""
    from store.db.conn import cursor
    with cursor() as cur:
        cur.execute("SELECT id, display_name, logo_url FROM company WHERE logo_url LIKE 'http%'")
        rows = cur.fetchall()
    moved = 0
    for r in rows:
        local = mirror(r["logo_url"])
        moved += bool(local)
        with cursor() as cur:
            cur.execute("UPDATE company SET logo_origin = logo_url, logo_url = %s::text,"
                        " logo_checked_at = CASE WHEN %s::text IS NULL THEN NULL ELSE logo_checked_at END WHERE id = %s",
                        (local, local, r["id"]))
        time.sleep(jitter(400) / 1000)
    print(f"[logos] 원본 주소 {len(rows)}곳 → 우리 서버 {moved}곳", flush=True)
    return {"checked": len(rows), "moved": moved}


DOMAIN_TS = JD_VIEWER_DIR / "src" / "utils" / "companyMark.ts"
_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,80}\.[a-z]{2,}$")


def favicons(refresh_days: int = 30) -> dict:
    """뷰어 도메인 표의 파비콘을 받아 logos/d/<도메인>.png 로 둔다. 있는 파일은 refresh_days 가 지나야 다시 받는다."""
    src = DOMAIN_TS.read_text(encoding="utf-8")
    block = src[src.index("const DOMAIN"):src.index("\n}\n", src.index("const DOMAIN"))]
    domains = sorted({d for d in re.findall(r":\s*'([^']*)'", block) if _DOMAIN_RE.match(d)})
    got = skipped = 0
    for dom in domains:
        out = LOGO_DIR / "d" / f"{dom}.png"
        if out.exists() and time.time() - out.stat().st_mtime < refresh_days * 86400:
            skipped += 1
            continue
        # 구글은 맨 도메인(kdn.com)을 모르고 www. 호스트만 아는 곳이 많다 — 16px 지구본이 오면 www. 로 한 번 더 묻는다.
        ok = False
        for host in (dom, f"www.{dom}"):
            try:
                data = _download(f"https://www.google.com/s2/favicons?domain={host}&sz=64")
            except Exception:                           # noqa: BLE001
                data = None
            if data and store_image(data, "d", dom):
                ok = True
                break
            time.sleep(jitter(300) / 1000)
        got += ok
        time.sleep(jitter(300) / 1000)
    print(f"[logos] 파비콘 {len(domains)}개 — 새로 {got}, 이미 있음 {skipped}", flush=True)
    stored = favicons_to_db()
    return {"domains": len(domains), "got": got, "skipped": skipped, "stored": stored}


def _viewer_norm(name: str) -> str:
    """뷰어 companyMark.ts normalizeCompany 의 파이썬 판 — 도메인 표의 키를 같은 규칙으로 맞춘다."""
    import unicodedata
    n = unicodedata.normalize("NFKC", name)
    n = re.sub(r"\((주|유|재|사)\)", "", n)
    n = re.sub(r"(주식회사|유한회사)", "", n)
    n = re.sub(r"\s*\([^)]*\)\s*", "", n)
    return re.sub(r"\s+", "", n).strip()


def favicons_to_db() -> int:
    """도메인 표로 파비콘을 받은 회사를 DB 에도 적는다(company.logo_url·domains).

    뷰어는 표를 직접 읽어 파비콘을 띄우지만, API·통계·에이전트 서버는 DB 만 본다. 파일은 /logos/c/ 에
    한 벌 더 둔다 — DB 로고 경로 규칙(/logos/c/<16자 해시>.png, safeLogoUrl·safe_logo)을 그대로 지키려고.
    공고 원문에서 받은 로고(dev·jumpit·saramin)가 이미 있으면 덮지 않는다.
    """
    import shutil
    from store.db.conn import cursor
    src = DOMAIN_TS.read_text(encoding="utf-8")
    block = src[src.index("const DOMAIN"):src.index("\n}\n", src.index("const DOMAIN"))]
    table = {_viewer_norm(k): v for k, v in re.findall(r"'([^']+)':\s*'([^']*)'", block) if _DOMAIN_RE.match(v)}
    with cursor() as cur:
        cur.execute("SELECT id, display_name, domains FROM company WHERE logo_url IS NULL AND merged_into IS NULL")
        rows = cur.fetchall()
    n = 0
    for r in rows:
        dom = table.get(_viewer_norm(r["display_name"]))
        fav = LOGO_DIR / "d" / f"{dom}.png" if dom else None
        if not fav or not fav.exists():
            continue
        name = hashlib.sha1(f"favicon:{dom}".encode()).hexdigest()[:16]
        out = LOGO_DIR / "c" / f"{name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fav, out)
        with cursor() as cur:
            cur.execute("UPDATE company SET logo_url = %s, logo_source = 'favicon', logo_origin = %s,"
                        " domains = CASE WHEN cardinality(domains) = 0 THEN ARRAY[%s] ELSE domains END,"
                        " logo_checked_at = now() WHERE id = %s AND logo_url IS NULL",
                        (f"/logos/c/{name}.png", f"https://www.google.com/s2/favicons?domain={dom}", dom, r["id"]))
        n += 1
    print(f"[logos] 파비콘 → DB {n}곳", flush=True)
    return n


if __name__ == "__main__":
    args = _sys.argv[1:]
    if "--mirror" in args:
        mirror_existing()
    elif "--favicons" in args:
        favicons()
    else:
        limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 200
        run(limit, dry_run="--dry-run" in args)
