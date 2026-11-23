@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (echo ERROR: Instala Python 3.10+.; pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" puente_usb_aws.py --port auto --solo-local --duration 40
pause
