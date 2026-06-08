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

:: Öppna webbläsaren efter 2 sekunder
start /b cmd /c "timeout /t 2 >nul && start http://localhost:8000"

:: Starta servern (synligt fönster så vi ser fel)
python app.py
pause
