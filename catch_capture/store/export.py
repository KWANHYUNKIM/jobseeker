"""정본 DB → 뷰어가 읽는 JSON. `jd-viewer/bin/enrich_jobs.py` 를 대체한다.

이관 3단계. 뷰어는 지금까지처럼 `public/all_jobs_enriched.json` 을 fetch 하고,
필드 이름도 그대로다 — 바뀌는 건 **그 값이 어디서 오는가**뿐이다.

  전:  크롤 스냅샷 → normalize → classify_status(계산해서 파일에 굽기) → JSON
  후:  DB → v_job(읽는 시점에 status·dday 계산) → JSON

그래서 파일이 며칠 묵어도 `status` 가 틀릴 수 없다. 다시 뽑기만 하면 그 시점 기준으로
다시 계산된다. `dday` 는 아예 내보내지 않는다 — 지금까지 크롤 시점 문자열을 실어
보내서 마감일 8/23 인 공고가 며칠 뒤에도 'D-4' 로 보였다. 화면은 `deadline_date` 로
직접 계산해야 한다.

사용:
    python -m store.export                 # public/all_jobs_enriched.json 갱신
    python -m store.export --out - | head  # 표준출력으로
    python -m store.export --check         # 쓰지 않고 기존 파일과 비교만
"""
from __future__ import annotations

import argparse
import json
import os
import sys as _sys
import tempfile
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from store import conn as store_conn  # noqa: E402

ROOT = _Path(__file__).resolve().parent.parent.parent
OUT_DEFAULT = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"

# 급감 가드 — refresh-data.sh 가 심링크에 대해 하던 일을 여기서 한다.
# 2026-08-17 에 10,275건이 25건으로 덮여 쓰인 적이 있다. 원인이 무엇이든 증상은
# 늘 "건수가 확 준다" 이므로, 쓰기 전에 기존 파일과 비교해 급감이면 멈춘다.
MIN_RATIO = float(os.environ.get("EXPORT_MIN_RATIO", "0.5"))


def fetch_jobs() -> list[dict]:
    """v_job 을 뷰어의 Job 형태로. 필드 이름은 types.ts 를 따른다."""
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute(
            """
            SELECT site, pid, company, company_slug, title, url,
                   career_text, location_text, tech_stack,
                   main_tasks, qualifications, preferences, benefits, full_jd,
                   status, status_source, deadline_on, dday, last_verified_at,
                   region, source_board, overseas, deadline_text,
                   employment, education
              FROM v_job
             ORDER BY site, pid
            """
        )
        rows = cur.fetchall()

    out = []
    for i, r in enumerate(rows, start=1):
        job = {
            "site": r["site"],
            "idx": i,
            "pid": r["pid"],
            "company": r["company"],
            "title": r["title"],
            "url": r["url"],
            "career": r["career_text"] or "",
            "location": r["location_text"] or "",
            "tech_stack": list(r["tech_stack"] or []),
            "main_tasks": r["main_tasks"] or "",
            "qualifications": r["qualifications"] or "",
            "preferences": r["preferences"] or "",
            "benefits": r["benefits"] or "",
            "full_jd": r["full_jd"] or "",
            "status": r["status"],
            "deadline_date": r["deadline_on"].isoformat() if r["deadline_on"] else "",
            "deadline": r["deadline_text"] or "",
            # dday 는 저장값이 아니라 **지금 다시 계산한** 값이다. 지금까지는 크롤
            # 시점 문자열('D-4')을 그대로 실어 보내서 하루만 지나도 틀렸다.
            # build_calendar.py 와 build_reposts.py 가 이 필드를 파싱하므로 형식은
            # 유지한다(빈 문자열 = 마감일을 모르거나 이미 지남).
            "dday": _dday_text(r["dday"]),
            # 판정 근거를 함께 내보낸다. 'unknown' 은 "모집중"이 아니라 "마감을 알
            # 방법이 없어 열어둔 것"이다 — 화면이 그 둘을 구분해 보여줄 수 있다.
            "status_source": r["status_source"],
            "closed_reason": _reason(r),
            # 회사 주소 슬러그. 지금까지 화면이 company_stacks 를 뒤져 찾던 값이다.
            "company_slug": r["company_slug"],
        }
        # build_role_insights.py 가 학력 분포를 세어 RoleInsights 화면에 그린다.
        # 고용형태는 ENUM 이 걸러 낸 값만 남는다 — 지금 데이터는 공고 제목이 통째로
        # 들어간 것이 대부분이라 대개 비어 있다(jobkorea txt 파서를 고쳐야 채워진다).
        if r["education"]:
            job["education"] = r["education"]
        if r["employment"]:
            job["employment"] = r["employment"]
        if r["region"]:
            job["region"] = r["region"]
        if r["source_board"]:
            job["source_board"] = r["source_board"]
        if r["overseas"]:
            job["overseas"] = True
        out.append(job)
    return out


