"""PC 부품 가격 크롤러 → jd-viewer/public/hardware/prices.json (누적, 하루 한 번).

무엇을 사는지는 여기서 정하지 않는다. 부품 목록·스펙·등급은 hw-engine 이 공식 자료로
조사해 `public/hardware/parts.json` 에 두고, 이 크롤러는 그 부품마다 **오늘 최저가**만
받아 온다. 부품의 `price_query` 가 검색어와 거름 규칙이다.

수집처 (2026-09-29 조사 — robots/약관 확인):
  danawa : 통합검색 search.danawa.com/dsearch.php?query=…  (robots 허용, Crawl-delay 10)
           한 쪽에 상품마다 상품번호(pcode)·분류·최저가·상품명이 다 실려 있어서 상세
           페이지를 따로 열지 않는다. 가격 차트(/info/ajax/)와 목록 ajax(/list/ajax/)는
           robots 가 막는다 — 그래서 **가격 이력은 우리가 매일 찍어서 쌓는다.**
           약관·콘텐츠이용안내가 콘텐츠산업 진흥법으로 DB 를 보호한다고 적고 있어
           **가격 숫자·상품명·링크만** 남긴다. 이미지·설명·스펙 문자열·리뷰는 받지 않는다.
           스펙은 parts.json 이 제조사 공식 자료에서 가져온다.

누적 규칙:
  - 부품마다 그날의 최저가·중앙값·매물 수를 `history` 에 하루 한 줄 남긴다(같은 날 다시
    돌면 그 줄을 바꾼다). 지난날의 가격은 다시 받을 수 없으니 지우지 않는다.
  - 하루에 한 번만 돈다. 크롤 사이클은 30분마다 돌지만 가격은 하루 단위로 보면 충분하고,
    Crawl-delay 10초 × 부품 수(~70) 라 한 번에 12분쯤 걸린다. `--force` 로 다시 돈다.
  - 거름 규칙에 걸린 매물이 하나도 없으면 그날 줄을 비워 둔다(0원으로 적지 않는다).

사용:
    python -m crawlers.crawl_hardware                 # 오늘 아직 안 돌았으면 돈다
    python -m crawlers.crawl_hardware --force
    python -m crawlers.crawl_hardware --only gpu-rtx-5070,cpu-ryzen-7-9800x3d --dry-run
    python -m crawlers.crawl_hardware --selftest     # 파서 점검(네트워크 없이)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import html
import json
import re
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from crawlers.jobs_common import USER_AGENT, jitter

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
HW_DIR = ROOT_DIR / "jd-viewer" / "public" / "hardware"
PARTS_PATH = HW_DIR / "parts.json"
OUT_PATH = HW_DIR / "prices.json"

SEARCH_URL = "https://search.danawa.com/dsearch.php?query={q}&tab=goods"
PRODUCT_URL = "https://prod.danawa.com/info/?pcode={pcode}"
CRAWL_DELAY_MS = 10_500     # robots.txt 의 Crawl-delay: 10 보다 조금 넉넉하게
TIMEOUT = 25
KEEP_OFFERS = 60            # 부품마다 남기는 매물 수(가격 오름차순). 제품별 스펙(models/)이 제 가격을 찾으려면 잘리면 안 된다

# 상품 한 줄은 다음 상품이 시작하는 곳까지다. 상품 안에도 <ul> 이 여럿이라 </ul> 로는 못 끊는다.
# 마지막 상품은 쪽 끝까지 가므로 ITEM_MAX 로 자른다(한 상품은 20~30KB).
ITEM_RE = re.compile(r'id="productItem(\d+)"(.*?)(?=id="productItem\d+"|\Z)', re.S)
ITEM_MAX = 40_000
CATE_RE = re.compile(r'id="productItem_categoryInfo_\d+"\s+value="([^"]*)"')
PRICE_RE = re.compile(r'id="min_price_\d+"\s+value="(\d+)"')
NAME_RE = re.compile(r'<p class="prod_name">\s*<a[^>]*>(.*?)</a>', re.S)
# 옵션 한 줄: <li id="productInfoDetail_<pcode>"> … <strong>409,640</strong>원 … <span class="text">24GB</span>
OPT_PRICE_RE = re.compile(r'<strong>([\d,]+)</strong>\s*원')
OPT_LABEL_RE = re.compile(r'<p class="memory_sect">.*?<span class="text">(.*?)</span>', re.S)
# 보증·상태가 다른 매물은 같은 물건의 가격으로 치지 않는다 — 최저가가 늘 중고·병행이 된다.
ALWAYS_NOT = ["중고", "리퍼", "해외구매", "병행수입", "전시", "반품"]


def _norm(s: str) -> str:
    """비교용 — 대소문자·공백을 지운다. 'RTX 5070 Ti' 와 'RTX5070TI' 를 같게 본다."""
    return re.sub(r"\s+", "", s).lower()


def fetch(q: str) -> str:
    req = urllib.request.Request(SEARCH_URL.format(q=urllib.parse.quote(q)),
                                 headers={"User-Agent": USER_AGENT, "Accept": "text/html",
                                          "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", "ignore")


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def parse(page: str) -> list[dict]:
    """검색 결과 한 쪽 → [{pcode, cate, price, name}]. 가격이 없는 상품(단종·품절)은 뺀다.

    다나와는 용량만 다른 상품(16GB·32GB, 1TB·2TB)을 한 줄로 묶고 옵션마다 상품번호와
    가격을 따로 단다. 대표가(min_price)는 옵션 중 가장 싼 값이라 그대로 쓰면 16GB 를 찾는데
    8GB 값이 잡힌다 — 그래서 옵션이 있으면 옵션마다 한 건으로 펼치고, 옵션 글자(용량)를
    상품명 뒤에 붙여 거름 규칙이 볼 수 있게 한다.
    """
    out, seen = [], set()
    for m in ITEM_RE.finditer(page):
        body = m.group(2)[:ITEM_MAX]
        cate, name = CATE_RE.search(body), NAME_RE.search(body)
        if not name:
            continue
        base = {"cate": html.unescape(cate.group(1)) if cate else "", "name": _text(name.group(1))}
        opts = _options(body)
        if not opts:
            price = PRICE_RE.search(body)
            opts = [(m.group(1), price.group(1), "")] if price else []
        for pcode, price, label in opts:
            label = _text(label)
            price = int(price.replace(",", ""))
            if pcode in seen or price <= 0:
                continue
            seen.add(pcode)
            out.append({**base, "pcode": pcode, "price": price,
                        "name": f"{base['name']} {label}".strip() if label and label not in base["name"] else base["name"]})
    return out


def _options(body: str) -> list[tuple[str, str, str]]:
    """옵션 줄을 줄 단위로 끊어 읽는다 — 한 줄에 용량 표시가 없을 때 다음 줄 것을 끌어오지 않게."""
    out = []
    for chunk in body.split('id="productInfoDetail_')[1:]:
        pcode = re.match(r"(\d+)", chunk)
        price = OPT_PRICE_RE.search(chunk)
        if pcode and price:
            label = OPT_LABEL_RE.search(chunk)
            out.append((pcode.group(1), price.group(1), label.group(1) if label else ""))
    return out


def _has(name: str, token: str) -> bool:
    """'GOLD|골드' 처럼 | 로 적은 말은 그중 하나만 있어도 된다 — 다나와 표기가 한영으로 섞인다."""
    return any(_norm(t) in name for t in token.split("|"))


def match(items: list[dict], rule: dict) -> list[dict]:
    """부품의 거름 규칙(분류·반드시 들어갈 말·들어가면 안 되는 말)에 맞는 매물만."""
    cate = rule.get("cate", "")
    must = rule.get("must", [])
    nots = list(rule.get("not", [])) + ALWAYS_NOT
    got = []
    for it in items:
        n = _norm(it["name"])
        if cate and cate not in it["cate"]:
            continue
        if not all(_has(n, t) for t in must) or any(_has(n, t) for t in nots):
            continue
        if it["price"] <= 0:
            continue
        got.append(it)
    return got


def summarize(offers: list[dict]) -> dict:
    prices = sorted(o["price"] for o in offers)
    return {"min": prices[0], "median": int(statistics.median(prices)), "n": len(prices)}


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def run(force: bool = False, only: set[str] | None = None, dry_run: bool = False) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    parts = _load(PARTS_PATH, {}).get("parts", [])
    prev = _load(OUT_PATH, {"schema": 1, "source": "danawa", "parts": {}})
    if not force and not only and prev.get("day") == today and prev.get("complete"):
        print(f"[hardware] 오늘({today}) 가격은 이미 받았다 — 건너뜀(--force 로 다시)", flush=True)
        return {"skipped": True, "total": len(prev.get("parts", {})), "priced": None, "failed": 0}

    targets = [p for p in parts if p.get("price_query") and (not only or p["id"] in only)]
    book = prev.setdefault("parts", {})
    priced = failed = empty = 0
    for i, p in enumerate(targets):
        if i:
            time.sleep(jitter(CRAWL_DELAY_MS, ratio=0.1, floor_ms=CRAWL_DELAY_MS) / 1000)
        rule = p["price_query"]
        try:
            items = parse(fetch(rule["q"]))
        except Exception as e:  # 한 부품이 실패해도 나머지는 받는다
            failed += 1
            print(f"  [!] {p['id']} — {e}", flush=True)
            continue
        offers = sorted(match(items, rule), key=lambda o: o["price"])
        # 묶음으로만 파는 부품(메모리 '32Gx2' 패키지) — 한 개 값으로 나눠 부품의 단위와 맞춘다
        per = int(rule.get("per") or 1)
        if per > 1:
            offers = [{**o, "price": o["price"] // per, "name": f"{o['name']} (÷{per})"} for o in offers]
        rec = book.setdefault(p["id"], {"history": []})
        if not offers:
            empty += 1
            rec["last_empty"] = today
            print(f"  [ ] {p['id']:<32} 검색 {len(items)}건 중 맞는 매물 없음 — q={rule['q']!r}", flush=True)
            continue
        s = summarize(offers)
        rec.update(day=today, **s,
                   offers=[{"pcode": o["pcode"], "name": o["name"], "price": o["price"],
                            "url": PRODUCT_URL.format(pcode=o["pcode"])} for o in offers[:KEEP_OFFERS]])
        hist = [h for h in rec.get("history", []) if h.get("d") != today]
        hist.append({"d": today, **s})
        rec["history"] = sorted(hist, key=lambda h: h["d"])
        priced += 1
        print(f"  [+] {p['id']:<32} {s['min']:>10,}원 (중앙 {s['median']:,} · {s['n']}건)", flush=True)

    prev.update(schema=1, source="danawa", day=today, updated_at=datetime.now().isoformat(timespec="seconds"),
                complete=not only and failed == 0)
    stats = {"total": len(targets), "priced": priced, "empty": empty, "failed": failed}
    if dry_run:
        print(f"[hardware] dry-run — 저장 안 함 {stats}", flush=True)
        return stats
    OUT_PATH.write_text(json.dumps(prev, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    try:  # 이중 쓰기 — 실패해도 크롤 단계는 죽지 않는다
        from store import hardware as _db
        if _db.enabled():
            _db.ingest(parts, prev, today)
    except Exception as e:
        print(f"[hardware] DB 이중 쓰기 건너뜀: {e}", flush=True)
    print(f"[hardware] {stats} → {OUT_PATH}", flush=True)
    return stats


_FIXTURE = """
<li id="productItem100" class="prod_item">
 <input type="hidden" id="productItem_categoryInfo_100" value="PC 주요 부품_RAM" />
 <input type="hidden" id="min_price_100" value="180000" />
 <p class="prod_name"><a href="#">삼성전자 DDR5-5600</a></p>
 <div class="prod_pricelist"><ul>
  <li id="productInfoDetail_101"><p class="price_sect"><a><strong>790,390</strong>원</a></p>
   <p class="memory_sect"><span class="text"> 32GB </span></p></li>
  <li id="productInfoDetail_102"><p class="price_sect"><a><strong>349,900</strong>원</a></p>
   <p class="memory_sect"><span class="text"> 16GB </span></p></li>
  <li id="productInfoDetail_103"><p class="price_sect"><a><strong>338,510</strong>원</a></p>
   <p class="memory_sect"><span class="text"> 16GB 중고 </span></p></li>
 </ul></div>
