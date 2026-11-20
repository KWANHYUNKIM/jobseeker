"""velog·dev.to 밖의 블로그 후기 — Medium 태그 피드(키 없음) + 티스토리(카카오 검색 API, 키 있을 때만).

  python -m careers.blogs medium
  python -m careers.blogs tistory "합격 후기" "이직 회고"     # KAKAO_REST_KEY 가 있어야 한다

일부러 뺀 곳: 네이버 블로그(사용자 결정), 브런치(robots 가 AI 크롤러를 이름으로 막는다),
구글·다음 검색 결과 페이지(robots `Disallow: /`·약관). 티스토리 본문은 블로그마다 robots 를 읽고 허용된 곳만 받는다.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from careers import checks, store
from careers.collect import _RELEVANT, USER_AGENT

MEDIUM_TAGS = ["개발자", "신입개발자", "개발자취업", "개발자이직", "개발자회고", "개발자면접", "코딩테스트", "부트캠프",
               "주니어개발자", "백엔드", "프론트엔드", "비전공개발자", "회고", "취업", "이직"]   # 넓은 태그(회고·취업·이직)는 본문 IT 검사로 거른다
KAKAO = "https://dapi.kakao.com/v2/search/blog"
_TAG = re.compile(r"<[^>]+>")
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(url: str, headers: dict | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _text(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    lines = (ln.strip() for ln in soup.get_text("\n").splitlines())
    return "\n".join(ln for ln in lines if ln)


def _allowed(url: str) -> bool:
    host = urllib.parse.urlsplit(url).netloc
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            rp.parse(_get(f"https://{host}/robots.txt", timeout=10).decode("utf-8", "replace").splitlines())
            _robots[host] = rp
        except Exception:  # noqa: BLE001 — robots 를 못 읽으면 받지 않는다
            _robots[host] = None
    rp = _robots[host]
    return bool(rp and rp.can_fetch(USER_AGENT, url))


def _save(source: str, key: str, url: str, title: str, date: str, body: str, query: str, tags=None) -> str:
    item = {"id": store.rid(source, key), "source": source, "url": url, "title": title, "date": date,
            "tags": tags or [], "query": query, "body": body[:30000], "collected_at": _now()}
    store.save_json(store.RAW / f"{item['id']}.json", item)
    return item["id"]


# ── Medium: 태그 피드(medium.com/feed/tag/<태그>, robots 허용) — 태그마다 최신 10개.
#    태그 피드에는 요약만 있고, 본문은 글쓴이 피드(medium.com/feed/@아이디)의 content:encoded 에 있다.
def _medium_body(link: str, authors: dict, ns: dict) -> str:
    m = re.match(r"https://medium\.com/(@[^/]+)/", link)
    if not m:
        return ""
    who = m.group(1)
    if who not in authors:
        authors[who] = {}
        try:
            root = ET.fromstring(_get(f"https://medium.com/feed/{who}"))
            for it in root.iter("item"):
                authors[who][(it.findtext("link") or "").split("?")[0]] = it.findtext("content:encoded", "", ns) or ""
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.5)
    return _text(authors[who].get(link, ""))


def run_medium(tags: list[str] | None = None) -> int:
    seen = store.load_json(store.SEEN, {})
    for k in [k for k, v in seen.items() if k.startswith("medium:") and v == "skip:nobody"]:
        del seen[k]                          # 예전 판은 태그 피드의 요약만 보고 본문 없음으로 넘겼다
    new = 0
    authors: dict[str, dict[str, str]] = {}
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    for tag in tags or MEDIUM_TAGS:
        try:
            root = ET.fromstring(_get(f"https://medium.com/feed/tag/{urllib.parse.quote(tag)}"))
        except Exception as e:  # noqa: BLE001
            print(f"  ! medium #{tag}: {e}", flush=True)
            continue
        time.sleep(2)
        got = 0
        for it in root.iter("item"):
            link = (it.findtext("link") or "").split("?")[0]
            key = f"medium:{link}"
            title = it.findtext("title") or ""
            if not link or key in seen:
                continue
            if not _RELEVANT.search(title):
                seen[key] = "skip:title"
                continue
            body = _medium_body(link, authors, ns)      # 태그 피드는 요약뿐 — 본문은 글쓴이 피드에 있다
            if len(body) < 300:
                seen[key] = "skip:nobody"
                continue
            if not checks.is_it(f"{title}\n{body}"):
                seen[key] = "skip:not_it"
                continue
            try:
                date = parsedate_to_datetime(it.findtext("pubDate") or "").date().isoformat()
            except Exception:  # noqa: BLE001
                date = ""
            seen[key] = _save("medium", link, link, title, date, body, f"tag:{tag}",
                              [c.text for c in it.findall("category") if c.text])
            got += 1
        new += got
        print(f"  medium #{tag}: 새 글 {got}", flush=True)
    store.save_json(store.SEEN, seen)
    print(f"medium 끝 — 새 글 {new}", flush=True)
    return new


# ── 티스토리: 카카오 블로그 검색 API 로 글 주소를 찾고, 본문은 그 블로그(robots 허용)에서 받는다
def kakao_key() -> str:
    return os.environ.get("KAKAO_REST_KEY", "").strip()


def _tistory_body(url: str) -> str:
    soup = BeautifulSoup(_get(url), "lxml")
    for sel in ("div.tt_article_useless_p_margin", "div.entry-content", "div.article_view", "div#article-view",
                "div.contents_style", "article"):
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 200:
            return _text(str(el))
    return ""


def it_query(kw: str) -> str:
    """티스토리는 블로그 전체를 찾는다 — IT 낱말이 없는 검색어('합격 후기', '하나은행 입사')에는 '개발자' 를 붙인다."""
    return kw if checks.is_it(kw) else f"{kw} 개발자"


def run_tistory(keywords: list[tuple[str, int]]) -> int:
    """keywords: (검색어, 쪽 수). 한 쪽 = 50건, 카카오 상한 50쪽."""
    key = kakao_key()
    if not key:
        print("티스토리 건너뜀: KAKAO_REST_KEY 없음", flush=True)
        return 0
    seen = store.load_json(store.SEEN, {})
    new = 0
    for n, (kw, pages) in enumerate(keywords, 1):
        found = got = 0
        for page in range(1, min(pages, 50) + 1):
            q = urllib.parse.urlencode({"query": it_query(kw), "size": 50, "page": page, "sort": "accuracy"})
            try:
                d = json.loads(_get(f"{KAKAO}?{q}", {"Authorization": f"KakaoAK {key}"}))
            except Exception as e:  # noqa: BLE001
                print(f"  ! 카카오 검색 {kw} p{page}: {e}", flush=True)
                if "401" in str(e) or "429" in str(e):
                    store.save_json(store.SEEN, seen)
                    return new
                break
            docs = d.get("documents") or []
            found += len(docs)
            for doc in docs:
                url = doc.get("url") or ""
                if ".tistory.com/" not in url:
                    continue
                sk = f"tistory:{url}"
                title = html.unescape(_TAG.sub("", doc.get("title") or ""))
                if sk in seen:
                    continue
                if not _RELEVANT.search(title):
                    seen[sk] = "skip:title"
                    continue
                if not _allowed(url):
                    seen[sk] = "skip:robots"
                    continue
                try:
                    body = _tistory_body(url)
                except Exception:  # noqa: BLE001
                    continue
                time.sleep(1)
                if len(body) < 300:
                    seen[sk] = "skip:nobody"
                    continue
                if not checks.is_it(f"{title}\n{body}"):
                    seen[sk] = "skip:not_it"
                    continue
                seen[sk] = _save("tistory", url, url, title, (doc.get("datetime") or "")[:10], body, kw)
                got += 1
            time.sleep(0.5)
            if (d.get("meta") or {}).get("is_end") or len(docs) < 50:
                break
        new += got
        print(f"[티스토리 {n}/{len(keywords)}] {kw}: 검색 {found} → 새 글 {got} (누적 {new})", flush=True)
        if n % 10 == 0:
            store.save_json(store.SEEN, seen)
    store.save_json(store.SEEN, seen)
    print(f"티스토리 끝 — 새 글 {new}", flush=True)
    return new


if __name__ == "__main__":
    store.ensure()
    if sys.argv[1:2] == ["medium"]:
        run_medium()
    elif sys.argv[1:2] == ["tistory"]:
        run_tistory([(k, 5) for k in sys.argv[2:]])
    else:
        print(__doc__)
