@echo off
title SentimenS - Aplikasi Analisis Sentimen
echo ================================================
echo   SentimenS - Sistem Klasifikasi Sentimen
echo   Memuat model IndoBERT, harap tunggu...
echo ================================================
echo.

cd /d %~dp0

:: Aktifkan virtual environment
call venv\Scripts\activate.bat

:: Jalankan Flask app
echo [*] Menjalankan server di http://localhost:5000
echo [*] Tekan Ctrl+C untuk berhenti
echo.
python app.py

pause
