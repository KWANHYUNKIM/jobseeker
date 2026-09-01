#!/usr/bin/env python3
"""공고의 근무지(location)를 원본에서 다시 받아 채운다.

지역 필터를 붙이면서 드러난 것: 근무지 칸은 사이트마다 다른 이유로 비거나 엉뚱한
값이 들어와 있었다.

  wanted   — 검색 카드에서 근무지가 사라진 뒤 선택자가 그 자리의 경력 표기를
             긁고 있었다. location 칸에 "경력 3년 이상" 이 들어앉아 있었다.
  jobkorea — 일부 공고 레이아웃에서 위치 대신 공고 제목이 들어왔다
             ("[울산] 제조 시스템 개발자 모집" 이 근무지로 저장돼 있었다).

둘 다 회사 주소로 때우고 싶은 유혹이 있지만 그러면 안 된다. ㈜티맥스소프트의
"[TmaxsoftJapan] 일본법인근무" 공고는 회사가 성남에 있어도 근무지는 도쿄다.
회사 위치와 근무지는 다른 값이고, 필터가 대답해야 하는 건 근무지다. 그래서 여기서는
추정하지 않고 원본이 말하는 주소만 가져온다.

  wanted   — 상세 API(/api/chaos/jobs/v1/{id}/details)의 address.location/district
  jobkorea — 공고 페이지의 JSON-LD(JobPosting.jobLocation.address.streetAddress)

사용:
  python -m pipeline.backfill_location              # 근무지가 비었거나 깨진 것만
  python -m pipeline.backfill_location --refetch    # 캐시 무시하고 다시 조회
  python -m pipeline.backfill_location --site wanted

캐시(screenshots/location_cache.json)에 사이트별 키→근무지를 남겨 재실행이 싸다.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paths import JD_VIEWER_DIR, ROOT_DIR, SCREENSHOTS_DIR  # noqa: E402

SCREENSHOTS = SCREENSHOTS_DIR
CACHE = SCREENSHOTS / "location_cache.json"
LEGACY_WANTED_CACHE = SCREENSHOTS / "wanted_location_cache.json"
ENRICHED = JD_VIEWER_DIR / "public" / "all_jobs_enriched.json"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
WANTED_API = "https://www.wanted.co.kr/api/chaos/jobs/v1/{pid}/details"
JOBKOREA_URL = "https://www.jobkorea.co.kr/Recruit/GI_Read/{rid}"

# location 칸에 들어앉은 경력 표기를 골라내는 규칙. 이 꼴이면 지역이 아니라 경력이다.
CAREER_TEXT = re.compile(r"(경력|신입|무관|\d+\s*년)")

# 시도 17개. 뷰어의 lib/region.ts 와 같은 목록이다 — 여기서는 "국내 주소인가"를
# 가르는 데만 쓰고, 화면에 보일 접기는 뷰어가 한다.
SIDO = ("서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
        "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주")
# JSON-LD 는 정식 명칭으로 온다("대한민국 서울특별시 강서구 …"). 약칭으로 접는다.
LONG_SIDO = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산",
    "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원",
    "충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북",
    "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주", "제주도": "제주",
}
DISTRICT = re.compile(r"^\s*([가-힣]+?(?:시|군|구))")
LD_SCRIPT = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
JOBKOREA_ID = re.compile(r"/GI_Read/(\d+)")


def looks_like_career(text: str) -> bool:
    return bool(CAREER_TEXT.search(text or ""))


def normalize_address(raw: str) -> str:
    """원본 주소 → "시도 시군구". 국내 주소가 아니면 "해외 <원문>" 으로 표시한다.

    해외를 별도 표기로 남기는 이유는, 도쿄·호치민 같은 도시 이름을 뷰어가 알아야
    할 이유가 없기 때문이다. 국내 시도로 접히지 않는다는 사실 자체가 정보다.
    """
    s = re.sub(r"\s+", " ", (raw or "").strip())
    if not s:
        return ""
    s = re.sub(r"^대한민국\s*", "", s)
    for long, short in LONG_SIDO.items():
        if s.startswith(long):
            s = short + s[len(long):]
            break
    for sido in SIDO:
        if s.startswith(sido):
            rest = s[len(sido):]
            m = DISTRICT.match(rest)
            return f"{sido} {m.group(1)}" if m else sido
    return f"해외 {s}"


def fetch_wanted(pid: str) -> str | None:
    """None = 조회 실패(다음 실행에서 재시도), "" = 주소 없는 공고(재시도 안 함)."""
    req = urllib.request.Request(
        WANTED_API.format(pid=pid), headers={"User-Agent": UA, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        # 404/410 = 내려간 공고. 다시 물어도 답이 안 나오므로 빈 값으로 굳힌다.
        return "" if e.code in (400, 403, 404, 410) else None
    except Exception:
        return None

    addr = ((body.get("job") or {}).get("address")) or {}
    country = (addr.get("country") or "").strip()
    loc = (addr.get("location") or "").strip()
    district = (addr.get("district") or "").strip()
    if country and country != "한국":
        return f"해외 {country}"
    return " ".join(p for p in (loc, district) if p)


def fetch_jobkorea(rid: str) -> str | None:
    """공고 페이지의 JSON-LD 에서 근무지를 읽는다.

    화면 마크업(선택자)이 아니라 구조화 데이터를 보는 이유는, 애초에 이 칸이 빈
    원인이 선택자가 레이아웃에 따라 다른 요소를 잡았기 때문이다. JSON-LD 는
    잡코리아가 검색엔진에 내보내는 값이라 레이아웃과 무관하다.
    """
    req = urllib.request.Request(
        JOBKOREA_URL.format(rid=rid), headers={"User-Agent": UA, "Accept-Language": "ko"}
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return "" if e.code in (400, 403, 404, 410) else None
    except Exception:
        return None

    for m in LD_SCRIPT.finditer(html):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict) or node.get("@type") != "JobPosting":
                continue
            loc = node.get("jobLocation")
            for entry in (loc if isinstance(loc, list) else [loc]):
                if not isinstance(entry, dict):
                    continue
                addr = entry.get("address") or {}
                value = (addr.get("streetAddress") or addr.get("addressLocality") or "").strip()
                if value:
                    return normalize_address(value)
    return ""  # JSON-LD 가 없는 공고 — 다시 받아도 같다


def job_key(job: dict) -> tuple[str, str] | None:
    """(site, 캐시 키). 사이트마다 원본을 다시 찾아갈 수 있는 식별자가 다르다."""
    site = job.get("site") or "wanted"
    if site == "wanted":
        pid = str(job.get("pid") or job.get("position_id") or "").strip()
        return ("wanted", pid) if pid else None
    if site == "jobkorea":
        m = JOBKOREA_ID.search(job.get("url") or "")
        return ("jobkorea", m.group(1)) if m else None
    return None


def needs_location(job: dict) -> bool:
    """근무지가 비었거나, 근무지가 아닌 값(경력·제목)이 들어앉았는가."""
    loc = (job.get("location") or "").strip()
    if not loc or looks_like_career(loc):
        return True
    if loc.startswith(SIDO) or loc.startswith("해외"):
        return False
    return True  # 시도로 시작하지 않으면 근무지 표기가 아니다


FETCHERS = {"wanted": fetch_wanted, "jobkorea": fetch_jobkorea}


def load_cache() -> dict[str, dict[str, str]]:
    cache: dict[str, dict[str, str]] = {"wanted": {}, "jobkorea": {}}
    if CACHE.exists():
        cache.update(json.loads(CACHE.read_text(encoding="utf-8")))
    elif LEGACY_WANTED_CACHE.exists():
        # 이전 wanted 전용 캐시를 그대로 이어받는다(3천 건을 다시 조회할 이유가 없다).
        cache["wanted"] = json.loads(LEGACY_WANTED_CACHE.read_text(encoding="utf-8"))
    cache.setdefault("wanted", {})
    cache.setdefault("jobkorea", {})
    return cache


def save_cache(cache: dict[str, dict[str, str]]) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def targets() -> list[Path]:
    """누적 폴더 → 스냅샷 → 뷰어 산출물. 앞을 안 고치면 다음 재빌드가 되돌린다."""
    out = sorted(SCREENSHOTS.glob("wanted_*/jobs.json"))
    out += sorted(SCREENSHOTS.glob("jobkorea_*/jobs.json"))
    latest = SCREENSHOTS / "all_개발자_latest"
    for name in ("all_jobs.json", "all_jobs_closed.json"):
        if (latest / name).exists():
            out.append(latest / name)
    if ENRICHED.exists():
        out.append(ENRICHED)
    return out


def patch_records(records: list[dict], cache: dict[str, dict[str, str]]) -> int:
    n = 0
    for j in records:
        key = job_key(j)
        if not key:
            continue
        site, kid = key
        loc = (j.get("location") or "").strip()
        # wanted 는 경력 표기가 location 칸에 실려 왔다 — 있어야 할 자리로 옮긴다.
        if site == "wanted" and looks_like_career(loc):
            if not (j.get("career") or "").strip():
                j["career"] = loc
            j["location"] = ""
            n += 1
        found = cache.get(site, {}).get(kid)
        if found and j.get("location") != found:
            j["location"] = found
            n += 1
    return n


def main() -> None:
    argv = sys.argv[1:]
    refetch = "--refetch" in argv
    only = None
    if "--site" in argv:
        only = argv[argv.index("--site") + 1]

    cache = {} if refetch else load_cache()
    if refetch:
        cache = {"wanted": {}, "jobkorea": {}}

    jobs = json.loads(ENRICHED.read_text(encoding="utf-8"))
    todo: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for j in jobs:
        key = job_key(j)
        if not key or key in seen:
            continue
        seen.add(key)
        site, kid = key
        if only and site != only:
            continue
        if not needs_location(j):
            continue
        if kid in cache.get(site, {}):
            continue
        todo.append(key)

    by_site: dict[str, int] = {}
    for site, _ in todo:
        by_site[site] = by_site.get(site, 0) + 1
    print(f"[*] 근무지 조회 대상 {len(todo):,}건 {by_site or ''}", flush=True)

    lock = threading.Lock()
    done = 0

    def work(key: tuple[str, str]) -> None:
        nonlocal done
        site, kid = key
        loc = FETCHERS[site](kid)
        time.sleep(0.2)
        with lock:
            done += 1
            if loc is not None:
                cache.setdefault(site, {})[kid] = loc
            if done % 50 == 0:
                print(f"    {done:,}/{len(todo):,} 조회", flush=True)
                save_cache(cache)

    if todo:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(work, todo))
    save_cache(cache)

    for site in ("wanted", "jobkorea"):
        vals = cache.get(site, {})
        filled = sum(1 for v in vals.values() if v)
        print(f"[*] {site}: 지역 확보 {filled:,} / 주소 없음 {len(vals) - filled:,}", flush=True)

    for path in targets():
        records = json.loads(path.read_text(encoding="utf-8"))
        n = patch_records(records, cache)
        if n:
            path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    {path.relative_to(ROOT_DIR)} — {n:,}건 반영", flush=True)


if __name__ == "__main__":
    main()
