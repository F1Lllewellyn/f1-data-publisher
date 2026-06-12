param(
    [string]$RepoPath = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
)

$ErrorActionPreference = "Stop"

Write-Host "F1 No-Code Forecast Automation Buttons installer"
Write-Host "Default repo path: $RepoPath"
$entered = Read-Host "Press Enter to use this path, or paste a different repo path"
if ($entered -and $entered.Trim().Length -gt 0) {
    $RepoPath = $entered.Trim()
}

if (!(Test-Path $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptDir
$PayloadRoot = Join-Path $PackageRoot "payload"

if (!(Test-Path $PayloadRoot)) {
    throw "Payload folder missing: $PayloadRoot"
}

$items = @(
    @{ From = ".github\workflows\f1-forecast-automation-safe-test-button-v1.yml"; To = ".github\workflows\f1-forecast-automation-safe-test-button-v1.yml" },
    @{ From = ".github\workflows\f1-forecast-automation-run-now-button-v1.yml"; To = ".github\workflows\f1-forecast-automation-run-now-button-v1.yml" },
    @{ From = "docs\F1_NO_CODE_FORECAST_AUTOMATION_BUTTONS_2026-06-12.md"; To = "docs\F1_NO_CODE_FORECAST_AUTOMATION_BUTTONS_2026-06-12.md" }
)

foreach ($item in $items) {
    $src = Join-Path $PayloadRoot $item.From
    $dst = Join-Path $RepoPath $item.To
    $dstDir = Split-Path -Parent $dst
    if (!(Test-Path $src)) {
        throw "Payload item missing: $src"
    }
    if (!(Test-Path $dstDir)) {
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    }
    Copy-Item -Force $src $dst
    Write-Host "Installed: $($item.To)"
}

Write-Host "Install complete. Review, commit, and push with GitHub Desktop."
Write-Host "After push, use either:"
Write-Host " - F1 Forecast Automation - Safe Test Button"
Write-Host " - F1 Forecast Automation - Run Now Button"
