from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from backupflow.config.defaults import DEFAULT_DB_PATH


def get_db_path() -> Path:
    override = os.environ.get("BACKUPFLOW_DB_PATH")
    return Path(override).expanduser() if override else DEFAULT_DB_PATH


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection

