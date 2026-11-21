"""크롤 → DB 적재의 마감일 — 스키마 CHECK(job_deadline_sane)에 걸리는 값이 들어가지 않게.

2026-11-21: 인크루트 공고 한 건의 마감일이 '상시'를 뜻하는 2999-12-31 로 들어와 CHECK 에 걸렸고,
그 한 건 때문에 사이클 전체(5,099건)의 이중 쓰기가 되돌아갔다.
"""
from datetime import date

from store.ingest.crawl import _deadline

TODAY = date(2026, 11, 21)


def test_far_future_means_always_open():
    assert _deadline({"deadline_date": "2999-12-31"}, TODAY) == (None, True)
    assert _deadline({"deadline_date": "9999-12-31"}, TODAY) == (None, True)


def test_out_of_range_is_unknown():
    assert _deadline({"deadline_date": "1999-01-01"}, TODAY) == (None, False)
    assert _deadline({"deadline_date": "2150-06-01"}, TODAY) == (None, False)


def test_normal_date_kept():
    assert _deadline({"deadline_date": "2026-12-31"}, TODAY) == (date(2026, 12, 31), False)
