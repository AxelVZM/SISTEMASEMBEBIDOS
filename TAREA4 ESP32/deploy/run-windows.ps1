param(
    [Parameter(Mandatory=$true)][string]$Ec2Host,
    [Parameter(Mandatory=$true)][string]$KeyFile,
    [string]$SshUser = 'ubuntu'
)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$python = (Resolve-Path '.venv\Scripts\python.exe').Path
$key = (Resolve-Path $KeyFile).Path
# Only one supervisor/backend may own COM6. Logs and config stay out of Git.
$env:DETECTOR_DATA = Join-Path (Get-Location) 'data'
& $python deploy\supervise.py --host $Ec2Host --key $key --user $SshUser
exit $LASTEXITCODE
