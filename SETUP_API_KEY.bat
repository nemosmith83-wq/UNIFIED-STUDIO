@echo off
REM Unified Studio — Local configuration setup (no API key required)
cls
setlocal

echo.
echo =======================================================================
echo              UNIFIED STUDIO - LOCAL SETUP
echo            No LLM API key is required (Ollama)
echo =======================================================================
echo.

python setup.py
if errorlevel 1 (
    echo.
    echo ERROR: Local setup failed.
    pause
    exit /b 1
)

echo.
pause
