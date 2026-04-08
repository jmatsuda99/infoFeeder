# Creates a Windows shortcut that launches infoFeeder Web (FastAPI) via start_infofeeder.vbs.
# Run once after clone or when the shortcut target breaks (e.g. folder moved).
param(
    [switch]$Desktop
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$vbs = Join-Path $repo "start_infofeeder.vbs"
if (-not (Test-Path $vbs)) {
    throw "Not found: $vbs"
}

$linkPath = if ($Desktop) {
    Join-Path ([Environment]::GetFolderPath("Desktop")) "infoFeeder Web.lnk"
} else {
    Join-Path $repo "infoFeeder Web.lnk"
}

$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($linkPath)
$sc.TargetPath = $vbs
$sc.WorkingDirectory = $repo
# Windows system icon (network / globe style; change if you prefer)
$sc.IconLocation = "$env:SystemRoot\System32\imageres.dll,-102"
$sc.Description = "infoFeeder Web UI (http://127.0.0.1:8510)"
$sc.Save()
Write-Host "Created: $linkPath"
