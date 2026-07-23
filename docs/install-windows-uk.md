# Встановлення BackupFlow на Windows

Це інструкція для встановлення BackupFlow на новий Windows-комп'ютер.

BackupFlow поки запускається як development-застосунок: окремо стартує Python backend і Tauri desktop-вікно. Це ще не `.exe`-інсталятор, але вже нормальний спосіб запустити програму з GitHub.

## Що буде встановлено

Глобально в систему потрібно встановити тільки базові інструменти:

- Git
- Python 3.12 або новіший
- Node.js LTS
- Rust

Python-бібліотеки BackupFlow не встановлюються глобально. Скрипт запуску створює локальне середовище:

```text
Twinary\.venv
```

Тобто Python-частина ізольована всередині папки проєкту і не засмічує системний Python.

Node.js залежності також ставляться локально:

```text
Twinary\apps\desktop\node_modules
```

## 1. Встановити Git

1. Відкрий сайт:
   ```text
   https://git-scm.com/download/win
   ```
2. Завантаж інсталятор Git for Windows.
3. Запусти інсталятор.
4. Можна залишати стандартні налаштування.
5. Після встановлення відкрий нове вікно `Command Prompt` або `PowerShell`.
6. Перевір:
   ```bat
   git --version
   ```

Якщо бачиш версію Git, усе добре.

## 2. Встановити Python

1. Відкрий сайт:
   ```text
   https://www.python.org/downloads/windows/
   ```
2. Завантаж Python 3.12 або новіший.
3. На першому екрані інсталятора обов'язково постав галочку:
   ```text
   Add python.exe to PATH
   ```
4. Натисни `Install Now`.
5. Після встановлення відкрий нове вікно `Command Prompt` або `PowerShell`.
6. Перевір:
   ```bat
   py -3 --version
   ```

Якщо команда `py -3` не працює, спробуй:

```bat
python --version
```

Одна з цих команд має показати Python 3.12+.

## 3. Встановити Node.js

1. Відкрий сайт:
   ```text
   https://nodejs.org/
   ```
2. Завантаж LTS-версію.
3. Встанови зі стандартними налаштуваннями.
4. Відкрий нове вікно `Command Prompt` або `PowerShell`.
5. Перевір:
   ```bat
   node --version
   npm --version
   ```

Обидві команди мають показати версії.

## 4. Встановити Rust

Tauri використовує Rust для desktop-оболонки.

1. Відкрий сайт:
   ```text
   https://rustup.rs/
   ```
2. Завантаж `rustup-init.exe`.
3. Запусти його.
4. Коли побачиш меню в терміналі, натисни `1` для стандартної установки.
5. Після завершення закрий термінал і відкрий новий.
6. Перевір:
   ```bat
   cargo --version
   rustc --version
   ```

Якщо команди не знаходяться, перезавантаж комп'ютер і спробуй ще раз.

## 5. Завантажити BackupFlow з GitHub

Відкрий `Command Prompt` або `PowerShell` і перейди в папку, де хочеш тримати програму. Наприклад:

```bat
cd %USERPROFILE%\Documents
```

Склонуй репозиторій:

```bat
git clone https://github.com/Kostyaov/Twinary.git
```

Перейди в папку проєкту:

```bat
cd Twinary
```

## 6. Запустити BackupFlow

Найпростіший спосіб:

1. Відкрий папку `Twinary` у Провіднику Windows.
2. Двічі клацни:
   ```text
   start-windows.bat
   ```

Або запусти з термінала:

```bat
start-windows.bat
```

Перший запуск може тривати довше, бо скрипт:

- створить локальне Python-середовище `.venv`
- встановить desktop-залежності в `apps\desktop\node_modules`
- запустить Python backend
- відкриє Tauri desktop-вікно BackupFlow

Після запуску зазвичай буде одне головне вікно BackupFlow.

Python backend запускається у фоні без окремого термінального вікна.

Коли завершиш роботу з програмою, закрий головне вікно BackupFlow. Скрипт запуску сам зупинить backend.

## 7. Як перевірити, що `.venv` використовується

Після першого запуску в папці проєкту має з'явитися:

```text
Twinary\.venv
```

Backend запускається командою з цього середовища:

```text
Twinary\.venv\Scripts\python.exe -m backupflow serve
```

Це означає, що Python-запуск ізольований від системного Python.

## 8. Перший профіль синхронізації

1. Натисни `New profile`.
2. Вкажи назву профілю.
3. Для `Computer folder` вибери папку на комп'ютері.
4. Для `External folder` вибери папку на зовнішньому диску.
5. Натисни `Save`.
6. Натисни `Analyze`.
7. Перевір `Sync Plan`.
8. Натисни `Synchronize`.
9. Після завершення знову натисни `Analyze`.

Якщо все синхронізовано, програма має показати:

```text
0 changes to sync
```

## 9. Де зберігаються налаштування

Профілі, metadata і історія синхронізації зберігаються в SQLite-базі:

```text
%USERPROFILE%\.backupflow\backupflow.sqlite3
```

Це не копіюється в GitHub і не лежить у папці проєкту.

## 10. Як оновити програму

1. Закрий BackupFlow.
2. Закрий backend-вікно.
3. Відкрий `Command Prompt` або `PowerShell`.
4. Перейди в папку проєкту:
   ```bat
   cd %USERPROFILE%\Documents\Twinary
   ```
5. Завантаж оновлення:
   ```bat
   git pull
   ```
6. Запусти:
   ```bat
   start-windows.bat
   ```

## 11. Типові проблеми

### `Python 3.12+ is required`

Python не встановлений або не доданий у `PATH`.

Рішення:

- перевстанови Python
- на першому екрані інсталятора постав `Add python.exe to PATH`
- відкрий новий термінал

### `Node.js and npm are required`

Node.js не встановлений або термінал відкритий до встановлення Node.js.

Рішення:

- встанови Node.js LTS
- закрий і відкрий термінал
- перевір `npm --version`

### `Rust/Cargo is required`

Rust не встановлений або `cargo` ще не доступний у PATH.

Рішення:

- встанови Rust через `rustup.rs`
- закрий і відкрий термінал
- якщо не допомогло, перезавантаж Windows

### Windows попереджає про запуск `.bat`

Це нормальне попередження для скриптів, завантажених з інтернету. Якщо файл взятий з твого GitHub-репозиторію, можна дозволити запуск.

### Перше відкриття довге

Це нормально. Перший запуск встановлює Node.js залежності й компілює Tauri dev-застосунок.

### `PermissionError: [WinError 10013]`

Це означає, що Windows заборонив backend-у зайняти порт `127.0.0.1:8765`.

BackupFlow автоматично пробує резервні порти:

```text
18765
28765
38765
48765
```

Desktop-інтерфейс сам шукає backend на цих портах. Якщо в логах є повідомлення `port_unavailable`, але потім `listening` на іншому порту, це нормально.

Backend-вікно приховане. Логи можна подивитися тут:

```text
Twinary\.backupflow\backend.log
Twinary\.backupflow\backend-error.log
```

## 12. Що не варто робити

- Не запускай `pip install` глобально для BackupFlow.
- Не видаляй `.venv`, якщо не хочеш пересоздавати Python-середовище.
- Не видаляй `apps\desktop\node_modules`, якщо не хочеш перевстановлювати frontend-залежності.
- Не створюй профіль, де local і external вказують на одну й ту саму папку.
- Не синхронізуй саму папку `Twinary`, якщо в цей момент розробляєш або оновлюєш BackupFlow.
