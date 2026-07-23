# BackupFlow

BackupFlow is a cross-platform desktop app for safely synchronizing a primary computer folder with an external drive folder.

Version: `1.0.0`

## What It Does

- creates synchronization profiles for local and external folders
- lets you choose folders with the native file picker
- analyzes both folder trees before copying anything
- reuses a prepared analyze plan when you press Synchronize after Analyze
- copies files in both directions with native tools: `rsync` on macOS and `robocopy` on Windows
- keeps both versions when both sides changed, instead of silently overwriting data
- tracks sync sessions and file metadata in SQLite
- shows long-running analyze/sync progress in the desktop UI
- supports cancelling long analyze and sync jobs
- ignores common system files such as `.DS_Store`, `Thumbs.db`, `desktop.ini`, and macOS AppleDouble `._*` files
- handles Unicode filename normalization across APFS/exFAT-style filesystem differences
- avoids expensive content hashing for large media files; normal comparison uses file size and modification time

Safety rule: BackupFlow must never silently overwrite conflicting files.

## Launch Desktop Interface

On macOS, double-click:

```text
start-macos.command
```

On Windows, double-click:

```text
start-windows.bat
```

These launchers start the Python backend and open the Tauri desktop interface.

For a beginner-friendly Windows setup guide in Ukrainian, see:

```text
docs/install-windows-uk.md
```

The launchers create and use a local Python virtual environment in `.venv`, so BackupFlow does not install Python packages globally.

## Basic Workflow

1. Click `New profile`.
2. Choose the computer folder and external folder.
3. Click `Analyze` to preview the sync plan.
4. Review the plan summary.
5. Click `Synchronize` to execute the prepared plan.
6. Run `Analyze` again. A clean sync should show `0 changes to sync` unless files changed again.

Deleting a profile removes only BackupFlow settings and history. It does not delete files from synchronized folders.

## Backend Commands

```bash
cd apps/backend
python3 -m backupflow init-db
python3 -m backupflow create-profile "My Projects" /path/to/local /path/to/external
python3 -m backupflow list-profiles
python3 -m backupflow analyze PROFILE_ID
python3 -m backupflow sync PROFILE_ID
python3 -m backupflow serve
```

## Development Checks

From the repository root:

```bash
python3 -m compileall apps/backend/backupflow apps/backend/tests
pytest apps/backend/tests
```

From `apps/desktop`:

```bash
npm run build
```

From `apps/desktop/src-tauri`:

```bash
cargo check
```
