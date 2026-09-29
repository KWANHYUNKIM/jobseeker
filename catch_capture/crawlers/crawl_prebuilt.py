"""완제품 조립PC 크롤러 → jd-viewer/public/hardware/prebuilt.json (누적, 하루 한 번).

누가 설계해 파는 조립PC(모맨·피씨스토어·다나와표준PC …)를 모아 **부품 구성·가격**을 남긴다.
'왜 잘 만들었나 / 가성비가 왜 좋은가' 분석은 여기서 하지 않는다 — 구성을 우리 부품 목록
(parts.json)에 이어 두면 뷰어(lib/prebuilt.ts)가 부품값 합계·균형·파워 여유·예상 성능으로 계산한다.

수집처 (2026-09-29 조사 — robots/약관 확인):
  danawa : 통합검색(robots 허용, Crawl-delay 10) → 조립PC 목록(상품번호·이름·최저가).
           구성은 상품 페이지(prod.danawa.com/info, robots 허용)의 JSON-LD 에서 **부품 모델명만**
           뽑아 구조로 남긴다. 스펙 문자열 원문·이미지·설명·리뷰 글은 저장하지 않는다(콘진법 DB 보호
           문구). 사용자 의견은 JSON-LD 에 별점·리뷰 수가 있을 때 그 숫자만 — 글은 원문 링크로 본다.
  naver  : 네이버 검색 API(쇼핑) — 페이지 크롤링이 아니라 공식 API. 환경변수 NAVER_CLIENT_ID /
           NAVER_CLIENT_SECRET 이 있을 때만 돈다(developers.naver.com 에서 발급). 쇼핑 페이지는
           robots 가 AI·RAG 목적 수집을 금지하므로 긁지 않는다. 구성은 상품명에서만 읽는다.
뺀 곳: 쿠팡(robots.txt 부터 접근 거부 — 쿠팡 파트너스 API 는 가입·키가 있어야 한다),
      컴퓨존(robots 는 열려 있지만 약관이 무단 수집·게시를 제재 사유로 적는다 — 쓸 때도 가격·구성만).

누적 규칙:
  - 키는 "<출처>:<상품번호>". 처음·마지막으로 본 날, 가격 이력(하루 한 줄)을 남긴다.
  - 구성은 한 번 읽으면 30일 동안 다시 읽지 않는다(상품 페이지는 한 회차에 SPEC_PER_RUN 개까지).
  - 구성 → 부품 id 연결(mapped)은 매 회차 다시 한다 — parts.json 이 자라면 못 잇던 부품이 이어진다.

사용:
    python -m crawlers.crawl_prebuilt              # 오늘 아직 안 돌았으면
    python -m crawlers.crawl_prebuilt --force
    python -m crawlers.crawl_prebuilt --selftest   # 구성 파서 점검(네트워크 없이)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

from crawlers.crawl_hardware import CRAWL_DELAY_MS, PRODUCT_URL, _norm, fetch, parse
from crawlers.jobs_common import USER_AGENT, jitter

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
HW_DIR = ROOT_DIR / "jd-viewer" / "public" / "hardware"
PARTS_PATH = HW_DIR / "parts.json"
OUT_PATH = HW_DIR / "prebuilt.json"

QUERIES = ["게이밍 조립PC", "조립PC", "사무용 조립PC", "영상편집 조립PC", "AI 조립PC", "게이밍 컴퓨터 본체"]
SPEC_PER_RUN = 80          # 한 회차에 새로 읽는 상품 페이지 수(3초 간격 — 4분)
SPEC_TTL_DAYS = 30
PAGE_DELAY_MS = 3_000
TIMEOUT = 25
NAVER_API = "https://openapi.naver.com/v1/search/shop.json?query={q}&display=100&sort=sim"

LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
CHIPSET_RE = re.compile(r"^\((인텔|AMD)\)\s*([A-Z]\d{3}[A-Z]?)$")
GB_RE = re.compile(r"^(\d+)\s*(GB|TB)$")
WATT_RE = re.compile(r"^(\d{3,4})\s*W$")
CASES = {"미니타워": "case-matx-mini", "미들타워": "case-atx-mid", "빅타워": "case-atx-full"}


# ── 구성 파서 ─────────────────────────────────────────────────────────

def _gb(tok: str) -> int | None:
    m = GB_RE.match(tok.replace(" ", ""))
    if not m:
        return None
    n = int(m.group(1))
    return n * 1000 if m.group(2) == "TB" else n


def parse_composition(desc: str) -> dict:
    """다나와 완제품의 요약 스펙('i5-14400F / RTX 5060 Ti / (인텔) B760 / … ') → 구조.

    순서가 대개 CPU · 그래픽 · 칩셋 · OS · 파워 … 메모리 종류 · 용량 · 저장장치 · 용량 순이다.
    모르는 칸은 비운다. 원문 문자열은 저장하지 않는다 — 여기서 뽑은 사실만 남긴다.
    """
    toks = [t.strip() for t in desc.split("/") if t.strip()]
    out: dict = {"cpu": toks[0] if toks else None, "gpu": None, "chipset": None, "os": None, "psu_w": None,
                 "ram_type": None, "ram_gb": None, "storage": None, "storage_gb": None, "vram_gb": None,
                 "case": None, "purpose": None}
    if len(toks) > 1 and not CHIPSET_RE.match(toks[1]):
        out["gpu"] = toks[1]
    for i, t in enumerate(toks):
        m = CHIPSET_RE.match(t)
        if m and not out["chipset"]:
            out["chipset"] = m.group(2)
        elif ("OS" in t or "윈도우" in t) and not out["os"]:
            out["os"] = t
        elif WATT_RE.match(t.replace(" ", "")) and not out["psu_w"]:
            out["psu_w"] = int(WATT_RE.match(t.replace(" ", "")).group(1))
        elif t in ("DDR4", "DDR5") and not out["ram_type"]:
            out["ram_type"] = t
            if i + 1 < len(toks):
                out["ram_gb"] = _gb(toks[i + 1])
        elif t in ("M.2", "SSD", "NVMe", "HDD") and not out["storage"]:
            out["storage"] = t
            if i + 1 < len(toks):
                out["storage_gb"] = _gb(toks[i + 1])
        elif t.startswith("그래픽 메모리"):
            out["vram_gb"] = _gb(t.split(":", 1)[-1].strip())
        elif t in CASES and not out["case"]:
            out["case"] = t
        elif t.startswith("용도"):
            out["purpose"] = t.split(":", 1)[-1].strip()
    return out


def parse_title(title: str) -> dict:
    """상품명만 있을 때(네이버) — 'i5 14400F RTX5060 16GB 500GB' 에서 읽을 수 있는 만큼."""
    t = re.sub(r"<[^>]+>", "", title)
    out = parse_composition("")
    out["cpu"] = t
    out["gpu"] = t
    m = re.search(r"(DDR[45])", t)
    out["ram_type"] = m.group(1) if m else None
    gbs = [int(x) for x in re.findall(r"(\d+)\s*GB", t)]
    out["ram_gb"] = next((g for g in gbs if g in (8, 16, 32, 48, 64, 96, 128)), None)
    # 'M.2 1TB' 처럼 장치 이름 뒤의 용량을 먼저 본다 — '32GB NVMe 1TB' 에서 앞의 32GB 는 메모리다
    m = re.search(r"(?:SSD|NVMe|M\.2)\s*(\d+)\s*(TB|GB)", t) or re.search(r"(\d+)\s*(TB|GB)\s*(?:SSD|NVMe|M\.2)", t)
    if m:
        out["storage_gb"] = int(m.group(1)) * (1000 if m.group(2) == "TB" else 1)
    return out


# ── 부품 목록에 잇기 ─────────────────────────────────────────────────

def _hit(text: str, rule: dict) -> bool:
    n = _norm(text)
    has = lambda tok: any(_norm(x) in n for x in tok.split("|"))
    return bool(rule.get("must")) and all(has(t) for t in rule["must"]) and not any(has(t) for t in rule.get("not", []))


def map_parts(comp: dict, parts: list[dict]) -> dict:
    """구성 → 부품 id. 못 이으면 None(뷰어가 '부품 목록에 없음' 으로 보이고, 엔진 일감이 된다)."""
    by_cat: dict[str, list[dict]] = {}
    for p in parts:
        by_cat.setdefault(p["category"], []).append(p)

    def first(cat: str, text: str | None, extra: str = "") -> str | None:
        if not text:
            return None
        rule_ok = [p for p in by_cat.get(cat, []) if p.get("price_query") and _hit(f"{text} {extra}", p["price_query"])]
        # 규칙이 긴(구체적인) 부품이 먼저 — 'RTX 5060' 보다 'RTX 5060 Ti' 가 앞선다
        rule_ok.sort(key=lambda p: -sum(len(t) for t in p["price_query"]["must"]))
        return rule_ok[0]["id"] if rule_ok else None

    vram = f"{comp['vram_gb']}GB" if comp.get("vram_gb") else ""
    mb = None
    if comp.get("chipset"):
        chip = comp["chipset"].lower()
        cand = [f"mb-{chip}-{(comp.get('ram_type') or 'ddr5').lower()}", f"mb-{chip}"]
        ids = {p["id"] for p in by_cat.get("mainboard", [])}
        mb = next((c for c in cand if c in ids), None)
    ram = None
    if comp.get("ram_type") and comp.get("ram_gb"):
        std = {"DDR5": 5600, "DDR4": 3200}[comp["ram_type"]]
        rid = f"ram-{comp['ram_type'].lower()}-{std}-{comp['ram_gb'] // 2}"
        ram = rid if any(p["id"] == rid for p in by_cat.get("ram", [])) else None
    psu = None
    if comp.get("psu_w"):
        psu = next((p["id"] for p in by_cat.get("psu", []) if p["specs"].get("watt") == comp["psu_w"]), None)
    gpu = first("gpu", comp.get("gpu"), vram)
    gpu_assumed = None
    if not gpu and comp.get("gpu") and not vram:
        # 메모리 용량만 다른 형제(5060 Ti 8GB/16GB)인데 판매 표기에 VRAM 이 없다 — 낮은 쪽으로 가정한다.
        # 높은 쪽으로 잡으면 성능·가성비를 부풀린다. 가정했다는 사실을 남겨 화면이 밝힌다.
        for cand in sorted(by_cat.get("gpu", []), key=lambda p: p["specs"].get("vram_gb") or 0):
            rule = cand.get("price_query") or {}
            base = {"must": [t for t in rule.get("must", []) if not re.fullmatch(r"\d+GB", t)], "not": rule.get("not", [])}
            if len(base["must"]) < len(rule.get("must", [])) and _hit(comp["gpu"], base):
                gpu, gpu_assumed = cand["id"], f"VRAM 표기가 없어 {cand['specs'].get('vram_gb')}GB 로 가정했다(낮은 쪽)"
                break
    return {
        "cpu": first("cpu", comp.get("cpu")),
        "gpu": gpu,
        "gpu_assumed": gpu_assumed,
        "mainboard": mb,
        "ram": ram,
        "psu": psu,
        "case": CASES.get(comp.get("case") or ""),
    }


# ── 수집 ─────────────────────────────────────────────────────────────

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html", "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "ignore")


def product_facts(pcode: str) -> dict:
    """상품 페이지 JSON-LD → 구성(구조)과 별점 숫자. 원문 문자열은 돌려주지 않는다."""
    page = _get(PRODUCT_URL.format(pcode=pcode))
    for m in LD_RE.finditer(page):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if d.get("@type") != "Product":
            continue
        rating = d.get("aggregateRating") or {}
        return {
            "comp": parse_composition(html.unescape(d.get("description") or "")),
            "brand": (d.get("brand") or {}).get("name"),
            "rating": {"avg": float(rating["ratingValue"]), "count": int(rating.get("reviewCount") or rating.get("ratingCount") or 0)}
            if rating.get("ratingValue") else None,
            "offer_count": int((d.get("offers") or {}).get("offerCount") or 0) or None,
        }
    return {}


def naver_items(query: str) -> list[dict]:
    cid, sec = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and sec):
        return []
    req = urllib.request.Request(NAVER_API.format(q=urllib.parse.quote(query)),
                                 headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = []
    for it in data.get("items", []):
        cats = " ".join(it.get(k, "") for k in ("category2", "category3", "category4"))
        if "데스크탑" not in cats and "조립" not in cats:
            continue
        out.append({"key": f"naver:{it['productId']}", "name": re.sub(r"<[^>]+>", "", html.unescape(it["title"])),
                    "price": int(it["lprice"]), "url": it["link"], "mall": it.get("mallName"), "brand": it.get("brand") or it.get("maker")})
    return out


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def run(force: bool = False) -> dict:
    today = date.today().isoformat()
    parts = _load(PARTS_PATH, {}).get("parts", [])
    doc = _load(OUT_PATH, {"schema": 1, "items": {}})
    if not force and doc.get("day") == today and doc.get("complete"):
        print(f"[prebuilt] 오늘({today}) 이미 받았다 — 건너뜀", flush=True)
        return {"skipped": True, "total": len(doc.get("items", {}))}
    items = doc.setdefault("items", {})
    seen: dict[str, dict] = {}
    failed = 0

    # 1) 다나와 목록 — 이름·가격·상품번호
    for i, q in enumerate(QUERIES):
        if i:
            time.sleep(jitter(CRAWL_DELAY_MS, ratio=0.1, floor_ms=CRAWL_DELAY_MS) / 1000)
        try:
            for it in parse(fetch(q)):
                if "데스크탑" in it["cate"] and it["price"] > 0:
                    seen.setdefault(f"danawa:{it['pcode']}", {"name": it["name"], "price": it["price"], "source": "danawa",
                                                               "url": PRODUCT_URL.format(pcode=it["pcode"]), "pcode": it["pcode"]})
        except Exception as e:
            failed += 1
            print(f"  [!] 다나와 '{q}' — {e}", flush=True)
    # 2) 네이버 공식 API(키가 있을 때만)
    for q in QUERIES:
        try:
            for it in naver_items(q):
                seen.setdefault(it["key"], {**it, "source": "naver"})
        except Exception as e:
            failed += 1
            print(f"  [!] 네이버 '{q}' — {e}", flush=True)

    # 3) 누적 — 가격 이력
    for key, it in seen.items():
        rec = items.setdefault(key, {"first_seen": today, "history": []})
        rec.update({k: v for k, v in it.items() if k != "key"})
        rec["last_seen"] = today
        rec["history"] = [h for h in rec["history"] if h["d"] != today] + [{"d": today, "price": it["price"]}]

    # 4) 구성 — 다나와 상품 페이지(새것·오래된 것부터, 회차당 SPEC_PER_RUN 개)
    todo = [k for k, r in items.items() if r.get("source") == "danawa" and k in seen
            and (not r.get("spec_checked") or (date.fromisoformat(today) - date.fromisoformat(r["spec_checked"])).days > SPEC_TTL_DAYS)]
    todo.sort(key=lambda k: items[k].get("spec_checked") or "")
    got = 0
    for k in todo[:SPEC_PER_RUN]:
        time.sleep(jitter(PAGE_DELAY_MS) / 1000)
        try:
            f = product_facts(items[k]["pcode"])
        except Exception as e:
            failed += 1
            print(f"  [!] {k} 상품 페이지 — {e}", flush=True)
            continue
        if f.get("comp"):
            items[k].update(comp=f["comp"], brand=f.get("brand"), rating=f.get("rating"),
                            offer_count=f.get("offer_count"), spec_checked=today)
            got += 1
    for k, r in items.items():  # 네이버는 상품명에서
        if r.get("source") == "naver" and not r.get("comp"):
            r["comp"] = parse_title(r["name"])
            r["spec_checked"] = today

    # 5) 부품 목록에 잇기 — 매 회차
    unmapped = 0
    for r in items.values():
        if r.get("comp"):
            r["mapped"] = map_parts(r["comp"], parts)
            unmapped += sum(1 for c in ("cpu", "gpu") if r["comp"].get(c) and not r["mapped"].get(c)
                            and not (c == "gpu" and "내장" in str(r["comp"].get("gpu"))))

    doc.update(schema=1, day=today, updated_at=datetime.now().isoformat(timespec="seconds"), complete=failed == 0,
               sources=sorted({r.get("source") for r in items.values()}))
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    stats = {"total": len(items), "seen_today": len(seen), "specs_read": got, "unmapped_cpu_gpu": unmapped, "failed": failed}
    print(f"[prebuilt] {stats} → {OUT_PATH}", flush=True)
    return stats


def selftest() -> int:
    c = parse_composition("i5-14400F / RTX 5060 Ti / (인텔) B760 / OS미포함 / 800W / 인텔 / 코어 14세대 / 코어i5 / "
                          "DDR5 / 16GB / M.2 / 500GB / NVIDIA / 그래픽 메모리: 16GB / 미들타워 / 용도: 게임용")
    assert c["cpu"] == "i5-14400F" and c["gpu"] == "RTX 5060 Ti" and c["chipset"] == "B760", c
    assert c["psu_w"] == 800 and c["ram_type"] == "DDR5" and c["ram_gb"] == 16 and c["storage_gb"] == 500, c
    assert c["vram_gb"] == 16 and c["case"] == "미들타워" and c["purpose"] == "게임용", c
    parts = _load(PARTS_PATH, {}).get("parts", [])
    m = map_parts(c, parts)
    assert m["cpu"] == "cpu-core-i5-14400f" and m["gpu"] == "gpu-rtx-5060-ti-16", m
    assert m["mainboard"] == "mb-b760-ddr5" and m["case"] == "case-atx-mid" and m["ram"] is None, m
    m2 = map_parts({**c, "vram_gb": None}, parts)
    assert m2["gpu"] == "gpu-rtx-5060-ti-8" and m2["gpu_assumed"], m2
    t = parse_title("[모맨] 게이밍PC i5 14400F RTX5060 DDR5 32GB NVMe 1TB")
    assert t["ram_type"] == "DDR5" and t["ram_gb"] == 32 and t["storage_gb"] == 1000, t
    print("[prebuilt] selftest ok")
    return 0


if __name__ == "__main__":
    args = _sys.argv[1:]
    raise SystemExit(selftest() if "--selftest" in args else (1 if run(force="--force" in args).get("failed") else 0))
