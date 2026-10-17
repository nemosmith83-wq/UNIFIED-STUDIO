@echo off
REM UNIFIED STUDIO - ONE-BUTTON START
REM Installs/checks dependencies, creates .env if missing, starts the server, opens browser.

cls
setlocal enabledelayedexpansion

echo.
echo =======================================================================
echo                      UNIFIED STUDIO
echo          ONE-BUTTON START (Full Setup + Launch)
echo     Chat + Comic Forge + Image Lab + Files + Automation
echo =======================================================================
echo.

echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python not found.
    echo Install from: https://www.python.org/downloads
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo OK: %%i
echo.

echo [2/5] Installing/checking dependencies...
echo Syncing packages from requirements.txt...
python -m pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo ERROR: Installation failed.
    pause
    exit /b 1
)
echo OK: Packages ready
echo.

echo [3/5] Checking configuration...
if not exist ".env" (
    echo .env file not found. Creating from template...
    if not exist ".env.example" (
        echo ERROR: .env.example not found.
        pause
        exit /b 1
    )
    copy ".env.example" ".env" >nul
    echo OK: .env created
) else (
    echo OK: .env file exists
)

echo.
echo Checking optional Ollama local AI...
powershell -Command "try { $null = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2 -ErrorAction Stop; Write-Host 'OK: Ollama is connected' } catch { Write-Host 'WARNING: Ollama is not running. Chat may show an Ollama message, but the app will still start.' }"
echo.

echo [4/5] Validating setup...
set VALID=1

if not exist "backend" (
    echo ERROR: backend/ missing
    set VALID=0
) else (
    echo OK: backend/ exists
)

if not exist "frontend" (
    echo ERROR: frontend/ missing
    set VALID=0
) else (
    echo OK: frontend/ exists
)

if not exist "backend\server.py" (
    echo ERROR: backend/server.py missing
    set VALID=0
) else (
    echo OK: backend/server.py exists
)

if not exist "frontend\index.html" (
    echo ERROR: frontend/index.html missing
    set VALID=0
) else (
    echo OK: frontend/index.html exists
)

if !VALID! equ 0 (
    echo.
    echo ERROR: Validation failed.
    pause
    exit /b 1
)

echo.
echo [5/5] Starting server...
echo.
echo FastAPI server starting on http://localhost:5000
echo Open this address if the browser does not open automatically.
echo.

powershell -Command "if (Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if not errorlevel 1 (
    echo Port 5000 is already in use. Opening the existing Unified Studio server.
    start http://localhost:5000
    echo.
    echo If the page does not load, close the old Python/uvicorn window and run START.bat again.
    pause
    exit /b 0
)

echo Server output:
echo -----------------------------------------------------------------------
echo.

timeout /t 2 /nobreak >nul
start http://localhost:5000

cd /d backend
python -m uvicorn server:app --host 127.0.0.1 --port 5000 --log-level warning

cd ..
echo.
echo -----------------------------------------------------------------------
echo.
echo Server stopped.
pause
