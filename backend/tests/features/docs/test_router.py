"""정적 문서 API — 같은 이름의 public 파일과 내용이 같아야 한다(뷰어가 둘을 바꿔 가며 읽는다)."""
from __future__ import annotations

import json

import pytest

from tests.conftest import VIEWER

PUBLIC = VIEWER / "public"


def _synced(client, path):
    r = client.get(f"/api/docs/{path}")
    if r.status_code == 404:
        pytest.skip(f"{path} 가 DB 에 없음(store.ingest.docs 를 먼저)")
    assert r.status_code == 200
    return r


@pytest.mark.db
@pytest.mark.parametrize("path", ["reveng/index.json", "guide/index.json", "book/index.json",
                                  "hardware/parts.json", "trends.json"])
def test_json_matches_file(client, path):
    if not (PUBLIC / path).exists():
        pytest.skip(f"{path} 파일 없음")
    r = _synced(client, path)
    assert r.json() == json.loads((PUBLIC / path).read_text(encoding="utf-8"))
    assert r.headers.get("etag")


@pytest.mark.db
def test_markdown_is_text(client):
    if not (PUBLIC / "mindmap.md").exists():
        pytest.skip("mindmap.md 없음")
    r = _synced(client, "mindmap.md")
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.text == (PUBLIC / "mindmap.md").read_text(encoding="utf-8")


@pytest.mark.db
def test_missing_is_404(client):
    assert client.get("/api/docs/없는/문서.json").status_code == 404


@pytest.mark.parametrize("path", ["../secret.json", "a//b.json", "x.txt", ".env"])
def test_bad_paths_are_rejected(client, path):
    assert client.get(f"/api/docs/{path}").status_code in (400, 404)
