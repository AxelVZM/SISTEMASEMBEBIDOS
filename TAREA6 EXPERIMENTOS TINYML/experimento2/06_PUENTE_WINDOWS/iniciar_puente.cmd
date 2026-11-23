@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if not exist ".venv\Scripts\python.exe" (echo ERROR: Instala Python 3.10 o posterior y activa py; pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" puente_usb_aws.py --port auto
pause
