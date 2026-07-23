#!/bin/zsh
set -e

SCRIPT_DIR="${0:A:h}"
BACKEND_DIR="$SCRIPT_DIR/apps/backend"
DESKTOP_DIR="$SCRIPT_DIR/apps/desktop"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "Starting BackupFlow..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.12+ is required."
  read -k 1 "reply?Press any key to close..."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js and npm are required."
  read -k 1 "reply?Press any key to close..."
  exit 1
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "Rust/Cargo is required for Tauri development mode."
  read -k 1 "reply?Press any key to close..."
  exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Creating local Python virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

PYTHON_CMD="$VENV_DIR/bin/python"

if [ ! -d "$DESKTOP_DIR/node_modules" ]; then
  echo "Installing desktop dependencies..."
  cd "$DESKTOP_DIR"
  npm install
fi

cleanup() {
  if [ -n "$BACKEND_PID" ]; then
    echo "Stopping BackupFlow backend..."
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

cd "$BACKEND_DIR"
"$PYTHON_CMD" -m backupflow serve &
BACKEND_PID=$!

echo "Backend started with PID $BACKEND_PID"
echo "Opening BackupFlow desktop window..."

cd "$DESKTOP_DIR"
npm run tauri dev
