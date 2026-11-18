$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path '.venv\Scripts\python.exe')) { throw 'Ejecuta primero scripts\install.ps1' }
Write-Host 'Panel: http://127.0.0.1:8000 · Ctrl+C para detener'
Write-Host 'Cierra idf.py monitor antes de iniciar, para liberar COM6.'
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) { throw 'El servidor terminó con un error.' }
