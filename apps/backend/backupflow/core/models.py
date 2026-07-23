from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class FileSide(StrEnum):
    LOCAL = "local"
    EXTERNAL = "external"


class SyncActionType(StrEnum):
    COPY_LOCAL_TO_EXTERNAL = "copy_local_to_external"
    COPY_EXTERNAL_TO_LOCAL = "copy_external_to_local"
    UPDATE_LOCAL_TO_EXTERNAL = "update_local_to_external"
    UPDATE_EXTERNAL_TO_LOCAL = "update_external_to_local"
    SKIP = "skip"
    IGNORE = "ignore"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class Profile:
    id: int | None
    name: str
    local_path: Path
    external_path: Path
    exclude_rules: tuple[str, ...]
    strict_verification: bool = False


@dataclass(frozen=True)
class FileRecord:
    relative_path: str
    absolute_path: Path
    size: int
    modified_ns: int
    side: FileSide
    hash_xx64: str | None = None


@dataclass(frozen=True)
class StoredFileMetadata:
    relative_path: str
    side: FileSide
    size: int
    modified_ns: int
    hash_xx64: str | None


@dataclass(frozen=True)
class SyncAction:
    action_type: SyncActionType
    relative_path: str
    source: FileSide | None
    destination: FileSide | None
    size: int = 0
    reason: str = ""


@dataclass(frozen=True)
class CopyResult:
    relative_path: str
    success: bool
    command: tuple[str, ...]
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0


@dataclass(frozen=True)
class SyncRunResult:
    session_id: int
    status: str
    copied_count: int
    updated_count: int
    skipped_count: int
    conflict_count: int
    conflicts_resolved_count: int
    error_count: int
    total_bytes: int
    events: tuple[str, ...]


@dataclass
class AnalyzePlan:
    profile: Profile
    actions: list[SyncAction] = field(default_factory=list)
    ignored_count: int = 0

    @property
    def total_bytes(self) -> int:
        return sum(action.size for action in self.actions if action.source is not None)

    def count(self, action_type: SyncActionType) -> int:
        return sum(1 for action in self.actions if action.action_type == action_type)
