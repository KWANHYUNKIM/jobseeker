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

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

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


def aggregate(keyword: str, keywords: list[str] | None = None,
              label: str | None = None) -> Path:
    """단일/멀티 키워드 통합.

    keywords 가 주어지면 여러 키워드의 사이트 폴더를 한 통합 폴더로 병합한다
    (교차 사이트 + 교차 키워드 중복을 회사명+제목 기준으로 제거).
    label 은 출력 폴더/아카이브/헬스 기록에 쓰는 이름(미지정 시 keyword).
    """
    base = Path(__file__).resolve().parent.parent
    screens = base / "screenshots"
    kws = [k for k in (keywords or [keyword]) if k]
    out_label = label or keyword
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = screens / f"all_{out_label}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_jobs: list[dict] = []
    site_counts: dict[str, int] = {}
    site_sources: dict[str, str] = {}

    for site in SITES:
        srcs: list[str] = []
        site_jobs: list[dict] = []
        site_out = out_dir / site
        copied_files = 0
        for kw in kws:
            src = latest_run_dir(screens, site, kw)
            if not src:
                continue
            srcs.append(src.name)
            site_out.mkdir(exist_ok=True)

            # copy all txt files and jobs.json (if any)
            for f in src.iterdir():
                if f.is_file():
                    shutil.copy2(f, site_out / f.name)
                    copied_files += 1

            # merge jobs.json
            jobs_file = src / "jobs.json"
            if jobs_file.exists():
                try:
                    jobs = json.loads(jobs_file.read_text(encoding="utf-8"))
                except Exception as e:
                    print(f"  [{site}] {kw} jobs.json 파싱 실패: {e}", flush=True)
                    jobs = []
                for j in jobs:
                    all_jobs.append({"site": site, **j})
                    site_jobs.append(j)

        if not srcs:
            print(f"  [{site}] 최근 결과 없음 — 스킵", flush=True)
            site_counts[site] = 0
            site_sources[site] = "(none)"
            continue

        site_counts[site] = len(site_jobs)
        site_sources[site] = ", ".join(dict.fromkeys(srcs))
        kw_note = f"{len(srcs)}개 키워드" if len(srcs) > 1 else srcs[0]
        print(f"  [{site}] {kw_note} → {len(site_jobs)}건 (파일 {copied_files}개 복사)", flush=True)

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
    from pipeline.job_status import classify_status, today_date
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

    # 누적 마감 아카이브(영구 보관): screenshots/closed_<label>.json
    archive_path = screens / f"closed_{out_label}.json"
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
        f"통합 키워드: {', '.join(kws)}",
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
    print(f"  모집중 {len(active_jobs)}건 / 마감 {len(closed_jobs)}건  (마감 누적보관: closed_{out_label}.json)")

    # 헬스 기록 + 이상 탐지: history.jsonl 누적, latest.json, 이상시 경고
    try:
        from monitoring.health import record as _health_record
        _, _anom = _health_record(out_label, site_counts, all_jobs, active_jobs, closed_jobs, cross_dups)
        if _anom:
            print(f"  [health] \u26a0\ufe0f 이상 {len(_anom)}건:", flush=True)
            for a in _anom:
                print(f"    - {a}", flush=True)
        else:
            print("  [health] 이상 없음 — 기록 저장", flush=True)
    except Exception as e:
        print(f"  [health] 기록 실패: {e}", flush=True)

    # 트렌드 일일 스냅샷(하루 1회) + 마크다운 리포트
    try:
        from pipeline.trends import record as _trends_record
        _snap = _trends_record(out_label, active_jobs)
        if _snap is not None:
            print(f"  [trends] 일일 스냅샷 기록 → trends_reports/trends_{out_label}_{_snap['date']}.md", flush=True)
        else:
            print("  [trends] 오늘 이미 기록됨 — skip", flush=True)
    except Exception as e:
        print(f"  [trends] 기록 실패: {e}", flush=True)

    return out_dir


def main() -> None:
    # 사용: aggregate.py 개발자
    #       aggregate.py "개발자,백엔드,프론트엔드" [라벨]
    raw = sys.argv[1] if len(sys.argv) > 1 else "개발자"
    kws = [k.strip() for k in raw.split(",") if k.strip()]
    label = sys.argv[2] if len(sys.argv) > 2 else ("통합" if len(kws) > 1 else kws[0])
    aggregate(kws[0], keywords=kws, label=label)


if __name__ == "__main__":
    main()
