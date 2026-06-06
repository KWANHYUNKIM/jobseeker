"""사이트별 최신 크롤링 결과를 통합 폴더로 묶는다.

생성 결과:
    screenshots/all_<keyword>_<timestamp>/
        ├── all_jobs.json      # 모든 사이트의 jobs.json을 site 필드로 합친 통합 인덱스
        ├── summary.txt        # 사이트별 수집 건수 요약
        ├── wanted/            # 각 사이트별 txt + jobs.json 사본
        ├── jumpit/
        ├── jobkorea/
        ├── saramin/
        └── dev/

사용법:
    python aggregate.py                 # 키워드 "개발자" (기본)
    python aggregate.py 개발자
    python aggregate.py 백엔드
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SITES = ["wanted", "jumpit", "jobkorea", "saramin", "dev"]


def _norm_key(value: str | None) -> str:
    """중복 판정용 정규화: 양끝 공백 제거 + 내부 공백 제거 + 소문자."""
    return re.sub(r"\s+", "", (value or "").strip().lower())


def latest_run_dir(screens: Path, site: str, keyword: str) -> Path | None:
    # 1순위: 고정 폴더 (타임스탬프 없음, 누적용)
    fixed = screens / f"{site}_{keyword}"
    if fixed.exists() and fixed.is_dir():
        return fixed
    # 2순위: 옛 타임스탬프 폴더 중 가장 최근
    pattern = f"{site}_{keyword}_*"
    matches = sorted(screens.glob(pattern), key=lambda p: p.name, reverse=True)
    return matches[0] if matches else None


def aggregate(keyword: str) -> Path:
    base = Path(__file__).parent
    screens = base / "screenshots"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = screens / f"all_{keyword}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_jobs: list[dict] = []
    site_counts: dict[str, int] = {}
    site_sources: dict[str, str] = {}

    for site in SITES:
        src = latest_run_dir(screens, site, keyword)
        if not src:
            print(f"  [{site}] 최근 결과 없음 — 스킵", flush=True)
            site_counts[site] = 0
            site_sources[site] = "(none)"
            continue

        site_sources[site] = src.name
        site_out = out_dir / site
        site_out.mkdir(exist_ok=True)

        # copy all txt files and jobs.json (if any)
        copied_files = 0
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, site_out / f.name)
                copied_files += 1

        # merge jobs.json
        jobs_file = src / "jobs.json"
        jobs: list[dict] = []
        if jobs_file.exists():
            try:
                jobs = json.loads(jobs_file.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  [{site}] jobs.json 파싱 실패: {e}", flush=True)
                jobs = []

        for j in jobs:
            entry = {"site": site, **j}
            all_jobs.append(entry)

        site_counts[site] = len(jobs)
        print(f"  [{site}] {src.name} → {len(jobs)}건 (파일 {copied_files}개 복사)", flush=True)

    # 교차 사이트 중복 제거: (회사명+제목) 정규화 키로 첫 등장만 유지.
    # SITES 순서(wanted→dev)가 우선순위이므로 앞 사이트 게시물이 보존된다.
    deduped: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    cross_dups = 0
    for j in all_jobs:
        ckey = (_norm_key(j.get("company")), _norm_key(j.get("title")))
        if ckey[0] and ckey[1]:
            if ckey in seen_keys:
                cross_dups += 1
                continue
            seen_keys.add(ckey)
        deduped.append(j)
    if cross_dups:
        print(f"  [dedup] 교차 사이트 중복 {cross_dups}건 제거 → {len(deduped)}건", flush=True)
    all_jobs = deduped

    # 수동 보정(override): overrides.json 의 (site:pid) 항목으로 자동추출 값을 덮어쓴다.
    # 사람이 직접 고친 값이 크롤을 반복해도 유지되도록 별도 파일로 관리한다.
    overrides_path = base / "overrides.json"
    overrides: dict = {}
    if overrides_path.exists():
        try:
            overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [override] overrides.json 파싱 실패: {e}", flush=True)
    if overrides:
        OVR_FIELDS = ("main_tasks", "qualifications", "preferences", "tech_stack")
        applied = 0
        for j in all_jobs:
            ov = overrides.get(f"{j.get('site')}:{j.get('pid')}")
            if not isinstance(ov, dict):
                continue
            changed = [f for f in OVR_FIELDS if ov.get(f) not in (None, "", [])]
            for f in changed:
                j[f] = ov[f]
            if changed:
                j["_overridden"] = changed
                applied += 1
        if applied:
            print(f"  [override] 수동 보정 {applied}건 적용", flush=True)

    # 모집중(active) / 마감(closed) 분리: job_status 의 마감일 파싱 기준
    from job_status import classify_status, today_date
    today = today_date()
    active_jobs: list[dict] = []
    closed_jobs: list[dict] = []
    for j in all_jobs:
        status, reason, dl_iso = classify_status(j, today)
        j["status"] = status
        j["closed_reason"] = reason
        j["deadline_date"] = dl_iso
        (active_jobs if status == "active" else closed_jobs).append(j)
    print(f"  [status] 모집중 {len(active_jobs)}건 / 마감 {len(closed_jobs)}건", flush=True)

    # 누적 마감 아카이브(영구 보관): screenshots/closed_<keyword>.json
    archive_path = screens / f"closed_{keyword}.json"
    archive: list[dict] = []
    if archive_path.exists():
        try:
            archive = json.loads(archive_path.read_text(encoding="utf-8"))
        except Exception:
            archive = []
    arch_keys = {(_norm_key(a.get("company")), _norm_key(a.get("title"))) for a in archive}
    newly_archived = 0
    for j in closed_jobs:
        k = (_norm_key(j.get("company")), _norm_key(j.get("title")))
        if k not in arch_keys:
            arch_keys.add(k)
            archive.append(j)
            newly_archived += 1
    archive_path.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if newly_archived:
        print(f"  [archive] 신규 마감 {newly_archived}건 보관 → {archive_path.name} (누적 {len(archive)}건)", flush=True)

    # 통합 인덱스: all_jobs.json = 모집중(active), all_jobs_closed.json = 마감(이번 회차)
    (out_dir / "all_jobs.json").write_text(
        json.dumps(active_jobs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "all_jobs_closed.json").write_text(
        json.dumps(closed_jobs, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # write summary
    summary_lines = [
        f"통합 키워드: {keyword}",
        f"생성 시각: {ts}",
        f"총 수집 건수: {sum(site_counts.values())}건 (사이트별 원본)",
        f"중복 제거 후: {len(all_jobs)}건 (교차 사이트 중복 {cross_dups}건 제거)",
        f"모집중(active): {len(active_jobs)}건  /  마감(closed): {len(closed_jobs)}건",
        "",
        "[사이트별 수집 결과]",
    ]
    for site in SITES:
        summary_lines.append(
            f"  {site:<10} {site_counts[site]:>3}건   ← {site_sources[site]}"
        )
    summary_lines.append("")
    summary_lines.append("[파일 구조]")
    summary_lines.append("  all_jobs.json  — 모든 사이트의 jobs.json을 site 필드로 합친 통합 인덱스")
    summary_lines.append("  <site>/        — 사이트별 txt + jobs.json 원본")
    (out_dir / "summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")

    print()
    print(f"[완료] 통합 폴더: {out_dir}")
    print(f"  사이트별 원본 {sum(site_counts.values())}건  ({', '.join(f'{s}={n}' for s,n in site_counts.items())})")
    print(f"  중복 제거 후 {len(all_jobs)}건  (교차 사이트 중복 {cross_dups}건 제거)")
    print(f"  모집중 {len(active_jobs)}건 / 마감 {len(closed_jobs)}건  (마감 누적보관: closed_{keyword}.json)")
    return out_dir


def main() -> None:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "개발자"
    aggregate(keyword)


if __name__ == "__main__":
    main()
