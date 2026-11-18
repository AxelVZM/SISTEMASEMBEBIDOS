param([string]$Port = 'COM6')
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\firmware')
if (!(Get-Command idf.py -ErrorAction SilentlyContinue)) { throw 'Abre ESP-IDF 5.4 PowerShell o activa primero export.ps1 de ESP-IDF.' }
# sdkconfig.defaults selects the ESP32 original with BTDM and 4 MB flash.
idf.py build
if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación.' }
idf.py -p $Port flash
if ($LASTEXITCODE -ne 0) { throw 'Falló la carga. Revisa COM6/cable/BOOT y cierra otros monitores seriales.' }
