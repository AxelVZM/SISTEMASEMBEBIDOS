@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto deps
py -3 -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto deps
python -m venv .venv
:deps
if not exist ".venv\Scripts\python.exe" (
 echo ERROR: Instala Python 3.10 o superior.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (pause & exit /b 1)
echo Abre http://127.0.0.1:8765
".venv\Scripts\python.exe" servidor.py
pause
