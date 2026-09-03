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

import hashlib
import json
import re
import socket
import ssl
import sys
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobs_common import USER_AGENT, html_to_text, jitter  # noqa: E402
from tech_taxonomy import CATEGORIES, CATEGORY_OF, categories_of, extract_tech_tags  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent          # jobseeker/
OUT = ROOT / "jd-viewer" / "public" / "tech_blogs.json"
CONTENT_DIR = ROOT / "jd-viewer" / "public" / "blog_content"   # 글별 본문/번역 (글 열 때만 로드)
FAILURE_LOG = CONTENT_DIR / "_failures.json"                   # 본문 수집 실패 이력 (재시도 백오프)

CONTENT_CHARS_MAX = 40000   # 저장 본문 상한 (과도한 길이 방지)
TRANSLATE_CHUNK = 4500      # 무료 번역 endpoint 1회 요청 길이 한도(문자)
TRANSLATE_URL_MAX = 12000   # 같은 한도를 URL 인코딩 길이로 잰 것 — CJK 본문의 실질 한도
TRANSLATE_RETRY = 3         # 청크 1개당 재시도 횟수 (일시적 네트워크/차단 대비)
TRANSLATE_TIMEOUT = 30      # 번역 요청 소켓 타임아웃(초). deep_translator 1.9.1 은 내부
                            # requests.get 에 timeout 을 안 넘겨서, 서버가 응답을 멈추면
                            # 영원히 대기한다 — auto_crawl 데몬이 TLS 핸드셰이크에서
                            # 12일간 멈춰 있던 원인.
CONTENT_LIMIT_DEFAULT = 40  # 회차당 신규 본문 수집/번역 상한 (폭주·차단 방지)
RENDER_MIN = 1000           # 정적 추출이 이보다 짧으면 JS 렌더(Playwright) 시도
CONTENT_MAX_FAILS = 3       # 이만큼 연속 실패하면 '수집 불가'로 보고 재시도 주기를 늦춘다
CONTENT_RETRY_DAYS = 14     # 수집 불가 판정 후 다시 시도해 보는 간격(일)

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
        "_content_html": content or summary or "",                     # content 단계용 원문 HTML
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


def content_id(url: str) -> str:
    """글별 본문 파일 식별자 (정규 URL의 안정 해시)."""
    return hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()[:16]


# 펜스 코드블록 (``` ... ``` / ~~~ ... ~~~) — 번역 제외 대상
_CODE_FENCE = re.compile(r"(```.*?```|~~~.*?~~~)", re.DOTALL)


_SENTENCE_END = re.compile(r"(?<=[.。!?！？])\s+")
# 무료 endpoint 가 간헐적으로 돌려주는 구글 오류 페이지 — 예외 대신 본문처럼 들어온다
_TRANSLATE_ERROR = re.compile(r"That[’']s an error|That[’']s all we know")


def _fits(text: str) -> bool:
    """번역 요청 1회에 담을 수 있는 크기인가.

    무료 번역 endpoint 는 원문을 URL 쿼리로 실어 보내므로 실제 한도는 문자 수가 아니라
    퍼센트 인코딩 후 길이다. 일본어·한국어는 1 글자가 9 바이트로 부풀어서 4,500 자만 돼도
    요청이 통째로 거부된다 — 일본계 블로그 본문이 매 회차 번역 실패로 남던 원인."""
    return len(text) <= TRANSLATE_CHUNK and len(quote(text)) <= TRANSLATE_URL_MAX


def _pack(pieces: list[str], sep: str) -> list[str]:
    """조각들을 한도 안에서 최대한 이어붙인다. 혼자서도 한도를 넘는 조각은 그대로 둔다."""
    out: list[str] = []
    buf = ""
    for piece in pieces:
        cand = f"{buf}{sep}{piece}" if buf else piece
        if buf and not _fits(cand):
            out.append(buf)
            buf = piece
        else:
            buf = cand
    if buf:
        out.append(buf)
    return out


@contextmanager
def _socket_timeout(seconds: float):
    """이 블록 안에서 만들어지는 소켓에 기본 타임아웃을 건다(타임아웃 인자가 없는 라이브러리용)."""
    prev = socket.getdefaulttimeout()
    socket.setdefaulttimeout(seconds)
    try:
        yield
    finally:
        socket.setdefaulttimeout(prev)


