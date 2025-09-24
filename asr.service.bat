@echo off
REM ASR Pipeline Windows Service Runner
REM This script runs the ASR service (does not install dependencies)
REM Use install_windows.bat for first-time installation

REM Get current directory
set "ASR_DIR=%~dp0"
set "ASR_DIR=%ASR_DIR:~0,-1%"

REM Change to ASR directory
cd /d "%ASR_DIR%"

REM Check if virtual environment exists
if not exist "%ASR_DIR%\.venv" (
    echo ERROR: Virtual environment not found
    echo Please run install_windows.bat first to set up the environment
    exit /b 1
)

REM Check if required files exist
if not exist "%ASR_DIR%\src\asr_service.py" (
    echo ERROR: src\asr_service.py not found in %ASR_DIR%
    exit /b 1
)

REM Create logs and audios directories if they don't exist
if not exist "%ASR_DIR%\logs" mkdir "%ASR_DIR%\logs"
if not exist "%ASR_DIR%\audios" mkdir "%ASR_DIR%\audios"

REM Run the ASR service using uv
echo Starting ASR Pipeline service...
echo Logs will be written to: %ASR_DIR%\logs\
echo Press Ctrl+C to stop the service

uv run "%ASR_DIR%\src\asr_service.py"
