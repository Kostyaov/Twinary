from __future__ import annotations

import sqlite3
from pathlib import Path

from backupflow.core.models import CopyResult, Profile
from backupflow.db.repositories import ConflictRepository, FileMetadataRepository, SyncSessionRepository
from backupflow.db.schema import initialize_schema
from backupflow.sync.analyzer import SyncAnalyzer
from backupflow.sync.executor import SyncExecutor


class FakeCopyAdapter:
    def copy_file(self, action, source_path: Path, destination_path: Path) -> CopyResult:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(source_path.read_bytes())
        return CopyResult(
            relative_path=action.relative_path,
            success=True,
            command=("fake-copy", str(source_path), str(destination_path)),
        )


class FailingAnalyzer:
    def analyze(self, profile, previous_metadata):
        raise AssertionError("Analyzer should not run when a prepared plan is provided.")


def test_synchronize_copies_both_directions_and_updates_metadata(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    (local / "local-only.txt").write_text("local", encoding="utf-8")
    (external / "external-only.txt").write_text("external", encoding="utf-8")

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    profile = _profile(local, external)
    metadata_repo = FileMetadataRepository(connection)
    session_repo = SyncSessionRepository(connection)

    result = SyncExecutor(
        session_repo,
        metadata_repo,
        copy_adapter=FakeCopyAdapter(),
    ).synchronize(profile)

    assert result.status == "completed"
    assert result.copied_count == 2
    assert (external / "local-only.txt").read_text(encoding="utf-8") == "local"
    assert (local / "external-only.txt").read_text(encoding="utf-8") == "external"

    stored = metadata_repo.list_for_profile(1)
    assert len(stored) == 4

    next_plan = SyncAnalyzer().analyze(profile, stored)
    assert all(action.source is None for action in next_plan.actions)


def test_synchronize_uses_prepared_plan_without_reanalyzing(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    (local / "local-only.txt").write_text("local", encoding="utf-8")
    profile = _profile(local, external)
    prepared_plan = SyncAnalyzer().analyze(profile)

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)

    result = SyncExecutor(
        SyncSessionRepository(connection),
        FileMetadataRepository(connection),
        analyzer=FailingAnalyzer(),
        copy_adapter=FakeCopyAdapter(),
    ).synchronize(profile, prepared_plan)

    assert result.status == "completed"
    assert result.copied_count == 1
    assert (external / "local-only.txt").read_text(encoding="utf-8") == "local"


def test_synchronize_emits_progress_events(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    (local / "local-only.txt").write_text("local", encoding="utf-8")

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    events: list[dict] = []

    result = SyncExecutor(
        SyncSessionRepository(connection),
        FileMetadataRepository(connection),
        copy_adapter=FakeCopyAdapter(),
        progress_callback=events.append,
    ).synchronize(_profile(local, external))

    assert result.status == "completed"
    assert [event["stage"] for event in events][0] == "analyzing"
    assert "copying" in {event["stage"] for event in events}
    assert events[-1]["stage"] == "metadata"
    assert any(event["total_actions"] == 1 for event in events)


def test_synchronize_keeps_both_versions_for_conflicts(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    (local / "conflict.txt").write_text("local-change", encoding="utf-8")
    (external / "conflict.txt").write_text("external-change", encoding="utf-8")

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    metadata_repo = FileMetadataRepository(connection)
    session_repo = SyncSessionRepository(connection)
    metadata_repo.replace_for_profile(
        1,
        [
            _stored_record(local / "conflict.txt", "conflict.txt", "local", 4, 100),
            _stored_record(external / "conflict.txt", "conflict.txt", "external", 4, 100),
        ],
    )

    conflict_repo = ConflictRepository(connection)
    result = SyncExecutor(
        session_repo,
        metadata_repo,
        conflict_repo,
        copy_adapter=FakeCopyAdapter(),
    ).synchronize(_profile(local, external))

    assert result.status == "completed"
    assert result.conflict_count == 1
    assert result.conflicts_resolved_count == 1
    assert result.copied_count == 0
    assert (local / "conflict.txt").read_text(encoding="utf-8") == "external-change"
    assert (external / "conflict.txt").read_text(encoding="utf-8") == "external-change"
    assert (local / "conflict.backupflow-conflict-local-s1.txt").read_text(encoding="utf-8") == "local-change"
    assert (external / "conflict.backupflow-conflict-local-s1.txt").read_text(encoding="utf-8") == "local-change"

    rows = connection.execute("SELECT relative_path, resolution FROM conflicts").fetchall()
    assert [(row["relative_path"], row["resolution"]) for row in rows] == [("conflict.txt", "keep_both")]

    next_plan = SyncAnalyzer().analyze(_profile(local, external), metadata_repo.list_for_profile(1))
    assert all(action.source is None for action in next_plan.actions)


def _profile(local: Path, external: Path) -> Profile:
    return Profile(
        id=1,
        name="Test",
        local_path=local,
        external_path=external,
        exclude_rules=("node_modules", ".git"),
    )


def _stored_record(path: Path, relative_path: str, side: str, size: int, modified_ns: int):
    from backupflow.core.models import FileRecord, FileSide

    return FileRecord(
        relative_path=relative_path,
        absolute_path=path,
        size=size,
        modified_ns=modified_ns,
        side=FileSide(side),
    )
