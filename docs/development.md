# Розробка

Цей документ описує локальний запуск, перевірки й корисні debug-команди для BackupFlow.

## Структура Проєкту

```text
apps/backend
apps/desktop
apps/desktop/src-tauri
docs
start-macos.command
start-windows.bat
```

Основні частини:

- `apps/backend` - Python backend, CLI, sync engine, SQLite repositories;
- `apps/desktop` - React + TypeScript UI;
- `apps/desktop/src-tauri` - Tauri desktop shell;
- `docs` - документація;
- `start-macos.command` і `start-windows.bat` - development launcher-и.

## Нормальний Development-Запуск

На macOS:

```text
start-macos.command
```

На Windows:

```text
start-windows.bat
```

Launcher-и створюють `.venv` у корені репозиторію і запускають backend через локальний Python:

```text
.venv/bin/python
.venv\Scripts\python.exe
```

Не встановлюй Python-залежності BackupFlow глобально через `pip install`.

## Backend

Ручні backend-команди:

```bash
cd apps/backend
python3 -m compileall backupflow tests
python3 -m pytest tests
python3 -m backupflow init-db
python3 -m backupflow list-profiles
python3 -m backupflow create-profile Demo /path/to/local /path/to/external
python3 -m backupflow analyze PROFILE_ID
python3 -m backupflow sync PROFILE_ID
python3 -m backupflow serve
```

Для ізольованої бази:

```bash
BACKUPFLOW_DB_PATH=/tmp/backupflow-dev.sqlite3 python3 -m backupflow serve
```

## Desktop

Ручний запуск frontend/Tauri:

```bash
cd apps/desktop
npm install
npm run build
npm run tauri dev
```

Tauri dev server показує локальну адресу Vite, зазвичай:

```text
http://localhost:1420/
```

Backend слухає `127.0.0.1`, починаючи з порту `8765`, і може перейти на fallback-порти:

```text
8765
18765
28765
38765
48765
```

Frontend перевіряє ці порти через `/health` і підключається до доступного backend-а.

## API Для UI

Профілі:

```text
GET    /profiles
POST   /profiles
DELETE /profiles/{profile_id}
```

Аналіз:

```text
GET  /analyze?profile_id=...
POST /analyze
GET  /analyze-jobs/{job_id}
POST /analyze-jobs/{job_id}/cancel
```

Синхронізація:

```text
POST /synchronize
GET  /sync-jobs/{job_id}
POST /sync-jobs/{job_id}/cancel
```

`POST /analyze` повертає job snapshot. UI потім polling-ом читає `/analyze-jobs/{job_id}`.

Коли analysis job завершується, результат містить `plan_id`. UI передає цей `plan_id` у `POST /synchronize`, щоб backend не робив аналіз повторно.

## UI Поведінка

Мова інтерфейсу:

- UI-тексти живуть у `apps/desktop/src/i18n.ts`;
- підтримуються `uk` і `en`;
- вибір мови зберігається в `localStorage`;
- backend/CLI/terminal logs не перекладаються;
- український UI отримує `lang="uk"` і окремий font stack у `styles.css`.

Під час активного аналізу або синхронізації:

- кнопки `Analyze` і `Synchronize` заблоковані;
- створення/видалення профілю заблоковане;
- вибір папок заблокований;
- доступна кнопка `Stop`;
- progress panel показує stage, elapsed time, current path, actions і bytes.

Під час scanning/analyzing загальний обсяг роботи може бути невідомий, тому progress bar може бути indeterminate.

## Debug Logs

Scanner і analyzer мають debug-логування через environment variables:

```bash
BACKUPFLOW_SCAN_DEBUG=1 BACKUPFLOW_SCAN_VERBOSE=1 BACKUPFLOW_ANALYZE_DEBUG=1 python3 -m backupflow serve
```

Значення:

- `BACKUPFLOW_SCAN_DEBUG=1` - показує етапи сканування;
- `BACKUPFLOW_SCAN_VERBOSE=1` - показує окремі entries під час сканування;
- `BACKUPFLOW_ANALYZE_DEBUG=1` - показує порівняння і hash/fast-metadata рішення.

На Windows при запуску через `start-windows.bat` backend прихований, а логи пишуться в:

```text
.backupflow\backend.log
.backupflow\backend-error.log
```

## Перевірки Перед Комітом

З кореня репозиторію:

```bash
python3 -m compileall apps/backend/backupflow apps/backend/tests
pytest apps/backend/tests
```

З frontend-папки:

```bash
cd apps/desktop
npm run build
```

З Tauri-папки:

```bash
cd apps/desktop/src-tauri
cargo check
```

Перевірка whitespace у Git diff:

```bash
git diff --check
```

## Git Workflow

Перед змінами:

```bash
git status --short --branch
```

Після перевірок:

```bash
git add ...
git commit -m "Short clear message"
git push
```

Не додавай у Git локальні залежності й runtime-файли:

```text
.venv
.backupflow
apps/desktop/node_modules
apps/desktop/dist
apps/desktop/src-tauri/target
```
