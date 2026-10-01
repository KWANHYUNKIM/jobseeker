"""정적 문서 → viewer_doc 동기화 — 바뀐 것만 쓰고, 사라진 것은 지우고, 깨진 파일은 건너뛴다."""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.db
KIND = "file-test"


def _rows():
    from store.db import conn
    with conn.cursor(autocommit=True) as cur:
        cur.execute("SELECT key, payload FROM viewer_doc WHERE kind = %s ORDER BY key", (KIND,))
        return {r["key"]: r["payload"] for r in cur.fetchall()}


@pytest.fixture
def public(tmp_path):
    (tmp_path / "reveng" / "companies").mkdir(parents=True)
    (tmp_path / "trends.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    (tmp_path / "mindmap.md").write_text("# 제목", encoding="utf-8")
    (tmp_path / "reveng" / "companies" / "toss.json").write_text('{"name": "토스"}', encoding="utf-8")
    (tmp_path / "hardware").mkdir()
    (tmp_path / "hardware" / "prices.json").write_text("{}", encoding="utf-8")   # API 가 따로 답한다
    (tmp_path / "all_jobs_enriched.json").write_text("[]", encoding="utf-8")      # 대상 아님
    yield tmp_path
    from store.db import conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM viewer_doc WHERE kind = %s", (KIND,))


def test_sync_incremental_and_removal(public):
    from store.ingest.docs import sync
    s = sync(public, kind=KIND)
    assert s["written"] == 3
    rows = _rows()
    assert set(rows) == {"trends.json", "mindmap.md", "reveng/companies/toss.json"}
    assert rows["mindmap.md"] == {"_text": "# 제목"}

    assert sync(public, kind=KIND)["written"] == 0, "바뀌지 않았으면 다시 쓰지 않는다"

    (public / "trends.json").write_text(json.dumps({"a": 2}), encoding="utf-8")
    (public / "reveng" / "companies" / "toss.json").unlink()
    s = sync(public, kind=KIND)
    assert (s["written"], s["removed"]) == (1, 1)
    assert _rows()["trends.json"] == {"a": 2}


def test_broken_file_keeps_old_copy(public):
    from store.ingest.docs import sync
    sync(public, kind=KIND)
    (public / "trends.json").write_text('{"a": ', encoding="utf-8")   # 반쯤 쓰인 파일
    s = sync(public, kind=KIND)
    assert s["skipped_bad"] == 1 and _rows()["trends.json"] == {"a": 1}
