@echo off
REM ============================================================
REM run_all.bat — Jalankan Flask + FastAPI bersamaan (SM-07)
REM Sistem Klasifikasi Sentimen IndoBERT Multi-Domain
REM ============================================================
echo.
echo  ============================================
echo   SentimenID — Sistem Sentimen IndoBERT
echo  ============================================
echo.

REM Aktifkan virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment diaktifkan
) else (
    echo [PERINGATAN] Virtual environment tidak ditemukan.
    echo Jalankan: python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
    echo.
)

echo.
echo [INFO] Memulai Flask Scraper Service (Port 8000)...
start "Flask Scraper - Port 8000" cmd /k "cd /d %~dp0scraper && python main.py"

REM Tunggu sebentar agar scraper siap
timeout /t 3 /nobreak > nul

echo [INFO] Memulai Flask Main Application (Port 5000)...
start "Flask App - Port 5000" cmd /k "cd /d %~dp0 && python app.py"

echo.
echo  ============================================
echo   KEDUA SERVER SEDANG BERJALAN
echo  ============================================
echo.
echo   Flask App:    http://localhost:5000
echo   Scraper API:  http://localhost:8000
echo   Health Check: http://localhost:8000/health
echo.
echo   Tekan CTRL+C di masing-masing terminal untuk berhenti.
echo.
pause
