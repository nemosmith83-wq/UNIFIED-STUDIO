@echo off
REM UNIFIED STUDIO - OPTIONAL OLLAMA SETUP
REM Run this only if you want local AI chat through Ollama.

cls
setlocal enabledelayedexpansion

echo.
echo =======================================================================
echo              UNIFIED STUDIO SETUP - LOCAL AI
echo        Optional Ollama setup for local chat responses
echo =======================================================================
echo.

echo What is Ollama?
echo   - Local AI running on your computer
echo   - Free local model runtime
echo   - Needed only for the Chat tab's local assistant responses
echo   - Other app tools can run without it
echo.
echo -----------------------------------------------------------------------
echo.

ollama --version >nul 2>&1
if errorlevel 1 (
    echo Ollama is not installed.
    echo.
    echo INSTALL OLLAMA:
    echo   1. Go to: https://ollama.ai
    echo   2. Download for Windows
    echo   3. Run installer
    echo   4. Run this setup script again
    echo.
    pause
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('ollama --version') do echo OK: %%i installed
)

echo.
echo Checking if Ollama daemon is running...
powershell -Command "try { $null = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2 -ErrorAction Stop; Write-Host 'OK: Ollama is running'; exit 0 } catch { Write-Host 'Ollama is not running. Starting it now.'; exit 1 }"

if errorlevel 1 (
    echo.
    echo Starting Ollama daemon in a new window...
    start "" cmd /k "ollama serve"
    timeout /t 8 /nobreak >nul
)

echo.
echo Checking for Mistral model...
ollama list | findstr /i "mistral" >nul
if errorlevel 1 (
    echo Mistral model not found.
    echo Downloading Mistral 7B. This can take a while.
    call ollama pull mistral
    echo OK: Mistral downloaded.
) else (
    echo OK: Mistral model ready.
)

echo.
echo =======================================================================
echo SETUP COMPLETE
echo.
echo Next step: Run START.bat to launch Unified Studio.
echo =======================================================================
echo.
pause
