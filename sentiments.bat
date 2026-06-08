@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM sentiments.bat - CLI for SentimenS project
REM Usage: sentiments [start|stop|status]
REM ============================================================

set "PROJECT_DIR=%~dp0"
set "SCRAPER_DIR=%PROJECT_DIR%scraper"
set "FLASK_PORT=5000"
set "SCRAPER_PORT=8000"
set "VENV_ACTIVATE=%PROJECT_DIR%venv\Scripts\activate.bat"

set "CMD=%~1"
if /i "%CMD%"=="start"  goto :do_start
if /i "%CMD%"=="stop"   goto :do_stop
if /i "%CMD%"=="status" goto :do_status

echo.
echo  Usage: sentiments [start^|stop^|status]
echo.
echo    start    Start Flask (port %FLASK_PORT%) and Scraper (port %SCRAPER_PORT%)
echo    stop     Stop all servers
echo    status   Show server status
echo.
goto :eof


:do_start
cls
echo.
echo  ================================================
echo    SentimenS - Sentiment Analysis System
echo  ================================================
echo.

netstat -ano 2>nul | findstr ":%FLASK_PORT% " | findstr "LISTENING" >nul
if !errorlevel!==0 (
    echo  [!] Flask is already running on port %FLASK_PORT%.
    echo  Run: sentiments stop  to stop it first.
    echo.
    goto :eof
)
netstat -ano 2>nul | findstr ":%SCRAPER_PORT% " | findstr "LISTENING" >nul
if !errorlevel!==0 (
    echo  [!] Scraper is already running on port %SCRAPER_PORT%.
    echo  Run: sentiments stop  to stop it first.
    echo.
    goto :eof
)

if exist "%VENV_ACTIVATE%" (
    call "%VENV_ACTIVATE%"
    echo  [OK] Virtual environment activated
) else (
    echo  [!!] venv not found - using global Python
)

echo.
echo  [1/2] Starting Scraper API on port %SCRAPER_PORT%...
start "SentimenS Scraper :8000" cmd /k "cd /d "%SCRAPER_DIR%" && uvicorn main:app --host 127.0.0.1 --port %SCRAPER_PORT% --no-access-log"

timeout /t 4 /nobreak >nul

echo  [2/2] Starting Flask App on port %FLASK_PORT%...
start "SentimenS Flask :5000" cmd /k "cd /d "%PROJECT_DIR%" && python app.py"

timeout /t 2 /nobreak >nul

echo.
echo  ================================================
echo    BOTH SERVERS ARE RUNNING
echo  ================================================
echo.
echo    Flask App  :  http://localhost:%FLASK_PORT%
echo    Scraper API:  http://localhost:%SCRAPER_PORT%
echo    API Docs   :  http://localhost:%SCRAPER_PORT%/docs
echo.
echo    Run: sentiments stop  to stop all servers.
echo.
goto :eof


:do_stop
echo.
echo  Stopping servers...

for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":%FLASK_PORT% " ^| findstr "LISTENING"') do (
    echo  [OK] Stopping Flask   (PID %%P)
    taskkill /PID %%P /F >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":%SCRAPER_PORT% " ^| findstr "LISTENING"') do (
    echo  [OK] Stopping Scraper (PID %%P)
    taskkill /PID %%P /F >nul 2>&1
)

echo  Done.
echo.
goto :eof


:do_status
echo.
echo  ================================================
echo    SentimenS - Server Status
echo  ================================================
echo.

netstat -ano 2>nul | findstr ":%FLASK_PORT% " | findstr "LISTENING" >nul
if !errorlevel!==0 (
    echo  [ON]  Flask     http://localhost:%FLASK_PORT%
) else (
    echo  [OFF] Flask     not running
)

netstat -ano 2>nul | findstr ":%SCRAPER_PORT% " | findstr "LISTENING" >nul
if !errorlevel!==0 (
    echo  [ON]  Scraper   http://localhost:%SCRAPER_PORT%
) else (
    echo  [OFF] Scraper   not running
)

echo.
goto :eof
