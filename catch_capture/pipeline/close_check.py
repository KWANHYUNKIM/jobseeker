"""공고 마감 재확인 — 원본 사이트에 다시 물어 끝난 공고를 닫는다.

`job_status` 는 공고가 들고 온 **텍스트**("~06/14", "D-4")만 보고 마감을 판정한다.
그 텍스트가 없으면 판정할 근거도 없어서 모집중으로 남는데, 문제는 그런 공고가
소수가 아니라는 것이다 — wanted 는 마감일 필드가 아예 없어 3천여 건 전부가
영구 모집중이었고, 연도 없는 "06/14" 도 몇 달 지나면 어느 해인지로 다시 흔들린다.

그래서 여기서는 추측하지 않고 원본에 다시 묻는다. 사이트마다 답이 있는 자리가 다르다:

  wanted   : chaos API 의 job.status / due_time      (status != active → 마감)
  jumpit   : position API 의 closedAt / alwaysOpen   (연도 포함 마감일)
  jobkorea : 상세 페이지 JSON-LD 의 validThrough     (연도 포함 마감일)
  saramin  : 상세 페이지의 "마감일:YYYY-MM-DD"
  dev      : catch 상세 JSON-LD 제목의 "[마감]" 접두
  ats      : greenhouse/lever API 404, ashby 보드 목록에서 사라짐
  remote   : 원본 URL 이 404/410

판정 결과는 `catch_capture/job_closures.json`(원장)에 쌓이고, 그걸 읽는 쪽은
`job_status.classify_status` 하나다. 즉 aggregate 든 enrich 든 같은 답을 본다.

한 번 마감으로 확인된 공고는 다시 묻지 않는다(재공고는 새 pid 로 온다). 나머지는
`--recheck-days` 마다 다시 확인하되 회차당 `--limit` 건으로 끊는다 — 사이클마다
수천 건을 두드리면 차단당하고, 그러면 크롤 본체까지 같이 죽는다.

사용:
    python -m pipeline.close_check                      # 기본 400건 확인
    python -m pipeline.close_check --limit 50 --dry-run # 원장 안 건드리고 보기만
    python -m pipeline.close_check --sites wanted       # 특정 사이트만
    python -m pipeline.close_check --selftest           # 파서 회귀 테스트(네트워크 없음)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import random
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

from pipeline.job_status import (
    CLOSURES_PATH,
    closure_key,
    load_closures,
    today_date,
)

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
LATEST_DIR = BASE_DIR / "screenshots" / "all_개발자_latest"
ENRICHED = ROOT_DIR / "jd-viewer" / "public" / "all_jobs_enriched.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
TIMEOUT = 20
LIMIT_DEFAULT = 400      # 회차당 확인 건수 — 차단 방지용 상한
RECHECK_DAYS = 7         # 모집중으로 확인된 공고를 다시 묻기까지의 간격
SLEEP_MS = 450           # 요청 간 기본 간격(지터 적용)
SAVE_EVERY = 25          # 중간 저장 간격 — 도중에 죽어도 확인분은 남는다

# 판정 결과: (status, reason, deadline_iso)
#   status "closed" | "active" | "unknown"
#   unknown 은 "물어봤지만 답을 못 얻음" 이다. 원장에는 남기되(같은 공고를 매 회차
#   다시 두드리지 않으려고) job_status 는 이를 무시하고 기존 텍스트 규칙으로 돌아간다.
Verdict = tuple[str, str, str | None]


def _sleep() -> None:
    time.sleep(max(0.15, SLEEP_MS * random.uniform(0.7, 1.4) / 1000))


def _fetch(url: str, referer: str | None = None) -> tuple[int | None, str]:
    """(HTTP 상태코드, 본문). 네트워크 자체가 실패하면 (None, 사유)."""
    headers = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:                                          # noqa: BLE001
        return None, repr(e)


def _iso(value: str | None) -> str | None:
    """'2026-06-30T00:00:00' / '2026-06-30 23:59:59' / '2026.06.30' → 'YYYY-MM-DD'."""
    if not value:
        return None
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", str(value))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def _by_deadline(iso: str | None, today: date, open_reason: str) -> Verdict:
    """연도까지 확인된 마감일로 판정. 마감일이 없으면 모집중으로 둔다."""
    if iso:
        if date.fromisoformat(iso) < today:
            return "closed", f"원본 확인: 마감일 경과({iso})", iso
        return "active", f"원본 확인: 마감 {iso}", iso
    return "active", open_reason, None


# ── 사이트별 판정(파싱만; 네트워크 없음 → selftest 가능) ─────────────────

def verdict_wanted(payload: dict, today: date) -> Verdict:
    job = payload.get("job") or {}
    status = str(job.get("status") or "").lower()
    iso = _iso(job.get("due_time"))
    if status and status != "active":
        # close(마감) / draft(내림) / hidden — 어느 쪽이든 지원할 수 없다
        return "closed", f"원본 상태 {status}" + (f"(마감 {iso})" if iso else ""), iso
    if not status:
        return "unknown", "원본 상태 필드 없음", iso
    return _by_deadline(iso, today, "원본 확인: 모집중")


def verdict_jumpit(payload: dict, today: date) -> Verdict:
    result = payload.get("result")
    if not result:
        return "closed", "원본 조회 불가(내려간 공고)", None
    if result.get("alwaysOpen"):
        return "active", "원본 확인: 상시채용", None
    iso = _iso(result.get("closedAt"))
    if not iso:
        return "unknown", "마감일 필드 없음", None
    return _by_deadline(iso, today, "원본 확인: 모집중")


_JOBKOREA_VALID = re.compile(r'validThrough\\?"?\s*:\s*\\?"(\d{4}-\d{2}-\d{2})')
_JOBKOREA_DEADLINE = re.compile(r"마감일\s*:\s*(\d{4}\.\d{1,2}\.\d{1,2})")
_SARAMIN_DEADLINE = re.compile(r"마감일\s*:\s*(\d{4}-\d{1,2}-\d{1,2})")
_CATCH_CLOSED = re.compile(r'"@type"\s*:\s*"JobPosting"\s*,\s*"title"\s*:\s*"\[마감\]')
# 페이지가 통째로 "없는 공고" 로 바뀐 경우 — 사이트 공통으로 쓰는 문구들
_GONE = re.compile(r"마감된\s*(?:채용)?공고|삭제된\s*공고|종료된\s*채용|존재하지\s*않는\s*공고"
                   r"|채용이\s*마감|삭제되었습니다")
_ALWAYS_OPEN = re.compile(r"상시\s*채용|수시\s*채용|채용\s*시\s*마감|채용시\s*마감")


def verdict_jobkorea(html: str, today: date) -> Verdict:
    if _GONE.search(html):
        return "closed", "원본 확인: 마감된 공고", None
    m = _JOBKOREA_VALID.search(html)
    iso = _iso(m.group(1)) if m else None
    if not iso:
        m = _JOBKOREA_DEADLINE.search(html)
        iso = _iso(m.group(1)) if m else None
    if not iso:
        if _ALWAYS_OPEN.search(html):
            return "active", "원본 확인: 상시채용", None
        return "unknown", "마감일 표기를 찾지 못함", None
    return _by_deadline(iso, today, "원본 확인: 모집중")


def verdict_saramin(html: str, today: date) -> Verdict:
    if _GONE.search(html):
        return "closed", "원본 확인: 마감된 공고", None
    m = _SARAMIN_DEADLINE.search(html)
    iso = _iso(m.group(1)) if m else None
    if not iso:
        if _ALWAYS_OPEN.search(html):
            return "active", "원본 확인: 상시채용", None
        return "unknown", "마감일 표기를 찾지 못함", None
    return _by_deadline(iso, today, "원본 확인: 모집중")


def verdict_catch(html: str, today: date) -> Verdict:
    """catch(dev)는 마감돼도 페이지가 남고, 대신 JSON-LD 제목 앞에 [마감] 이 붙는다.

    표기가 없다고 모집중으로 단정하지는 않는다 — catch 는 남의 공채를 모아 오는 자리라
    원본이 닫혀도 여기 표기가 늦을 수 있다. 마감 쪽으로만 확정하고, 아니면 공고가
    들고 온 마감일 텍스트("~06.14(일) 24시")에 판정을 돌려준다."""
    if _CATCH_CLOSED.search(html):
        return "closed", "원본 확인: 제목 [마감]", None
    return "unknown", "[마감] 표기 없음 — 텍스트 규칙 유지", None


# ── 사이트별 확인(네트워크) ──────────────────────────────────────────────

def _json_verdict(url: str, parse, today: date, referer: str | None = None) -> Verdict:
    code, body = _fetch(url, referer=referer)
    if code in (404, 410):
        return "closed", f"원본 삭제(HTTP {code})", None
    if code != 200 or not body:
        return "unknown", f"확인 실패(http={code})", None
    try:
        payload = json.loads(body)
    except Exception:                                               # noqa: BLE001
        return "unknown", "응답 파싱 실패", None
    return parse(payload, today)


def _html_verdict(url: str, parse, today: date) -> Verdict:
    code, body = _fetch(url)
    if code in (404, 410):
        return "closed", f"원본 삭제(HTTP {code})", None
    if code != 200 or not body:
        return "unknown", f"확인 실패(http={code})", None
    return parse(body, today)


def check_wanted(job: dict, today: date, cache: dict) -> Verdict:
    pid = str(job.get("pid") or job.get("position_id") or "")
    return _json_verdict(
        f"https://www.wanted.co.kr/api/chaos/jobs/v1/{pid}/details",
        verdict_wanted, today, referer=f"https://www.wanted.co.kr/wd/{pid}")


def check_jumpit(job: dict, today: date, cache: dict) -> Verdict:
    pid = str(job.get("pid") or job.get("position_id") or "")
    return _json_verdict(f"https://jumpit.saramin.co.kr/api/position/{pid}",
                         verdict_jumpit, today)


def check_jobkorea(job: dict, today: date, cache: dict) -> Verdict:
    pid = str(job.get("pid") or "")
    return _html_verdict(f"https://www.jobkorea.co.kr/Recruit/GI_Read/{pid}",
                         verdict_jobkorea, today)


def check_saramin(job: dict, today: date, cache: dict) -> Verdict:
    pid = str(job.get("pid") or job.get("rec_idx") or "")
    return _html_verdict(
        f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={pid}",
        verdict_saramin, today)


def check_dev(job: dict, today: date, cache: dict) -> Verdict:
    url = job.get("url") or ""
    if not url:
        return "unknown", "URL 없음", None
    return _html_verdict(url, verdict_catch, today)


def _ashby_board(slug: str, cache: dict) -> set[str] | None:
    """ashby 는 공고별 엔드포인트가 없다 — 보드 전체를 회차당 한 번만 받아 캐시한다."""
    key = f"ashby:{slug}"
    if key in cache:
        return cache[key]
    code, body = _fetch(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    ids: set[str] | None = None
    if code == 200 and body:
        try:
            ids = {str(j.get("id")) for j in (json.loads(body).get("jobs") or [])}
        except Exception:                                           # noqa: BLE001
            ids = None
    elif code in (404, 410):
        ids = set()   # 보드 자체가 사라짐 → 그 회사 공고는 전부 마감
    cache[key] = ids
    return ids


def check_board(job: dict, today: date, cache: dict) -> Verdict:
    """ats/remote — 공고가 보드에 아직 있는지만 본다(마감일 개념이 없다)."""
    pid = str(job.get("pid") or "")
    parts = pid.split(":")
    provider = parts[0] if parts else ""

    if provider == "greenhouse" and len(parts) == 3:
        code, _ = _fetch(f"https://boards-api.greenhouse.io/v1/boards/{parts[1]}/jobs/{parts[2]}")
        if code in (404, 410):
            return "closed", "greenhouse 보드에서 내려감", None
        return ("active", "원본 확인: 모집중", None) if code == 200 else \
               ("unknown", f"확인 실패(http={code})", None)

    if provider == "lever" and len(parts) == 3:
        code, _ = _fetch(f"https://api.lever.co/v0/postings/{parts[1]}/{parts[2]}")
        if code in (404, 410):
            return "closed", "lever 보드에서 내려감", None
        return ("active", "원본 확인: 모집중", None) if code == 200 else \
               ("unknown", f"확인 실패(http={code})", None)

    if provider == "ashby" and len(parts) == 3:
        ids = _ashby_board(parts[1], cache)
        if ids is None:
            return "unknown", "ashby 보드 조회 실패", None
        if parts[2] in ids:
            return "active", "원본 확인: 모집중", None
        return "closed", "ashby 보드에서 내려감", None

    # 스크랩 보드(remoteok/wwr/himalayas): 페이지가 살아 있으면 모집중으로 단정할 수
    # 없으니 사라진 경우만 닫는다.
    url = job.get("url") or ""
    if not url:
        return "unknown", "URL 없음", None
    code, _ = _fetch(url)
    if code in (404, 410):
        return "closed", f"원본 삭제(HTTP {code})", None
    return "unknown", f"페이지 생존(http={code}) — 마감 여부 불명", None


CHECKERS = {
    "wanted": check_wanted,
    "jumpit": check_jumpit,
    "jobkorea": check_jobkorea,
    "saramin": check_saramin,
    "dev": check_dev,
    "ats": check_board,
    "remote": check_board,
}


# ── 원장 ────────────────────────────────────────────────────────────────

def save_closures(ledger: dict, path: Path = CLOSURES_PATH) -> None:
    """원장 원자적 저장(임시 파일 → rename). 읽는 쪽이 반쯤 쓰인 파일을 보면 안 된다."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _source_jobs() -> tuple[list[dict], str]:
    """확인 대상 공고 목록. 최신 통합 스냅샷 우선, 없으면 뷰어 데이터."""
    latest = LATEST_DIR / "all_jobs.json"
    if latest.exists():
        try:
            return json.loads(latest.read_text(encoding="utf-8")), str(latest)
        except Exception as e:                                      # noqa: BLE001
            print(f"[!] {latest} 파싱 실패: {e}", flush=True)
    if ENRICHED.exists():
        jobs = json.loads(ENRICHED.read_text(encoding="utf-8"))
        return [j for j in jobs if j.get("status") != "closed"], str(ENRICHED)
    return [], "(없음)"


