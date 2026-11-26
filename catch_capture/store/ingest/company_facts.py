"""회사 사실 → 정본 DB(migrations/020).

`crawlers/crawl_company_facts.py` 가 모은 수집 중간물(`var/roles/company_facts.json` · `market_wage.json`)을
표로 옮긴다. 같은 내용이면 content_hash 로 건너뛰고, 중간물에서 사라진 회사·공고 행은 지운다(다시 만들 수 있는 값이다).

    python -m store.ingest.company_facts             # 옮기기
    python -m store.ingest.company_facts --dry-run   # 셀 것만
    python -m store.ingest.company_facts --full      # 해시 무시하고 다 쓰기
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))  # catch_capture 루트

import hashlib
import json

from core.paths import VAR_DIR

FACTS = VAR_DIR / "roles" / "company_facts.json"
WAGE = VAR_DIR / "roles" / "market_wage.json"


def _h(row: dict) -> str:
    return hashlib.sha1(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _upsert(cur, table: str, key: str, rows: list[dict], *, full: bool, prune: bool = True) -> tuple[int, int]:
    """키 하나짜리 표에 해시가 바뀐 행만 쓴다. prune 이면 rows 에 없는 행을 지운다. (쓴 수, 지운 수)."""
    for r in rows:
        r["content_hash"] = _h({k: v for k, v in r.items() if k != "content_hash"})
    cur.execute(f"SELECT {key} AS k, content_hash AS h FROM {table}")
    have = {r["k"]: r["h"] for r in cur.fetchall()}
    todo = [r for r in rows if full or have.get(r[key]) != r["content_hash"]]
    if todo:
        cols = list(todo[0].keys())
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != key) + ", updated_at = now()"
        cur.executemany(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('%s' for _ in cols)}) "
                        f"ON CONFLICT ({key}) DO UPDATE SET {sets}", [[r[c] for c in cols] for r in todo])
    gone = [k for k in have if k not in {r[key] for r in rows}] if prune else []
    if gone:
        cur.execute(f"DELETE FROM {table} WHERE {key} = ANY(%s)", (gone,))
    return len(todo), len(gone)


def wage_rows(doc: dict) -> tuple[list[dict], list[dict]]:
    y = int(doc["year"])
    occ = [{"year": y, "occ_code": code, "occ_name": o["name"], "career": c, "annual_pay": v.get("annual_만원"),
            "workers": v.get("workers")}
           for code, o in doc["occupations"].items() for c, v in o["careers"].items()]
    size = [{"year": y, "size": sz, "age": age, "annual_pay": v.get("annual_만원"), "tenure_years": v.get("tenure_years")}
            for sz, ages in doc["sizes_college"].items() for age, v in ages.items()]
    return occ, size


def sync(*, dry_run: bool = False, full: bool = False) -> dict:
    from crawlers.crawl_company_facts import fact_rows
    out: dict = {}
    facts = _load(FACTS)
    frows, srows = fact_rows(facts) if facts else ([], [])
    wage = _load(WAGE)
    occ, size = wage_rows(wage) if wage else ([], [])
    out.update(facts=len(frows), salaries=len(srows), wage=len(occ), wage_size=len(size))
    if dry_run:
        return out
    from store.db import conn as store_conn
    with store_conn.cursor() as cur:
        if facts:   # 중간물이 없으면(다른 머신) 표를 비우지 않는다
            out["facts_written"], out["facts_removed"] = _upsert(cur, "company_fact", "company_key", frows, full=full)
            out["salaries_written"], out["salaries_removed"] = _upsert(cur, "company_posting_salary", "job_key", srows, full=full)
        if wage:    # 통계는 해마다 한 번 — 같은 해 값만 갈아 끼운다(지난 해는 남긴다)
            y = occ[0]["year"]
            cur.execute("DELETE FROM market_wage WHERE year = %s", (y,))
            cur.execute("DELETE FROM market_wage_size WHERE year = %s", (y,))
            for table, rows in (("market_wage", occ), ("market_wage_size", size)):
                cols = list(rows[0].keys())
                cur.executemany(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('%s' for _ in cols)})",
                                [[r[c] for c in cols] for r in rows])
            out["wage_year"] = y
    return out


def main() -> int:
    print(f"[company_facts] {sync(dry_run='--dry-run' in _sys.argv, full='--full' in _sys.argv)}")
    return 0


if __name__ == "__main__":
    _sys.exit(main())
