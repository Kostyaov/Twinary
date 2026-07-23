# База Даних

BackupFlow використовує SQLite для профілів, metadata файлів, історії синхронізацій і конфліктів.

База за замовчуванням:

```text
~/.backupflow/backupflow.sqlite3
```

На Windows це зазвичай:

```text
C:\Users\<User>\.backupflow\backupflow.sqlite3
```

Для тестів або development-запуску можна задати інший шлях:

```bash
BACKUPFLOW_DB_PATH=/path/to/dev.sqlite3
```

## Таблиці

Поточна schema створює такі таблиці:

- `profiles`
- `external_drives`
- `file_metadata`
- `sync_sessions`
- `sync_events`
- `conflicts`

## profiles

Зберігає профілі синхронізації.

Основні поля:

- `id` - primary key;
- `name` - назва профілю;
- `local_path` - папка на комп'ютері;
- `external_path` - папка на зовнішньому диску;
- `exclude_rules` - JSON/текстовий список виключень;
- `strict_verification` - `0` або `1`;
- `created_at`;
- `updated_at`.

Видалення профілю через UI або API видаляє тільки запис профілю і пов'язані записи в базі. Файли в синхронізованих папках не видаляються.

## external_drives

Зарезервована таблиця для ідентифікації зовнішніх дисків.

Поточна версія вже має schema, але основна логіка профілів зараз працює напряму з `external_path`.

## file_metadata

Зберігає останній відомий стан файлів для кожного профілю.

Основні поля:

- `profile_id`;
- `relative_path`;
- `side` - `local` або `external`;
- `size`;
- `modified_ns`;
- `hash_xx64`;
- `last_seen_at`;
- `deleted_at`.

Є uniqueness rule:

```text
profile_id + relative_path + side
```

Ця таблиця потрібна для:

- визначення, чи змінився файл після останньої синхронізації;
- виявлення ситуацій, коли обидві сторони змінилися;
- зменшення повторних зайвих дій.

## sync_sessions

Один запис на одну синхронізацію.

Основні поля:

- `profile_id`;
- `started_at`;
- `finished_at`;
- `status`;
- `copied_count`;
- `updated_count`;
- `ignored_count`;
- `conflict_count`;
- `error_count`;
- `total_bytes`.

## sync_events

Детальні події всередині sync session.

Приклади event types:

- copied;
- updated;
- skipped;
- conflict;
- error.

Основні поля:

- `session_id`;
- `event_type`;
- `relative_path`;
- `source_path`;
- `destination_path`;
- `message`;
- `created_at`.

UI використовує summary і events, щоб показати, що саме зробила синхронізація.

## conflicts

Зберігає інформацію про файли, де обидві сторони змінилися.

Основні поля:

- `session_id`;
- `relative_path`;
- `local_modified_ns`;
- `external_modified_ns`;
- `local_size`;
- `external_size`;
- `resolution`;
- `resolved_at`.

У версії `1.1.0` default resolution - `Keep both`.

## Ініціалізація Schema

Schema створюється автоматично під час backend-запуску і перед операціями, які працюють із базою.

CLI-команда:

```bash
cd apps/backend
python3 -m backupflow init-db
```

## Що Не Зберігається В Базі

SQLite не зберігає вміст файлів. Вона зберігає тільки metadata, історію і службову інформацію.

Самі файли залишаються у вибраних користувачем папках:

- `Папка на комп'ютері`;
- `Папка на зовнішньому диску`.
