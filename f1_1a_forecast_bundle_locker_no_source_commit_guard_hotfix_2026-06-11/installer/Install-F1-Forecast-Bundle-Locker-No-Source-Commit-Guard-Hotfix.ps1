param(
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"

Write-Host "F1 Forecast Bundle Locker No-Source Commit Guard Hotfix - 2026-06-11"
if (-not $RepoPath -or $RepoPath.Trim() -eq "") {
    $RepoPath = Read-Host "Paste your local f1-data-publisher repo path"
}
$RepoPath = $RepoPath.Trim('"')
if (-not (Test-Path $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}

$PackageRoot = Split-Path -Parent $PSScriptRoot
$PayloadRoot = Join-Path $PackageRoot "payload"
$BackupRoot = Join-Path $RepoPath "_backup_F1_1A_no_source_commit_guard_2026-06-11"
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

$Files = @(
    @{ Source = "payload\.github\workflows\f1-forecast-bundle-locker-v1.yml"; Destination = ".github\workflows\f1-forecast-bundle-locker-v1.yml" },
    @{ Source = "payload\scripts\forecast_bundles\create_forecast_bundles_v1.py"; Destination = "scripts\forecast_bundles\create_forecast_bundles_v1.py" }
)

# Preflight package contents before copying anything
foreach ($f in $Files) {
    $src = Join-Path $PackageRoot $f.Source
    if (-not (Test-Path $src)) {
        throw "Package is missing required file: $($f.Source)"
    }
}

foreach ($f in $Files) {
    $src = Join-Path $PackageRoot $f.Source
    $dst = Join-Path $RepoPath $f.Destination
    $dstDir = Split-Path -Parent $dst
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null

    if (Test-Path $dst) {
        $backupDst = Join-Path $BackupRoot ($f.Destination -replace "[:\\\/]", "_")
        Copy-Item -Force $dst $backupDst
        Write-Host "Backed up: $($f.Destination)"
    }

    Copy-Item -Force $src $dst
    Write-Host "Installed: $($f.Destination)"
}

$InstallReport = Join-Path $RepoPath "F1_FORECAST_BUNDLE_LOCKER_NO_SOURCE_COMMIT_GUARD_INSTALL_REPORT_2026-06-11.md"
@"
# F1 Forecast Bundle Locker No-Source Commit Guard Install Report

Installed UTC: $([DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"))

Installed files:
- .github/workflows/f1-forecast-bundle-locker-v1.yml
- scripts/forecast_bundles/create_forecast_bundles_v1.py

Purpose:
- Prevent manual validation runs from committing structural placeholder bundles when actual forecast rows are missing.
- Add explicit allow_structural_placeholders control.
- Keep scheduled guard behaviour intact.

Stable engine touched: No
Canonical workbook touched: No
Promotion attempted: No
"@ | Set-Content -Path $InstallReport -Encoding UTF8

Write-Host ""
Write-Host "Install complete. Commit and push these changes."
