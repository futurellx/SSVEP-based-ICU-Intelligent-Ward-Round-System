param(
  [string]$Python = "$env:USERPROFILE\.conda\envs\ICUenv\python.exe",
  [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$localPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $localPython) { $Python = $localPython }

$Scripts = @(
  (Join-Path $PSScriptRoot 'main.py'),
  (Join-Path $PSScriptRoot '智能查房患者端cs.py'),
  (Join-Path $PSScriptRoot 'run_1cs.py'),
  (Join-Path $PSScriptRoot 'SerialPort32\Afy_2cs.py')
)

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
  throw "Python not found: $Python"
}
foreach ($Script in $Scripts) {
  if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) {
    throw "Missing script: $Script"
  }
}
if ($CheckOnly) {
  Write-Output "Python: $Python"
  Write-Output "Working directory: $PSScriptRoot"
  $Scripts | ForEach-Object { Write-Output "Script: $_" }
  exit 0
}

$env:PYTHONUNBUFFERED = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONNOUSERSITE = '1'
$childProcesses = @()
try {
  foreach ($Script in $Scripts) {
    Write-Host "Starting: $Script"
    # This entry intentionally opens one interactive console per component.
    $proc = Start-Process -FilePath $Python -ArgumentList @('-u', "`"$Script`"") -WorkingDirectory $PSScriptRoot -PassThru
    $childProcesses += $proc
    Start-Sleep -Seconds 1
  }
  Write-Host 'All processes started. Press Ctrl+C to stop them.'
  Wait-Process -Id ($childProcesses | ForEach-Object { $_.Id })
}
finally {
  foreach ($proc in $childProcesses) {
    if (-not $proc.HasExited) { $proc.Kill() }
  }
}
