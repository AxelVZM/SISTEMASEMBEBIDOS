$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
py -3.12 scripts\launcher.py install
if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación. Revisa el error y usa DIAGNOSTICAR.bat.' }
