@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%apps\backend"
set "DESKTOP_DIR=%SCRIPT_DIR%apps\desktop"

echo Starting BackupFlow...

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if %ERRORLEVEL% NEQ 0 (
    echo Python 3.12+ is required.
    pause
    exit /b 1
  )
  set "PYTHON_CMD=python"
)

where npm >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  echo Node.js and npm are required.
  pause
  exit /b 1
)

where cargo >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  echo Rust/Cargo is required for Tauri development mode.
  pause
  exit /b 1
)

if not exist "%DESKTOP_DIR%\node_modules" (
  echo Installing desktop dependencies...
  pushd "%DESKTOP_DIR%"
  call npm install
  if %ERRORLEVEL% NEQ 0 (
    popd
    pause
    exit /b 1
  )
  popd
)

echo Starting backend...
start "BackupFlow Backend" /D "%BACKEND_DIR%" cmd /k "%PYTHON_CMD% -m backupflow serve"

echo Opening BackupFlow desktop window...
pushd "%DESKTOP_DIR%"
call npm run tauri dev
set "TAURI_EXIT=%ERRORLEVEL%"
popd

echo.
echo Close the "BackupFlow Backend" window when you are done.
pause
exit /b %TAURI_EXIT%
