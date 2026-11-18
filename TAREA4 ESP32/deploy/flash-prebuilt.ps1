param([string]$Port = 'COM6')
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$python = '.venv\Scripts\python.exe'
Get-Content firmware\prebuilt\SHA256SUMS.txt | ForEach-Object {
    $parts = $_ -split '\s+',2
    $path = Join-Path 'firmware\prebuilt' $parts[1]
    if ((Get-FileHash $path -Algorithm SHA256).Hash.ToLower() -ne $parts[0]) { throw "Hash incorrecto: $path" }
}
& $python -m esptool --chip esp32 --port $Port --baud 460800 write_flash 0x0 firmware\prebuilt\esp32-detector.bin
if ($LASTEXITCODE -ne 0) { throw 'Falló la carga. Cierra monitores seriales; revisa cable, puerto y botón BOOT.' }