def _age_days(checked_at: str, now: datetime) -> float:
    try:
        return (now - datetime.fromisoformat(checked_at)).total_seconds() / 86400
    except Exception:                                               # noqa: BLE001
        return 1e9


def due_jobs(jobs: list[dict], entries: dict, now: datetime, *,
             sites: set[str] | None, recheck_days: float,
             recheck_closed: bool) -> list[dict]:
    """확인이 필요한 공고를 오래 방치된 순으로 정렬해 돌려준다."""
    out: list[tuple[float, dict]] = []
    seen: set[str] = set()
    for job in jobs:
        site = job.get("site") or ""
        if site not in CHECKERS or (sites and site not in sites):
            continue
        key = closure_key(job)
        if not key or key in seen:
            continue
        seen.add(key)
        entry = entries.get(key)
        if entry:
            # 마감은 되돌아오지 않는다 — 재공고는 새 pid 로 온다.
            if entry.get("status") == "closed" and not recheck_closed:
                continue
            age = _age_days(entry.get("checked_at", ""), now)
            if age < recheck_days:
                continue
        else:
            age = 1e9   # 한 번도 확인 안 한 공고가 최우선
        out.append((age, job))
    out.sort(key=lambda t: t[0], reverse=True)

    # 사이트별로 번갈아 내보낸다. 오래된 순서 그대로면 한 호스트에 수백 번을 연달아
    # 두드리게 되고(= 차단 유도), 건수가 많은 사이트가 앞을 다 차지해 뒤쪽 사이트는
    # 며칠씩 확인을 못 받는다. 각 사이트 안에서는 오래 방치된 순서를 지킨다.
    queues: dict[str, list[dict]] = {}
    for _, job in out:
        queues.setdefault(job["site"], []).append(job)
    mixed: list[dict] = []
    while queues:
        for site in list(queues):
            mixed.append(queues[site].pop(0))
            if not queues[site]:
                del queues[site]
    return mixed


