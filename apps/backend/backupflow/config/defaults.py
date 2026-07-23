from __future__ import annotations

from pathlib import Path

APP_DIR = Path.home() / ".backupflow"
DEFAULT_DB_PATH = APP_DIR / "backupflow.sqlite3"

DEFAULT_EXCLUSIONS = (
    "node_modules",
    ".venv",
    "venv",
    ".git",
    ".hg",
    "svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".cache",
    ".next",
    ".nuxt",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    "coverage",
    ".idea",
    ".vscode",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
)

LARGE_FILE_BYTES = 5 * 1024 * 1024 * 1024

