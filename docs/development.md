# Development

## Backend

```bash
cd apps/backend
python3 -m compileall backupflow tests
python3 -m pytest tests
python3 -m backupflow init-db
python3 -m backupflow serve
python3 -m backupflow sync PROFILE_ID
```

Use `BACKUPFLOW_DB_PATH=/path/to/dev.sqlite3` to isolate local smoke tests.

## Desktop

The desktop app is prepared as a Tauri + React application.

Use the root launcher files for normal development startup:

```text
start-macos.command
start-windows.bat
```

Manual startup is still useful while debugging:

```bash
cd apps/desktop
npm install
npm run build
npm run tauri dev
```

In development mode, React expects the Python backend at:

```text
http://127.0.0.1:8765
```

Profiles can be created from the UI with `New profile`. Use the folder buttons to select local and external folders with the system picker, or type paths manually. Profiles can also be created through the backend CLI:

```bash
cd apps/backend
python3 -m backupflow create-profile Demo /path/to/local /path/to/external
```

Deleting a profile from the UI removes the profile, metadata, and history rows from SQLite. It never deletes synchronized files from the local or external folders.

Synchronization from the UI runs as a backend job:

```text
GET /analyze?profile_id=...
POST /analyze
GET /analyze-jobs/{job_id}
POST /analyze-jobs/{job_id}/cancel
POST /synchronize
GET /sync-jobs/{job_id}
POST /sync-jobs/{job_id}/cancel
```

The progress panel polls the analyze/sync job endpoints and shows the current stage, elapsed time, current path, processed actions, and copied bytes. During scanning/analyzing, the total amount of work may be unknown, so the UI shows an indeterminate progress animation instead of a fixed percentage.

Analyze responses include a `plan_id`. When the UI calls `POST /synchronize` with that `plan_id`, the backend uses the prepared plan instead of running analysis again. If no valid `plan_id` is supplied, synchronization falls back to building a fresh plan.

Scanner and analyzer debug logs can be enabled temporarily:

```bash
BACKUPFLOW_SCAN_DEBUG=1 BACKUPFLOW_SCAN_VERBOSE=1 BACKUPFLOW_ANALYZE_DEBUG=1 python3 -m backupflow serve
```
