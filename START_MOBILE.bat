@echo off
REM UNIFIED STUDIO - MOBILE / LAN START
REM Starts the same Unified Studio application for access from a phone/tablet on the same LAN.

cls
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "UNIFIED_HOST=0.0.0.0"
set "UNIFIED_PORT=5000"

for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4 Address"') do (
    set "LAN_IP=%%A"
    set "LAN_IP=!LAN_IP: =!"
    goto :got_ip
)

:got_ip
if not defined LAN_IP set "LAN_IP=YOUR-PC-IP"

echo.
echo =======================================================================
echo                   UNIFIED STUDIO - MOBILE
echo             Phone / Tablet access on your local network
echo =======================================================================
echo.

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    pause
    exit /b 1
)

echo Checking dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" copy ".env.example" ".env" >nul
)

echo.
echo PC browser:    http://127.0.0.1:%UNIFIED_PORT%
echo PHONE/TABLET:  http://%LAN_IP%:%UNIFIED_PORT%
echo.
echo Keep this window open while using Unified Studio from the phone.
echo Use only on a trusted private LAN. The mobile listener is reachable by other

echo devices on that network.
echo.

cd /d backend
python -m uvicorn server:app --host %UNIFIED_HOST% --port %UNIFIED_PORT% --log-level warning

cd ..
pause
