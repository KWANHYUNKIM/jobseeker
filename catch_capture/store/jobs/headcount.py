"""모집인원을 본문 문구에서 채운다 — `job.headcount_*`(db/migrations/021).

잡코리아는 공고 페이지의 '모집인원' 칸을 close_check 가 읽어 `source='page'` 로 쓴다. 칸이 없는
사이트(사람인·원티드·회사 채용페이지 …)는 본문의 "모집인원 : ○명" 문구가 유일한 근거라 여기서
`source='text'` 로 채운다. **page 로 채운 값은 건드리지 않는다**(회사가 칸에 직접 고른 값이다).

    python -m store.jobs.headcount             # 비어 있거나 text 인 공고를 다시 읽는다
    python -m store.jobs.headcount --dry-run   # 쓰지 않고 분포만
    python -m store.jobs.headcount --pages 300 # 잡코리아 모집중 공고 중 칸을 아직 안 읽은 것을 페이지로 채운다

`--pages` 는 처음 한 번(021 을 깐 직후) 쓰는 것이다. 그 뒤로는 close_check 가 마감을 물으며 같은
페이지에서 칸을 읽으므로 따로 돌 필요가 없다. 요청 간격·UA 는 close_check 의 것을 그대로 쓴다.
"""
from __future__ import annotations

from collections import Counter

from core.headcount import from_text, parse
from store.db import conn

_SELECT = """
    SELECT id, concat_ws(E'\\n', main_tasks, qualifications, preferences, full_jd) AS text
      FROM job
     WHERE headcount_source IS DISTINCT FROM 'page'
"""

_UPDATE = """
    UPDATE job SET headcount_raw = %s, headcount_n = %s, headcount_digits = %s,
                   headcount_source = CASE WHEN %s::text IS NULL THEN NULL ELSE 'text' END
     WHERE id = %s
       AND headcount_source IS DISTINCT FROM 'page'
       AND (headcount_raw IS DISTINCT FROM %s)
"""


def refresh(*, dry_run: bool = False) -> Counter:
    tally: Counter = Counter()
    with conn.cursor() as cur:
        cur.execute(_SELECT)
        rows = cur.fetchall()
        for r in rows:
            hc = parse(from_text(r["text"]))
            if hc is None:
                tally["밝히지 않음"] += 1
            elif hc.n is not None:
                tally["정확한 수"] += 1
            else:
                tally[f"{hc.digits}자릿수"] += 1
            if not dry_run:
                raw = hc.raw if hc else None
                cur.execute(_UPDATE, (raw, hc.n if hc else None, hc.digits if hc else None,
                                      raw, r["id"], raw))
        if dry_run:
            cur.connection.rollback()
    tally["대상"] = len(rows)
    return tally


_PAGE_TODO = """
    SELECT j.id, j.pid
      FROM job j
      JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
     WHERE j.site = 'jobkorea' AND j.headcount_source IS DISTINCT FROM 'page'
     ORDER BY j.first_seen_at DESC
     LIMIT %s
"""


def fill_pages(limit: int) -> Counter:
    """잡코리아 공고 페이지의 '모집인원' 칸. 칸이 '0명'·없음이어도 읽었다는 표시는 남기지 않는다 —
    다음에 close_check 가 다시 보면 그때 회사가 고친 값이 들어온다."""
    from core.headcount import from_jobkorea_page
    from pipeline.close_check import _fetch, _sleep

    tally: Counter = Counter()
    with conn.cursor(autocommit=True) as cur:
        cur.execute(_PAGE_TODO, (limit,))
        todo = cur.fetchall()
        for i, r in enumerate(todo, 1):
            code, html = _fetch(f"https://www.jobkorea.co.kr/Recruit/GI_Read/{r['pid']}")
            if code != 200:
                tally[f"http {code}"] += 1
                if code in (403, 429):
                    print(f"  [headcount] HTTP {code} — 멈춘다", flush=True)
                    break
            else:
                hc = parse(from_jobkorea_page(html))
                if hc is None:
                    tally["밝히지 않음"] += 1
                else:
                    tally["정확한 수" if hc.n is not None else f"{hc.digits}자릿수"] += 1
                    cur.execute(
                        """UPDATE job SET headcount_raw = %s, headcount_n = %s, headcount_digits = %s,
                                          headcount_source = 'page' WHERE id = %s""",
                        (hc.raw, hc.n, hc.digits, r["id"]))
            if i % 50 == 0:
                print(f"  [headcount] {i}/{len(todo)} " + " · ".join(f"{k} {v}" for k, v in tally.items()),
                      flush=True)
            _sleep()
    tally["대상"] = len(todo)
    return tally


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="본문 문구로 모집인원 채우기")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pages", type=int, default=0, metavar="N",
                    help="잡코리아 모집중 공고 N건을 페이지로 채운다(처음 한 번)")
    args = ap.parse_args()
    t = fill_pages(args.pages) if args.pages else refresh(dry_run=args.dry_run)
    print("[headcount] " + " · ".join(f"{k} {v:,}" for k, v in t.most_common()), flush=True)


if __name__ == "__main__":
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
    main()
