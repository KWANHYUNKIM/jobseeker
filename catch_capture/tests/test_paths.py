"""core.paths.adopt — 폴더 개편 전 위치의 데이터를 새 위치로 옮긴다(맥의 운영 데이터가 걸린 일)."""
from __future__ import annotations

from core import paths


def _setup(tmp_path, monkeypatch, new, old):
    monkeypatch.setattr(paths, "LEGACY", {new: old})


def test_moves_file_when_new_missing(tmp_path, monkeypatch):
    old, new = tmp_path / "engagement" / "events.jsonl", tmp_path / "var" / "engagement" / "events.jsonl"
    old.parent.mkdir(parents=True); old.write_text("a\n", encoding="utf-8")
    _setup(tmp_path, monkeypatch, new, old)
    paths.adopt(new)
    assert new.read_text(encoding="utf-8") == "a\n" and not old.exists()


def test_never_overwrites_existing_file(tmp_path, monkeypatch):
    old, new = tmp_path / "old.json", tmp_path / "var" / "new.json"
    old.write_text("old", encoding="utf-8"); new.parent.mkdir(); new.write_text("new", encoding="utf-8")
    _setup(tmp_path, monkeypatch, new, old)
    paths.adopt(new)
    assert new.read_text(encoding="utf-8") == "new"
    assert (new.parent / "new.json.legacy").read_text(encoding="utf-8") == "old"


def test_merges_directory_without_overwriting(tmp_path, monkeypatch):
    old, new = tmp_path / "admin" / "data", tmp_path / "var" / "admin" / "data"
    (old / "resumes").mkdir(parents=True)
    (old / "profile.json").write_text("old-profile", encoding="utf-8")
    (old / "resumes" / "r1.json").write_text("r1", encoding="utf-8")
    new.mkdir(parents=True); (new / "profile.json").write_text("new-profile", encoding="utf-8")
    _setup(tmp_path, monkeypatch, new, old)
    paths.adopt(new)
    assert (new / "profile.json").read_text(encoding="utf-8") == "new-profile"
    assert (new / "resumes" / "r1.json").read_text(encoding="utf-8") == "r1"


def test_nothing_to_do(tmp_path, monkeypatch):
    new = tmp_path / "var" / "x"
    _setup(tmp_path, monkeypatch, new, tmp_path / "missing")
    paths.adopt(new)
    assert not new.exists()
