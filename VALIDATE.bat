@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM UNIFIED STUDIO — Setup Validation Script
REM Checks if everything is installed correctly
REM ─────────────────────────────────────────────────────────────────────────

cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════════╗
echo ║        ⚡ UNIFIED STUDIO — Setup Validation                         ║
echo ╚═══════════════════════════════════════════════════════════════════════╝
echo.

setlocal enabledelayedexpansion
set ISSUES=0

REM Check Python
echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not installed
    set ISSUES=1
) else (
    for /f "tokens=*" %%i in ('python --version') do (
        echo ✅ %%i
    )
)
echo.

REM Check .env
 echo Checking .env configuration...
if not exist ".env" (
    echo ❌ .env file missing!
    echo    Copy: .env.example -^> .env
    set ISSUES=1
) else (
    echo ✅ .env file exists
    for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"OLLAMA_URL=" /C:"OLLAMA_MODEL=" /C:"UNIFIED_PORT=" .env') do (
        if "%%A"=="OLLAMA_URL" set "OLLAMA_URL=%%B"
        if "%%A"=="OLLAMA_MODEL" set "OLLAMA_MODEL=%%B"
        if "%%A"=="UNIFIED_PORT" set "UNIFIED_PORT=%%B"
    )
    if "!OLLAMA_URL!"=="" echo ⚠️ OLLAMA_URL not set; defaults to http://localhost:11434
    if "!OLLAMA_MODEL!"=="" echo ⚠️ OLLAMA_MODEL not set; defaults to mistral
    echo ✅ Ollama configuration checked
)
echo.

REM Check directories
echo Checking project structure...
if not exist "backend" (
    echo ❌ backend/ directory missing
    set ISSUES=1
) else (
    echo ✅ backend/ exists
)

if not exist "frontend" (
    echo ❌ frontend/ directory missing
    set ISSUES=1
) else (
    echo ✅ frontend/ exists
)

if not exist "backend\server.py" (
    echo ❌ backend/server.py missing
    set ISSUES=1
) else (
    echo ✅ backend/server.py exists
)

if not exist "frontend\index.html" (
    echo ❌ frontend/index.html missing
    set ISSUES=1
) else (
    echo ✅ frontend/index.html exists
)
echo.

REM Check Python packages
echo Checking installed packages...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo ❌ FastAPI not installed
    set ISSUES=1
) else (
    echo ✅ FastAPI installed
)

pip show ddgs >nul 2>&1
if errorlevel 1 (
    echo ⚠️ ddgs not installed - Unified Studio will use its dependency-free DuckDuckGo fallback
) else (
    echo ✅ ddgs installed
)

pip show uvicorn >nul 2>&1
if errorlevel 1 (
    echo ❌ Uvicorn not installed
    set ISSUES=1
) else (
    echo ✅ Uvicorn installed
)

pip show Pillow >nul 2>&1
if errorlevel 1 (
    echo ❌ Pillow not installed
    set ISSUES=1
) else (
    echo ✅ Pillow installed
)
echo.

REM Summary
if %ISSUES% equ 0 (
    echo ╔═══════════════════════════════════════════════════════════════════════╗
    echo ║  ✅ ALL CHECKS PASSED! You're ready to start.                        ║
    echo ║                                                                       ║
    echo ║  Next: Run START_UNIFIED.bat                                         ║
    echo ╚═══════════════════════════════════════════════════════════════════════╝
    echo.
) else (
    echo ╔═══════════════════════════════════════════════════════════════════════╗
    echo ║  ❌ ISSUES FOUND!                                                     ║
    echo ║                                                                       ║
    echo ║  Run INSTALL.bat to fix all issues.                                  ║
    echo ╚═══════════════════════════════════════════════════════════════════════╝
    echo.
)

pause
