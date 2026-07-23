# Database Schema

SQLite stores user profiles, drive identity, file metadata, sync sessions, events, and conflicts.

The first increment creates these tables:

- `profiles`
- `external_drives`
- `file_metadata`
- `sync_sessions`
- `sync_events`
- `conflicts`

The database is stored at `~/.backupflow/backupflow.sqlite3` by default. Tests and development commands may override this with `BACKUPFLOW_DB_PATH`.

