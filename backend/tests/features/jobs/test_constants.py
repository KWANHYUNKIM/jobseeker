"""지역 목록이 뷰어 TS 원본과 같은지 — 어긋나면 그 지역 칩이 사라진다."""
from __future__ import annotations

import re

from app.features.jobs.constants import REGION_OPTIONS, REGIONS
from tests.conftest import VIEWER

REGION_TS = VIEWER / "src" / "features" / "jobs" / "region.ts"


def _ts_list(name: str, src: str) -> list[str]:
    body = re.search(name + r"[^=]*=\s*\[(.*?)\]", src, re.S).group(1)
    return re.findall(r"'([^']+)'", body)


def test_regions_match_viewer():
    src = REGION_TS.read_text(encoding="utf-8")
    assert _ts_list(r"export const REGIONS\b", src) == REGIONS
    assert REGION_OPTIONS[-2:] == ["해외·원격", "정보없음"]
