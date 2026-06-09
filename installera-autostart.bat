@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Skapar autostart for Ishoo Creator...

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%~dp0start.bat"
set "SHORTCUT=%STARTUP%\Ishoo Creator.lnk"

powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell;$s=$ws.CreateShortcut('%SHORTCUT%');$s.TargetPath='cmd.exe';$s.Arguments='/c start """" ""%TARGET%""""';$s.WorkingDirectory='%~dp0';$s.WindowStyle=1;$s.Description='Ishoo Creator';$s.Save()"

if exist "%SHORTCUT%" (
    echo Klart! Startar nu vid inloggning.
    echo Plats: %SHORTCUT%
) else (
    echo FEL: Kunde inte skapa genvaeg.
)
echo.
pause
