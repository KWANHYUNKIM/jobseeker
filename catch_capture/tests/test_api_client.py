"""core.api — API 먼저, 304 면 그대로, 실패하면 파일, 그것도 없으면 마지막 값."""
from __future__ import annotations

import json

import pytest

from core import api


@pytest.fixture(autouse=True)
def fresh(monkeypatch, tmp_path):
    api.clear()
    monkeypatch.setattr(api, "VIEWER_PUBLIC", tmp_path)
    monkeypatch.setattr(api, "TTL", 0)          # 매번 다시 묻게
    yield tmp_path
    api.clear()


def test_api_first_then_304_reuses(monkeypatch):
    calls = []

    def fake(path, etag):
        calls.append(etag)
        return (200, '"v1"', {"n": 1}) if etag is None else (304, etag, None)
    monkeypatch.setattr(api, "_request", fake)
    assert api.get("/api/x", build=lambda d: d["n"] + 1) == 2
    assert api.get("/api/x", build=lambda d: d["n"] + 1) == 2
    assert calls == [None, '"v1"'], "두 번째는 ETag 로 묻고 304 면 가공본을 그대로 쓴다"


def test_falls_back_to_file_then_last_value(monkeypatch, fresh):
    (fresh / "x.json").write_text(json.dumps({"n": 5}), encoding="utf-8")

    def down(path, etag):
        raise ConnectionError("refused")
    monkeypatch.setattr(api, "_request", down)
    assert api.get("/api/x", file="x.json") == {"n": 5}
    (fresh / "x.json").unlink()
    assert api.get("/api/x", file="x.json") == {"n": 5}, "파일도 없으면 마지막 값"


def test_nothing_anywhere_is_none(monkeypatch):
    monkeypatch.setattr(api, "_request", lambda p, e: (_ for _ in ()).throw(OSError("x")))
    assert api.get("/api/none", file="none.json") is None
