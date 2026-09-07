"""크롤 사이클 → 정본 DB. 이관 2단계(이중 쓰기)의 알맹이.

`pipeline/aggregate.py` 가 사이트별 결과를 합친 **중복 제거 전** 목록을 그대로 받는다.
DB 는 URL 로 공고를 식별하므로 aggregate 의 `(회사명, 제목)` 중복 제거가 필요 없고,
오히려 그 규칙이 같은 회사의 다른 팀 공고를 뭉개던 자리다.

이 단계는 **절대 사이클을 죽이면 안 된다.** 아직 정본은 JSON 이고, DB 가 없거나
꺼져 있다고 크롤 결과를 잃으면 손해가 훨씬 크다. 부르는 쪽이 try/except 로 감싸고
여기서도 사이트별 가드가 실패해도 나머지는 진행한다.

마감일은 **여기서** 계산한다. `D-4` 같은 상대 표기는 크롤 시점을 기준으로 해야
맞는데, 나중에 다시 파싱하면 그만큼 미래로 밀린다(백필에서 899건이 그랬다).
"""
from __future__ import annotations

import json
import os
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from pipeline.job_status import parse_deadline, today_date  # noqa: E402
from store import conn as store_conn  # noqa: E402
from store.upsert import (  # noqa: E402
    content_hash, log_event, parse_career, parse_employment, refresh_display_names,
    set_job_techs, upsert_company, upsert_job,
)

CATCH = _Path(__file__).resolve().parent.parent
OVERRIDES = CATCH / "overrides.json"

SITES = {"wanted", "jumpit", "jobkorea", "saramin", "dev", "remote", "ats"}

# 사이트별 급감 가드. 이번 사이클에 본 건수가 DB 에 살아 있는 건수의 이 비율보다
# 적으면 그 사이트의 gone_at 처리를 **건너뛴다**.
#
# 사라짐과 마감은 다르다. 크롤이 차단당하거나 페이지네이션이 끊기면 멀쩡한 공고가
# 통째로 안 보이는데, 그때 gone_at 을 찍으면 close_check 가 수백 건을 헛되이 재확인하고
# 화면에서도 근거 없이 사라진다. 2026-08-17 에 JSON 쪽에서 10,275건이 25건으로
# 덮인 사고가 정확히 이 모양이었다.
GONE_MIN_RATIO = float(os.environ.get("DB_GONE_MIN_RATIO", "0.5"))

# 수동 보정에서 DB 로 옮기는 필드(overrides.json 의 형식 그대로).
OVR_FIELDS = ("main_tasks", "qualifications", "preferences", "tech_stack")


