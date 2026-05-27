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
import shutil
import sys
from datetime import datetime
from pathlib import Path

SITES = ["wanted", "jumpit", "jobkorea", "saramin", "dev"]


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

    # write merged index
    (out_dir / "all_jobs.json").write_text(
        json.dumps(all_jobs, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # write summary
    summary_lines = [
        f"통합 키워드: {keyword}",
        f"생성 시각: {ts}",
        f"총 수집 건수: {sum(site_counts.values())}건",
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
    print(f"  총 {sum(site_counts.values())}건  ({', '.join(f'{s}={n}' for s,n in site_counts.items())})")
    return out_dir


def main() -> None:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "개발자"
    aggregate(keyword)


if __name__ == "__main__":
    main()