def run(limit: int = LIMIT_DEFAULT, *, recheck_days: float = RECHECK_DAYS,
        sites: set[str] | None = None, dry_run: bool = False,
        recheck_closed: bool = False, verbose: bool = True) -> dict:
    today = today_date()
    now = datetime.now()
    jobs, src = _source_jobs()
    if not jobs:
        print("[close_check] 확인할 공고 목록을 찾지 못했습니다.", flush=True)
        return {"checked": 0, "closed": 0, "active": 0, "unknown": 0}

    ledger = load_closures(force=True)
    entries: dict = ledger.setdefault("checked", {})
    targets = due_jobs(jobs, entries, now, sites=sites, recheck_days=recheck_days,
                       recheck_closed=recheck_closed)
    print(f"[close_check] 대상 {len(targets):,}건 / 전체 {len(jobs):,}건 "
          f"(원장 {len(entries):,}건, 출처 {Path(src).name}) — 이번 회차 {min(limit, len(targets)):,}건 확인",
          flush=True)

    cache: dict = {}
    stats = {"checked": 0, "closed": 0, "active": 0, "unknown": 0}
    per_site: dict[str, list[int]] = {}
    for job in targets[:limit]:
        site = job["site"]
        try:
            status, reason, iso = CHECKERS[site](job, today, cache)
        except Exception as e:                                      # noqa: BLE001
            status, reason, iso = "unknown", f"예외: {e!r}", None
        stats["checked"] += 1
        stats[status] += 1
        tally = per_site.setdefault(site, [0, 0, 0])
        tally[{"closed": 0, "active": 1, "unknown": 2}[status]] += 1

        if verbose and status == "closed":
            print(f"  ✖ {site:<8} {str(job.get('company'))[:14]:<14} "
                  f"{str(job.get('title'))[:34]:<34} {reason}", flush=True)
        if not dry_run:
            entries[closure_key(job)] = {
                "status": status,
                "reason": reason,
                "deadline": iso,
                "checked_at": now.isoformat(timespec="seconds"),
                "url": job.get("url", ""),
                "company": job.get("company", ""),
                "title": job.get("title", ""),
            }
            if stats["checked"] % SAVE_EVERY == 0:
                save_closures(ledger)
        _sleep()

    if not dry_run:
        ledger["updated_at"] = now.isoformat(timespec="seconds")
        save_closures(ledger)

    print(f"[close_check] 확인 {stats['checked']:,}건 → 마감 {stats['closed']:,} / "
          f"모집중 {stats['active']:,} / 판정불가 {stats['unknown']:,}"
          f"{' (dry-run: 원장 미기록)' if dry_run else ''}", flush=True)
    for site, (c, a, u) in sorted(per_site.items()):
        print(f"    {site:<9} 마감 {c:>4} / 모집중 {a:>4} / 불명 {u:>4}", flush=True)
    return stats