def _load_overrides() -> dict:
    if not OVERRIDES.exists():
        return {}
    try:
        return json.loads(OVERRIDES.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _deadline(j: dict, today):
    """(마감일, 상시여부). 크롤 시점 기준으로 정해져야 하는 값이다.

    `D-4` 같은 상대 표기는 언제 파싱하느냐로 답이 달라진다. 이 함수는 크롤 사이클
    안에서 불리므로 지금 파싱하는 게 맞지만, 입력이 이미 `deadline_date` 를 들고
    있다면(이미 계산된 스냅샷을 다시 넣는 경우) 그쪽이 더 이른 시점의 답이라 그것을
    쓴다. 다시 파싱하면 끝난 공고가 미래 마감으로 되살아난다.
    """
    iso = (j.get("deadline_date") or "").strip()
    if iso:
        try:
            from datetime import date as _date
            return _date.fromisoformat(iso), False
        except ValueError:
            pass
    return parse_deadline(j, today)


def _usable(j: dict) -> bool:
    """스키마가 거부할 레코드를 미리 걸러 낸다.

    거부 자체는 정상 동작이지만(회사명 없는 공고는 데이터가 아니라 크롤러 버그다),
    한 건이 트랜잭션 전체를 되돌리면 사이클이 통째로 날아간다. 여기서 세고 넘긴다.
    """
    return bool(
        (j.get("company") or "").strip()
        and (j.get("title") or "").strip()
        and str(j.get("pid") or "").strip()
        and str(j.get("url") or "").startswith(("http://", "https://"))
        and j.get("site") in SITES
    )


def record_tech_daily(cur) -> int:
    """오늘의 기술별 모집중 공고 수를 남긴다. `trends_reports/*.md` 가 하던 일이다.

    하루에 한 행이라 같은 날 여러 사이클이 돌면 마지막 값으로 덮인다 — 그게 맞다.
    하루치 추이에 사이클 단위 잡음까지 담을 이유가 없다.
    """
    cur.execute(
        """
        INSERT INTO tech_daily (day, tech_id, n_active)
        SELECT CURRENT_DATE, t.id, count(*)
          FROM job_tech jt
          JOIN tech t ON t.id = jt.tech_id AND NOT t.is_noise
          JOIN job_state s ON s.job_id = jt.job_id AND s.status = 'active'
         GROUP BY t.id
        ON CONFLICT (day, tech_id) DO UPDATE SET n_active = EXCLUDED.n_active
        """
    )
    return cur.rowcount


def ingest(jobs: list[dict], *, label: str, keywords: list[str] | None = None,
           site_counts: dict[str, int] | None = None) -> dict:
    """공고 목록을 정본 DB 에 반영하고 요약을 돌려준다."""
    today = today_date()
    overrides = _load_overrides()
    keywords = keywords or []
    site_counts = site_counts or {}

    usable, skipped = [], 0
    seen_urls: set[str] = set()
    for j in jobs:
        if not _usable(j):
            skipped += 1
            continue
        url = j["url"].strip()
        if url in seen_urls:      # 같은 사이클에 같은 URL 이 두 번 오면 뒤엣것은 버린다
            continue
        seen_urls.add(url)
        usable.append(j)

    stats = {
        "input": len(jobs), "usable": len(usable), "skipped": skipped,
        "new": 0, "reopened": 0, "gone": 0, "techs": 0, "overrides": 0,
        "unchanged": 0,
        "gone_skipped_sites": [],
    }

    with store_conn.connect() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO crawl_run (label, keywords, n_raw) VALUES (%s,%s,%s) RETURNING id",
                (label, keywords, len(jobs)),
            )
            run_id = cur.fetchone()["id"]

            # 이번에 본 URL 들의 현재 상태를 **한 번에** 읽어 둔다. 공고마다 따로
            # 물으면 만 건이면 만 번이다. 여기서 얻는 것은 둘:
            #   gone_at  — 다시 나타난 순간(reopened)을 잡는 유일한 방법. upsert 는
            #              새 행인지만 알려주고 옛 값은 안 알려준다.
            #   content_hash — 본문이 그대로면 기술 연결을 다시 맞출 이유가 없다.
            #              사이클 대부분의 공고가 이 경우다.
            cur.execute(
                "SELECT url, gone_at, content_hash FROM job WHERE url = ANY(%s)",
                (list(seen_urls),),
            )
            known = {r["url"]: r for r in cur.fetchall()}
            was_gone = {u for u, r in known.items() if r["gone_at"] is not None}

            company_ids: dict[str, int] = {}
            tech_cache: dict[str, int | None] = {}
            seen_ids_by_site: dict[str, list[int]] = {}

            for j in usable:
                raw_company = j["company"].strip()
                cid = company_ids.get(raw_company)
                if cid is None:
                    cid = upsert_company(cur, raw_company)
                    if cid is None:
                        stats["skipped"] += 1
                        continue
                    company_ids[raw_company] = cid

                deadline_on, always_open = _deadline(j, today)
                region = j.get("region") if j.get("region") in ("kr", "global") else None
                career_min, accepts_entry = parse_career(j.get("career"))
                chash = content_hash(j)
                prev = known.get(j["url"].strip())
                body_same = prev is not None and prev["content_hash"] == chash

                job_id, inserted = upsert_job(cur, {
                    "site": j["site"], "pid": str(j["pid"]), "url": j["url"].strip(),
                    "company_id": cid, "title": j["title"].strip(),
                    "career_text": j.get("career") or "",
                    "career_min": career_min, "accepts_entry": accepts_entry,
                    "location_text": j.get("location") or "",
                    "sido": None, "sigungu": None, "region": region,
                    "overseas": bool(j.get("overseas")),
                    "employment": parse_employment(j.get("employment")),
                    "education": j.get("education") or None,
                    "source_board": j.get("source_board") or None,
                    "main_tasks": j.get("main_tasks") or "",
                    "qualifications": j.get("qualifications") or "",
                    "preferences": j.get("preferences") or "",
                    "benefits": j.get("benefits") or "",
                    "full_jd": j.get("full_jd") or "",
                    "deadline_text": j.get("deadline") or "",
                    "deadline_on": deadline_on, "always_open": always_open,
                    "dday_text_raw": j.get("dday") or "",
                    "content_hash": chash,
                })
                seen_ids_by_site.setdefault(j["site"], []).append(job_id)
                # 본문 해시가 그대로면 기술 목록도 그대로다(해시 입력에 tech_stack 이
                # 들어 있다). 사이클마다 75,000건을 다시 맞출 이유가 없다.
                if not body_same:
                    stats["techs"] += set_job_techs(
                        cur, job_id, j.get("tech_stack"), cache=tech_cache)
                else:
                    stats["unchanged"] += 1

                if inserted:
                    stats["new"] += 1
                    log_event(cur, job_id, "appeared", run_id=run_id,
                              detail={"site": j["site"]})
                elif j["url"] in was_gone:
                    stats["reopened"] += 1
                    log_event(cur, job_id, "reopened", run_id=run_id)

                ov = overrides.get(f"{j['site']}:{j['pid']}")
                if isinstance(ov, dict):
                    for field in OVR_FIELDS:
                        val = ov.get(field)
                        if val in (None, "", []):
                            continue
                        cur.execute(
                            """INSERT INTO job_override (job_id, field, value, author)
                               VALUES (%s,%s,%s,'overrides.json')
                               ON CONFLICT (job_id, field) DO UPDATE SET value = EXCLUDED.value""",
                            (job_id, field, json.dumps(val, ensure_ascii=False)),
                        )
                        stats["overrides"] += 1

            # ── 사라진 공고 ────────────────────────────────────────────
            for site, ids in seen_ids_by_site.items():
                cur.execute(
                    "SELECT count(*) AS n FROM job WHERE site = %s AND gone_at IS NULL",
                    (site,),
                )
                alive = cur.fetchone()["n"]
                if alive and len(ids) < alive * GONE_MIN_RATIO:
                    stats["gone_skipped_sites"].append(
                        f"{site}({len(ids)}/{alive})"
                    )
                    continue
                cur.execute(
                    "UPDATE job SET gone_at = now() "
                    " WHERE site = %s AND gone_at IS NULL AND NOT (id = ANY(%s)) "
                    " RETURNING id",
                    (site, ids),
                )
                for r in cur.fetchall():
                    stats["gone"] += 1
                    log_event(cur, r["id"], "disappeared", run_id=run_id)

            # 크롤이 아예 안 돈 사이트는 손대지 않는다 — 목록에 없는 것과
            # "0건이 왔다"는 것은 다르다.
            for site, n in site_counts.items():
                if site in SITES:
                    cur.execute(
                        """INSERT INTO crawl_run_site (crawl_run_id, site, n_raw, n_new, ok)
                           VALUES (%s,%s,%s,%s,%s)
                           ON CONFLICT (crawl_run_id, site) DO NOTHING""",
                        (run_id, site, n, len(seen_ids_by_site.get(site, [])), n > 0),
                    )

            renamed = refresh_display_names(cur)
            stats["renamed"] = renamed
            stats["tech_daily"] = record_tech_daily(cur)

            cur.execute(
                """UPDATE crawl_run SET ended_at = now(), ok = true,
                          n_upserted = %s, n_new = %s, detail = %s
                    WHERE id = %s""",
                (len(usable), stats["new"],
                 json.dumps(stats, ensure_ascii=False), run_id),
            )
            stats["run_id"] = run_id
        db.commit()

    return stats


