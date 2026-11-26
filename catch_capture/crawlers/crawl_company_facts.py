#!/usr/bin/env python3
"""회사 사실 모으기 — 공고 풀이(engine/roles)가 회차마다 웹을 뒤지던 연봉·인원·주소·복지를 미리 모은다(2026-11-26).

AI 없이 크롤링·공개 파일만 쓴다. 풀이 일꾼은 이 파일을 먼저 읽고, 없는 것만 찾는다.

출처 셋:
  nps      국민연금 가입 사업장 내역(공공데이터포털 15083277, 매달 갱신, 로그인 없이 CSV) — 인원·월 고지금액
           → 1인 평균 월 소득 추정 = 고지금액 / 가입자수 / 보험료율. 기준소득월액 상한이 있어 고연봉 회사는 낮게 나온다.
  wanted   원티드 회사 페이지(robots 허용 /company/<id>, /wd/<id>) — NPS 기반 평균 연봉·인원·도로명 주소·복지 태그·매출
  posting  우리가 이미 모은 공고의 복리후생 칸(회사가 직접 쓴 글)

저장: 수집 중간물은 catch_capture/var/roles/{company_facts,market_wage}.json(키는 validate.co_norm(회사명), 커밋 안 함),
      정본은 DB — company_fact · company_posting_salary · market_wage · market_wage_size(migrations/020).
      build·wage 가 끝에 store.ingest.company_facts 로 옮기고, 뷰어는 backend /api/company-facts · /api/market-wage 로 읽는다.
      **public/ 에 JSON 을 굽지 않는다** — 크롤 산출물을 git 에 싣지 않는다.

    python -m crawlers.crawl_company_facts nps          # CSV 받기(이번 달 것이 있으면 건너뜀) + 묶기
    python -m crawlers.crawl_company_facts wanted       # 원티드 회사 페이지(이미 받은 회사는 건너뜀)
    python -m crawlers.crawl_company_facts build        # 셋을 합쳐 company_facts.json
    python -m crawlers.crawl_company_facts all          # 위 셋 차례로
    python -m crawlers.crawl_company_facts wage         # 연차별 시장 시세(KOSIS, .env 의 KOSIS_API_KEY)
    python -m crawlers.crawl_company_facts show 토스뱅크
"""
from __future__ import annotations

import csv
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # catch_capture 루트
from core.paths import VAR_DIR, VIEWER_PUBLIC  # noqa: E402
from crawlers.jobs_common import jitter  # noqa: E402

OUT_DIR = VAR_DIR / "roles" / "facts"
OUT = VAR_DIR / "roles" / "company_facts.json"
JOBS = VIEWER_PUBLIC / "all_jobs_enriched.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

NPS_PK = "15083277"
NPS_PAGE = f"https://www.data.go.kr/data/{NPS_PK}/fileData.do"
# 보험료율 — 2025년 연금개혁: 2026년 9.5%, 이후 해마다 0.5%p(13%까지). 자료 연도의 율로 나눈다.
NPS_RATE = {2025: 0.09, 2026: 0.095, 2027: 0.10, 2028: 0.105}


def co_norm(s: str | None) -> str:
    """engine/roles/validate.py 의 co_norm 과 같아야 한다(풀이 일꾼이 같은 키로 찾는다)."""
    return re.sub(r"\(주\)|㈜|주식회사|\s", "", s or "").lower()


def keys(name: str) -> list[str]:
    """찾기 키 — 원래 키, 괄호 뺀 키(쿠팡 (Coupang) → 쿠팡), 법인 꼬리표 뺀 키."""
    k = co_norm(name)
    out = [k]
    bare = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", k)
    bare = re.sub(r"^(유한회사|유한책임회사|재단법인|사단법인|\(유\)|\(재\)|\(사\))|(유한회사|유한책임회사|\(유\))$", "", bare)
    if bare and bare not in out:
        out.append(bare)
    return out


