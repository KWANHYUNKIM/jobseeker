"""채용 추이 — '지금 공격적으로 뽑는 회사'를 주별 새 공고 수로 본다.

지원자 수·조회수는 원본 사이트만 알고 공개하지 않는다(잡코리아의 공개 통계도 비로그인에는
지원자 수를 가린다). 그래서 우리가 실제로 가진 것만 쓴다:

  · 뽑는 양   — 최근 4주(진행 중인 이번 주 제외)에 새로 올린 공고 수, 그 전 4주와의 차이
  · 자리 수   — 공고가 밝힌 모집인원. 개발 공고는 숫자 대신 자릿수로 쓰는 일이 많아서
                (○명 = 1~9명, ○○명 = 10~99명) 정확한 수와 구간을 더해 '최소~최대'로 낸다.
                모집인원을 밝힌 공고만 센다 — `known`/`of` 가 그 비율이다(대부분 잡코리아).
  · 빨리 닫힘 — 낸 공고가 2주 안에 닫힌 비율. 사람이 빨리 찼을 수도, 공고를 내렸을 수도
                있어서 '지원이 몰렸다'의 증거가 아니라 **신호**다. 화면에도 그렇게 적는다.

닫힌 공고가 MIN_N 건 미만이면 비율을 내지 않는다(careers 와 같은 규칙 — 1건 중 1건은 100%가 아니다).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.features.hiring import repository
from app.utils.cache import cached

KST = ZoneInfo("Asia/Seoul")
COMPARE_WEEKS = 4      # 최근 4주 대 그 전 4주
FAST_DAYS = 14         # 이 날 수 안에 닫히면 '빨리 닫힘'
MIN_N = 3
TOP_ROLES = 3
SIZES = ("대기업", "중견기업", "중소기업", "해외 기업", "미분류")
SORTS = ("recent", "growth", "fast", "active", "seats")
HC_KEYS = ("hc_known", "hc_exact", "hc_one", "hc_two", "seats_low", "seats_high")


def week_starts(weeks: int, today: date | None = None) -> list[date]:
    """오늘이 든 주(월요일 시작)까지 거슬러 weeks 개 — 오래된 것이 앞."""
    today = today or datetime.now(KST).date()
    this_monday = today - timedelta(days=today.weekday())
    return [this_monday - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]


def reliable_weeks(starts: list[date], coverage: datetime | None) -> list[bool]:
    """주마다 '건수를 믿어도 되나'. 수집 시작(+ 첫 수집 BACKFILL 일) 전에 시작한 주는 그날까지
    살아남은 공고만 잡혀 있어 실제보다 적다 — 이번 주가 그런 주와 비교되면 '급증'으로 잘못 읽힌다."""
    if coverage is None:
        return [False] * len(starts)
    ok_from = coverage.astimezone(KST).date() + timedelta(days=repository.BACKFILL_DAYS)
    return [d >= ok_from for d in starts]


def comparable(reliable: list[bool]) -> bool:
    """최근 4주와 그 전 4주(이번 주 제외)가 전부 믿을 만한 주인가."""
    full = reliable[:-1]
    return len(full) >= 2 * COMPARE_WEEKS and all(full[-2 * COMPARE_WEEKS:])


def trend_label(recent: int, prev: int, ok: bool = True) -> str:
    """사람이 읽는 한 낱말. 차이가 3건 미만이면 비율이 커도 '그대로'다(1건 → 2건은 급증이 아니다).
    비교할 기간의 데이터가 아직 안 쌓였으면 'unknown' — 0 과 비교해 'new' 라고 하지 않는다."""
    if not ok:
        return "unknown"
    if prev == 0 and recent > 0:
        return "new"
    if recent - prev >= 3 and recent >= prev * 1.5:
        return "up"
    if prev - recent >= 3 and recent <= prev * 0.5:
        return "down"
    return "flat"


def summarize(series: list[int]) -> tuple[int, int]:
    """주별 건수 → (최근 4주, 그 전 4주). 마지막 칸은 진행 중인 이번 주라 비교에서 뺀다."""
    full = series[:-1]
    recent = sum(full[-COMPARE_WEEKS:])
    prev = sum(full[-2 * COMPARE_WEEKS:-COMPARE_WEEKS])
    return recent, prev


def recent_seats(weekly_hc: list[dict], of: int) -> dict:
    """최근 4주(이번 주 제외)의 자리 수. weekly_hc 는 주 칸마다 HC_KEYS 합계(오래된 것이 앞)."""
    window = weekly_hc[:-1][-COMPARE_WEEKS:]
    t = {k: sum(w[k] for w in window) for k in HC_KEYS}
    return {
        "known": t["hc_known"],            # 모집인원을 밝힌 공고 수
        "of": of,                          # 최근 4주 공고 수
        "low": t["seats_low"] if t["hc_known"] else None,
        "high": t["seats_high"] if t["hc_known"] else None,
        "exact": t["hc_exact"],            # '3명'처럼 숫자로 쓴 공고
        "one_digit": t["hc_one"],          # ○명
        "two_digit": t["hc_two"],          # ○○명 이상
    }


def fast_ratio(closed: int, closed_fast: int) -> float | None:
    return round(closed_fast / closed, 3) if closed >= MIN_N else None


def _sort_key(sort: str):
    if sort == "growth":
        return lambda c: (c["recent"] - c["prev"], c["recent"])
    if sort == "fast":
        return lambda c: (c["fast_close_ratio"] if c["fast_close_ratio"] is not None else -1, c["closed"])
    if sort == "seats":
        return lambda c: (c["seats"]["low"] or 0, c["seats"]["high"] or 0, c["recent"])
    if sort == "active":
        return lambda c: (c["active"], c["recent"])
    return lambda c: (c["recent"], c["recent"] - c["prev"])


def momentum(weeks: int = 12, size: str = "", sort: str = "recent", min_recent: int = 3,
             limit: int = 50) -> dict:
    return cached(("hiring", weeks, size, sort, min_recent, limit),
                  lambda: _momentum(weeks, size, sort, min_recent, limit))


def _momentum(weeks: int, size: str, sort: str, min_recent: int, limit: int) -> dict:
    starts = week_starts(weeks)
    coverage = repository.coverage_start()
    reliable = reliable_weeks(starts, coverage)
    ok = comparable(reliable)
    since = datetime.combine(starts[0], datetime.min.time(), tzinfo=KST)
    companies, weekly, roles, has_hc = repository.window_rows(since, FAST_DAYS)

    idx = {d: i for i, d in enumerate(starts)}
    series: dict[int, list[int]] = defaultdict(lambda: [0] * len(starts))
    hc: dict[int, list[dict]] = defaultdict(lambda: [dict.fromkeys(HC_KEYS, 0) for _ in starts])
    for r in weekly:
        i = idx.get(r["week"])
        if i is not None:
            series[r["company_id"]][i] += r["n"]
            for k in HC_KEYS:
                hc[r["company_id"]][i][k] += int(r[k] or 0)

    top_roles: dict[int, list[dict]] = defaultdict(list)
    for r in sorted(roles, key=lambda r: (-r["n"], r["role"])):
        if len(top_roles[r["company_id"]]) < TOP_ROLES:
            top_roles[r["company_id"]].append({"name": r["role"], "count": r["n"]})

    out = []
    for c in companies:
        if size and c["size"] != size:
            continue
        s = series[c["company_id"]]
        recent, prev = summarize(s)
        if recent < min_recent:
            continue
        mod = c["median_open_days"]
        out.append({
            "company": c["company"],
            "slug": c["slug"],
            "size": c["size"],
            "logo": c["logo_url"],
            "weekly": s,
            "recent": recent,
            "prev": prev,
            "trend": trend_label(recent, prev, ok),
            "seats": recent_seats(hc[c["company_id"]], recent),
            "active": c["active"],
            "total": c["total"],
            "closed": c["closed"],
            "closed_fast": c["closed_fast"],
            "fast_close_ratio": fast_ratio(c["closed"], c["closed_fast"]),
            "median_open_days": round(float(mod), 1) if mod is not None and c["closed"] >= MIN_N else None,
            "roles": top_roles[c["company_id"]],
            "sites": sorted(c["sites"] or []),
        })

    out.sort(key=_sort_key(sort), reverse=True)
    return {
        "weeks": [d.isoformat() for d in starts],
        "reliable": reliable,
        "comparable": ok,
        "coverage_start": coverage.astimezone(KST).date().isoformat() if coverage else None,
        "compare_weeks": COMPARE_WEEKS,
        "fast_days": FAST_DAYS,
        "min_n": MIN_N,
        "headcount": has_hc,
        "total": len(out),
        "companies": out[:limit],
        "notes": [
            "공고 수는 우리가 수집한 보드 기준이다 — 회사 전체 채용량이 아니다.",
            "이번 주는 진행 중이라 최근/이전 비교에서 뺀다.",
            "수집을 시작하기 전 주(reliable=false)는 그때까지 열려 있던 공고만 잡혀 실제보다 적다 — "
            "비교 기간이 거기 걸리면 추세(trend)를 'unknown' 으로 둔다.",
            "자리 수(seats)는 모집인원을 밝힌 공고만 더한 것이다 — ○명은 1~9명, ○○명은 10~99명으로 "
            "'최소~최대'를 낸다. 대부분 잡코리아 공고 페이지의 모집인원 칸에서 온다.",
            f"'빨리 닫힘'은 {FAST_DAYS}일 안에 닫힌 비율이다. 지원 쏠림의 신호일 뿐 증거는 아니다"
            "(공고를 내린 경우도 섞인다).",
        ],
    }
