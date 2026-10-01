from __future__ import annotations

import pytest


@pytest.mark.db
def test_health(client):
    d = client.get("/api/health").json()
    assert d["ok"] is True and d["stats"]["job_facets"] > 0


def test_db_down_is_503_not_crash(monkeypatch):
    """DB 가 내려가도 서버는 산다 — 503 을 주고, 뷰어는 정적 파일로 물러선다."""
    import psycopg
    from fastapi.testclient import TestClient
    from app.features.health import service
    from app.main import create_app

    def boom():
        raise psycopg.OperationalError("connection refused")
    monkeypatch.setattr(service, "stats", boom)
    r = TestClient(create_app()).get("/api/health")
    assert r.status_code == 503 and r.json()["ok"] is False


def test_root_lists_endpoints(client):
    d = client.get("/").json()
    assert d["ok"] and "/api/jobs" in d["endpoints"]