def summary(s: dict) -> str:
    parts = [
        f"공고 {s['usable']:,}건 반영(신규 {s['new']:,}",
        f"재등장 {s['reopened']:,}" if s["reopened"] else "",
        f"사라짐 {s['gone']:,})" if s["gone"] else ")",
    ]
    line = " · ".join(p for p in parts if p).replace(" · )", ")")
    extra = []
    if s["skipped"]:
        extra.append(f"제외 {s['skipped']:,}건(회사명·제목·URL 결측)")
    if s["gone_skipped_sites"]:
        extra.append("급감 가드로 사라짐 처리 보류: " + ", ".join(s["gone_skipped_sites"]))
    if s.get("renamed"):
        extra.append(f"대표표기 재선정 {s['renamed']:,}건")
    return line + ("  — " + " / ".join(extra) if extra else "")


if __name__ == "__main__":
    # 시험용: 기존 enriched JSON 을 한 사이클의 크롤 결과인 셈 치고 넣어 본다.
    import argparse
    ap = argparse.ArgumentParser(description="크롤 결과 → 정본 DB (시험 실행)")
    ap.add_argument("--from-json", default=str(
        CATCH.parent / "jd-viewer" / "public" / "all_jobs_enriched.json"))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--label", default="시험")
    args = ap.parse_args()

    data = json.loads(_Path(args.from_json).read_text(encoding="utf-8"))
    if args.limit:
        data = data[: args.limit]
    counts: dict[str, int] = {}
    for _j in data:
        counts[_j.get("site")] = counts.get(_j.get("site"), 0) + 1
    print(summary(ingest(data, label=args.label, site_counts=counts)))
