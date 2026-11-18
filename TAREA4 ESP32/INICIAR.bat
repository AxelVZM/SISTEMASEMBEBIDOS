@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\launcher.py start
) else (
  py -3.12 scripts\launcher.py start
)
set "DETECTOR_EXIT=%ERRORLEVEL%"
if not "%DETECTOR_EXIT%"=="0" echo Revisa el mensaje anterior. Si no hay Python, instala Python 3.12 x64 con el lanzador py.
echo.
pause
exit /b %DETECTOR_EXIT%
