"""채용공고 마감일(deadline/dday)을 파싱해 모집중(active)/마감(closed)을 판정.

사이트별 마감 표기가 제각각이라 통합 파서로 흡수한다:
  - jobkorea : "06/07(일) 마감"
  - saramin  : "~ 07/04(토)"
  - dev      : deadline "~ 06.28(일) 23시", dday "~06.28(일)"
  - jumpit   : dday "D-4" / "D-DAY"
  - wanted   : 마감일 필드 없음 → 정보없음(active 유지)

판정 규칙:
  - 상시/수시/채용시/충원시/미정 등 → active (상시채용)
  - 마감일 파싱 성공 & 오늘보다 과거 → closed
  - 그 외(파싱 실패/필드 없음) → active (정보없음)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import re
from datetime import date, timedelta

# 상시채용/마감일 미정 계열 → 항상 모집중으로 간주
ALWAYS_OPEN_RE = re.compile(
    r"상시|수시|채용\s*시|충원\s*시|채용시\s*마감|마감일\s*미정|미정|연중|정시채용"
)
DDAY_RE = re.compile(r"D-\s*(\d+)", re.IGNORECASE)
DDAY_TODAY_RE = re.compile(r"D-?\s*(?:DAY|day|0)\b")
# MM/DD 또는 MM.DD (연도 없음)
MD_RE = re.compile(r"(\d{1,2})\s*[./]\s*(\d{1,2})")


def today_date() -> date:
    return date.today()


def _collect_text(job: dict) -> str:
    parts = []
    for k in ("deadline", "dday"):
        v = job.get(k)
        if v:
            parts.append(str(v))
    return " ".join(parts).strip()


def parse_deadline(job: dict, today: date | None = None) -> tuple[date | None, bool]:
    """(마감일, 상시채용여부) 반환. 마감일을 못 구하면 (None, 상시여부)."""
    today = today or today_date()
    text = _collect_text(job)
    if not text:
        return None, False
    if ALWAYS_OPEN_RE.search(text):
        return None, True

    # D-DAY / D-0 → 오늘 마감
    if DDAY_TODAY_RE.search(text):
        return today, False
    m = DDAY_RE.search(text)
    if m:
        return today + timedelta(days=int(m.group(1))), False

    # MM/DD or MM.DD
    m = MD_RE.search(text)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            # 연도가 없으므로 작년/올해/내년 후보 중 오늘에 가장 가까운 것을 고른다.
            # "60일 이상 과거면 내년"으로 밀던 이전 규칙은 연말 롤오버를 잡으려다
            # 두 달 지난 마감(예: 8월에 보는 "~ 06/14")을 내년 6월로 해석해
            # 마감 공고를 영원히 모집중으로 남겼다. 12/28 을 1월에 보면 작년이,
            # 01/05 를 12월에 보면 내년이 가장 가깝다 — 롤오버는 그대로 잡힌다.
            cands = []
            for year in (today.year - 1, today.year, today.year + 1):
                try:
                    cands.append(date(year, mm, dd))
                except ValueError:  # 2/29 같은 날짜는 해당 연도에 없을 수 있다
                    continue
            if cands:
                return min(cands, key=lambda c: abs((c - today).days)), False
            return None, False
    return None, False


def classify_status(job: dict, today: date | None = None) -> tuple[str, str, str | None]:
    """(status, reason, deadline_iso) 반환. status는 'active' | 'closed'."""
    today = today or today_date()
    deadline, always_open = parse_deadline(job, today)
    if always_open:
        return "active", "상시/수시 채용", None
    if deadline is None:
        return "active", "마감일 정보 없음", None
    iso = deadline.isoformat()
    if deadline < today:
        return "closed", f"마감일 경과({iso})", iso
    return "active", f"마감 {iso}", iso


def _selftest() -> int:
    """`python -m pipeline.job_status --selftest` — 연도 없는 마감 표기 회귀 방지.

    이 파서는 사이트마다 표기가 다르고 연도가 없어서 조용히 틀리기 쉽다.
    실제로 "8월에 본 06/14"를 내년으로 밀어 마감 공고가 전부 모집중으로 남은 적이 있다.
    """
    cases = [
        ({"deadline": "~ 06/14(일)"}, date(2026, 8, 18), "closed"),   # 두 달 지난 마감
        ({"deadline": "~ 08/31(월)"}, date(2026, 8, 18), "active"),   # 앞으로 올 마감
        ({"deadline": "~ 01/05(월)"}, date(2026, 12, 20), "active"),  # 연말→연초 롤오버
        ({"deadline": "12/28(일) 마감"}, date(2027, 1, 5), "closed"),  # 연초에 보는 작년 마감
        ({"deadline": "상시채용"}, date(2026, 8, 18), "active"),
        ({"dday": "D-4"}, date(2026, 8, 18), "active"),
        ({"dday": "D-DAY"}, date(2026, 8, 18), "active"),             # 오늘 마감은 아직 모집중
        ({}, date(2026, 8, 18), "active"),                            # 마감일 정보 없음
    ]
    failed = 0
    for job, today, want in cases:
        got, reason, _iso = classify_status(job, today)
        if got != want:
            failed += 1
            print(f"FAIL {job} @{today} → {got} (기대 {want}, {reason})")
    print(f"job_status selftest: {len(cases) - failed}/{len(cases)} 통과")
    return 1 if failed else 0


if __name__ == "__main__":
    if "--selftest" in _sys.argv:
        raise SystemExit(_selftest())
    raise SystemExit("사용법: python -m pipeline.job_status --selftest")
