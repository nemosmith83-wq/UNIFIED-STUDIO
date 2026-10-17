@echo off
REM UNIFIED STUDIO - DIRECT START
REM Starts the FastAPI server and serves the web app.

cls
echo.
echo =======================================================================
echo                    UNIFIED STUDIO - Starting
echo     Chat + Comic Forge + Image Lab + Files + Automation
echo =======================================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install from: https://www.python.org/downloads
    pause
    exit /b 1
)

if not exist ".env" (
    echo .env file not found. Creating from .env.example if available...
    if exist ".env.example" copy ".env.example" ".env" >nul
)

if not exist "backend" (
    echo ERROR: backend directory not found.
    echo This script must be run from the UNIFIED_STUDIO directory.
    pause
    exit /b 1
)

echo Checking packages...
python -m pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo ERROR: Package installation failed.
    pause
    exit /b 1
)
echo OK: Packages ready
echo.

echo Checking optional Ollama local AI...
powershell -Command "try { $null = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2 -ErrorAction Stop; Write-Host 'OK: Ollama is connected' } catch { Write-Host 'WARNING: Ollama is not running. Chat may show an Ollama message, but the app will still start.' }"
echo.

set UNIFIED_PORT=5000
set UNIFIED_HOST=127.0.0.1

echo Starting FastAPI server on http://%UNIFIED_HOST%:%UNIFIED_PORT%
echo.

powershell -Command "if (Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if not errorlevel 1 (
    echo Port 5000 is already in use. Unified Studio may already be running.
    echo Open: http://localhost:5000
    pause
    exit /b 0
)

echo Server output:
echo -----------------------------------------------------------------------
echo.

cd /d backend
python -m uvicorn server:app --host %UNIFIED_HOST% --port %UNIFIED_PORT% --log-level warning

echo.
echo -----------------------------------------------------------------------
echo.
echo Server stopped.
pause
