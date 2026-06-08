@echo off
chcp 65001 >nul
echo.
echo ============================================
echo   Ishoo Creator — Ollama Setup
echo   RTX 3080 / 10GB VRAM optimerat
echo ============================================
echo.

:: Kolla om Ollama ar installerat
where ollama >nul 2>&1
if errorlevel 1 (
    echo Ollama ar inte installerat.
    echo.
    echo Installera Ollama fran: https://ollama.com/download
    echo Ladda ner Windows-installationen, kor den, kom tillbaka hit.
    echo.
    start https://ollama.com/download
    pause
    exit /b 1
)

echo [OK] Ollama hittades.
echo.

:: Starta Ollama-servern om den inte kör
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo Startar Ollama-server...
    start /b ollama serve
    timeout /t 3 >nul
)

echo Laddar ner modeller for RTX 3080 (10GB VRAM)...
echo.

:: qwen2.5-coder:7b — bast for kodgranskning (4.7GB VRAM)
echo [1/2] qwen2.5-coder:7b — kodgranskningsmodell (4.7GB)...
echo       Bast for: DBA, Konflikt, Prestanda, Testgranskare
ollama pull qwen2.5-coder:7b
echo.

:: llama3.2:3b — snabb for enkla uppgifter (2.0GB VRAM)
echo [2/2] llama3.2:3b — snabb latt modell (2.0GB)...
echo       Bast for: Mobil/Falt-agenten, enkla kontroller
ollama pull llama3.2:3b
echo.

echo ============================================
echo   [OK] Modeller installerade!
echo.
echo   Totalt VRAM-anvandning: ~6.7GB / 10GB
echo   Kvar for andra uppgifter: ~3.3GB
echo.
echo   Nasta steg:
echo   1. Starta Ishoo Creator (start.bat)
echo   2. Ga till Installningar > Agenter
echo   3. Byt modell fran "haiku" till
echo      "ollama:qwen2.5-coder:7b" for:
echo      - DBA
echo      - Konfliktgranskare
echo      - Prestandagranskare
echo      - Testgranskare
echo      - Mobil/Faltanvandare
echo ============================================
echo.
pause
