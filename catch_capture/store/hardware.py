"""PC 부품 가격 ↔ 정본 DB (db/migrations/009_hardware_price.sql).

쓰기:  crawl_hardware 가 그날 받은 가격을 hw_price_day·hw_offer_day 에 한 줄씩 남기고,
       부품 목록(parts.json 의 사본)을 hw_part 에 맞춘다.
읽기:  hw_price_day → prices.json 의 history (파일이 사라져도 이력을 되살린다).

크롤러는 JSON 을 직접 쓰고 여기로 **이중 쓰기** 한다(DB_DUAL_WRITE=0 으로 끈다).
DB 가 없거나 실패해도 크롤 단계는 죽지 않는다 — 외주 쪽 store.freelance 와 같은 약속이다.

    python -m store.hardware ingest            # public/hardware/prices.json → DB (백필·복구)
    python -m store.hardware export [경로]     # DB 의 가격 이력 → prices.json 의 history
    python -m store.hardware stats
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import os
from datetime import date
from pathlib import Path

from psycopg.types.json import Jsonb

from store.conn import cursor

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
HW_DIR = ROOT_DIR / "jd-viewer" / "public" / "hardware"


def enabled() -> bool:
    return os.environ.get("DB_DUAL_WRITE", "1") != "0"


PART_SQL = """
INSERT INTO hw_part (id, category, name, maker, specs, perf_index, updated_at)
VALUES (%(id)s, %(category)s, %(name)s, %(maker)s, %(specs)s, %(perf_index)s, now())
ON CONFLICT (id) DO UPDATE SET
    category = EXCLUDED.category, name = EXCLUDED.name, maker = EXCLUDED.maker,
    specs = EXCLUDED.specs, perf_index = EXCLUDED.perf_index, updated_at = now()
"""

PRICE_SQL = """
INSERT INTO hw_price_day (day, part_id, min_price, median_price, n)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (day, part_id) DO UPDATE SET
    min_price = EXCLUDED.min_price, median_price = EXCLUDED.median_price, n = EXCLUDED.n
"""

OFFER_SQL = """
INSERT INTO hw_offer_day (day, part_id, pcode, name, price) VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (day, part_id, pcode) DO UPDATE SET name = EXCLUDED.name, price = EXCLUDED.price
"""


def ingest(parts: list[dict], prices: dict, only_day: str | None = None) -> dict:
    """부품 목록과 가격 원장 → DB. only_day 를 주면 그날 줄만(크롤 직후), 없으면 전 이력(백필)."""
    stats = {"parts": 0, "days": 0, "offers": 0}
    known = {p["id"] for p in parts}
    with cursor() as cur:
        for p in parts:
            cur.execute(PART_SQL, {"id": p["id"], "category": p["category"], "name": p["name"],
                                   "maker": p.get("maker"), "specs": Jsonb(p.get("specs") or {}),
                                   "perf_index": (p.get("perf") or {}).get("index")})
            stats["parts"] += 1
        for pid, rec in (prices.get("parts") or {}).items():
            if pid not in known:  # 목록에서 빠진 부품의 옛 가격은 원장 파일에만 남긴다
                continue
            for h in rec.get("history") or []:
                if only_day and h["d"] != only_day:
                    continue
                cur.execute(PRICE_SQL, (h["d"], pid, h["min"], h["median"], h["n"]))
                stats["days"] += 1
            if rec.get("day") and (not only_day or rec["day"] == only_day):
                for o in rec.get("offers") or []:
                    cur.execute(OFFER_SQL, (rec["day"], pid, o["pcode"], o["name"], o["price"]))
                    stats["offers"] += 1
    return stats


def history() -> dict[str, list[dict]]:
    """DB 의 일별 가격 → {part_id: [{d,min,median,n}]}."""
    out: dict[str, list[dict]] = {}
    with cursor(autocommit=True) as cur:
        cur.execute("SELECT day, part_id, min_price, median_price, n FROM hw_price_day ORDER BY part_id, day")
        for r in cur.fetchall():
            d = r["day"].isoformat() if isinstance(r["day"], date) else str(r["day"])
            out.setdefault(r["part_id"], []).append(
                {"d": d, "min": r["min_price"], "median": r["median_price"], "n": r["n"]})
    return out


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "stats"
    parts = _load(HW_DIR / "parts.json", {}).get("parts", [])
    if cmd == "ingest":
        print(ingest(parts, _load(HW_DIR / "prices.json", {})))
    elif cmd == "export":
        path = Path(argv[1]) if len(argv) > 1 else HW_DIR / "prices.json"
        doc = _load(path, {"schema": 1, "source": "danawa", "parts": {}})
        for pid, hist in history().items():
            doc.setdefault("parts", {}).setdefault(pid, {})["history"] = hist
        path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"→ {path}")
    else:
        with cursor(autocommit=True) as cur:
            cur.execute("SELECT count(*) AS n, count(DISTINCT day) AS days, max(day) AS last FROM hw_price_day")
            print(dict(cur.fetchone()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
