from __future__ import annotations

import os
import unicodedata
from pathlib import Path

from backupflow.core.models import FileSide, Profile, StoredFileMetadata, SyncActionType
import backupflow.sync.analyzer as analyzer_module
from backupflow.sync.analyzer import SyncAnalyzer


def test_analyze_detects_files_that_exist_on_one_side(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    (local / "from-local.txt").write_text("local", encoding="utf-8")
    (external / "from-external.txt").write_text("external", encoding="utf-8")

    plan = SyncAnalyzer().analyze(_profile(local, external))

    action_types = {action.relative_path: action.action_type for action in plan.actions}
    assert action_types["from-local.txt"] == SyncActionType.COPY_LOCAL_TO_EXTERNAL
    assert action_types["from-external.txt"] == SyncActionType.COPY_EXTERNAL_TO_LOCAL


def test_analyze_ignores_macos_appledouble_files(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    (local / "document.md").write_text("visible", encoding="utf-8")
    (local / "._document.md").write_text("resource fork", encoding="utf-8")

    plan = SyncAnalyzer().analyze(_profile(local, external))

    assert [action.relative_path for action in plan.actions] == ["document.md"]
    assert plan.ignored_count == 1


def test_analyze_skips_equal_files(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    local_file = local / "same.txt"
    external_file = external / "same.txt"
    local_file.write_text("same", encoding="utf-8")
    external_file.write_text("same", encoding="utf-8")
    stat = local_file.stat()
    os.utime(external_file, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    plan = SyncAnalyzer().analyze(_profile(local, external))

    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == SyncActionType.SKIP


def test_analyze_skips_files_with_filesystem_timestamp_rounding(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    local_file = local / "rounded.jpg"
    external_file = external / "rounded.jpg"
    local_file.write_text("same-size", encoding="utf-8")
    external_file.write_text("same-size", encoding="utf-8")
    os.utime(local_file, ns=(100, 2_000_008_436))
    os.utime(external_file, ns=(100, 2_000_000_000))

    plan = SyncAnalyzer().analyze(_profile(local, external))

    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == SyncActionType.SKIP


def test_analyze_matches_unicode_normalized_paths_across_filesystems(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    local_file = local / "Потоцький.mp3"
    external_file = external / unicodedata.normalize("NFD", "Потоцький.mp3")
    local_file.write_text("same", encoding="utf-8")
    external_file.write_text("same", encoding="utf-8")
    os.utime(local_file, ns=(100, 2_000_000_000))
    os.utime(external_file, ns=(100, 2_000_000_000))

    plan = SyncAnalyzer().analyze(_profile(local, external))

    assert len(plan.actions) == 1
    assert plan.actions[0].relative_path == "Потоцький.mp3"
    assert plan.actions[0].action_type == SyncActionType.SKIP


def test_analyze_updates_newer_local_file(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    local_file = local / "changed.txt"
    external_file = external / "changed.txt"
    local_file.write_text("new", encoding="utf-8")
    external_file.write_text("old", encoding="utf-8")
    os.utime(local_file, ns=(100, 2_000_000_000))
    os.utime(external_file, ns=(100, 1_000_000_000))

    plan = SyncAnalyzer().analyze(_profile(local, external))

    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == SyncActionType.UPDATE_LOCAL_TO_EXTERNAL


def test_default_analyze_uses_fast_metadata_comparison(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    local_file = local / "same-size.txt"
    external_file = external / "same-size.txt"
    local_file.write_text("abc", encoding="utf-8")
    external_file.write_text("xyz", encoding="utf-8")
    os.utime(local_file, ns=(100, 2_000_000_000))
    os.utime(external_file, ns=(100, 1_000_000_000))

    def fail_hash(path: Path) -> str:
        raise AssertionError(f"Hash should not run in default mode: {path}")

    monkeypatch.setattr(analyzer_module, "xxhash64", fail_hash)

    plan = SyncAnalyzer().analyze(_profile(local, external))

    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == SyncActionType.UPDATE_LOCAL_TO_EXTERNAL


def test_strict_analyze_hashes_equal_size_files(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    local_file = local / "same-content.txt"
    external_file = external / "same-content.txt"
    local_file.write_text("same", encoding="utf-8")
    external_file.write_text("same", encoding="utf-8")
    os.utime(local_file, ns=(100, 2_000_000_000))
    os.utime(external_file, ns=(100, 1_000_000_000))

    plan = SyncAnalyzer().analyze(_profile(local, external, strict_verification=True))

    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == SyncActionType.SKIP


def test_strict_analyze_uses_fast_metadata_for_media_files(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    local_file = local / "video.mp4"
    external_file = external / "video.mp4"
    local_file.write_text("abc", encoding="utf-8")
    external_file.write_text("xyz", encoding="utf-8")
    os.utime(local_file, ns=(100, 2_000_000_000))
    os.utime(external_file, ns=(100, 1_000_000_000))

    def fail_hash(path: Path, *args, **kwargs) -> str:
        raise AssertionError(f"Hash should not run for media files: {path}")

    monkeypatch.setattr(analyzer_module, "xxhash64", fail_hash)

    plan = SyncAnalyzer().analyze(_profile(local, external, strict_verification=True))

    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == SyncActionType.UPDATE_LOCAL_TO_EXTERNAL


def test_strict_analyze_uses_fast_metadata_for_large_files(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    local_file = local / "large.dat"
    external_file = external / "large.dat"
    local_file.write_text("abc", encoding="utf-8")
    external_file.write_text("xyz", encoding="utf-8")
    over_limit = analyzer_module.STRICT_HASH_SIZE_LIMIT_BYTES + 1
    os.truncate(local_file, over_limit)
    os.truncate(external_file, over_limit)
    os.utime(local_file, ns=(100, 2_000_000_000))
    os.utime(external_file, ns=(100, 1_000_000_000))

    def fail_hash(path: Path, *args, **kwargs) -> str:
        raise AssertionError(f"Hash should not run for large files: {path}")

    monkeypatch.setattr(analyzer_module, "xxhash64", fail_hash)

    plan = SyncAnalyzer().analyze(_profile(local, external, strict_verification=True))

    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == SyncActionType.UPDATE_LOCAL_TO_EXTERNAL


def test_analyze_can_be_cancelled(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    (local / "file.txt").write_text("local", encoding="utf-8")

    analyzer = SyncAnalyzer(should_cancel=lambda: True)

    try:
        analyzer.analyze(_profile(local, external))
    except InterruptedError as error:
        assert str(error) == "Operation cancelled."
    else:
        raise AssertionError("Analyze should stop when cancellation is requested.")


def test_analyze_detects_conflict_when_both_sides_changed(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    local_file = local / "conflict.txt"
    external_file = external / "conflict.txt"
    local_file.write_text("local-change", encoding="utf-8")
    external_file.write_text("external-change", encoding="utf-8")

    previous = {
        ("conflict.txt", FileSide.LOCAL): StoredFileMetadata(
            "conflict.txt",
            FileSide.LOCAL,
            4,
            100,
            None,
        ),
        ("conflict.txt", FileSide.EXTERNAL): StoredFileMetadata(
            "conflict.txt",
            FileSide.EXTERNAL,
            4,
            100,
            None,
        ),
    }

    plan = SyncAnalyzer().analyze(_profile(local, external), previous)

    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == SyncActionType.CONFLICT


def _profile(local: Path, external: Path, strict_verification: bool = False) -> Profile:
    return Profile(
        id=1,
        name="Test",
        local_path=local,
        external_path=external,
        exclude_rules=("node_modules", ".git"),
        strict_verification=strict_verification,
    )
