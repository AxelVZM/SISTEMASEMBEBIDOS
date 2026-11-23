@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
set /p API_TOKEN=Introduce el token configurado en AWS: 
".venv\Scripts\python.exe" puente_usb_aws.py --port COM10 --token "%API_TOKEN%"
pause
