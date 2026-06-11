@echo off
REM start_scraper.bat — Jalankan scraper FastAPI di background
REM Simpan PID ke file agar bisa di-stop nanti

set "SCRAPER_DIR=%~dp0scraper"
set "VENV_PYTHON=%~dp0venv\Scripts\python.exe"
set "PID_FILE=%~dp0scraper.pid"

echo Starting SentimenS Scraper on port 8000...
start "SentimenS-Scraper" /min cmd /k "cd /d "%SCRAPER_DIR%" && "%VENV_PYTHON%" main.py"
echo Scraper started! Tutup window "SentimenS-Scraper" untuk stop.
