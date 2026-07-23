from __future__ import annotations

import os
import fnmatch
import sys
import time
import unicodedata
from pathlib import Path
from typing import Callable

from backupflow.core.models import FileRecord, FileSide

SYSTEM_EXCLUSIONS = (".DS_Store", "Thumbs.db", "desktop.ini", "._*")


class FolderScanner:
    def scan(
        self,
        root: Path,
        side: FileSide,
        exclude_rules: tuple[str, ...],
        progress_callback: Callable[[dict], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[dict[str, FileRecord], int]:
        if not root.exists():
            raise FileNotFoundError(f"Folder does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Path is not a folder: {root}")

        excluded = (*exclude_rules, *SYSTEM_EXCLUSIONS)
        records: dict[str, FileRecord] = {}
        ignored_count = 0
        scanned_count = 0
        debug_enabled = os.environ.get("BACKUPFLOW_SCAN_DEBUG") == "1"
        debug_verbose = os.environ.get("BACKUPFLOW_SCAN_VERBOSE") == "1"

        self._ensure_not_cancelled(should_cancel)
        self._debug(debug_enabled, f"start side={side.value} root={root}")

        pending_directories = [root]
        while pending_directories:
            self._ensure_not_cancelled(should_cancel)
            current_path = pending_directories.pop()
            relative_current_path = current_path.relative_to(root).as_posix() if current_path != root else "."
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "analyzing",
                        "message": f"Opening {side.value} folder: {scanned_count} files found.",
                        "current_path": relative_current_path,
                        "processed_actions": 0,
                        "total_actions": 0,
                        "bytes_done": 0,
                    }
                )

            open_started_at = time.monotonic()
            self._debug(debug_enabled, f"open side={side.value} path={current_path}")
            try:
                with os.scandir(current_path) as iterator:
                    entries = sorted(iterator, key=lambda entry: entry.name.lower())
            except OSError as error:
                self._debug(debug_enabled, f"open failed side={side.value} path={current_path} error={error}")
                ignored_count += 1
                continue
            open_elapsed = time.monotonic() - open_started_at
            self._debug(
                debug_enabled,
                f"opened side={side.value} entries={len(entries)} elapsed={open_elapsed:.3f}s path={current_path}",
            )

            next_directories: list[Path] = []
            for entry in entries:
                self._ensure_not_cancelled(should_cancel)
                entry_started_at = time.monotonic()
                self._debug(debug_verbose, f"entry side={side.value} path={entry.path}")
                if self._is_excluded(entry.name, excluded):
                    ignored_count += 1
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        next_directories.append(Path(entry.path))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        ignored_count += 1
                        continue
                    stat = entry.stat(follow_symlinks=False)
                except OSError:
                    ignored_count += 1
                    continue
                entry_elapsed = time.monotonic() - entry_started_at
                if entry_elapsed >= 0.5:
                    self._debug(
                        debug_enabled,
                        f"slow entry side={side.value} elapsed={entry_elapsed:.3f}s path={entry.path}",
                    )
                absolute_path = Path(entry.path)
                relative_path = self._normalize_relative_path(absolute_path.relative_to(root).as_posix())
                records[relative_path] = FileRecord(
                    relative_path=relative_path,
                    absolute_path=absolute_path,
                    size=stat.st_size,
                    modified_ns=stat.st_mtime_ns,
                    side=side,
                )
                scanned_count += 1
                if progress_callback is not None and scanned_count % 250 == 0:
                    progress_callback(
                        {
                            "stage": "analyzing",
                            "message": f"Scanning {side.value} folder: {scanned_count} files found.",
                            "current_path": relative_path,
                            "processed_actions": 0,
                            "total_actions": 0,
                            "bytes_done": 0,
                        }
                    )
            pending_directories.extend(reversed(next_directories))
            self._debug(
                debug_enabled,
                f"done side={side.value} files={scanned_count} queued_dirs={len(pending_directories)} path={current_path}",
            )

        self._debug(debug_enabled, f"finish side={side.value} files={scanned_count} ignored={ignored_count} root={root}")
        return records, ignored_count

    def _ensure_not_cancelled(self, should_cancel: Callable[[], bool] | None) -> None:
        if should_cancel is not None and should_cancel():
            raise InterruptedError("Operation cancelled.")

    def _is_excluded(self, name: str, exclude_rules: tuple[str, ...]) -> bool:
        return any(fnmatch.fnmatchcase(name, rule) for rule in exclude_rules)

    def _debug(self, enabled: bool, message: str) -> None:
        if enabled:
            print(f"[backupflow-scan] {message}", file=sys.stderr, flush=True)

    def _normalize_relative_path(self, relative_path: str) -> str:
        return unicodedata.normalize("NFC", relative_path)
