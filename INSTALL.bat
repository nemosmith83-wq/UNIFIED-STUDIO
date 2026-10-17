@echo off
REM Unified Studio — Windows installation

echo.
echo =======================================================================
echo           UNIFIED STUDIO - INSTALLATION
echo      Chat + Image + Code + Search + Talent + Automation
echo =======================================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install from: https://www.python.org/downloads
    pause
    exit /b 1
)

echo Python found:
python --version

echo.
echo Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo.
python setup.py
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
echo Installation complete.
echo Run START.bat to launch Unified Studio.
pause
