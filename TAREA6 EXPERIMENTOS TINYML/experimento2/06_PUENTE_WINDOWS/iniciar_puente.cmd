@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (echo Se necesita Python y el lanzador py; pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if not exist ".venv\Scripts\python.exe" (echo No se pudo crear entorno; pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (pause & exit /b 1)
".venv\Scripts\python.exe" puente_usb_aws.py --port auto
pause
