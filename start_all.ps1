param([string]$Python = "$env:USERPROFILE\.conda\envs\ICUenv\python.exe")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$localPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $localPython) { $Python = $localPython }
if (-not (Test-Path -LiteralPath $Python)) { throw "Python environment not found: $Python" }
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONIOENCODING = 'utf-8'
& $Python (Join-Path $PSScriptRoot 'start_controller.py')
exit $LASTEXITCODE
