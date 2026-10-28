@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo  Starting RO3 CPanel (White-Label Admin Panel)
echo ===================================================

if not exist config.json (
    if exist config.example.json (
        echo [Notice] config.json not found, copying from config.example.json...
        copy config.example.json config.json >nul
    )
)

:loop
python server.py
echo [Info] Server exited, restarting in 3 seconds...
powershell -NoProfile -Command "Start-Sleep -Seconds 3"
goto loop
