@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Ishoo Creator

echo.
echo  === ISHOO CREATOR startar ===
echo.

:: Kill gammal process pa port 8000
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: Kolla Python
where python >nul 2>&1
if errorlevel 1 (
    echo FEL: Python saknas. Installera Python 3.10+
    pause
    exit /b 1
)

:: Installera beroenden om de saknas
python -c "import fastapi, uvicorn, anthropic" >nul 2>&1
if errorlevel 1 (
    echo Installerar beroenden...
    pip install -r requirements.txt -q
)

:: Oppna webblasaren automatiskt
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

echo  Server: http://localhost:8000
echo  Auto-reload ON - sparar app.py = server startar om
echo  Stang INTE detta fonster.
echo.

python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload

echo.
echo Servern stangdes.
pause >nul
