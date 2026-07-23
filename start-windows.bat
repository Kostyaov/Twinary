@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%apps\backend"
set "DESKTOP_DIR=%SCRIPT_DIR%apps\desktop"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "LOCAL_STATE_DIR=%SCRIPT_DIR%.backupflow"
set "BACKEND_LOG=%LOCAL_STATE_DIR%\backend.log"
set "BACKEND_ERR_LOG=%LOCAL_STATE_DIR%\backend-error.log"
set "BACKEND_PID_FILE=%LOCAL_STATE_DIR%\backend.pid"

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

if not exist "%VENV_PYTHON%" (
  echo Creating local Python virtual environment...
  %PYTHON_CMD% -m venv "%VENV_DIR%"
  if %ERRORLEVEL% NEQ 0 (
    echo Failed to create Python virtual environment.
    pause
    exit /b 1
  )
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
if not exist "%LOCAL_STATE_DIR%" mkdir "%LOCAL_STATE_DIR%"
if exist "%BACKEND_LOG%" del /q "%BACKEND_LOG%" >nul 2>nul
if exist "%BACKEND_ERR_LOG%" del /q "%BACKEND_ERR_LOG%" >nul 2>nul
if exist "%BACKEND_PID_FILE%" del /q "%BACKEND_PID_FILE%" >nul 2>nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $process = Start-Process -FilePath $env:VENV_PYTHON -ArgumentList @('-m','backupflow','serve') -WorkingDirectory $env:BACKEND_DIR -WindowStyle Hidden -RedirectStandardOutput $env:BACKEND_LOG -RedirectStandardError $env:BACKEND_ERR_LOG -PassThru; Set-Content -Path $env:BACKEND_PID_FILE -Value $process.Id"
if %ERRORLEVEL% NEQ 0 (
  echo Failed to start BackupFlow backend.
  echo See logs:
  echo %BACKEND_LOG%
  echo %BACKEND_ERR_LOG%
  pause
  exit /b 1
)

echo Opening BackupFlow desktop window...
pushd "%DESKTOP_DIR%"
call npm run tauri dev
set "TAURI_EXIT=%ERRORLEVEL%"
popd

echo.
echo Stopping BackupFlow backend...
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path $env:BACKEND_PID_FILE) { $backendPid = [int](Get-Content $env:BACKEND_PID_FILE | Select-Object -First 1); if (Get-Process -Id $backendPid -ErrorAction SilentlyContinue) { Stop-Process -Id $backendPid -Force }; Remove-Item $env:BACKEND_PID_FILE -Force -ErrorAction SilentlyContinue }"
if %TAURI_EXIT% NEQ 0 (
  echo BackupFlow exited with an error. Backend logs:
  echo %BACKEND_LOG%
  echo %BACKEND_ERR_LOG%
)
pause
exit /b %TAURI_EXIT%
