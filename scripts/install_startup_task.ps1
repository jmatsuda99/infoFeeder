param(
    [string]$TaskName = "infoFeederAutoStart",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$vbsPath = Join-Path $repo "start_infofeeder.vbs"

if (-not (Test-Path $vbsPath)) {
    throw "Not found: $vbsPath"
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument ('"{0}"' -f $vbsPath)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Launch infoFeeder Web at user logon." `
    -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "infoFeeder will start automatically when $currentUser signs in."
