"""뷰어 TS 원본과의 전량 대조 — 규칙이 두 곳에 있으니 어긋나면 여기서 걸린다."""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.db, pytest.mark.node]


def test_facets_match_viewer_rules_on_all_jobs():
    from store.facets import parity
    assert parity() == 0


def test_api_matches_browser_filter():
    from store import api_parity
    assert api_parity.main() == 0
