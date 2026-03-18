Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

python -m pip install --upgrade pip | Out-Host
python -m pip install -r requirements.txt | Out-Host

# Use the spec for a repeatable build (bundles mediapipe + model file).
python -m PyInstaller --noconfirm --clean SmartPostureTracker.spec | Out-Host

Write-Host ""
Write-Host "Built: $PSScriptRoot\dist\SmartPostureTracker.exe"

