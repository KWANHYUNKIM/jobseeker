"""빈 주요업무·자격요건·우대사항을 본문(full_jd)에서 다시 나눠 정본 DB 에 채운다.

공고 상세에 "이 공고는 해당 정보가 비어있습니다" 가 뜨던 공고 대부분은 본문은 받아 놓고 칸을
못 나눈 것이었다 — 머리말을 말로 쓴 공고("이런 업무를 해요", "# 이런 분과 함께하고 싶어요",
"You will:", "Bonus Points")를 옛 규칙(정확한 낱말만)이 못 알아봤다. 규칙은
crawlers/jobs_common.py 의 split_jd_sections 가 원본이고, 크롤 회차의 aggregate 도 같은 일을 한다.
이 모듈은 다음 회차를 기다리지 않고 지금 DB 를 채울 때 쓴다. **빈 칸만** 채우고 있는 값은 건드리지 않는다.

    python -m store.jobs.refill_sections            # 모집중 공고
    python -m store.jobs.refill_sections --all      # 마감 공고까지
    python -m store.jobs.refill_sections --dry-run
    python -m store.jobs.refill_sections --trim     # 칸에 섞여 든 '기타 안내사항' 아래를 잘라 낸다

`--trim`: 옛 규칙은 '기타 안내사항'·'■ 지원 안내사항' 을 끊는 머리말로 몰라서 그 아래(전형 절차·
지원서 유의사항·'목록가기')가 우대사항·복지 칸에 붙었다(2026-10, CJ ENM 공고 판에서 보임). 규칙은
split_jd_sections 에 고쳤고, 이미 저장된 칸은 그 줄에서 자른다 — 그 위의 내용은 건드리지 않는다.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))  # catch_capture 루트

import re

from crawlers.jobs_common import build_jd_sections
from store.db.conn import cursor

FIELDS = ("main_tasks", "qualifications", "preferences", "benefits")


def run(active_only: bool = True, dry_run: bool = False) -> dict:
    where = "AND s.status = 'active'" if active_only else ""
    with cursor(autocommit=True) as cur:
        cur.execute(f"""
            SELECT j.id, j.full_jd, j.main_tasks, j.qualifications, j.preferences, j.benefits
              FROM job j JOIN job_state s ON s.job_id = j.id
             WHERE length(coalesce(j.full_jd, '')) > 200 {where}
               AND (coalesce(j.main_tasks, '') = '' OR coalesce(j.qualifications, '') = ''
                    OR coalesce(j.preferences, '') = '')""")
        rows = cur.fetchall()
    updates = []
    for r in rows:
        parts = build_jd_sections(None, r["full_jd"])
        new = {k: parts[k] for k in FIELDS if parts.get(k) and not r[k]}
        if new:
            updates.append((r["id"], new))
    filled = {k: sum(1 for _, n in updates if k in n) for k in FIELDS}
    print(f"[refill] 대상 {len(rows):,}건 → 채울 공고 {len(updates):,}건 {filled}", flush=True)
    if dry_run or not updates:
        return {"candidates": len(rows), "updated": 0, **filled}
    with cursor() as cur:                     # 한 트랜잭션 — 중간에 실패하면 전부 되돌린다
        for jid, new in updates:
            sets = ", ".join(f"{k} = %({k})s" for k in new)
            cur.execute(f"UPDATE job SET {sets} WHERE id = %(id)s AND "
                        + " AND ".join(f"coalesce({k}, '') = ''" for k in new), {**new, "id": jid})
    print(f"[refill] {len(updates):,}건 채움", flush=True)
    return {"candidates": len(rows), "updated": len(updates), **filled}


#: 칸 안에 홀로 선 '…안내사항' 줄 — 앞뒤 기호·번호(■ @ © 9. [ ])와 '기타'·'지원'·'채용 절차 및' 같은 머리를 받는다
_GUIDE_HEAD = re.compile(r"^\W{0,3}(?:\d+\.\s*)?[^\n]{0,10}안내\s*사항\W{0,3}$", re.M)


def trim(dry_run: bool = False) -> dict:
    with cursor(autocommit=True) as cur:
        cur.execute(f"""SELECT id, {", ".join(FIELDS)} FROM job
                         WHERE {" OR ".join(f"{k} ~ '안내\\s*사항'" for k in FIELDS)}""")
        rows = cur.fetchall()
    updates = []
    for r in rows:
        new = {}
        for k in FIELDS:
            m = _GUIDE_HEAD.search(r[k] or "")
            if m:
                new[k] = r[k][:m.start()].rstrip()
        if new:
            updates.append((r["id"], new))
    cut = {k: sum(1 for _, n in updates if k in n) for k in FIELDS}
    print(f"[trim] 안내사항 줄이 든 공고 {len(updates):,}건 {cut}", flush=True)
    if dry_run or not updates:
        return {"updated": 0, **cut}
    with cursor() as cur:
        for jid, new in updates:
            sets = ", ".join(f"{k} = %({k})s" for k in new)
            cur.execute(f"UPDATE job SET {sets} WHERE id = %(id)s", {**new, "id": jid})
    print(f"[trim] {len(updates):,}건 잘라 냄", flush=True)
    return {"updated": len(updates), **cut}


if __name__ == "__main__":
    a = _sys.argv[1:]
    if "--trim" in a:
        trim(dry_run="--dry-run" in a)
    else:
        run(active_only="--all" not in a, dry_run="--dry-run" in a)