def _dday_text(dday: int | None) -> str:
    """남은 일수 → 'D-4' / 'D-DAY'. 모르거나 이미 지났으면 빈 문자열.

    지난 마감을 'D+3' 같은 형태로 내보내지 않는 이유: build_calendar 는 이 문자열을
    미래 날짜로 되돌려 읽으므로, 지난 값을 주면 캘린더에 없는 일정이 생긴다.
    지난 공고는 어차피 status='closed' 라 캘린더가 제외한다.
    """
    if dday is None or dday < 0:
        return ""
    return "D-DAY" if dday == 0 else f"D-{dday}"


def _reason(r: dict) -> str:
    """기존 closed_reason 문구를 최대한 유지한다(화면이 그대로 보여준다)."""
    src, status, dl = r["status_source"], r["status"], r["deadline_on"]
    if src == "override":
        return "수동 보정"
    if src == "always_open":
        return "상시/수시 채용"
    if src == "unknown":
        return "마감일 정보 없음"
    if src == "ledger":
        return f"원본 확인: {'마감' if status == 'closed' else '모집중'}"
    iso = dl.isoformat() if dl else ""
    return f"마감일 경과({iso})" if status == "closed" else f"마감 {iso}"


def write_atomic(path: _Path, payload: str) -> None:
    """같은 디렉터리에 임시파일로 쓰고 os.replace 로 바꿔치기한다.

    지금까지는 99MB 를 write_text() 로 직접 덮어썼다. 도중에 죽으면 반쯤 쓰인
    JSON 이 남고, 뷰어는 그걸 그대로 fetch 한다. replace 는 원자적이라
    독자는 옛 파일 아니면 새 파일만 본다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    except BaseException:
        _Path(tmp).unlink(missing_ok=True)
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description="정본 DB → all_jobs_enriched.json")
    ap.add_argument("--out", default=str(OUT_DEFAULT), help="'-' 면 표준출력")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 기존 파일과 비교")
    ap.add_argument("--force", action="store_true", help="급감 가드를 무시")
    args = ap.parse_args()

    jobs = fetch_jobs()
    n_active = sum(1 for j in jobs if j["status"] == "active")
    print(f"v_job {len(jobs):,}건 (모집중 {n_active:,} / 마감 {len(jobs)-n_active:,})")

    if args.out == "-":
        print(json.dumps(jobs, ensure_ascii=False, indent=2))
        return 0

    out = _Path(args.out)
    old = None
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            old = None

    if old is not None:
        print(f"기존 파일 {len(old):,}건")
        if args.check:
            return _compare(old, jobs)
        ratio = len(jobs) / max(len(old), 1)
        if ratio < MIN_RATIO and not args.force:
            print(f"\n[중단] 건수가 기존의 {ratio:.0%} 로 줄었다 "
                  f"(하한 {MIN_RATIO:.0%}). 파일을 건드리지 않는다.\n"
                  f"       의도한 것이면 --force, 하한 조정은 EXPORT_MIN_RATIO.")
            return 2

    if args.check:
        print("비교 대상 파일이 없다.")
        return 0

    write_atomic(out, json.dumps(jobs, ensure_ascii=False, indent=2))
    print(f"기록: {out} ({out.stat().st_size // (1024*1024)}MB)")
    return 0


def _compare(old: list[dict], new: list[dict]) -> int:
    """기존 JSON 과 DB 산출물의 차이. 2단계(이중 쓰기) 검증에 쓴다."""
    by_url_old = {j.get("url"): j for j in old}
    by_url_new = {j.get("url"): j for j in new}
    only_old = set(by_url_old) - set(by_url_new)
    only_new = set(by_url_new) - set(by_url_old)
    print(f"\n기존에만 있는 공고 {len(only_old):,}건 / DB 에만 있는 공고 {len(only_new):,}건")

    from collections import Counter
    flips = Counter()
    for url in set(by_url_old) & set(by_url_new):
        o, n = by_url_old[url], by_url_new[url]
        if o.get("status") != n.get("status"):
            flips[f"{o.get('status')} → {n.get('status')} ({n.get('status_source')})"] += 1
    print("\n[status 가 달라진 공고]")
    for k, v in flips.most_common():
        print(f"  {k:<40} {v:>7,}")
    if not flips:
        print("  없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
