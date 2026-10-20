@echo off
cd /d "%~dp0\.."
set /p ORBITA_SERVER_URL=URL del servidor (https://dominio/esp32 o http://localhost:8010): 
set /p ORBITA_COM_PORT=Puerto USB (por ejemplo COM6): 
py herramientas\puente_usb.py --port "%ORBITA_COM_PORT%" --server "%ORBITA_SERVER_URL%" --sensor esp32-principal
pause
