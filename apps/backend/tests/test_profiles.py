from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backupflow.db.repositories import ProfileRepository
from backupflow.db.schema import initialize_schema


def test_create_profile_requires_existing_folders(tmp_path: Path) -> None:
    connection = _connection()
    repo = ProfileRepository(connection)

    with pytest.raises(ValueError, match="Local path must be an existing folder"):
        repo.create("Demo", tmp_path / "missing-local", tmp_path)


def test_create_profile_rejects_same_folder(tmp_path: Path) -> None:
    connection = _connection()
    repo = ProfileRepository(connection)

    with pytest.raises(ValueError, match="must be different"):
        repo.create("Demo", tmp_path, tmp_path)


def test_create_profile_stores_valid_profile(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    connection = _connection()
    repo = ProfileRepository(connection)

    profile = repo.create("Demo", local, external)

    assert profile.id == 1
    assert profile.name == "Demo"
    assert profile.local_path == local
    assert profile.external_path == external


def test_delete_profile_removes_profile_without_touching_folders(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    (local / "keep.txt").write_text("local data", encoding="utf-8")
    connection = _connection()
    repo = ProfileRepository(connection)
    profile = repo.create("Demo", local, external)

    assert repo.delete(profile.id or 0) is True

    assert repo.get(profile.id or 0) is None
    assert (local / "keep.txt").read_text(encoding="utf-8") == "local data"


def test_delete_profile_returns_false_when_missing() -> None:
    repo = ProfileRepository(_connection())

    assert repo.delete(999) is False


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    return connection
