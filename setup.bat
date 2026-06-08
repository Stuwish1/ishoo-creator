@echo off
chcp 65001 >nul
echo.
echo ============================================
echo   Ishoo Creator v6 — Installation
echo ============================================
echo.

:: Kontrollera Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [FEL] Python hittades inte.
    echo.
    echo Installera Python från: https://www.python.org/downloads/
    echo Se till att kryssa i "Add Python to PATH" under installationen.
    echo.
    pause
    exit /b 1
)

echo [OK] Python hittades.

:: Installera Python-paket
echo.
echo Installerar Python-paket...
pip install anthropic fastapi uvicorn websockets python-dotenv watchfiles --quiet

if errorlevel 1 (
    echo [FEL] Kunde inte installera paket.
    pause
    exit /b 1
)

echo [OK] Paket installerade.

:: Skapa .env om den inte finns
if not exist .env (
    echo.
    echo Skapar .env-fil...
    echo ANTHROPIC_API_KEY=din_nyckel_har> .env
    echo [OK] .env skapad.
    echo.
    echo ============================================
    echo   VIKTIGT: Öppna .env och byt ut
    echo   "din_nyckel_har" mot din riktiga
    echo   Anthropic API-nyckel
    echo ============================================
) else (
    echo [OK] .env finns redan.
)

:: Skapa minnesmapp
if not exist memory mkdir memory
echo [OK] memory-mapp skapad.

echo.
echo ============================================
echo   Installation klar!
echo.
echo   Nästa steg:
echo   1. Öppna .env i Anteckningar
echo   2. Ersätt "din_nyckel_har" med din nyckel
echo   3. Dubbelklicka på start.bat
echo ============================================
echo.
pause