</li>
<li id="productItem200" class="prod_item">
 <input type="hidden" id="productItem_categoryInfo_200" value="PC 주요 부품_파워" />
 <input type="hidden" id="min_price_200" value="148840" />
 <p class="prod_name"><a href="#">마이크로닉스 Classic II 850W 80PLUS골드 풀모듈러 ATX3.1</a></p>
</li>
"""


def selftest() -> int:
    """파서·거름 규칙 점검 — 다나와 마크업이 바뀌면 여기서 먼저 깨진다."""
    items = parse(_FIXTURE)
    assert [i["pcode"] for i in items] == ["101", "102", "103", "200"], items
    ram16 = match(items, {"cate": "RAM", "must": ["DDR5-5600", "16GB"]})
    assert [i["pcode"] for i in ram16] == ["102"], ram16  # 32GB 옵션·중고는 빠진다
    psu = match(items, {"cate": "파워", "must": ["850W", "GOLD|골드"]})
    assert [i["price"] for i in psu] == [148840], psu  # 한글 '골드' 도 GOLD 로 본다
    assert summarize(ram16) == {"min": 349900, "median": 349900, "n": 1}
    print("[hardware] selftest ok")
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    stats = run(force="--force" in argv, only=only, dry_run="--dry-run" in argv)
    return 1 if stats.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
