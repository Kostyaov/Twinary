# Архітектура BackupFlow

BackupFlow складається з п'яти основних шарів.

1. **Desktop UI** - React і TypeScript.
2. **Desktop shell** - Tauri.
3. **Backend process** - Python 3.12+ HTTP API і CLI.
4. **Sync engine** - Python-логіка аналізу, копіювання, конфліктів і metadata.
5. **Persistence** - SQLite база даних.

Головний принцип архітектури: спочатку аналіз, потім виконання. Програма не має мовчки перезаписувати потенційно конфліктні файли.

## Запуск

Для звичайного development-запуску використовуються launcher-файли в корені репозиторію:

```text
start-macos.command
start-windows.bat
```

Launcher:

- перевіряє наявність Python, Node.js/npm і Rust/Cargo;
- створює локальне Python-середовище `.venv`;
- встановлює frontend-залежності в `apps/desktop/node_modules`;
- запускає Python backend;
- відкриває Tauri desktop-вікно.

На Windows backend запускається приховано, без окремого terminal-вікна. Його stdout/stderr пишуться в:

```text
.backupflow/backend.log
.backupflow/backend-error.log
```

На macOS backend стартує як дочірній процес launcher-а і зупиняється через `trap`, коли launcher завершується.

## Runtime Communication

React UI спілкується з Python backend через локальний HTTP API.

Backend спочатку пробує порт:

```text
127.0.0.1:8765
```

Якщо порт недоступний, він автоматично пробує резервні порти:

```text
18765
28765
38765
48765
```

Frontend також перевіряє ці порти через `/health` і підключається до першого доступного backend-а.

## Backend API

Основні endpoint-и:

```text
GET    /health
GET    /profiles
POST   /profiles
DELETE /profiles/{profile_id}

GET    /analyze?profile_id=...
POST   /analyze
GET    /analyze-jobs/{job_id}
POST   /analyze-jobs/{job_id}/cancel

POST   /synchronize
GET    /sync-jobs/{job_id}
POST   /sync-jobs/{job_id}/cancel
```

`GET /analyze` є синхронним варіантом для простих CLI/smoke сценаріїв.

UI використовує job-based endpoint-и:

- `POST /analyze` стартує analysis job;
- `GET /analyze-jobs/{job_id}` повертає прогрес;
- `POST /analyze-jobs/{job_id}/cancel` просить backend зупинити аналіз;
- `POST /synchronize` стартує sync job;
- `GET /sync-jobs/{job_id}` повертає прогрес синхронізації;
- `POST /sync-jobs/{job_id}/cancel` просить backend зупинити синхронізацію.

Зупинка не завжди миттєва: backend завершує поточну файлову операцію або поточний крок сканування й тільки після цього переходить у `cancelled`.

## Підготовлений Analyze Plan

Після успішного `Analyze` backend повертає `plan_id`.

Коли UI викликає `Synchronize` з цим `plan_id`, backend бере вже підготовлений план і не запускає повний аналіз повторно.

Якщо `plan_id` не переданий, застарів або належить іншому профілю, backend будує новий план перед синхронізацією.

## Sync Engine

Основні частини sync engine:

- `FolderScanner` - сканує дерева папок і збирає metadata файлів;
- `SyncAnalyzer` - порівнює local/external карти файлів і створює план дій;
- `SyncExecutor` - виконує план, копіює файли, фіксує події й оновлює metadata;
- `CopyAdapter` - використовує `rsync` на macOS/Linux і `robocopy` на Windows;
- repositories - читають і пишуть SQLite.

## UI

UI має такі ключові частини:

- sidebar зі списком профілів;
- selector мови інтерфейсу;
- форма створення профілю;
- системний вибір папок для `Computer folder` і `External folder`;
- панель `Folders`;
- панель `Safety`;
- панель `Sync Plan`;
- панель `Progress`;
- журнал останніх подій.

Мова інтерфейсу перемикається на frontend-рівні. Вибір зберігається в `localStorage`. Backend, CLI, JSON API і terminal logs не локалізуються в межах цієї функції.

Тексти UI зібрані у frontend-словниках `uk` і `en`. Кореневий контейнер отримує `lang`, тому CSS може застосовувати мовно-залежну типографіку. Для українського UI використовується окремий system font stack з нативними macOS/Windows шрифтами першими, щоб кирилиця виглядала природніше.

Під час аналізу або синхронізації кнопки `Analyze`, `Synchronize`, створення/видалення профілів і вибір папок блокуються, щоб не запускати кілька довгих операцій одночасно.

## Persistence

SQLite зберігає:

- профілі;
- metadata файлів;
- sync sessions;
- sync events;
- conflicts.

База за замовчуванням:

```text
~/.backupflow/backupflow.sqlite3
```

Для тестів і ізольованого development-запуску можна використовувати:

```bash
BACKUPFLOW_DB_PATH=/path/to/dev.sqlite3
```
