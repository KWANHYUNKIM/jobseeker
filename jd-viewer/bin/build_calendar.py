#!/usr/bin/env python3
"""채용 모집 캘린더 데이터 빌더.

all_jobs_enriched.json 의 JD 본문(full_jd)에서 '접수기간/모집기간/마감일' 텍스트를 파싱해
각 공고의 모집 시작일·마감일·상시채용 여부를 뽑아 public/job_calendar.json 으로 낸다.
뷰어의 모집 캘린더 탭이 이 데이터를 소비해 '언제부터 언제까지 모집'을 한눈에 보여준다.

한국 공고는 상시/수시채용이 많아 마감일이 없는 경우가 흔하다 — 그런 공고는 always_open
으로 분류하고, 날짜를 못 찾으면 no_info 로 둔다. 사이트별 마감 표기가 제각각이라
통합 정규식으로 흡수한다(완벽하진 않으나 한눈 파악엔 충분).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from jobs_filter import active_only  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public" / "all_jobs_enriched.json"
OUT = ROOT / "public" / "job_calendar.json"

THIS_YEAR = date.today().year

# ── 원본 마감 표기(deadline/dday) 파서 ─────────────────────────────────
# 사이트별 형식 흡수: saramin "~07/04(토)", jumpit "D-4"/"D-day", dev "~06.28(일) 23시",
# jobkorea "07/06(월) 마감". pipeline/job_status.parse_deadline 로직과 동일.
ALWAYS_OPEN_RE = re.compile(r"상시|수시|채용\s*시|충원\s*시|채용시\s*마감|마감일\s*미정|미정|연중|정시채용")
DDAY_RE = re.compile(r"D-\s*(\d+)", re.IGNORECASE)
DDAY_TODAY_RE = re.compile(r"D-?\s*(?:DAY|day|0)\b")
MD_RE = re.compile(r"(\d{1,2})\s*[./]\s*(\d{1,2})")


def parse_field_deadline(deadline: str, dday: str, today: date) -> tuple[str | None, bool]:
    """원본 deadline/dday 문자열 → (마감일 ISO|None, 상시여부)."""
    text = " ".join(str(x) for x in (deadline, dday) if x).strip()
    if not text:
        return None, False
    if ALWAYS_OPEN_RE.search(text):
        return None, True
    if DDAY_TODAY_RE.search(text):
        return today.isoformat(), False
    m = DDAY_RE.search(text)
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat(), False
    m = MD_RE.search(text)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            for year in (today.year, today.year + 1, today.year - 1):
                try:
                    cand = date(year, mm, dd)
                except ValueError:
                    continue
                if cand < today - timedelta(days=60):
                    continue
                return cand.isoformat(), False
            try:
                return date(today.year, mm, dd).isoformat(), False
            except ValueError:
                return None, False
    return None, False

# 상시/수시/채용시 마감 등 → 마감일 없음(always_open)
ALWAYS_RE = re.compile(r"상시\s*채용|수시\s*채용|채용\s*시\s*마감|충원\s*시|마감일\s*미정|연중\s*수시|정시\s*채용|채용시")

# 접수/모집 기간 라인
PERIOD_RE = re.compile(r"(?:접수|모집|지원)\s*기간\s*[:：]?\s*(.+)")
# 마감 표기
DEADLINE_RE = re.compile(r"(?:마감일|마감)\s*[:：]?\s*([0-9]{4}[.\-/][0-9]{1,2}[.\-/][0-9]{1,2}|[0-9]{1,2}[.\-/][0-9]{1,2})")


def _to_iso(token: str) -> str | None:
    """'2026-06-30' / '2026.6.30' / '06/30' / '6.30' → ISO. 실패 시 None."""
    token = token.strip()
    m = re.match(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", token)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r"^(\d{1,2})[.\-/](\d{1,2})", token)
        if not m:
            return None
        mo, d = map(int, m.groups())
        y = THIS_YEAR
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_dates(full_jd: str) -> tuple[str | None, str | None, bool]:
    """(start_iso, deadline_iso, always_open) 반환."""
    if not full_jd:
        return None, None, False
    start = deadline = None
    always = False

    m = PERIOD_RE.search(full_jd)
    if m:
        seg = m.group(1)[:80]
        # "<start> ~ <end>" 형태
        parts = re.split(r"~|∼|〜|–|—", seg, maxsplit=1)
        start = _to_iso(parts[0])
        if len(parts) > 1:
            tail = parts[1]
            if ALWAYS_RE.search(tail) or "채용" in tail and "마감" in tail:
                always = True
            else:
                deadline = _to_iso(tail.strip())
        else:
            # 끝 표기 없음 → 본문 다른 곳의 상시 여부로 판단
            pass

    if deadline is None:
        dm = DEADLINE_RE.search(full_jd)
        if dm:
            deadline = _to_iso(dm.group(1))

    if deadline is None and not start and ALWAYS_RE.search(full_jd):
        always = True
    if deadline is None and ALWAYS_RE.search(full_jd):
        always = True

    return start, deadline, always


def main() -> None:
    # 마감 공고는 뺀다. all_jobs_enriched.json 은 이제 모집중과 마감을 함께 담는데
    # (색인·과거 조회를 살리려고) 이 빌더의 결과는 "지금 시장"이라 만료 공고를 세면
    # 수요가 과거에 눌린다.
    jobs = active_only(json.loads(SRC.read_text(encoding="utf-8")))
    today = date.today()
    items = []
    dated = always_open = no_info = 0
    src_field = 0
    for j in jobs:
        # ① 원본 마감 표기(구조화, 더 정확) 우선 → ② JD 본문 접수기간 보강
        f_deadline, f_always = parse_field_deadline(
            j.get("deadline", "") or "", j.get("dday", "") or "", today)
        start, jd_deadline, jd_always = parse_dates(j.get("full_jd", "") or "")
        deadline = f_deadline or jd_deadline
        always = (f_always or jd_always) and not deadline
        if f_deadline:
            src_field += 1
        if deadline:
            dated += 1
        elif always:
            always_open += 1
        else:
            no_info += 1
        if deadline or start or always:
            items.append({
                "company": j.get("company", ""),
                "title": j.get("title", ""),
                "url": j.get("url", ""),
                "site": j.get("site", ""),
                "career": j.get("career", ""),
                "tech_stack": j.get("tech_stack", [])[:8],
                "start": start,
                "deadline": deadline,
                "always_open": always,
            })

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(jobs),
        "dated": dated,
        "always_open": always_open,
        "no_info": no_info,
        "items": items,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"[calendar] 총 {len(jobs)}건 → 마감일 {dated}(원본필드 {src_field}) · 상시 {always_open} · 정보없음 {no_info}")
    print(f"           items {len(items)}건 저장 → {OUT}")


if __name__ == "__main__":
    main()
