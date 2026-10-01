"""뷰어 TS 원본과의 전량 대조 — 규칙이 두 곳에 있으니 어긋나면 여기서 걸린다."""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.db, pytest.mark.node]


def test_api_matches_browser_filter():
    from tests.features.jobs import parity
    assert parity.main() == 0
