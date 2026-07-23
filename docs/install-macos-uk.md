# Встановлення BackupFlow На macOS

Це інструкція для запуску BackupFlow на macOS.

BackupFlow зараз запускається як development-застосунок: Python backend стартує локально, а Tauri відкриває desktop-вікно. Це ще не `.app`-інсталятор, але вже зручний спосіб запуску програми з репозиторію.

## Що Потрібно Встановити

Глобально потрібні тільки базові інструменти:

- Git;
- Python 3.12 або новіший;
- Node.js LTS;
- Rust;
- Xcode Command Line Tools.

Python-бібліотеки BackupFlow встановлюються не глобально, а в локальне середовище:

```text
Twinary/.venv
```

Node.js залежності встановлюються локально:

```text
Twinary/apps/desktop/node_modules
```

## 1. Встановити Xcode Command Line Tools

Відкрий Terminal і виконай:

```bash
xcode-select --install
```

Якщо macOS скаже, що інструменти вже встановлені, це нормально.

## 2. Встановити Git

Після встановлення Xcode Command Line Tools Git зазвичай уже доступний.

Перевір:

```bash
git --version
```

Якщо команда не працює, встанови Git з офіційного сайту:

```text
https://git-scm.com/download/mac
```

## 3. Встановити Python

Перевір поточну версію:

```bash
python3 --version
```

Потрібен Python 3.12 або новіший.

Якщо версія стара або Python не встановлений, встанови актуальну версію з:

```text
https://www.python.org/downloads/macos/
```

Після встановлення відкрий новий Terminal і ще раз перевір:

```bash
python3 --version
```

## 4. Встановити Node.js

Встанови LTS-версію з:

```text
https://nodejs.org/
```

Після встановлення відкрий новий Terminal і перевір:

```bash
node --version
npm --version
```

## 5. Встановити Rust

Відкрий:

```text
https://rustup.rs/
```

Або виконай у Terminal команду, яку пропонує сайт rustup.

Після встановлення відкрий новий Terminal і перевір:

```bash
cargo --version
rustc --version
```

## 6. Завантажити BackupFlow З GitHub

Перейди в папку, де хочеш зберігати проєкт. Наприклад:

```bash
cd ~/Documents
```

Склонуй репозиторій:

```bash
git clone https://github.com/Kostyaov/Twinary.git
```

Перейди в папку:

```bash
cd Twinary
```

## 7. Запустити BackupFlow

Найпростіший спосіб:

1. Відкрий папку `Twinary` у Finder.
2. Двічі клацни:
   ```text
   start-macos.command
   ```

Якщо macOS не дозволяє запуск через подвійний клік, відкрий Terminal у папці проєкту й виконай:

```bash
chmod +x start-macos.command
./start-macos.command
```

Перший запуск може тривати довше. Launcher:

- створить `.venv`;
- встановить frontend-залежності в `apps/desktop/node_modules`;
- запустить Python backend;
- відкриє desktop-вікно BackupFlow.

На macOS backend працює в тому ж Terminal-вікні, з якого запущений launcher. Коли ти закриєш BackupFlow або зупиниш launcher, backend буде зупинений автоматично.

## 8. Перший Профіль Синхронізації

За замовчуванням BackupFlow відкривається українською. Якщо потрібна англійська, зміни мову в лівій панелі в блоці `Мова інтерфейсу`.

1. Натисни `Новий профіль`.
2. Введи назву профілю.
3. Обери `Папка на комп'ютері` кнопкою з іконкою папки.
4. Обери `Папка на зовнішньому диску` кнопкою з іконкою папки.
5. За потреби увімкни `Сувора перевірка`.
6. Натисни `Зберегти`.
7. Натисни `Аналіз`.
8. Перевір `План синхронізації`.
9. Натисни `Синхронізувати`.
10. Після завершення знову натисни `Аналіз`.

Якщо папки синхронізовані, програма має показати:

```text
0 changes to sync
```

## 9. Strict Verification

В українському інтерфейсі ця опція називається `Сувора перевірка`. В англійському - `Strict verification`.

Звичайний режим порівнює файли за шляхом, розміром і датою редагування.

`Сувора перевірка` додатково може рахувати хеш вмісту для малих не-медійних файлів, якщо розмір однаковий, а дата редагування різна.

Великі файли, відео, аудіо, архіви й образи дисків не хешуються навіть у strict-режимі, щоб аналіз не ставав занадто повільним.

## 10. Де Зберігаються Налаштування

Профілі, metadata і історія синхронізації:

```text
~/.backupflow/backupflow.sqlite3
```

Локальні залежності проєкту:

```text
Twinary/.venv
Twinary/apps/desktop/node_modules
```

## 11. Як Оновити Програму

1. Закрий BackupFlow.
2. Відкрий Terminal.
3. Перейди в папку проєкту:
   ```bash
   cd ~/Documents/Twinary
   ```
4. Завантаж оновлення:
   ```bash
   git pull
   ```
5. Запусти:
   ```bash
   ./start-macos.command
   ```

Якщо проєкт лежить не в `~/Documents/Twinary`, заміни шлях у команді `cd`.

## 12. Типові Проблеми

### `Python 3.12+ is required`

Python не встановлений або команда `python3` недоступна.

Перевір:

```bash
python3 --version
```

### `Node.js and npm are required`

Node.js не встановлений або Terminal відкритий до встановлення Node.js.

Встанови Node.js LTS, відкрий новий Terminal і перевір:

```bash
npm --version
```

### `Rust/Cargo is required`

Rust не встановлений або `cargo` ще не доступний у PATH.

Перевір:

```bash
cargo --version
```

### macOS блокує запуск `.command`

Якщо файл не запускається подвійним кліком, запусти його з Terminal:

```bash
chmod +x start-macos.command
./start-macos.command
```

### Перше відкриття довге

Це нормально: встановлюються Node.js залежності й компілюється Tauri development-застосунок.

### Backend не підключається

BackupFlow пробує порти:

```text
8765
18765
28765
38765
48765
```

Якщо один порт зайнятий, backend спробує наступний, а desktop-інтерфейс сам знайде доступний backend.

## 13. Що Не Варто Робити

- Не запускай `pip install` глобально для BackupFlow.
- Не синхронізуй саму папку `Twinary`.
- Не створюй профіль, де `Папка на комп'ютері` і `Папка на зовнішньому диску` вказують на одну й ту саму папку.
- Не видаляй `.venv` і `node_modules`, якщо не хочеш перевстановлювати залежності.
