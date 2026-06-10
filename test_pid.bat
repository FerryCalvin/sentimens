@echo off
setlocal enabledelayedexpansion
for /f "delims=" %%P in ('powershell -Command "Write-Output '27352`r'"') do (
    set /a "PID=%%P" 2>nul
    echo Casted: [!PID!]
)
