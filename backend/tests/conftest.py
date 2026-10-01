"""공통 테스트 준비.

DB 가 필요한 테스트는 `db` 마커를 달고, DB 에 못 붙으면 통째로 건너뛴다 — 순수 규칙·
계약 테스트는 DB 없는 노트북에서도 돌아야 한다.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

# 응답 캐시는 끈다 — 테스트끼리 서로의 답을 물려받으면 안 된다(캐시는 따로 시험한다).
os.environ.setdefault("API_CACHE_TTL", "0")

REPO = Path(__file__).resolve().parents[2]
VIEWER = REPO / "jd-viewer"


def _db_ok() -> bool:
    try:
        from app.db.session import fetch_one
        return bool(fetch_one("SELECT to_regclass('job_facet') IS NOT NULL AS ok")["ok"])
    except Exception:                                               # noqa: BLE001
        return False


_DB: bool | None = None


def pytest_collection_modifyitems(config, items):
    global _DB
    if any("db" in i.keywords for i in items) and _DB is None:
        _DB = _db_ok()
    for item in items:
        if "db" in item.keywords and not _DB:
            item.add_marker(pytest.mark.skip(reason="정본 DB 에 못 붙음(또는 job_facet 없음)"))
        if "node" in item.keywords and not shutil.which("node"):
            item.add_marker(pytest.mark.skip(reason="node 없음"))


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
