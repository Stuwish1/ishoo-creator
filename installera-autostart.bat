@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  Skapar autostart-genvag for Ishoo Creator...

:: Skapar en genvag i Windows Startup-mappen via PowerShell
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%~dp0start.bat"
set "SHORTCUT=%STARTUP%\Ishoo Creator.lnk"

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut('%SHORTCUT%');" ^
  "$s.TargetPath = 'cmd.exe';" ^
  "$s.Arguments = '/c start \"\" \"%TARGET%\"';" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.WindowStyle = 1;" ^
  "$s.Description = 'Ishoo Creator Server';" ^
  "$s.Save()"

if exist "%SHORTCUT%" (
    echo  Klart! Ishoo Creator startar nu automatiskt vid inloggning.
    echo  Genvagsplats: %SHORTCUT%
) else (
    echo  FEL: Kunde inte skapa genvagen. Kör som administratör?
)
echo.
pause