def _translate_one(tr, text: str) -> str | None:
    """청크 하나 번역. 일시적 실패는 백오프 후 재시도하고, 끝내 실패하면 None."""
    if not text.strip():
        return text
    for attempt in range(TRANSLATE_RETRY):
        try:
            with _socket_timeout(TRANSLATE_TIMEOUT):
                out = tr.translate(text) or text
        except Exception:
            out = None
        if out is not None and not _TRANSLATE_ERROR.search(out):
            time.sleep(jitter(400) / 1000)   # 연속 요청 간격 — 차단 방지
            return out
        time.sleep(1.5 * (attempt + 1))
    return None


def _translate_split(tr, text: str) -> str | None:
    """문단 → 줄 → 문장 순으로 쪼개 번역하고 구분자를 그대로 복원한다."""
    for sep, pieces in (("\n\n", text.split("\n\n")),
                        ("\n", text.split("\n")),
                        (" ", _SENTENCE_END.split(text))):
        chunks = _pack(pieces, sep) if len(pieces) > 1 else []
        if len(chunks) <= 1 and (not chunks or chunks[0] == text):
            continue     # 이 구분자로는 안 쪼개진다 → 다음 구분자
        out: list[str] = []
        for chunk in chunks:
            done = _translate_chunks(tr, chunk)
            if done is None:
                return None
            out.append(done)
        return sep.join(out)

    # 문장 경계조차 없는 덩어리 — 인코딩 비율로 환산해 강제 절단
    step = max(200, len(text) * TRANSLATE_URL_MAX // max(1, len(quote(text))))
    out = []
    for i in range(0, len(text), step):
        done = _translate_one(tr, text[i:i + step])
        if done is None:
            return None
        out.append(done)
    return "".join(out)


def _translate_chunks(tr, prose: str) -> str | None:
    """산문 마크다운을 한도 내 청크로 나눠 번역. 실패 시 None.

    한도 안이면 그대로 보내고, 넘거나 endpoint 가 실패를 돌려주면 더 잘게 쪼개 재시도한다."""
    if not prose.strip():
        return prose   # 코드블록 사이 공백/줄바꿈은 그대로
    if _fits(prose):
        done = _translate_one(tr, prose)
        if done is not None:
            return done
        # 한도 안인데도 실패 — 더 잘게 쪼개 한 번 더 (간헐적 500 대비)
    return _translate_split(tr, prose)


# 번역기는 URL 을 만나면 그 뒤 문장을 통째로 잘라먹고(마크다운 링크가 든 긴 문장에서 특히),
# 이미지 문법 ![alt](url) 은 아예 지워버린다. 둘 다 번역할 게 없으니 자리표시자로 빼두고
# 번역이 끝난 뒤 되돌린다. 이미지는 alt 까지 통째로 빼야 살아남는다(alt 는 번역 포기).
_MD_IMAGE = re.compile(r"!\[[^\]\n]*\]\([^)\s]+\)")
_URL_TOKEN = re.compile(r"https?://[^\s)\]\"'<>]+")
_ATOM_MASK = re.compile(r"⟦\s*(\d+)\s*⟧")


def _mask_atoms(md: str) -> tuple[str, list[str]]:
    """번역기가 훼손하는 조각(이미지·URL)을 ⟦n⟧ 으로 치환."""
    atoms: list[str] = []

    def repl(m: "re.Match[str]") -> str:
        atoms.append(m.group(0))
        return f"⟦{len(atoms) - 1}⟧"

    return _URL_TOKEN.sub(repl, _MD_IMAGE.sub(repl, md)), atoms


def _unmask_atoms(md: str, atoms: list[str]) -> str:
    def repl(m: "re.Match[str]") -> str:
        i = int(m.group(1))
        return atoms[i] if i < len(atoms) else m.group(0)

    return _ATOM_MASK.sub(repl, md)


_WARNED: set[str] = set()


def _warn_missing(pkg: str, effect: str) -> None:
    """빠진 선택 의존성을 프로세스당 한 번만 크게 알린다.

    이 파일의 import 들은 전부 try/except 안에 있어서, 패키지가 없어도 크롤은
    '성공'한 것처럼 끝난다. 실제로 trafilatura 없이 몇 주를 돌면서 RSS 요약을
    본문으로 저장하고, deep_translator 없이 영어 글을 통째로 버리고 있었다 —
    로그 어디에도 그 사실이 없었다. 조용한 실패를 시끄럽게 만든다.
    """
    if pkg in _WARNED:
        return
    _WARNED.add(pkg)
    print(f"  [!] {pkg} 미설치 — {effect}", flush=True)
    print("      해결: catch_capture/.venv/bin/pip install -r catch_capture/requirements.txt", flush=True)


def _translate_ko(md: str) -> str:
    """마크다운을 한국어 번역. 코드블록은 원문 그대로 두고 산문만 번역.

    제목(#)·목록(-)·표(|)·인라인코드(`)는 번역기가 구조를 보존하므로 그대로 번역하되,
    펜스 코드블록(``` ```)은 분리해 번역에서 제외한다(코드/식별자 훼손 방지)."""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        _warn_missing("deep_translator", "번역 불가 → 영어 글은 본문 파일이 생성되지 않는다")
        return ""
    tr = GoogleTranslator(source="auto", target="ko")
    md, atoms = _mask_atoms(md)
    parts = _CODE_FENCE.split(md)
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("```") or part.startswith("~~~"):
            out.append(part)            # 코드블록 원문 유지
            continue
        translated = _translate_chunks(tr, part)
        if translated is None:
            return ""                   # 실패 → 미완료로 처리(다음 회차 재시도)
        out.append(translated)
    return _unmask_atoms("".join(out), atoms).strip()


# 영상 임베드 — trafilatura가 통째로 버리므로, 추출 전에 링크 단락으로 치환해 보존
_VIDEO_HOSTS = (
    "tv.naver.com", "youtube.com/embed", "youtube-nocookie.com", "youtu.be",
    "youtube.com/watch", "player.vimeo.com", "vimeo.com", "dailymotion.com",
    "wistia.", "loom.com",
)
_IFRAME_RE = re.compile(r"<iframe\b[^>]*?\bsrc=[\"']([^\"']+)[\"'][^>]*>(?:</iframe>)?", re.I | re.S)
_VIDEO_RE = re.compile(r"<video\b[^>]*>.*?</video>", re.I | re.S)
_VSRC_RE = re.compile(r"\bsrc=[\"']([^\"']+)[\"']", re.I)


def _video_link_p(src: str) -> str:
    if src.startswith("//"):
        src = "https:" + src
    # 앵커로 치환 → trafilatura(include_links)가 마크다운 링크로 보존, 위치 유지
    return f'<p><a href="{src}">📹 영상 보기</a></p>'


def _inject_video_embeds(html: str) -> str:
    """영상 iframe/<video>를 링크 단락으로 치환(추출 시 드롭 방지). 비영상 iframe은 보존."""
    def iframe_repl(m: "re.Match[str]") -> str:
        src = m.group(1)
        return _video_link_p(src) if any(h in src.lower() for h in _VIDEO_HOSTS) else m.group(0)

    def video_repl(m: "re.Match[str]") -> str:
        sm = _VSRC_RE.search(m.group(0))
        return _video_link_p(sm.group(1)) if sm else ""

    html = _IFRAME_RE.sub(iframe_repl, html)
    html = _VIDEO_RE.sub(video_repl, html)
    return html


def _collect_video_urls(html: str) -> list[str]:
    """원문 HTML에서 영상 URL(영상 호스트 iframe + <video>/<source>) 수집."""
    if not html:
        return []
    urls: list[str] = []
    for src in _IFRAME_RE.findall(html):
        if any(h in src.lower() for h in _VIDEO_HOSTS):
            urls.append("https:" + src if src.startswith("//") else src)
    for block in _VIDEO_RE.findall(html):
        sm = _VSRC_RE.search(block)
        if sm:
            src = sm.group(1)
            urls.append("https:" + src if src.startswith("//") else src)
    seen: set[str] = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def _append_missing_videos(md: str, video_urls: list[str]) -> str:
    """본문에 빠진 영상 URL을 끝에 링크로 추가(추출기가 영상을 드롭한 경우 보강)."""
    missing = [u for u in video_urls if u not in md]
    if missing:
        md = md.rstrip() + "\n\n" + "\n\n".join(f"[📹 영상 보기]({u})" for u in missing)
    return md


def _to_markdown(html: str) -> str:
    """HTML → 구조 보존 마크다운 (제목·목록·표·코드블록·이미지·영상). 실패 시 빈 문자열."""
    if not html:
        return ""
    try:
        import trafilatura
    except ImportError:
        _warn_missing("trafilatura", "본문 추출 불가 → RSS 요약만 남고 이미지·표·코드블록 소실")
        return ""
    try:
        md = trafilatura.extract(
            _inject_video_embeds(html), output_format="markdown",
            include_tables=True, include_comments=False, include_formatting=True,
            include_images=True, include_links=True,
        )
        return md or ""
    except Exception:
        return ""


# 마크다운 링크/이미지의 URL 부분: ](URL ...)
_MD_URL = re.compile(r"(\]\()([^)\s]+)")


def _absolutize_md(md: str, base: str) -> str:
    """마크다운 내 상대경로 이미지/링크 URL을 글 주소 기준 절대경로로 변환."""
    def repl(m: "re.Match[str]") -> str:
        url = m.group(2)
        if url.startswith(("http://", "https://", "data:", "#", "mailto:", "//")):
            return m.group(0)
        return m.group(1) + urljoin(base, url)
    return _MD_URL.sub(repl, md)


def _render_html(url: str) -> str:
    """Playwright로 JS 렌더링한 HTML. D2처럼 본문이 JS로 그려지는 페이지용. 실패 시 빈 문자열."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                try:
                    page.goto(url, wait_until="networkidle", timeout=25000)
                except Exception:
                    pass            # 타임아웃이어도 그때까지 렌더된 내용 사용
                html = page.content()
            finally:
                browser.close()
            return html or ""
    except Exception:
        return ""


def _article_text(post: dict) -> str:
    """글 본문을 구조 보존 마크다운으로 추출.

    정적 페이지 추출 → RSS 본문 폴백 → 그래도 빈약하면(JS 렌더 페이지로 추정)
    Playwright로 렌더링해 추출. 영상은 위치 보존+누락분 보강한다."""
    url = post["url"]
    raw = post.get("_content_html") or ""
    static_html = ""
    try:
        import trafilatura
    except ImportError:
        _warn_missing("trafilatura", "원문 페이지를 받지 못해 RSS 본문으로만 처리된다")
        static_html = ""
    else:
        try:
            static_html = trafilatura.fetch_url(url) or ""
        except Exception:
            static_html = ""

    md = _to_markdown(static_html)          # 정적 페이지
    rss_md = _to_markdown(raw)              # RSS 본문
    if len(rss_md) > len(md):
        md = rss_md

    htmls = [static_html, raw]
    if len(md) < RENDER_MIN:                # JS 렌더 페이지로 추정 → 브라우저 렌더링
        rendered = _render_html(url)
        if rendered:
            htmls.append(rendered)
            rmd = _to_markdown(rendered)
            if len(rmd) > len(md):
                md = rmd

    if not md:
        md = html_to_text(raw)              # 최후의 폴백

    # 영상 보강: 모든 소스의 영상 URL 중 본문에 빠진 것을 끝에 추가(중복 제거)
    vids = list(dict.fromkeys(v for h in htmls for v in _collect_video_urls(h)))
    md = _append_missing_videos(md, vids)
    md = _absolutize_md(md, url)            # 상대 이미지/링크 → 절대경로
    return md.strip()[:CONTENT_CHARS_MAX]


def build_content(post: dict, translate: bool = True) -> bool:
    """글 본문(+번역) 파일을 생성. 이미 있으면 False(건너뜀), 새로 만들면 True.

    실패하면 사유를 post["_content_fail"] 에 남긴다(extract/translate). 인덱스에는
    안 들어가고(_ 접두사) 실패 이력 기록에만 쓴다."""
    cid = content_id(post["url"])
    path = CONTENT_DIR / f"{cid}.json"
    post["content_id"] = cid
    post.pop("_content_fail", None)
    if path.exists():
        return False
    text = _article_text(post)
    if not text:
        post["_content_fail"] = "extract"   # 본문 추출 실패(봇 차단·삭제된 글 등)
        return False
    content_ko = ""
    if translate and post.get("lang") != "ko":
        content_ko = _translate_ko(text)
        if not content_ko:
            post["_content_fail"] = "translate"
            return False   # 번역 실패(차단 등) → 파일 미작성, 다음 회차 재시도
    rec = {
        "url": post["url"],
        "title": post.get("title"),
        "lang": post.get("lang"),
        "format": "markdown",
        "content": text,
        "content_ko": content_ko,
        "translated": bool(content_ko),
        "chars": len(text),
    }
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return True


def _load_failures() -> dict:
    """본문 수집 실패 이력 {content_id: {url, company, reason, count, last}}."""
    try:
        return json.loads(FAILURE_LOG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_failures(fails: dict) -> None:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FAILURE_LOG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(fails, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FAILURE_LOG)


def process_content(posts: list[dict], limit: int = CONTENT_LIMIT_DEFAULT,
                    translate: bool = True) -> dict:
    """본문 파일이 없는 글을 최신순으로 limit개까지 수집/번역. content_id는 전부 채움.

    이미 본문 파일이 있는 글은 content_id만 세팅하고 건너뛴다(재번역 0, 멱등).
    """
    built = 0
    have = 0
    blocked = 0
    fails = _load_failures()
    now = time.time()
    ordered = sorted(posts, key=lambda p: p.get("published_ts") or 0, reverse=True)
    for p in ordered:
        if not p.get("url"):
            continue
        cid = content_id(p["url"])
        p["content_id"] = cid
        p.pop("content_state", None)
        if (CONTENT_DIR / f"{cid}.json").exists():
            have += 1
            fails.pop(cid, None)
            continue

        rec = fails.get(cid)
        if rec and rec.get("count", 0) >= CONTENT_MAX_FAILS:
            # 연속 실패 — 사이트가 막았거나 글이 사라졌다. 뷰어에 그대로 알리고
            # 재시도는 CONTENT_RETRY_DAYS 마다 한 번만 (매 회차 낭비 방지).
            p["content_state"] = "blocked"
            if now - rec.get("last", 0) < CONTENT_RETRY_DAYS * 86400:
                blocked += 1
                continue

        if built >= limit:
            continue   # 이번 회차 상한 — 나머지는 다음 회차에
        if build_content(p, translate=translate):
            built += 1
            fails.pop(cid, None)
            p.pop("content_state", None)
            print(f"  [content] {p['company']:12s} {p.get('lang'):2s} "
                  f"{'번역✓' if p.get('lang') != 'ko' else '원문'} {p['title'][:40]}", flush=True)
            time.sleep(jitter(600) / 1000)
        else:
            rec = fails.setdefault(cid, {"url": p["url"], "company": p.get("company"), "count": 0})
            rec["count"] = rec.get("count", 0) + 1
            rec["reason"] = p.pop("_content_fail", "unknown")
            rec["last"] = now
            if rec["count"] >= CONTENT_MAX_FAILS:
                p["content_state"] = "blocked"
                blocked += 1
    _save_failures(fails)
    skipped = sum(1 for p in posts if not (CONTENT_DIR / f"{content_id(p['url'])}.json").exists())
    print(f"[content] 신규 {built}건 · 기존 {have}건 · 미수집 {skipped}건 "
          f"(수집 불가 {blocked}건 포함, 상한 {limit})", flush=True)
    return {"built": built, "have": have, "pending": skipped, "blocked": blocked}


def _strip_internal(posts: list[dict]) -> list[dict]:
    """인덱스(tech_blogs.json) 기록 전 내부용(_) 필드 제거."""
    return [{k: v for k, v in p.items() if not k.startswith("_")} for p in posts]


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

    # 본문 전체 수집 + 번역 (본문 파일 없는 글만, 상한 내)
    process_content(posts)

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
        "posts": _strip_internal(posts),
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
