# Point this repo at .githooks so post-commit bumps VERSION automatically.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
git config core.hooksPath .githooks
Write-Host "Configured core.hooksPath=.githooks in $(Get-Location)"
