# BackupFlow Architecture

BackupFlow is split into five layers:

1. Desktop UI: React and TypeScript.
2. Desktop shell: Tauri.
3. Backend process: Python 3.12+.
4. Sync engine: pure Python domain logic plus OS adapters.
5. Persistence: SQLite.

The first production principle is data safety. Analyze mode always creates a synchronization plan before any file operation is executed. Destructive operations are not permanent; future delete handling will move files into `.BackupFlowTrash/`.

## Runtime Communication

The development launcher starts the Python backend on `127.0.0.1:8765` and then opens the Tauri desktop shell. React calls the local backend over HTTP and polls long-running analyze/sync jobs for progress.

The Python backend is also exposed through a CLI so the sync core can be compiled, tested, and smoke-tested without opening the desktop shell.
