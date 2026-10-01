"""사이트 등록부(sites.py)가 DB enum·마감 판정기·뷰어 타입과 같은지 — 한쪽만 고치면 조용히 빠진다."""
from __future__ import annotations

import re
from pathlib import Path

from sites import AGNOSTIC_SITES, KEYWORD_SITES, SITE_KEYS, SITES

REPO = Path(__file__).resolve().parents[2]


def test_db_enum_has_every_site():
    schema = (REPO / "db" / "schema.sql").read_text(encoding="utf-8")
    body = re.search(r"CREATE TYPE job_site\s+AS ENUM\s*\(([^)]*)\)", schema).group(1)
    assert set(re.findall(r"'([^']+)'", body)) >= set(SITE_KEYS)


def test_every_site_has_a_close_checker():
    from pipeline.close_check import CHECKERS
    assert set(CHECKERS) == set(SITE_KEYS)


def test_viewer_site_type_matches():
    types = (REPO / "jd-viewer" / "src" / "types.ts").read_text(encoding="utf-8")
    body = re.search(r"export type Site\s*=([^\n]*(?:\n\s*\|[^\n]*)*)", types).group(1)
    assert set(re.findall(r"'([^']+)'", body)) == set(SITE_KEYS)


def test_every_site_has_a_crawler_and_runs_once_per_cycle():
    crawlers = REPO / "catch_capture" / "crawlers"
    assert all((crawlers / s.script).exists() for s in SITES)
    assert sorted(KEYWORD_SITES + AGNOSTIC_SITES) == sorted(SITE_KEYS)
