param(
    [Parameter(Mandatory=$true)][string]$Ec2Host,
    [Parameter(Mandatory=$true)][string]$KeyFile
)
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run-windows.ps1'
$key = (Resolve-Path $KeyFile).Path
if ($Ec2Host -notmatch '^[a-zA-Z0-9.-]+$' -or $key.Contains('"')) { throw 'Host/ruta no válido' }
$arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Ec2Host "{1}" -KeyFile "{2}"' -f $runner,$Ec2Host,$key
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory (Split-Path $PSScriptRoot -Parent)
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'ESP32-Detector-AWS' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'ESP32-Detector-AWS'
Write-Host 'Registrado e iniciado. Se inicia al entrar a Windows y requiere mantener la sesión y PC activas.'