def _get(url: str, opener=None, referer: str | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Referer": referer} if referer else {})})
    with (opener.open(req, timeout=timeout) if opener else urllib.request.urlopen(req, timeout=timeout)) as r:
        return r.read()


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_jobs() -> list[dict]:
    d = json.loads(JOBS.read_text(encoding="utf-8"))
    return d["jobs"] if isinstance(d, dict) else d


# ── 국민연금 ─────────────────────────────────────────────────────────────

def nps_download() -> Path:
    """이번 파일의 날짜(예: 20261123)로 저장 — 이미 있으면 다시 받지 않는다."""
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    page = _get(NPS_PAGE, op).decode("utf-8", "replace")
    m = re.search(r"fn_fileDataDown\('(\d+)',\s*'(uddi:[^']+)'", page)
    stamp = (re.search(r"가입 사업장 내역_(\d{8})", page) or [None, datetime.now().strftime("%Y%m%d")])[1]
    dest = OUT_DIR / f"nps_{stamp}.csv"
    if dest.exists() and dest.stat().st_size > 10_000_000:
        print(f"[nps] 이미 있음 {dest.name}")
        return dest
    if not m:
        raise RuntimeError("공공데이터포털 페이지에서 다운로드 버튼을 못 찾았다 — 페이지 형식이 바뀌었다")
    q = urllib.parse.urlencode({"publicDataPk": m[1], "publicDataDetailPk": m[2], "fileDetailSn": 1, "publicDataTyCode": "PR0051"})
    meta = json.loads(_get(f"https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?{q}", op, NPS_PAGE))
    if not meta.get("status"):
        raise RuntimeError(f"다운로드 정보 실패: {meta.get('error')}")
    url = ("https://www.data.go.kr/cmm/cmm/fileDownload.do?"
           + urllib.parse.urlencode({"atchFileId": meta["atchFileId"], "fileDetailSn": meta["fileDetailSn"], "insertDataPrcus": "N"}))
    print(f"[nps] 받는 중 {dest.name} …", flush=True)
    data = _get(url, op, NPS_PAGE, timeout=600)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    for old in OUT_DIR.glob("nps_*.csv"):
        if old != dest:
            old.unlink()
    print(f"[nps] {len(data)/1e6:.0f}MB")
    return dest


def nps_index(want: set[str]) -> dict:
    """공고에 나온 회사 키(want)만 남긴다. 같은 이름 사업장이 여럿(지점·동명 회사)이면 가입자 많은 순으로 다 둔다."""
    path = max(OUT_DIR.glob("nps_*.csv"), default=None)
    if not path:
        raise FileNotFoundError("nps CSV 없음 — 먼저 `nps` 를 돌린다")
    hits: dict[str, list] = defaultdict(list)
    with open(path, encoding="cp949", errors="replace", newline="") as f:
        r = csv.reader(f)
        head = next(r)
        col = {h.split(" ")[0]: i for i, h in enumerate(head)}
        for row in r:
            if row[col["사업장가입상태코드"]] != "1":
                continue
            name = row[col["사업장명"]]
            k = next((k for k in keys(name) if k in want), None)
            if not k:
                continue
            try:
                n, fee = int(row[col["가입자수"]]), int(row[col["당월고지금액"]])
            except ValueError:
                continue
            ym = row[col["자료생성년월"]]
            rate = NPS_RATE.get(int(ym[:4]), 0.095)
            hits[k].append({
                "name": name, "biz6": row[col["사업자등록번호"]], "members": n,
                "monthly_income_est": round(fee / n / rate) if n else None,
                "annual_income_est_만원": round(fee / n / rate * 12 / 10000) if n else None,
                "new": int(row[col["신규취득자수"]] or 0), "lost": int(row[col["상실가입자수"]] or 0),
                "industry": row[col["사업장업종코드명"]], "address": row[col["사업장도로명상세주소"]] or row[col["사업장지번상세주소"]],
                "since": row[col["적용일자"]], "month": ym,
            })
    for v in hits.values():
        v.sort(key=lambda x: -x["members"])
    return {"file": path.name, "rate_note": "고지금액 ÷ 가입자수 ÷ 보험료율(2026년 9.5%) ×12. 기준소득월액 상한이 있어 고연봉 회사는 실제보다 낮다. 회사 전체(경력·비개발 포함) 평균이다.",
            "source_url": NPS_PAGE, "companies": dict(hits)}


# ── 원티드 ─────────────────────────────────────────────────────────────

def _next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else {}


def _company_from_page(d: dict) -> dict:
    out: dict = {}
    for q in (d.get("props", {}).get("pageProps", {}).get("dehydrateState", {}).get("queries") or []):
        data = (q.get("state") or {}).get("data")
        if not isinstance(data, dict):
            continue
        if "companyTags" in data or "regNoHash" in data:
            addr = data.get("address") or {}
            out.update(
                name=data.get("name") or out.get("name"),
                industry=data.get("industryName"), founded=data.get("foundedYear"),
                tags=[t.get("title") for t in data.get("companyTags") or []],
                address=((addr.get("geo_location") or {}).get("n_location") or {}).get("road_address") or addr.get("full_location"),
                full_location=addr.get("full_location"),
            )
        if "salary" in data and isinstance(data.get("salary"), dict):
            s, e, sa = data.get("salary") or {}, data.get("employee") or {}, data.get("sales") or {}
            det = data.get("detail") or {}
            out.update(
                avg_salary_won=s.get("salary"), salary_source=s.get("source"), salary_updated=s.get("updatedAt"),
                employees=e.get("total"), hired=e.get("hired"), left=e.get("left"), employee_updated=e.get("updatedAt"),
                sales_won=sa.get("total"), sales_source=sa.get("source"), sales_updated=sa.get("updatedAt"),
                site=det.get("site"),
            )
    return out


WANTED_TTL_DAYS = 30   # 원티드의 연봉·인원은 국민연금 자료로 달마다 바뀐다 — 한 달 지난 회사만 다시 받는다


def _stale(rec: dict) -> bool:
    try:
        return (datetime.now() - datetime.strptime(rec.get("fetched") or "2000-01-01", "%Y-%m-%d")).days >= WANTED_TTL_DAYS
    except ValueError:
        return True


def wanted(limit: int | None = None, wait_ms: int = 1500) -> None:
    store = OUT_DIR / "wanted.json"
    have = _load(store, {})
    todo: dict[str, str] = {}
    for j in load_jobs():
        if j.get("site") != "wanted" or not j.get("url"):
            continue
        k = co_norm(j.get("company"))
        if k and k not in todo and (k not in have or _stale(have[k])):
            todo[k] = j["url"]
    items = list(todo.items())[:limit] if limit else list(todo.items())
    print(f"[wanted] 받을 회사 {len(items)} (이미 {len(have)})", flush=True)
    fails = 0
    for i, (k, wd) in enumerate(items, 1):
        try:
            jd = _get(wd).decode("utf-8", "replace")
            cid = re.search(r'"company_id":\s*(\d+)', jd) or re.search(r"/company/(\d+)", jd)
            if not cid:
                have[k] = {"error": "회사 번호 없음(공고 내려감)", "job_url": wd, "fetched": datetime.now().strftime("%Y-%m-%d")}
                continue
            time.sleep(jitter(wait_ms) / 1000)
            url = f"https://www.wanted.co.kr/company/{cid[1]}"
            c = _company_from_page(_next_data(_get(url, referer=wd).decode("utf-8", "replace")))
            have[k] = {"url": url, "company_id": int(cid[1]), "fetched": datetime.now().strftime("%Y-%m-%d"), **c}
            fails = 0
        except Exception as e:  # noqa: BLE001 — 한 회사가 실패해도 다음으로
            fails += 1
            print(f"  ! {k}: {e}", flush=True)
            if fails >= 8:
                print("[wanted] 연속 8번 실패 — 막힌 것 같아 멈춘다(다시 돌리면 이어서 한다)")
                break
            time.sleep(30)
        if i % 25 == 0:
            _save(store, have)
            print(f"  {i}/{len(items)}", flush=True)
        time.sleep(jitter(wait_ms) / 1000)
    _save(store, have)
    print(f"[wanted] 저장 {len(have)}개")


# ── 합치기 ─────────────────────────────────────────────────────────────

def _benefit_lines(text: str) -> list[str]:
    out = []
    for ln in re.split(r"\n+", text or ""):
        ln = re.sub(r"^[\s•·\-*▶▪■□○●◦✔✓]+", "", ln).strip()
        if re.match(r"^(채용\s*전형|전형\s*절차|지원\s*방법|접수|기타|참고|유의)", ln):
            break
        if 2 <= len(ln) <= 160:
            out.append(ln)
    return out


# ── 공고에 적힌 연봉 ─────────────────────────────────────────────────────
# "연봉 4,000만원 이상", "3,000~4,000만 원", "대졸 신입 기준 4,000만원", "1억 2,000만원" 같은 줄.
# 회사·직무·경력이 맞는 숫자라 평균보다 낫다. 인상액·성과급·지원금·월급은 뺀다.
_PAY_HEAD = re.compile(r"(급여|연봉|초봉|임금|처우|보수|annual\s*salary)", re.I)
_AMT = r"(?:(\d{1,2})\s*억\s*)?(\d{1,2},?\d{3}|\d{1,2}\s*천)?\s*만?\s*원?"
_RANGE = re.compile(r"(?:(\d)\s*억\s*)?(\d{1,2},?\d{3}|\d\s*천)\s*(?:만\s*원?)?\s*(?:[~\-–]|부터|에서)\s*(?:(\d)\s*억\s*)?(\d{1,2},?\d{3}|\d\s*천)?\s*만\s*원")
_ONE = re.compile(r"(?:(\d)\s*억\s*)?(\d{1,2},?\d{3}|\d\s*천)\s*만\s*원|(\d)\s*억\s*원")
_SKIP = re.compile(r"인상|성과급|인센티브|보너스|상여|지원금|복지\s*포인트|포인트|대출|수당|퇴직|월\s*급|월\s*\d|시급|일급|주급|스톡|지급액|추천|포상|축하|매출|투자|규모")


def _man_of(eok, man) -> int:
    v = int(eok or 0) * 10000
    if man:
        man = man.replace(",", "").replace(" ", "")
        v += int(man[:-1]) * 1000 if man.endswith("천") else int(man)
    return v


def _career_of(ctx: str, career: str | None) -> str:
    if re.search(r"신입|초봉|대졸|학사\s*기준|new\s*grad", ctx, re.I):
        return "신입"
    m = re.search(r"(\d{1,2})\s*(?:~|-)\s*(\d{1,2})\s*년", ctx) or re.search(r"(\d{1,2})\s*년\s*(?:차|이상|↑|경력)", ctx)
    if m:
        return f"{m[1]}~{m[2]}년" if m.lastindex == 2 and m[2] else f"{m[1]}년 이상"
    return (career or "경력 무관").strip()


def posting_salary(j: dict) -> dict | None:
    text = "\n".join(x for x in (j.get("full_jd"), j.get("benefits")) if x)
    for ln in re.split(r"\n+", text):
        if not _PAY_HEAD.search(ln) or len(ln) > 220:
            continue
        seg = ln[_PAY_HEAD.search(ln).start():][:120]
        if _SKIP.search(seg[:60]):
            continue
        lo = hi = None
        m = _RANGE.search(seg)
        if m:
            lo = _man_of(m[1], m[2])
            hi = _man_of(m[3], m[4]) if (m[3] or m[4]) else None
        else:
            m = _ONE.search(seg)
            if m:
                lo = _man_of(m[1] or m[3], m[2])
        if not lo or not (1800 <= lo <= 30000) or (hi and not (lo <= hi <= 40000)):
            continue
        tail = seg[m.end():m.end() + 12]
        kind = "이상" if re.search(r"이상|부터|최소|~\s*$", tail) or "최소" in seg[:m.start()] else ("범위" if hi and hi != lo else "고정")
        val = f"{_fmt(lo)} ~ {_fmt(hi)}" if kind == "범위" else _fmt(lo) + (" 이상" if kind == "이상" else "")
        return {"min": lo, "max": hi if kind == "범위" else None, "kind": kind, "value": val,
                "career": _career_of(seg, j.get("career")), "quote": seg.strip()[:100],
                "title": j.get("title"), "url": j.get("url"), "key": f"{j.get('site')}-{j.get('pid')}",
                "seen": (j.get("posted_date") or j.get("first_seen_at") or "")[:10]}
    return None


def build() -> None:
    jobs = load_jobs()
    names: dict[str, set] = defaultdict(set)
    posts: dict[str, list] = defaultdict(list)
    locs: dict[str, set] = defaultdict(set)
    sal: dict[str, list] = defaultdict(list)
    for j in jobs:
        k = co_norm(j.get("company"))
        if not k:
            continue
        names[k].add(j["company"])
        if j.get("location"):
            locs[k].add(j["location"])
        ps = posting_salary(j)
        if ps:
            sal[k].append(ps)
        if j.get("benefits"):
            posts[k].append({"url": j.get("url"), "title": j.get("title"), "lines": _benefit_lines(j["benefits"])})
    want = set()
    for k in names:
        want.update(keys(k))
    nps = nps_index(want)
    wd = _load(OUT_DIR / "wanted.json", {})
    out = {}
    for k in sorted(names):
        rec: dict = {"names": sorted(names[k]), "posting_locations": sorted(locs[k])[:10]}
        n = next((nps["companies"][x] for x in keys(k) if x in nps["companies"]), None)
        if n:
            rec["nps"] = {"rows": n[:5], "same_name_rows": len(n),
                          "warn": "같은 이름 사업장이 여럿 — 주소·업종으로 맞는 줄을 고른다" if len(n) > 1 else None}
        w = wd.get(k)
        if w and not w.get("error"):
            rec["wanted"] = w
        if posts[k]:
            seen, merged = set(), []
            for p in posts[k]:
                for ln in p["lines"]:
                    if ln not in seen:
                        seen.add(ln)
                        merged.append(ln)
            rec["posting_benefits"] = {"lines": merged[:60], "from": [p["url"] for p in posts[k]][:5]}
        if sal[k]:
            seen_q, uniq = set(), []
            for x in sorted(sal[k], key=lambda x: x["seen"], reverse=True):
                sig = (x["value"], x["career"])
                if sig not in seen_q:
                    seen_q.add(sig)
                    uniq.append(x)
            rec["posting_salary"] = uniq[:8]
        out[k] = rec
    data = {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "about": "공고 풀이 일꾼용 회사 사실(AI 없이 모음). 연봉 칸에 쓸 때 basis 는 '공공데이터 집계'(nps·wanted), 출처 URL 은 각 칸의 url/source_url.",
            "nps_file": nps["file"], "nps_source_url": nps["source_url"], "nps_note": nps["rate_note"],
            "count": {"companies": len(out), "nps": sum("nps" in v for v in out.values()),
                      "wanted": sum("wanted" in v for v in out.values()),
                      "posting_benefits": sum("posting_benefits" in v for v in out.values()),
                      "posting_salary": sum("posting_salary" in v for v in out.values())},
            "companies": out}
    _save(OUT, data)
    print(f"[build] {OUT} — {data['count']}")
    _to_db("build")


def _to_db(what: str) -> None:
    """수집 중간물(var/ 의 JSON)을 정본 DB 로 옮긴다 — store.ingest.company_facts. DB 가 없으면 건너뛴다."""
    try:
        from store.ingest.company_facts import sync
        print(f"[{what}] DB {sync()}")
    except Exception as e:  # noqa: BLE001 — 크롤은 DB 없이도 끝까지 간다
        print(f"[{what}] DB 옮기기 건너뜀: {e}")


# ── DB 행 만들기(store.ingest.company_facts 가 부른다) ───────────────────────────


def _man(won: float | None) -> int | None:
    return round(won / 10000) if won else None


def _fmt(man: int) -> str:
    return f"{man // 10000}억 {man % 10000:,}만원".replace(" 0만원", "원") if man >= 10000 else f"{man:,}만원"


def _pick_nps(rows: list[dict], locs: list[str]) -> dict | None:
    """사업장 주소의 시·군·구가 공고 근무지에 들어 있는 줄을 고른다(가입자 많은 순).
    같은 이름이 여럿인데 근무지로 못 가르면 싣지 않는다 — 남의 회사 숫자를 싣는 것보다 비우는 게 낫다."""
    if not rows:
        return None
    here = re.sub(r"\s", "", " ".join(l for l in locs if l))
    def ok(r):
        ds = re.findall(r"([가-힣]{1,5}(?:구|군|시))(?=\s|$)", (r.get("address") or "").replace("특별시", "").replace("광역시", ""))
        return any(d in here for d in ds if len(d) >= 2)
    hit = [r for r in rows if ok(r)]
    if hit:
        return hit[0]
    return rows[0] if len(rows) == 1 else None


_SIZE_TAG = re.compile(r"\d+명|설립|연봉상위|대기업|중견|유망|TOP")


def fact_rows(data: dict) -> tuple[list[dict], list[dict]]:
    """company_facts.json → (company_fact 행, company_posting_salary 행). 화면 문장은 backend 가 만든다."""
    facts, sal = [], []
    for k, c in data["companies"].items():
        w, n = c.get("wanted"), None
        if c.get("nps"):
            wa = (w or {}).get("address") or (w or {}).get("full_location")
            # 원티드 주소가 있으면 그 주소와 같은 시·군·구의 사업장이 먼저다(이름이 같은 다른 회사가 공고를 같이 낸다)
            n = _pick_nps(c["nps"]["rows"], [wa]) if wa else _pick_nps(c["nps"]["rows"], c.get("posting_locations") or [])
            we = (w or {}).get("employees")
            if n and we and not (we / 3 <= n["members"] <= we * 3):
                n = None  # 원티드 인원과 세 배 넘게 다르면 동명의 다른 사업장으로 본다
        psal = c.get("posting_salary") or []
        if not (w or n or psal):
            continue
        waddr = (w or {}).get("full_location") or (w or {}).get("address")
        facts.append({
            "company_key": k, "name": (w or {}).get("name") or (c.get("names") or [k])[0], "names": c.get("names") or [],
            "employees": (w or {}).get("employees") or (n or {}).get("members"),
            "industry": (w or {}).get("industry") or (n or {}).get("industry"), "founded": (w or {}).get("founded"),
            "address": waddr or (n or {}).get("address"), "address_source": "wanted" if waddr else ("nps" if n else None),
            "benefit_tags": [t for t in (w or {}).get("tags") or [] if not _SIZE_TAG.search(t)],
            "wanted_url": (w or {}).get("url"), "wanted_avg_pay": _man((w or {}).get("avg_salary_won")),
            "wanted_pay_updated": ((w or {}).get("salary_updated") or "")[:10] or None,
            "nps_members": (n or {}).get("members"), "nps_annual_est": (n or {}).get("annual_income_est_만원"),
            "nps_month": (n or {}).get("month"), "nps_biz6": (n or {}).get("biz6"), "nps_address": (n or {}).get("address"),
        })
        for x in psal:
            sal.append({"job_key": x["key"], "company_key": k, "title": x.get("title"), "url": x.get("url"),
                        "pay_min": x["min"], "pay_max": x.get("max"), "kind": x["kind"], "career": x.get("career"),
                        "quote": x.get("quote"), "seen_on": x.get("seen") or None})
    return facts, sal


# ── 연차별 시장 시세(고용노동부 고용형태별노동실태조사, KOSIS OpenAPI) ───────────────────
# 회사별 연차 연봉은 공개된 곳이 없다(직원 제보 사이트는 약관·robots 로 막힘). 대신 정부 통계의
# 직종 × 경력년수 임금과 회사 규모 × 대졸 × 나이 임금을 실어, 공고 화면이 '이 직무·이 규모면 몇 년차에 얼마'를 보인다.
WAGE_OUT = VAR_DIR / "roles" / "market_wage.json"   # 수집 중간물 — 정본은 DB market_wage·market_wage_size
KOSIS_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
WAGE_OCC = {  # 한국표준직업분류 7차 — 개발 공고가 걸리는 직종
    "222": "컴퓨터 시스템 및 소프트웨어 전문가", "223": "데이터 및 네트워크 관련 전문가",
    "224": "정보 시스템 및 웹 운영자", "221": "컴퓨터 하드웨어 및 통신공학 전문가",
    "234": "전기·전자공학 기술자 및 시험원", "235": "기계·로봇공학 기술자 및 시험원",
    "22": "정보 통신 전문가 및 기술직", "28": "문화·예술 관련직(디자인 포함)",
}


def _env(name: str) -> str | None:
    import os
    if os.environ.get(name):
        return os.environ[name]
    for f in (Path(__file__).resolve().parent.parent / ".env",):
        try:
            for ln in f.read_text(encoding="utf-8").splitlines():
                if ln.startswith(name + "="):
                    return ln.split("=", 1)[1].strip()
        except OSError:
            pass
    return None


def _kosis(tbl: str, dims: int) -> list[dict]:
    key = _env("KOSIS_API_KEY")
    if not key:
        raise RuntimeError("KOSIS_API_KEY 없음 — catch_capture/.env 에 넣는다(kosis.kr/openapi 무료 발급)")
    p = {"method": "getList", "apiKey": key, "orgId": "118", "tblId": tbl, "itmId": "ALL", "prdSe": "Y",
         "newEstPrdCnt": "1", "format": "json", "jsonVD": "Y"}
    for i in range(1, 5):
        p[f"objL{i}"] = "ALL" if i <= dims else ""
    d = json.loads(_get(KOSIS_URL + "?" + urllib.parse.urlencode(p), timeout=120))
    if isinstance(d, dict):
        raise RuntimeError(f"KOSIS {tbl}: {d}")
    return d


def _annual(monthly_total_thousand: str) -> int:
    """월임금총액(천원, 특별급여 ÷12 포함) × 12 → 만원."""
    return round(float(monthly_total_thousand) * 12 / 10)


def wage() -> None:
    a = _kosis("DT_118N_PAYM47", 3)   # 직종 × 성별 × 경력년수
    b = _kosis("DT_118N_PAY0004", 4)  # 규모 × 학력 × 성별 × 연령
    year = a[0]["PRD_DE"]
    occ: dict = {}
    for x in a:
        if x["C2_NM"] != "전체":
            continue
        code = (re.search(r"\((\d+)\)\s*$", x["C1_NM"]) or [None, None])[1]
        if code not in WAGE_OCC:
            continue
        o = occ.setdefault(code, {"name": re.sub(r"\(\d+\)$", "", x["C1_NM"]).strip(), "careers": {}})
        c = o["careers"].setdefault(x["C3_NM"], {})
        if x["ITM_NM"] == "월임금총액":
            c["annual_만원"] = _annual(x["DT"])
        elif x["ITM_NM"] == "근로자수":
            c["workers"] = int(float(x["DT"]))
    sizes: dict = {}
    for x in b:
        if x["C2_NM"] != "대졸이상" or x["C3_NM"] != "전체" or x["ITM_NM"] not in ("월임금총액", "평균근속년수"):
            continue
        sz = re.sub(r"^\d\s*규모\s*|\s", "", x["C1_NM"]).replace("(", "").replace(")", "")
        row = sizes.setdefault(sz, {}).setdefault(x["C4_NM"].replace(" ", ""), {})
        if x["ITM_NM"] == "월임금총액":
            row["annual_만원"] = _annual(x["DT"])
        else:
            row["tenure_years"] = float(x["DT"])
    doc = {"kind": "market_wage", "year": year, "generated_at": datetime.now().isoformat(timespec="seconds"),
           "source": {"title": f"고용노동부 고용형태별노동실태조사 {year}년 — 직종·경력년수·성별 / 규모·학력·연령계층·성별 임금",
                      "url": "https://kosis.kr/statHtml/statHtml.do?orgId=118&tblId=DT_118N_PAYM47", "kind": "reference", "date": year},
           "note": "월임금총액(정액·초과급여 + 전년도 특별급여 ÷12) × 12 로 연봉을 셈했다. 6월 급여 기준, 회사별이 아니라 전국 직종·규모 평균이다.",
           "occupations": occ, "sizes_college": sizes}
    _save(WAGE_OUT, doc)
    print(f"[wage] {WAGE_OUT} — {year}년, 직종 {len(occ)}개, 규모 {len(sizes)}개")
    _to_db("wage")


def show(q: str) -> None:
    d = _load(OUT, {}).get("companies", {})
    for k in keys(q):
        if k in d:
            print(json.dumps(d[k], ensure_ascii=False, indent=1))
            return
    hits = [k for k in d if co_norm(q) in k][:10]
    print("없음. 비슷한 키:", hits)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    if cmd in ("nps", "all"):
        nps_download()
    if cmd in ("wanted", "all"):
        lim = int(argv[1]) if cmd == "wanted" and len(argv) > 1 else None
        wanted(lim)
    if cmd in ("build", "nps", "all"):
        build()
    if cmd in ("wage", "all"):
        wage()
    if cmd == "show":
        show(" ".join(argv[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
