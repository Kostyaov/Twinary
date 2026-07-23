from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Protocol

from backupflow.core.models import CopyResult, SyncAction


class CopyAdapter(Protocol):
    def copy_file(self, action: SyncAction, source_path: Path, destination_path: Path) -> CopyResult:
        pass


class NativeCopyAdapter:
    def copy_file(self, action: SyncAction, source_path: Path, destination_path: Path) -> CopyResult:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        system = platform.system()
        if system == "Darwin":
            return self._copy_with_rsync(action, source_path, destination_path)
        if system == "Windows":
            return self._copy_with_robocopy(action, source_path, destination_path)
        raise RuntimeError(f"Unsupported platform for native copy: {system}")

    def _copy_with_rsync(self, action: SyncAction, source_path: Path, destination_path: Path) -> CopyResult:
        command = ("rsync", "-a", "--", str(source_path), str(destination_path))
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        return CopyResult(
            relative_path=action.relative_path,
            success=completed.returncode == 0,
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            return_code=completed.returncode,
        )

    def _copy_with_robocopy(self, action: SyncAction, source_path: Path, destination_path: Path) -> CopyResult:
        command = (
            "robocopy",
            str(source_path.parent),
            str(destination_path.parent),
            source_path.name,
            "/COPY:DAT",
            "/R:1",
            "/W:1",
            "/NFL",
            "/NDL",
        )
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        return CopyResult(
            relative_path=action.relative_path,
            success=completed.returncode <= 7,
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            return_code=completed.returncode,
        )

