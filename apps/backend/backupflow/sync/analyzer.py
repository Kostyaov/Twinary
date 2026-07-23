from __future__ import annotations

import os
import sys
import time
from typing import Callable

from backupflow.core.models import (
    AnalyzePlan,
    FileRecord,
    FileSide,
    Profile,
    StoredFileMetadata,
    SyncAction,
    SyncActionType,
)
from backupflow.sync.hasher import xxhash64
from backupflow.sync.scanner import FolderScanner

STRICT_HASH_SIZE_LIMIT_BYTES = 100 * 1024 * 1024
MODIFIED_TIME_TOLERANCE_NS = 100 * 1_000_000
FAST_METADATA_EXTENSIONS = {
    ".3gp",
    ".7z",
    ".aac",
    ".aiff",
    ".avi",
    ".bak",
    ".bin",
    ".bz2",
    ".dmg",
    ".flac",
    ".gz",
    ".iso",
    ".m2ts",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".rar",
    ".tar",
    ".tgz",
    ".wav",
    ".webm",
    ".wmv",
    ".zip",
}


class SyncAnalyzer:
    def __init__(
        self,
        scanner: FolderScanner | None = None,
        progress_callback: Callable[[dict], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        self.scanner = scanner or FolderScanner()
        self.progress_callback = progress_callback
        self.should_cancel = should_cancel
        self.debug_enabled = os.environ.get("BACKUPFLOW_ANALYZE_DEBUG") == "1"

    def analyze(
        self,
        profile: Profile,
        previous_metadata: dict[tuple[str, FileSide], StoredFileMetadata] | None = None,
    ) -> AnalyzePlan:
        previous_metadata = previous_metadata or {}
        local_files, local_ignored = self.scanner.scan(
            profile.local_path,
            FileSide.LOCAL,
            profile.exclude_rules,
            self.progress_callback,
            self.should_cancel,
        )
        external_files, external_ignored = self.scanner.scan(
            profile.external_path,
            FileSide.EXTERNAL,
            profile.exclude_rules,
            self.progress_callback,
            self.should_cancel,
        )

        plan = AnalyzePlan(profile=profile, ignored_count=local_ignored + external_ignored)
        all_paths = sorted(set(local_files) | set(external_files))
        self._debug(
            f"compare start profile={profile.id} paths={len(all_paths)} strict={profile.strict_verification}"
        )

        for index, relative_path in enumerate(all_paths, start=1):
            self._ensure_not_cancelled()
            if self.progress_callback is not None and (index == 1 or index % 250 == 0):
                self.progress_callback(
                    {
                        "stage": "comparing",
                        "message": f"Comparing files: {index} of {len(all_paths)}.",
                        "current_path": relative_path,
                        "processed_actions": 0,
                        "total_actions": 0,
                        "bytes_done": 0,
                    }
                )
            local = local_files.get(relative_path)
            external = external_files.get(relative_path)
            if local and not external:
                plan.actions.append(
                    SyncAction(
                        SyncActionType.COPY_LOCAL_TO_EXTERNAL,
                        relative_path,
                        FileSide.LOCAL,
                        FileSide.EXTERNAL,
                        local.size,
                        "File exists only on local side.",
                    )
                )
                continue
            if external and not local:
                plan.actions.append(
                    SyncAction(
                        SyncActionType.COPY_EXTERNAL_TO_LOCAL,
                        relative_path,
                        FileSide.EXTERNAL,
                        FileSide.LOCAL,
                        external.size,
                        "File exists only on external side.",
                    )
                )
                continue
            if local is None or external is None:
                continue

            plan.actions.append(self._compare_pair(profile, previous_metadata, local, external))

        self._debug(f"compare finish profile={profile.id} actions={len(plan.actions)}")
        return plan

    def _compare_pair(
        self,
        profile: Profile,
        previous_metadata: dict[tuple[str, FileSide], StoredFileMetadata],
        local: FileRecord,
        external: FileRecord,
    ) -> SyncAction:
        if local.size == external.size and self._modified_times_match(local.modified_ns, external.modified_ns):
            return SyncAction(
                SyncActionType.SKIP,
                local.relative_path,
                None,
                None,
                0,
                "Path, size, and modification time match within filesystem tolerance.",
            )

        if self._changed_on_both_sides(previous_metadata, local, external):
            return SyncAction(
                SyncActionType.CONFLICT,
                local.relative_path,
                None,
                None,
                max(local.size, external.size),
                "Both sides changed since last known metadata.",
            )

        if profile.strict_verification and local.size == external.size and self._should_hash(local):
            self._emit_hash_progress(local.relative_path, local.absolute_path, "local", local.size)
            local_started_at = time.monotonic()
            local_hash = xxhash64(local.absolute_path, should_cancel=self.should_cancel)
            self._debug(
                f"hash done side=local elapsed={time.monotonic() - local_started_at:.3f}s path={local.absolute_path}"
            )
            self._ensure_not_cancelled()
            self._emit_hash_progress(external.relative_path, external.absolute_path, "external", external.size)
            external_started_at = time.monotonic()
            external_hash = xxhash64(external.absolute_path, should_cancel=self.should_cancel)
            self._debug(
                f"hash done side=external elapsed={time.monotonic() - external_started_at:.3f}s path={external.absolute_path}"
            )
            if local_hash == external_hash:
                return SyncAction(
                    SyncActionType.SKIP,
                    local.relative_path,
                    None,
                    None,
                    0,
                    "Content hash matches despite different modification time.",
                )
        elif profile.strict_verification and local.size == external.size:
            self._debug(
                f"hash skipped reason=fast-metadata size={local.size} path={local.relative_path}"
            )

        if local.modified_ns >= external.modified_ns:
            return SyncAction(
                SyncActionType.UPDATE_LOCAL_TO_EXTERNAL,
                local.relative_path,
                FileSide.LOCAL,
                FileSide.EXTERNAL,
                local.size,
                "Local version is newer.",
            )

        return SyncAction(
            SyncActionType.UPDATE_EXTERNAL_TO_LOCAL,
            external.relative_path,
            FileSide.EXTERNAL,
            FileSide.LOCAL,
            external.size,
            "External version is newer.",
        )

    def _changed_on_both_sides(
        self,
        previous_metadata: dict[tuple[str, FileSide], StoredFileMetadata],
        local: FileRecord,
        external: FileRecord,
    ) -> bool:
        previous_local = previous_metadata.get((local.relative_path, FileSide.LOCAL))
        previous_external = previous_metadata.get((external.relative_path, FileSide.EXTERNAL))
        if previous_local is None or previous_external is None:
            return False

        local_changed = self._metadata_changed(local.size, local.modified_ns, previous_local)
        external_changed = self._metadata_changed(external.size, external.modified_ns, previous_external)
        return local_changed and external_changed

    def _ensure_not_cancelled(self) -> None:
        if self.should_cancel is not None and self.should_cancel():
            raise InterruptedError("Operation cancelled.")

    def _metadata_changed(self, size: int, modified_ns: int, previous: StoredFileMetadata) -> bool:
        return size != previous.size or not self._modified_times_match(modified_ns, previous.modified_ns)

    def _modified_times_match(self, left_ns: int, right_ns: int) -> bool:
        return abs(left_ns - right_ns) <= MODIFIED_TIME_TOLERANCE_NS

    def _should_hash(self, file_record: FileRecord) -> bool:
        if file_record.size > STRICT_HASH_SIZE_LIMIT_BYTES:
            return False
        return file_record.absolute_path.suffix.lower() not in FAST_METADATA_EXTENSIONS

    def _emit_hash_progress(self, relative_path: str, absolute_path, side: str, size: int) -> None:
        self._debug(f"hash start side={side} size={size} path={absolute_path}")
        if self.progress_callback is not None:
            self.progress_callback(
                {
                    "stage": "hashing",
                    "message": f"Strict verification is hashing {side} file.",
                    "current_path": relative_path,
                    "processed_actions": 0,
                    "total_actions": 0,
                    "bytes_done": 0,
                }
            )

    def _debug(self, message: str) -> None:
        if self.debug_enabled:
            print(f"[backupflow-analyze] {message}", file=sys.stderr, flush=True)
