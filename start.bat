@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Ishoo Creator — Server

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       ISHOO CREATOR  startar...      ║
echo  ╚══════════════════════════════════════╝
echo.

:: ── Döda gammal process på port 8000 ────────────────────────────────────────
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo  Stanger gammal server ^(PID %%a^)...
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: ── Kontrollera Python ───────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo  FEL: Python hittades inte. Installera Python 3.10+ och forsok igen.
    pause
    exit /b 1
)

:: ── Installera beroenden om de saknas ───────────────────────────────────────
python -c "import fastapi, uvicorn, anthropic" >nul 2>&1
if errorlevel 1 (
    echo  Installerar beroenden ^(forsta gangen^)...
    pip install -r requirements.txt -q
)

:: ── Öppna webbläsaren automatiskt ───────────────────────────────────────────
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: ── Starta servern med auto-reload ──────────────────────────────────────────
echo  Servern kor pa http://localhost:8000
echo  Auto-reload ON — sparar i app.py, servern startar om automatiskt
echo  Stang INTE detta fonster.
echo.
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-exclude "projects/*" --reload-exclude "memory/*" --reload-exclude "*.json" --reload-exclude "*.md" --reload-exclude "*.txt"

echo.
echo  Servern stangdes. Tryck valfri tangent for att avsluta.
pause >nul
