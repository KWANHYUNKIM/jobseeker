"""이관 1단계 — 기존 JSON 을 정본 DB 로 옮긴다.

읽는 것:
    jd-viewer/public/all_jobs_enriched.json   공고 본체
    catch_capture/job_closures.json           마감 재확인 원장(있으면)
    catch_capture/overrides.json              수동 보정(있으면)

**기존 파이프라인은 건드리지 않는다.** JSON 은 그대로 살아 있고, 이 스크립트는
읽기만 한다. 목적은 "새 스키마에 넣으면 실제로 몇 개가 합쳐지고 몇 개가 걸리는가"를
숫자로 보는 것이다.

사용:
    python -m store.backfill --dry-run     # 넣지 않고 집계만
    python -m store.backfill               # 실제 적재(한 트랜잭션)
    python -m store.backfill --truncate    # 기존 내용을 지우고 다시

마감일은 pipeline.job_status 의 파서를 그대로 쓴다. 규칙을 여기서 다시 쓰면
두 벌이 되고, 그게 지금 정합성이 깨진 이유였다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys as _sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from pipeline.job_status import parse_deadline  # noqa: E402
from store import conn as store_conn  # noqa: E402
from store.slug import build_company_slugs, norm_company  # noqa: E402
from store.upsert import (  # noqa: E402
    content_hash, refresh_display_names, set_job_techs, upsert_company, upsert_job,
)

ROOT = _Path(__file__).resolve().parent.parent.parent
CATCH = ROOT / "catch_capture"
ENRICHED = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
CLOSURES = CATCH / "job_closures.json"
OVERRIDES = CATCH / "overrides.json"

SITES = {"wanted", "jumpit", "jobkorea", "saramin", "dev", "remote", "ats"}

# '경력3년↑' / '경력 3년 이상' → 3
_YEARS = re.compile(r"(\d+)\s*년")
_ENTRY = re.compile(r"신입|경력무관|무관")

_EMPLOYMENT = {
    "정규직": "정규직", "계약직": "계약직", "인턴": "인턴",
    "프리랜서": "프리랜서", "파견": "파견", "파견직": "파견",
}


def parse_career(text: str) -> tuple[int | None, bool | None]:
    """'경력3년↑' → (3, False) / '신입·경력' → (0, True) / 빈 값 → (None, None)"""
    t = (text or "").strip()
    if not t:
        return None, None
    m = _YEARS.search(t)
    years = int(m.group(1)) if m else None
    entry = bool(_ENTRY.search(t))
    if entry and years is None:
        years = 0
    return years, entry


def parse_employment(text: str) -> str | None:
    """지금 데이터의 employment 는 파싱이 깨져 있다 — 값에 공고 제목이 통째로
    들어간 것이 대부분이다. 아는 낱말만 받아들이고 나머지는 버린다(스키마의
    ENUM 이 어차피 거부한다). jobkorea txt 파서를 고치면 다시 채워진다."""
    t = (text or "").strip()
    if not t or len(t) > 12:
        return None
    for key, val in _EMPLOYMENT.items():
        if t == key:
            return val
    return None


def load_closures() -> dict:
    if not CLOSURES.exists():
        return {}
    try:
        data = json.loads(CLOSURES.read_text(encoding="utf-8"))
        return data.get("checked", {}) if isinstance(data, dict) else {}
    except Exception as e:
        print(f"  [경고] 원장 파싱 실패 — 건너뜀: {e}")
        return {}


def load_overrides() -> dict:
    if not OVERRIDES.exists():
        return {}
    try:
        return json.loads(OVERRIDES.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [경고] overrides 파싱 실패 — 건너뜀: {e}")
        return {}


def analyze(jobs: list[dict]) -> dict:
    """넣기 전에 무슨 일이 일어날지 센다."""
    stats = Counter()
    by_url: dict[str, dict] = {}
    norm_groups: dict[str, set[str]] = defaultdict(set)

    for j in jobs:
        raw_company = (j.get("company") or "").strip()
        norm = norm_company(raw_company)
        if not norm:
            stats["회사명 없음(제외)"] += 1
            continue
        if not (j.get("title") or "").strip():
            stats["제목 없음(제외)"] += 1
            continue
        url = (j.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            stats["URL 없음/이상(제외)"] += 1
            continue
        if (j.get("site") or "") not in SITES:
            stats["알 수 없는 site(제외)"] += 1
            continue
        if not str(j.get("pid") or "").strip():
            stats["pid 없음(제외)"] += 1
            continue

        norm_groups[norm].add(raw_company)
        if url in by_url:
            stats["URL 중복(병합)"] += 1
            continue
        by_url[url] = j

    # (site,pid) 중복은 URL 이 달라 위에서 안 걸린다. 스키마는 이것도 막으므로 미리 센다.
    seen_sp: dict[tuple, str] = {}
    for url, j in list(by_url.items()):
        key = (j.get("site"), str(j.get("pid")))
        if key in seen_sp:
            stats["(site,pid) 중복(병합)"] += 1
            del by_url[url]
        else:
            seen_sp[key] = url

    stats["적재 대상"] = len(by_url)
    stats["회사(정규화 후)"] = len(norm_groups)
    stats["회사 표기(원본)"] = sum(len(v) for v in norm_groups.values())
    stats["표기가 갈렸던 회사"] = sum(1 for v in norm_groups.values() if len(v) > 1)
    return {"stats": stats, "by_url": by_url, "norm_groups": norm_groups}


def main() -> int:
    ap = argparse.ArgumentParser(description="JSON → 정본 DB 백필")
    ap.add_argument("--dry-run", action="store_true", help="넣지 않고 집계만")
    ap.add_argument("--truncate", action="store_true", help="기존 내용을 비우고 적재")
    ap.add_argument("--limit", type=int, help="앞에서 N건만 (시험용)")
    args = ap.parse_args()

    if not ENRICHED.exists():
        print(f"입력이 없다: {ENRICHED}")
        return 1

    print(f"읽는 중: {ENRICHED.name} ({ENRICHED.stat().st_size // (1024*1024)}MB)")
    jobs = json.loads(ENRICHED.read_text(encoding="utf-8"))
    if args.limit:
        jobs = jobs[: args.limit]
    print(f"  공고 {len(jobs):,}건")

    a = analyze(jobs)
    print("\n[적재 전 집계]")
    for k, v in a["stats"].most_common():
        print(f"  {k:<24} {v:>7,}")

    merged = [(n, s) for n, s in a["norm_groups"].items() if len(s) > 1]
    if merged:
        print("\n[표기가 갈렸다가 합쳐지는 회사 상위 10]")
        for norm, raws in sorted(merged, key=lambda x: -len(x[1]))[:10]:
            print(f"  {norm:<20} ← {sorted(raws)}")

    if args.dry_run:
        print("\n--dry-run 이므로 여기서 멈춘다.")
        return 0

    closures = load_closures()
    overrides = load_overrides()
    print(f"\n원장 {len(closures):,}건 · 수동보정 {len(overrides):,}건")

    # 슬러그는 전체 회사 목록을 놓고 한 번에 배정한다 — 데이터 순서에 따라
    # 누가 -2 를 받는지 흔들리면 배포마다 주소가 바뀐다.
    slug_by_norm = build_company_slugs(a["norm_groups"].keys())

    n_job = n_new = n_tech = n_closure = n_override = 0
    company_ids: dict[str, int] = {}

    # 기술 표기가 겹칠 때(`JIRA`/`Jira`, `Vue.js`/`VueJS`) 먼저 들어온 쪽이 대표
    # 이름이 된다. 그래서 **자주 쓰이는 표기부터** 넣는다 — 아니면 오타 한 건이
    # 정본 이름을 차지한다.
    tech_freq = Counter(
        t for j in a["by_url"].values() for t in (j.get("tech_stack") or [])
    )

    with store_conn.connect() as db:
        with db.cursor() as cur:
            if args.truncate:
                cur.execute(
                    "TRUNCATE company, tech, job, crawl_run, post, study_article, "
                    "tech_daily RESTART IDENTITY CASCADE"
                )
                print("  기존 내용 비움")

            from store.upsert import upsert_tech
            for name, _cnt in tech_freq.most_common():
                upsert_tech(cur, name)
            cur.execute("SELECT count(*) AS n FROM tech")
            print(f"  기술 사전 {cur.fetchone()['n']:,}종 (빈도순 등록)")

            for url, j in a["by_url"].items():
                raw_company = (j.get("company") or "").strip()
                norm = norm_company(raw_company)
                cid = company_ids.get(norm)
                if cid is None:
                    cid = upsert_company(cur, raw_company, slug_hint=slug_by_norm.get(norm))
                    company_ids[norm] = cid
                else:
                    # 같은 회사의 다른 표기도 alias 로 남긴다
                    upsert_company(cur, raw_company, slug_hint=slug_by_norm.get(norm))

                # 마감일은 **크롤 시점 기준**으로 정해져야 한다. 'D-4' 같은 상대
                # 표기를 백필하는 오늘 다시 파싱하면 8/19 에 본 D-4 가 9/11 이 돼
                # 이미 끝난 공고가 미래 마감으로 되살아난다(실측 899건). 스냅샷이
                # 이미 계산해 둔 deadline_date 가 있으면 그것을 쓴다.
                iso = (j.get("deadline_date") or "").strip()
                if iso:
                    try:
                        deadline_on = datetime.fromisoformat(iso).date()
                        always_open = False
                    except ValueError:
                        deadline_on, always_open = parse_deadline(j)
                else:
                    deadline_on, always_open = parse_deadline(j)
                years, entry = parse_career(j.get("career"))
                region = j.get("region") or None
                if region not in (None, "kr", "global"):
                    region = None

                job_id, inserted = upsert_job(cur, {
                    "site": j.get("site"),
                    "pid": str(j.get("pid")),
                    "url": url,
                    "company_id": cid,
                    "title": (j.get("title") or "").strip(),
                    "career_text": j.get("career") or "",
                    "career_min": years,
                    "accepts_entry": entry,
                    "location_text": j.get("location") or "",
                    "sido": None,          # backfill_location 이 채우던 자리 — 2단계에서
                    "sigungu": None,
                    "region": region,
                    "overseas": bool(j.get("overseas")),
                    "employment": parse_employment(j.get("employment")),
                    "education": (j.get("education") or None),
                    "source_board": j.get("source_board") or None,
                    "main_tasks": j.get("main_tasks") or "",
                    "qualifications": j.get("qualifications") or "",
                    "preferences": j.get("preferences") or "",
                    "benefits": j.get("benefits") or "",
                    "full_jd": j.get("full_jd") or "",
                    "deadline_text": j.get("deadline") or "",
                    "deadline_on": deadline_on,
                    "always_open": always_open,
                    "dday_text_raw": j.get("dday") or "",
                    "content_hash": content_hash(j),
                })
                n_job += 1
                n_new += 1 if inserted else 0
                n_tech += set_job_techs(cur, job_id, j.get("tech_stack"))

                # 원장: site:pid 로 걸려 있던 것을 job_id 로 옮긴다
                entry_c = closures.get(f"{j.get('site')}:{j.get('pid')}")
                if isinstance(entry_c, dict) and entry_c.get("status") in ("active", "closed"):
                    dl = entry_c.get("deadline")
                    try:
                        dl_date = datetime.fromisoformat(dl).date() if dl else None
                    except (ValueError, TypeError):
                        dl_date = None
                    cur.execute(
                        """INSERT INTO job_closure_check
                               (job_id, closed, deadline_on, evidence, checker)
                           VALUES (%s,%s,%s,%s,'backfill')""",
                        (job_id, entry_c["status"] == "closed", dl_date,
                         entry_c.get("reason")),
                    )
                    n_closure += 1

                # 수동 보정: 필드 단위로 쪼갠다
                ov = overrides.get(f"{j.get('site')}:{j.get('pid')}")
                if isinstance(ov, dict):
                    for field in ("main_tasks", "qualifications", "preferences", "tech_stack"):
                        val = ov.get(field)
                        if val in (None, "", []):
                            continue
                        cur.execute(
                            """INSERT INTO job_override (job_id, field, value, author)
                               VALUES (%s,%s,%s,'backfill')
                               ON CONFLICT (job_id, field) DO NOTHING""",
                            (job_id, field, json.dumps(val, ensure_ascii=False)),
                        )
                        n_override += 1

                if n_job % 2000 == 0:
                    print(f"  … {n_job:,}건")

            renamed = refresh_display_names(cur)
            cur.execute("REFRESH MATERIALIZED VIEW mv_company_stack")

        db.commit()

    print("\n[적재 완료]")
    print(f"  공고 {n_job:,}건 (신규 {n_new:,})")
    print(f"  회사 {len(company_ids):,}곳 · 대표표기 재선정 {renamed:,}건")
    print(f"  기술 연결 {n_tech:,}건 · 원장 {n_closure:,}건 · 수동보정 {n_override:,}건")

    # 넣고 나서 실제로 무엇이 달라졌는지 — 여기가 이 스크립트의 핵심 산출물이다.
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute("""
            SELECT status, status_source, count(*) AS n
              FROM job_state GROUP BY 1,2 ORDER BY 1,3 DESC
        """)
        print("\n[status × 근거]  ※ 저장값이 아니라 지금 계산한 값이다")
        for r in cur.fetchall():
            print(f"  {r['status']:<7} {r['status_source']:<12} {r['n']:>7,}")
        cur.execute("SELECT count(*) AS n FROM company")
        n_co = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM company_alias")
        n_al = cur.fetchone()["n"]
        print(f"\n  회사 {n_co:,}곳 / 표기 {n_al:,}개 "
              f"(표기 {n_al - n_co:,}개가 기존 회사로 흡수됐다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
