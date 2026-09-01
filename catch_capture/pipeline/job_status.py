"""채용공고 마감일(deadline/dday)을 파싱해 모집중(active)/마감(closed)을 판정.

사이트별 마감 표기가 제각각이라 통합 파서로 흡수한다:
  - jobkorea : "06/07(일) 마감"
  - saramin  : "~ 07/04(토)"
  - dev      : deadline "~ 06.28(일) 23시", dday "~06.28(일)"
  - jumpit   : dday "D-4" / "D-DAY"
  - wanted   : 마감일 필드 없음 → 정보없음(active 유지)

판정 규칙(위에서부터 우선):
  - 원본 재확인 원장(job_closures.json)에 답이 있으면 그것 — 사이트에 직접 물어본
    결과라 추측이 끼어들 자리가 없다. `pipeline/close_check` 가 채운다.
  - 상시/수시/채용시/충원시/미정 등 → active (상시채용)
  - 마감일 파싱 성공 & 오늘보다 과거 → closed
  - 그 외(파싱 실패/필드 없음) → active (정보없음)

텍스트만 보던 시절의 한계가 원장을 만든 이유다: wanted 는 마감일 필드 자체가 없어
3천여 건이 영구 '모집중'이었고, 연도 없는 "06/14"는 몇 달만 지나면 어느 해인지로
다시 흔들린다. 원장에는 연도까지 확정된 마감일과 사이트가 직접 말한 마감 여부가 들어온다.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import json
import re
from datetime import date, timedelta

# 원본 재확인 원장 — pipeline/close_check 가 쓰고 여기서 읽는다.
CLOSURES_PATH = _Path(__file__).resolve().parent.parent / "job_closures.json"
_closures_cache: tuple[float, dict] | None = None   # (mtime, 원장)

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


def closure_key(job: dict) -> str:
    """원장 키. 사이트 안에서 pid 가 공고를 특정한다(재공고는 새 pid 로 온다)."""
    site = str(job.get("site") or "").strip()
    pid = str(job.get("pid") or job.get("position_id") or job.get("rec_idx") or "").strip()
    return f"{site}:{pid}" if site and pid else ""


def load_closures(force: bool = False) -> dict:
    """원장 로드. mtime 이 그대로면 캐시를 쓴다 — 만 건짜리 재판정 루프에서 매번
    파일을 다시 읽으면 aggregate/enrich 가 눈에 띄게 느려진다."""
    global _closures_cache
    try:
        mtime = CLOSURES_PATH.stat().st_mtime
    except OSError:
        _closures_cache = None
        return {"checked": {}}
    if not force and _closures_cache is not None and _closures_cache[0] == mtime:
        return _closures_cache[1]
    try:
        data = json.loads(CLOSURES_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("checked"), dict):
            data = {"checked": {}}
    except Exception:   # 깨진 원장 때문에 파이프라인 전체가 멈추면 손해가 더 크다
        data = {"checked": {}}
    _closures_cache = (mtime, data)
    return data


def closure_for(job: dict) -> dict | None:
    key = closure_key(job)
    if not key:
        return None
    entry = load_closures()["checked"].get(key)
    return entry if isinstance(entry, dict) else None


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

    # MM/DD or MM.DD — 연도가 없으므로 어느 해인지 골라야 한다.
    #
    # 예전 규칙은 "60일 이상 과거면 내년으로 간주"였다. 연말(12월)에 본 '01/05'를
    # 내년 1월로 읽으려는 의도였지만, 조건에 연말이라는 단서가 없어서 **모든** 과거
    # 날짜에 걸렸다. 2026-08-19 에 본 '06/07' 은 2026-06-07(73일 전)을 건너뛰고
    # 2027-06-07 을 돌려주었고, 두 달 전에 끝난 공고가 '내년 마감'이라 모집중으로
    # 남았다. 마감 아카이브에는 이미 들어가 있는 공고가 활성 목록에도 계속 남는
    # 이유가 이것이다(같은 URL·같은 마감일로 1,178건).
    #
    # 오늘에서 가장 가까운 후보를 고른다. 연말→연초는 그대로 처리되고(12/28 에 본
    # 01/05 는 내년 쪽이 8일 뒤라 더 가깝다) 몇 달 지난 마감은 과거로 남는다.
    m = MD_RE.search(text)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
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

    # 원본에 직접 물어본 결과가 있으면 그것이 답이다. status "unknown" 은 "물어봤지만
    # 답을 못 얻음"이라 아래 텍스트 규칙으로 넘긴다.
    entry = closure_for(job)
    if entry:
        confirmed = entry.get("deadline") or None
        try:
            dl = date.fromisoformat(confirmed) if confirmed else None
        except ValueError:
            dl = None
        if entry.get("status") == "closed":
            return "closed", entry.get("reason") or "원본 확인: 마감", confirmed
        if entry.get("status") == "active":
            # 확인 시점엔 열려 있었어도 마감일은 그 사이 지날 수 있다(연도까지 확정된
            # 날짜라 여기서는 안심하고 비교할 수 있다).
            if dl and dl < today:
                return "closed", f"원본 확인 마감일 경과({confirmed})", confirmed
            if dl:
                return "active", f"마감 {confirmed}", confirmed
            return "active", entry.get("reason") or "원본 확인: 모집중", None

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

    # 원장 우선 규칙 — 임시 원장 파일을 만들어 실제 로딩 경로 그대로 확인한다.
    global CLOSURES_PATH, _closures_cache
    import tempfile
    saved_path, saved_cache = CLOSURES_PATH, _closures_cache
    tmp = _Path(tempfile.mkdtemp()) / "job_closures.json"
    tmp.write_text(json.dumps({"checked": {
        "wanted:1": {"status": "closed", "reason": "원본 상태 close", "deadline": None},
        "wanted:2": {"status": "active", "reason": "원본 확인: 모집중", "deadline": "2026-09-30"},
        "wanted:3": {"status": "active", "reason": "원본 확인: 모집중", "deadline": "2026-06-30"},
        "wanted:4": {"status": "unknown", "reason": "확인 실패", "deadline": None},
    }}, ensure_ascii=False), encoding="utf-8")
    try:
        CLOSURES_PATH = tmp
        load_closures(force=True)
        ledger_cases = [
            ({"site": "wanted", "pid": "1"}, date(2026, 8, 18), "closed"),   # 사이트가 마감이라 함
            ({"site": "wanted", "pid": "2"}, date(2026, 8, 18), "active"),   # 확정 마감일이 미래
            ({"site": "wanted", "pid": "3"}, date(2026, 8, 18), "closed"),   # 확인 후 마감일이 지남
            ({"site": "wanted", "pid": "4", "deadline": "~ 06/14(일)"},      # 불명 → 텍스트 규칙
             date(2026, 8, 18), "closed"),
        ]
        for job, today, want in ledger_cases:
            got, reason, _iso = classify_status(job, today)
            if got != want:
                failed += 1
                print(f"FAIL(원장) {job} @{today} → {got} (기대 {want}, {reason})")
    finally:
        CLOSURES_PATH, _closures_cache = saved_path, saved_cache
        tmp.unlink(missing_ok=True)
        tmp.parent.rmdir()

    total = len(cases) + 4
    print(f"job_status selftest: {total - failed}/{total} 통과")
    return 1 if failed else 0


if __name__ == "__main__":
    if "--selftest" in _sys.argv:
        raise SystemExit(_selftest())
    raise SystemExit("사용법: python -m pipeline.job_status --selftest")