# ── selftest (네트워크 없음) ─────────────────────────────────────────────

def _selftest() -> int:
    """사이트별 판정 규칙 회귀 방지. 원본 응답의 최소 형태를 그대로 넣어 본다."""
    t = date(2026, 9, 1)
    cases: list[tuple[str, Verdict, str]] = [
        ("wanted-close",
         verdict_wanted({"job": {"status": "close", "due_time": None}}, t), "closed"),
        ("wanted-draft",
         verdict_wanted({"job": {"status": "draft"}}, t), "closed"),
        ("wanted-active",
         verdict_wanted({"job": {"status": "active", "due_time": "2026-09-30T00:00:00"}}, t), "active"),
        ("wanted-active-지난마감",
         verdict_wanted({"job": {"status": "active", "due_time": "2026-06-30T00:00:00"}}, t), "closed"),
        ("jumpit-지난마감",
         verdict_jumpit({"result": {"closedAt": "2026-06-09 23:59:59"}}, t), "closed"),
        ("jumpit-상시",
         verdict_jumpit({"result": {"alwaysOpen": True}}, t), "active"),
        ("jumpit-내려감", verdict_jumpit({"result": None}, t), "closed"),
        ("jobkorea-validThrough",
         verdict_jobkorea('x validThrough": "2026-06-07T23:59" y', t), "closed"),
        ("jobkorea-마감일표기",
         verdict_jobkorea("마감일 : 2026.10.11", t), "active"),
        ("jobkorea-마감문구",
         verdict_jobkorea("이미 마감된 공고입니다", t), "closed"),
        ("jobkorea-불명", verdict_jobkorea("<html>본문만 있음</html>", t), "unknown"),
        ("saramin-지난마감", verdict_saramin("마감일:2026-06-07, 홈페이지", t), "closed"),
        ("saramin-앞으로", verdict_saramin("마감일:2026-09-30", t), "active"),
        ("saramin-상시", verdict_saramin("접수기간 상시채용", t), "active"),
        ("catch-마감",
         verdict_catch('{"@type":"JobPosting","title":"[마감] 개발자 채용"}', t), "closed"),
        ("catch-표기없음",
         verdict_catch('{"@type":"JobPosting","title":"개발자 채용"}', t), "unknown"),
    ]
    failed = 0
    for name, (status, reason, _iso), want in cases:
        if status != want:
            failed += 1
            print(f"FAIL {name} → {status} (기대 {want}, {reason})")
    print(f"close_check selftest: {len(cases) - failed}/{len(cases)} 통과")
    return 1 if failed else 0


def main() -> None:
    args = _sys.argv[1:]
    if "--selftest" in args:
        raise SystemExit(_selftest())

    def opt(name: str, default: str) -> str:
        return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default

    sites_raw = opt("--sites", "")
    run(limit=int(opt("--limit", str(LIMIT_DEFAULT))),
        recheck_days=float(opt("--recheck-days", str(RECHECK_DAYS))),
        sites={s.strip() for s in sites_raw.split(",") if s.strip()} or None,
        dry_run="--dry-run" in args,
        recheck_closed="--recheck-closed" in args)


if __name__ == "__main__":
    main()
