from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backupflow.config.defaults import DEFAULT_EXCLUSIONS
from backupflow.core.models import FileRecord, FileSide, Profile, StoredFileMetadata


class ProfileRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create(
        self,
        name: str,
        local_path: Path,
        external_path: Path,
        exclude_rules: tuple[str, ...] = DEFAULT_EXCLUSIONS,
        strict_verification: bool = False,
    ) -> Profile:
        self._validate_profile_input(name, local_path, external_path)
        cursor = self.connection.execute(
            """
            INSERT INTO profiles (name, local_path, external_path, exclude_rules, strict_verification)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                str(local_path),
                str(external_path),
                json.dumps(list(exclude_rules)),
                int(strict_verification),
            ),
        )
        self.connection.commit()
        profile = self.get(cursor.lastrowid)
        if profile is None:
            raise RuntimeError("Profile was inserted but could not be loaded.")
        return profile

    def get(self, profile_id: int) -> Profile | None:
        row = self.connection.execute(
            "SELECT * FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def list(self) -> list[Profile]:
        rows = self.connection.execute("SELECT * FROM profiles ORDER BY name").fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, profile_id: int) -> bool:
        cursor = self.connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    def _validate_profile_input(self, name: str, local_path: Path, external_path: Path) -> None:
        if not name.strip():
            raise ValueError("Profile name is required.")
        if not local_path.exists() or not local_path.is_dir():
            raise ValueError(f"Local path must be an existing folder: {local_path}")
        if not external_path.exists() or not external_path.is_dir():
            raise ValueError(f"External path must be an existing folder: {external_path}")
        if local_path.resolve() == external_path.resolve():
            raise ValueError("Local and external folders must be different.")

    def _from_row(self, row: sqlite3.Row) -> Profile:
        return Profile(
            id=row["id"],
            name=row["name"],
            local_path=Path(row["local_path"]),
            external_path=Path(row["external_path"]),
            exclude_rules=tuple(json.loads(row["exclude_rules"])),
            strict_verification=bool(row["strict_verification"]),
        )


class FileMetadataRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_for_profile(self, profile_id: int) -> dict[tuple[str, FileSide], StoredFileMetadata]:
        rows = self.connection.execute(
            """
            SELECT relative_path, side, size, modified_ns, hash_xx64
            FROM file_metadata
            WHERE profile_id = ? AND deleted_at IS NULL
            """,
            (profile_id,),
        ).fetchall()
        result: dict[tuple[str, FileSide], StoredFileMetadata] = {}
        for row in rows:
            side = FileSide(row["side"])
            metadata = StoredFileMetadata(
                relative_path=row["relative_path"],
                side=side,
                size=row["size"],
                modified_ns=row["modified_ns"],
                hash_xx64=row["hash_xx64"],
            )
            result[(metadata.relative_path, side)] = metadata
        return result

    def replace_for_profile(self, profile_id: int, records: list[FileRecord]) -> None:
        self.connection.execute("DELETE FROM file_metadata WHERE profile_id = ?", (profile_id,))
        self.connection.executemany(
            """
            INSERT INTO file_metadata (profile_id, relative_path, side, size, modified_ns, hash_xx64)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    profile_id,
                    record.relative_path,
                    record.side,
                    record.size,
                    record.modified_ns,
                    record.hash_xx64,
                )
                for record in records
            ],
        )
        self.connection.commit()


class SyncSessionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create(self, profile_id: int, status: str) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO sync_sessions (profile_id, status)
            VALUES (?, ?)
            """,
            (profile_id, status),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finish(
        self,
        session_id: int,
        status: str,
        copied_count: int,
        updated_count: int,
        ignored_count: int,
        conflict_count: int,
        error_count: int,
        total_bytes: int,
    ) -> None:
        self.connection.execute(
            """
            UPDATE sync_sessions
            SET finished_at = CURRENT_TIMESTAMP,
                status = ?,
                copied_count = ?,
                updated_count = ?,
                ignored_count = ?,
                conflict_count = ?,
                error_count = ?,
                total_bytes = ?
            WHERE id = ?
            """,
            (
                status,
                copied_count,
                updated_count,
                ignored_count,
                conflict_count,
                error_count,
                total_bytes,
                session_id,
            ),
        )
        self.connection.commit()

    def add_event(
        self,
        session_id: int,
        event_type: str,
        relative_path: str | None,
        message: str,
        source_path: str | None = None,
        destination_path: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO sync_events (
                session_id,
                event_type,
                relative_path,
                source_path,
                destination_path,
                message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, event_type, relative_path, source_path, destination_path, message),
        )
        self.connection.commit()


class ConflictRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create(
        self,
        session_id: int,
        relative_path: str,
        local_modified_ns: int,
        external_modified_ns: int,
        local_size: int,
        external_size: int,
        resolution: str | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO conflicts (
                session_id,
                relative_path,
                local_modified_ns,
                external_modified_ns,
                local_size,
                external_size,
                resolution,
                resolved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CASE WHEN ? IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END)
            """,
            (
                session_id,
                relative_path,
                local_modified_ns,
                external_modified_ns,
                local_size,
                external_size,
                resolution,
                resolution,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)
