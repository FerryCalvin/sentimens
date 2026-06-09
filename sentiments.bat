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
if /i "%CMD%"=="login"  goto :do_login

echo.
echo  Usage: sentiments [start^|stop^|status^|login]
echo.
echo    start    Start Flask App (port %FLASK_PORT%) and Scraper (port %SCRAPER_PORT%)
echo    stop     Stop all servers
echo    status   Show server status
echo    login    Login ke Twitter/X dan simpan sesi (untuk scraping Twitter)
echo.
goto :eof


:do_start
cls
echo.
echo  ================================================
echo    SentimenS - Sentiment Analysis System
echo  ================================================
echo.

REM Check if ports are already in use
netstat -ano 2>nul | findstr ":%FLASK_PORT% " | findstr "LISTENING" >nul
if !errorlevel!==0 (
    echo  [!] Flask is already running on port %FLASK_PORT%.
    echo      Run: sentiments stop  to stop it first.
    echo.
    goto :eof
)
netstat -ano 2>nul | findstr ":%SCRAPER_PORT% " | findstr "LISTENING" >nul
if !errorlevel!==0 (
    echo  [!] Scraper is already running on port %SCRAPER_PORT%.
    echo      Run: sentiments stop  to stop it first.
    echo.
    goto :eof
)

REM Activate virtual environment
if exist "%VENV_ACTIVATE%" (
    call "%VENV_ACTIVATE%"
    echo  [OK] Virtual environment activated
) else (
    echo  [!!] venv not found - using global Python
)

echo.
echo  [1/2] Starting Scraper API on port %SCRAPER_PORT%...
start "SentimenS Scraper :8000" cmd /k "cd /d "%SCRAPER_DIR%" && call "%VENV_ACTIVATE%" && python main.py"

timeout /t 4 /nobreak >nul

echo  [2/2] Starting Flask App on port %FLASK_PORT%...
start "SentimenS Flask :5000" cmd /k "cd /d "%PROJECT_DIR%" && call "%VENV_ACTIVATE%" && python app.py"

timeout /t 2 /nobreak >nul

echo.
echo  ================================================
echo    BOTH SERVERS ARE RUNNING
echo  ================================================
echo.
echo    Flask App  :  http://localhost:%FLASK_PORT%
echo    Scraper API:  http://localhost:%SCRAPER_PORT%
echo    API Docs   :  http://localhost:%SCRAPER_PORT%/health
echo.
echo    Run: sentiments stop    to stop all servers
echo    Run: sentiments status  to check status
echo.
goto :eof


:do_stop
echo.
echo  Stopping servers...

for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":%FLASK_PORT% " ^| findstr "LISTENING"') do (
    echo  [OK] Stopping Flask App (PID %%P)
    taskkill /PID %%P /F >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":%SCRAPER_PORT% " ^| findstr "LISTENING"') do (
    echo  [OK] Stopping Scraper  (PID %%P)
    taskkill /PID %%P /F >nul 2>&1
)

echo  Done. All servers stopped.
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
    echo  [ON]  Flask App   http://localhost:%FLASK_PORT%
) else (
    echo  [OFF] Flask App   not running
)

netstat -ano 2>nul | findstr ":%SCRAPER_PORT% " | findstr "LISTENING" >nul
if !errorlevel!==0 (
    echo  [ON]  Scraper     http://localhost:%SCRAPER_PORT%
) else (
    echo  [OFF] Scraper     not running
)

echo.
goto :eof


:do_login
echo.
echo  ================================================
echo    SentimenS - Login Twitter/X
echo  ================================================
echo.

if exist "%VENV_ACTIVATE%" (
    call "%VENV_ACTIVATE%"
)

echo  [INFO] Membuka browser untuk login Twitter/X...
echo  [INFO] Silakan login di browser yang terbuka.
echo  [INFO] Setelah berhasil login, tekan ENTER di sini.
echo.

python "%SCRAPER_DIR%\twitter_login.py"

echo.
echo  [OK] Selesai. Sekarang sentiments start untuk mulai scraping Twitter.
echo.
goto :eof
