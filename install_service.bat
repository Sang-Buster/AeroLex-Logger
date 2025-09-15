@echo off
REM ASR Pipeline Windows Service Installation Script
REM This script sets up the ASR service to run automatically on Windows
REM using Task Scheduler for reliability and automatic restart

echo ============================================
echo ASR Pipeline Windows Service Installation
echo ============================================

REM Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script requires Administrator privileges
    echo Right-click and select "Run as Administrator"
    pause
    exit /b 1
)

REM Get current directory
set "ASR_DIR=%~dp0"
set "ASR_DIR=%ASR_DIR:~0,-1%"
echo ASR Directory: %ASR_DIR%

REM Check if uv is available, install if not
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing uv...
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    
    REM Refresh PATH
    call refreshenv >nul 2>&1
    
    REM Check again
    uv --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install uv
        echo Please install manually from: https://github.com/astral-sh/uv
        pause
        exit /b 1
    )
)

echo uv is available

REM Setup Python 3.10 environment
echo Setting up Python 3.10 environment...
uv python install 3.10
echo Python 3.10 is ready

REM Check if required files exist
if not exist "%ASR_DIR%\asr_service.py" (
    echo ERROR: asr_service.py not found in %ASR_DIR%
    pause
    exit /b 1
)

REM Create logs directory
if not exist "%ASR_DIR%\logs" mkdir "%ASR_DIR%\logs"

REM Install dependencies with uv
echo Installing Python dependencies with uv...
echo This may take several minutes...
uv pip install -r "%ASR_DIR%\requirements.txt" --python 3.10
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully

REM Download Whisper model
echo Downloading Whisper model...
echo This may take several minutes depending on internet connection...
uv run --python 3.10 "%ASR_DIR%\download_model.py"
if %errorlevel% neq 0 (
    echo WARNING: Model download may have failed
)

REM Run installation test
echo Running installation test...
uv run --python 3.10 "%ASR_DIR%\test_installation.py"
if %errorlevel% neq 0 (
    echo WARNING: Installation test had issues
)

echo.
echo Creating Windows Task Scheduler entry...

REM Delete existing task if it exists
schtasks /delete /tn "ASR_Pipeline" /f >nul 2>&1

REM Create the scheduled task with uv
schtasks /create /tn "ASR_Pipeline" /tr "uv run --python 3.10 \"%ASR_DIR%\asr_service.py\"" /sc onlogon /ru "SYSTEM" /rl highest /f

if %errorlevel% neq 0 (
    echo ERROR: Failed to create scheduled task
    pause
    exit /b 1
)

REM Configure the task for automatic restart on failure
echo Configuring automatic restart on failure...

REM Export the task to XML for modification
schtasks /query /tn "ASR_Pipeline" /xml > "%TEMP%\asr_task.xml"

REM Create a modified XML with restart settings
(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>ASR Pipeline - Local Speech Recognition Service^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<LogonTrigger^>
echo       ^<Enabled^>true^</Enabled^>
echo     ^</LogonTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<UserId^>S-1-5-18^</UserId^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
echo     ^<RunOnlyIfNetworkAvailable^>false^</RunOnlyIfNetworkAvailable^>
echo     ^<IdleSettings^>
echo       ^<StopOnIdleEnd^>false^</StopOnIdleEnd^>
echo       ^<RestartOnIdle^>false^</RestartOnIdle^>
echo     ^</IdleSettings^>
echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
echo     ^<Enabled^>true^</Enabled^>
echo     ^<Hidden^>false^</Hidden^>
echo     ^<RunOnlyIfIdle^>false^</RunOnlyIfIdle^>
echo     ^<DisallowStartOnRemoteAppSession^>false^</DisallowStartOnRemoteAppSession^>
echo     ^<UseUnifiedSchedulingEngine^>true^</UseUnifiedSchedulingEngine^>
echo     ^<WakeToRun^>false^</WakeToRun^>
echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
echo     ^<Priority^>7^</Priority^>
echo     ^<RestartOnFailure^>
echo       ^<Interval^>PT1M^</Interval^>
echo       ^<Count^>999^</Count^>
echo     ^</RestartOnFailure^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>uv^</Command^>
echo       ^<Arguments^>run --python 3.10 "%ASR_DIR%\asr_service.py"^</Arguments^>
echo       ^<WorkingDirectory^>%ASR_DIR%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%TEMP%\asr_task_modified.xml"

REM Import the modified task
schtasks /delete /tn "ASR_Pipeline" /f >nul 2>&1
schtasks /create /tn "ASR_Pipeline" /xml "%TEMP%\asr_task_modified.xml" /f

if %errorlevel% neq 0 (
    echo WARNING: Failed to configure automatic restart. Task created with basic settings.
)

REM Clean up temporary files
del "%TEMP%\asr_task.xml" >nul 2>&1
del "%TEMP%\asr_task_modified.xml" >nul 2>&1

echo.
echo ============================================
echo Installation completed successfully!
echo ============================================
echo.
echo The ASR Pipeline service has been installed and will:
echo - Start automatically when any user logs in
echo - Restart automatically if it crashes
echo - Run with elevated privileges for hardware access
echo.
echo Management commands:
echo - Start service:  schtasks /run /tn "ASR_Pipeline"
echo - Stop service:   taskkill /f /im python.exe
echo - Remove service: schtasks /delete /tn "ASR_Pipeline" /f
echo - View logs:      type "%ASR_DIR%\logs\asr.out"
echo.
echo The service will start automatically on next logon.
echo To start it now, run: schtasks /run /tn "ASR_Pipeline"
echo.

REM Ask if user wants to start now
set /p start_now="Start the service now? (y/n): "
if /i "%start_now%"=="y" (
    echo Starting ASR Pipeline service...
    schtasks /run /tn "ASR_Pipeline"
    echo Service started. Check logs in %ASR_DIR%\logs\ for status.
)

echo.
echo Installation complete. Press any key to exit.
pause >nul
