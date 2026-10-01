"""PC 부품 가격 — 크롤 단계(crawl_hardware → store/market/hardware.py)가 하루 한 번 쓴다."""
from __future__ import annotations

from app.db.docs import get_doc
from app.db.session import cursor


def price_rows() -> tuple[list[dict], list[dict]]:
    """일별 가격 전부, 부품마다 마지막으로 매물을 받은 날의 매물."""
    with cursor() as cur:
        cur.execute("SELECT part_id, day, min_price, median_price, n FROM hw_price_day "
                    "ORDER BY part_id, day")
        days = cur.fetchall()
        cur.execute("""
            SELECT o.part_id, o.day, o.pcode, o.name, o.price, o.rank
              FROM hw_offer_day o
              JOIN (SELECT part_id, max(day) AS day FROM hw_offer_day GROUP BY part_id) last
                ON last.part_id = o.part_id AND last.day = o.day
             ORDER BY o.part_id, o.price, o.rank NULLS LAST, o.pcode
        """)
        offers = cur.fetchall()
    return days, offers


def meta() -> dict | None:
    return get_doc("hardware", "meta")
