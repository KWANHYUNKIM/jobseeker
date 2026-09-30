"""회사 기본 정보 — 원티드 회사 페이지가 공개로 싣는 숫자(국민연금 기반 평균연봉·인원·매출·업력·업종).

취업 브리핑(guide-engine)은 28곳만 연봉을 갖고 있다. 나머지는 이 값을 캐시에 받아 두고 [인재상 해부]가 쓴다.
평균연봉은 **국민연금 납부액으로 추정한 전 직군 평균**이다 — 개발 직군 값이 아니고, 화면에도 그렇게 적는다.

    python -m poster.company_facts 컬리 제논 바로팜      # 받아서 state/company_facts.json 에 쌓는다
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
ROOT = LAB.parent
CACHE = LAB / "state" / "company_facts.json"
GUIDE = ROOT / "jd-viewer" / "public" / "guide" / "companies"
JOBS = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"
PAUSE = 2.0                                          # 요청 사이 쉼 — 회사 몇십 곳을 한 번에 받을 일은 없다


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def load() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _norm(s: str) -> str:
    return re.sub(r"\(.*?\)|㈜|주식회사|\s", "", s or "").lower()


def _wanted_posting(name: str) -> str | None:
    """이 회사의 원티드 공고 주소 하나 — 브리핑의 공고부터, 없으면 공고 색인에서."""
    for p in GUIDE.glob("*.json"):
        g = json.loads(p.read_text(encoding="utf-8"))
        if name in (g["name"], *(g.get("aliases") or [])):
            for s in (g.get("company") or {}).get("business_sources") or []:
                m = re.search(r"wanted\.co\.kr/company/(\d+)", s.get("url", ""))
                if m:
                    return f"https://www.wanted.co.kr/company/{m.group(1)}"
            for q in g.get("postings") or []:
                if "wanted.co.kr/wd/" in (q.get("url") or ""):
                    return q["url"]
    rows = json.loads(JOBS.read_text(encoding="utf-8"))
    rows = rows if isinstance(rows, list) else rows.get("jobs", [])
    key = _norm(name)
    for j in rows:
        if j.get("site") == "wanted" and _norm(j.get("company")) == key:
            return j["url"]
    return None


def _num(h: str, key: str):
    m = re.search(rf'"{key}":(-?[\d.]+|null|"[^"]*")', h)
    if not m or m.group(1) == "null":
        return None
    v = m.group(1)
    return v.strip('"') if v.startswith('"') else (float(v) if "." in v else int(v))


def fetch(name: str) -> dict | None:
    url = _wanted_posting(name)
    if not url:
        return None
    if "/company/" not in url:
        m = re.search(r"/company/(\d+)", _get(url))
        if not m:
            return None
        time.sleep(PAUSE)
        url = f"https://www.wanted.co.kr/company/{m.group(1)}"
    h = _get(url).replace('\\"', '"')
    i = h.find('"detail":{')
    if i < 0:
        return None
    d = h[i:i + 4000]
    sal = re.search(r'"salary":\{"salary":(\d+),"source":"(\w+)","updatedAt":"([\d-]+)', d)
    tags = re.search(r'"mainTags":\[(.*?)\]', h)
    return {
        "name": name, "url": url, "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "title": (re.search(r'"name":"([^"]+)","level"', h) or [None, name])[1],
        "industry": _num(d, "classNameByNts"),                 # 국세청 업종 분류
        "founded": _num(d, "foundedYear"), "age": _num(d, "age"),
        "employees": _num(d, "npsEmployeeCount"),             # 국민연금 가입자 수
        "hired": _num(d, "hiredCount"), "left": _num(d, "leftCount"),
        "sales": _num(d, "totalSales"),                       # 원
        "salary": int(sal.group(1)) // 10000 if sal else None,  # 만원
        "salary_source": sal.group(2) if sal else None, "salary_as_of": sal.group(3)[:7] if sal else None,
        "location": (re.search(r'"location":"([^"]+)"', h) or [None, None])[1],
        "tags": re.findall(r'"title":"([^"]+)"', tags.group(1)) if tags else [],
    }


def get(name: str, *, refresh: bool = False) -> dict | None:
    """캐시 먼저. 없으면 받아서 쌓는다. 받지 못하면 None — 화면은 그 칸을 빼고 그린다."""
    cache = load()
    if name in cache and not refresh:
        return cache[name]
    try:
        f = fetch(name)
    except Exception as e:                            # 네트워크·차단 — 사이클을 죽이지 않는다
        print(f"[facts] {name}: {e}", file=sys.stderr)
        return None
    if f:
        cache[name] = f
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return f


if __name__ == "__main__":
    for n in sys.argv[1:]:
        f = get(n, refresh=True)
        print(n, "→", {k: f[k] for k in ("salary", "employees", "sales", "age", "industry", "tags")} if f else "없음")
        time.sleep(PAUSE)
