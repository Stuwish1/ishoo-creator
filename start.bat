@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: Ladda .env om den finns
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
        if not "%%a"=="" if not "%%b"=="" set %%a=%%b
    )
)

echo.
echo  Ishoo Creator startar...
echo  Stang INTE detta fonster.
echo.

:: Dod gammal process pa port 8000 om den kors
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo  Stanger gammal server (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 >nul

:: Oppna webbläsaren efter 2 sekunder
start /b cmd /c "timeout /t 2 >nul && start http://localhost:8000"

:: Starta servern (synligt fönster så vi ser fel)
python app.py
pause
