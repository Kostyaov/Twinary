from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from backupflow.core.models import (
    AnalyzePlan,
    FileRecord,
    FileSide,
    Profile,
    SyncAction,
    SyncActionType,
    SyncRunResult,
)
from backupflow.db.repositories import ConflictRepository, FileMetadataRepository, SyncSessionRepository
from backupflow.os_adapters.copy import CopyAdapter, NativeCopyAdapter
from backupflow.sync.analyzer import SyncAnalyzer
from backupflow.sync.scanner import FolderScanner


EXECUTABLE_ACTIONS = {
    SyncActionType.COPY_LOCAL_TO_EXTERNAL,
    SyncActionType.COPY_EXTERNAL_TO_LOCAL,
    SyncActionType.UPDATE_LOCAL_TO_EXTERNAL,
    SyncActionType.UPDATE_EXTERNAL_TO_LOCAL,
}


class SyncExecutor:
    def __init__(
        self,
        session_repository: SyncSessionRepository,
        metadata_repository: FileMetadataRepository,
        conflict_repository: ConflictRepository | None = None,
        analyzer: SyncAnalyzer | None = None,
        scanner: FolderScanner | None = None,
        copy_adapter: CopyAdapter | None = None,
        progress_callback: Callable[[dict], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        self.session_repository = session_repository
        self.metadata_repository = metadata_repository
        self.conflict_repository = conflict_repository
        self.scanner = scanner or FolderScanner()
        self.progress_callback = progress_callback
        self.should_cancel = should_cancel
        self.analyzer = analyzer or SyncAnalyzer(self.scanner, progress_callback, should_cancel)
        self.copy_adapter = copy_adapter or NativeCopyAdapter()

    def synchronize(self, profile: Profile, prepared_plan: AnalyzePlan | None = None) -> SyncRunResult:
        if profile.id is None:
            raise ValueError("Profile must be stored before synchronization.")

        self._ensure_not_cancelled()
        if prepared_plan is None:
            self._emit_progress(
                stage="analyzing",
                message="Scanning folders and building synchronization plan.",
                current_path=None,
                processed_actions=0,
                total_actions=0,
                bytes_done=0,
            )
            previous_metadata = self.metadata_repository.list_for_profile(profile.id)
            plan = self.analyzer.analyze(profile, previous_metadata)
        else:
            self._ensure_not_cancelled()
            plan = prepared_plan
            self._emit_progress(
                stage="copying",
                message="Using prepared analyze plan.",
                current_path=None,
                processed_actions=0,
                total_actions=0,
                bytes_done=0,
            )
        session_id = self.session_repository.create(profile.id, "running")
        events: list[str] = []
        copied_count = 0
        updated_count = 0
        skipped_count = 0
        conflict_count = 0
        conflicts_resolved_count = 0
        error_count = 0
        total_bytes = 0
        executable_actions = [
            action
            for action in plan.actions
            if action.action_type not in {SyncActionType.SKIP, SyncActionType.IGNORE}
        ]
        total_action_count = len(executable_actions)
        processed_action_count = 0
        self._emit_progress(
            stage="copying" if total_action_count else "metadata",
            message=f"Plan ready: {total_action_count} actions to execute.",
            current_path=None,
            processed_actions=0,
            total_actions=total_action_count,
            bytes_done=0,
        )

        for action in plan.actions:
            self._ensure_not_cancelled()
            if action.action_type == SyncActionType.SKIP:
                skipped_count += 1
                continue
            if action.action_type == SyncActionType.IGNORE:
                continue

            processed_action_count += 1
            self._emit_progress(
                stage="copying",
                message=f"Processing {processed_action_count} of {total_action_count}.",
                current_path=action.relative_path,
                processed_actions=processed_action_count - 1,
                total_actions=total_action_count,
                bytes_done=total_bytes,
            )
            if action.action_type == SyncActionType.CONFLICT:
                conflict_count += 1
                self._emit_progress(
                    stage="resolving_conflict",
                    message=f"Keeping both versions for {action.relative_path}.",
                    current_path=action.relative_path,
                    processed_actions=processed_action_count - 1,
                    total_actions=total_action_count,
                    bytes_done=total_bytes,
                )
                conflict_result = self._resolve_keep_both(profile, action, session_id)
                if conflict_result.success:
                    conflicts_resolved_count += 1
                    total_bytes += conflict_result.bytes_copied
                    message = f"Conflict kept both: {action.relative_path}"
                    events.append(message)
                    self.session_repository.add_event(session_id, "conflict_resolved", action.relative_path, message)
                    events.extend(conflict_result.events)
                else:
                    error_count += 1
                    message = f"Conflict resolution failed: {action.relative_path}"
                    events.append(message)
                    self.session_repository.add_event(session_id, "error", action.relative_path, message)
                self._emit_progress(
                    stage="copying",
                    message=f"Processed {processed_action_count} of {total_action_count}.",
                    current_path=action.relative_path,
                    processed_actions=processed_action_count,
                    total_actions=total_action_count,
                    bytes_done=total_bytes,
                )
                continue
            if action.action_type not in EXECUTABLE_ACTIONS:
                continue

            self._ensure_not_cancelled()
            source_path, destination_path = self._paths_for_action(profile, action)
            result = self._copy_file(action, source_path, destination_path)
            command_text = " ".join(result.command)
            if result.success:
                if action.action_type in {
                    SyncActionType.COPY_LOCAL_TO_EXTERNAL,
                    SyncActionType.COPY_EXTERNAL_TO_LOCAL,
                }:
                    copied_count += 1
                    event_type = "copied"
                else:
                    updated_count += 1
                    event_type = "updated"
                total_bytes += action.size
                message = f"{event_type}: {action.relative_path}"
                events.append(message)
                self.session_repository.add_event(
                    session_id,
                    event_type,
                    action.relative_path,
                    message,
                    str(source_path),
                    str(destination_path),
                )
            else:
                error_count += 1
                message = f"Copy failed: {action.relative_path} ({command_text})"
                if result.stderr:
                    message = f"{message}: {result.stderr.strip()}"
                events.append(message)
                self.session_repository.add_event(
                    session_id,
                    "error",
                    action.relative_path,
                    message,
                    str(source_path),
                    str(destination_path),
                )
            self._emit_progress(
                stage="copying",
                message=f"Processed {processed_action_count} of {total_action_count}.",
                current_path=action.relative_path,
                processed_actions=processed_action_count,
                total_actions=total_action_count,
                bytes_done=total_bytes,
            )

        if error_count:
            status = "completed_with_errors"
        else:
            status = "completed"

        self._emit_progress(
            stage="metadata",
            message="Refreshing file metadata after synchronization.",
            current_path=None,
            processed_actions=processed_action_count,
            total_actions=total_action_count,
            bytes_done=total_bytes,
        )
        self._refresh_metadata(profile)
        self._emit_progress(
            stage="metadata",
            message="File metadata refreshed.",
            current_path=None,
            processed_actions=processed_action_count,
            total_actions=total_action_count,
            bytes_done=total_bytes,
        )
        self.session_repository.finish(
            session_id,
            status,
            copied_count,
            updated_count,
            plan.ignored_count,
            conflict_count,
            error_count,
            total_bytes,
        )
        return SyncRunResult(
            session_id=session_id,
            status=status,
            copied_count=copied_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            conflict_count=conflict_count,
            conflicts_resolved_count=conflicts_resolved_count,
            error_count=error_count,
            total_bytes=total_bytes,
            events=tuple(events),
        )

    def _emit_progress(
        self,
        stage: str,
        message: str,
        current_path: str | None,
        processed_actions: int,
        total_actions: int,
        bytes_done: int,
    ) -> None:
        if self.progress_callback is None:
            return
        self.progress_callback(
            {
                "stage": stage,
                "message": message,
                "current_path": current_path,
                "processed_actions": processed_actions,
                "total_actions": total_actions,
                "bytes_done": bytes_done,
            }
        )

    def _ensure_not_cancelled(self) -> None:
        if self.should_cancel is not None and self.should_cancel():
            raise InterruptedError("Operation cancelled.")

    def _paths_for_action(self, profile: Profile, action: SyncAction) -> tuple:
        if action.source == FileSide.LOCAL and action.destination == FileSide.EXTERNAL:
            return profile.local_path / action.relative_path, profile.external_path / action.relative_path
        if action.source == FileSide.EXTERNAL and action.destination == FileSide.LOCAL:
            return profile.external_path / action.relative_path, profile.local_path / action.relative_path
        raise ValueError(f"Action has no copy direction: {action.action_type}")

    def _copy_file(self, action: SyncAction, source_path: Path, destination_path: Path):
        result = self.copy_adapter.copy_file(action, source_path, destination_path)
        if result.success:
            source_stat = source_path.stat()
            os.utime(destination_path, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        return result

    def _refresh_metadata(self, profile: Profile) -> None:
        if profile.id is None:
            raise ValueError("Profile must be stored before metadata refresh.")
        self._ensure_not_cancelled()
        local_files, _ = self.scanner.scan(
            profile.local_path,
            FileSide.LOCAL,
            profile.exclude_rules,
            self.progress_callback,
            self.should_cancel,
        )
        external_files, _ = self.scanner.scan(
            profile.external_path,
            FileSide.EXTERNAL,
            profile.exclude_rules,
            self.progress_callback,
            self.should_cancel,
        )
        records: list[FileRecord] = [*local_files.values(), *external_files.values()]
        self.metadata_repository.replace_for_profile(profile.id, records)

    def _resolve_keep_both(self, profile: Profile, action: SyncAction, session_id: int):
        local_path = profile.local_path / action.relative_path
        external_path = profile.external_path / action.relative_path
        local_stat = local_path.stat()
        external_stat = external_path.stat()

        if self.conflict_repository is not None:
            self.conflict_repository.create(
                session_id,
                action.relative_path,
                local_stat.st_mtime_ns,
                external_stat.st_mtime_ns,
                local_stat.st_size,
                external_stat.st_size,
                "keep_both",
            )

        if local_stat.st_mtime_ns >= external_stat.st_mtime_ns:
            winner_side = FileSide.LOCAL
            loser_side = FileSide.EXTERNAL
            winner_path = local_path
            loser_path = external_path
            winner_original_destination = external_path
        else:
            winner_side = FileSide.EXTERNAL
            loser_side = FileSide.LOCAL
            winner_path = external_path
            loser_path = local_path
            winner_original_destination = local_path

        loser_conflict_relative = self._available_conflict_relative_path(
            profile,
            action.relative_path,
            loser_side,
            session_id,
        )
        local_conflict_destination = profile.local_path / loser_conflict_relative
        external_conflict_destination = profile.external_path / loser_conflict_relative

        operations = [
            (loser_path, local_conflict_destination, loser_conflict_relative, "local conflict copy"),
            (loser_path, external_conflict_destination, loser_conflict_relative, "external conflict copy"),
            (winner_path, winner_original_destination, action.relative_path, "aligned original path"),
        ]

        events: list[str] = []
        bytes_copied = 0
        for source_path, destination_path, relative_path, label in operations:
            self._ensure_not_cancelled()
            synthetic_action = SyncAction(
                SyncActionType.UPDATE_LOCAL_TO_EXTERNAL,
                relative_path,
                winner_side,
                loser_side,
                source_path.stat().st_size,
                "Keep both conflict resolution.",
            )
            result = self._copy_file(synthetic_action, source_path, destination_path)
            if not result.success:
                return _ConflictResolutionResult(False, bytes_copied, tuple(events))
            bytes_copied += source_path.stat().st_size
            events.append(f"{label}: {relative_path}")

        return _ConflictResolutionResult(True, bytes_copied, tuple(events))

    def _available_conflict_relative_path(
        self,
        profile: Profile,
        relative_path: str,
        side: FileSide,
        session_id: int,
    ) -> str:
        source = Path(relative_path)
        suffix = source.suffix
        stem = source.name[: -len(suffix)] if suffix else source.name
        parent = source.parent
        index = 1
        while True:
            extra = "" if index == 1 else f"-{index}"
            conflict_name = f"{stem}.backupflow-conflict-{side}-s{session_id}{extra}{suffix}"
            candidate = (parent / conflict_name).as_posix() if str(parent) != "." else conflict_name
            if not (profile.local_path / candidate).exists() and not (profile.external_path / candidate).exists():
                return candidate
            index += 1


class _ConflictResolutionResult:
    def __init__(self, success: bool, bytes_copied: int, events: tuple[str, ...]) -> None:
        self.success = success
        self.bytes_copied = bytes_copied
        self.events = events
