param(
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "F1 1A Cumulative GitHub Installer Validation Hotfix - 2026-06-11"
Write-Host "This installer repairs Forecast Bundle Locker quoting and Source Writer commit hygiene."
Write-Host ""

if ([string]::IsNullOrWhiteSpace($RepoPath)) {
    $RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repository"
}

$RepoPath = $RepoPath.Trim('"')
if (!(Test-Path $RepoPath)) {
    throw "Repository path not found: $RepoPath"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptDir
$PayloadRoot = Join-Path $PackageRoot "payload"
$BackupRoot = Join-Path $RepoPath ("_backups\F1_1A_Cumulative_Validation_Hotfix_2026-06-11_" + (Get-Date -Format "yyyyMMdd_HHmmss"))

if (!(Test-Path $PayloadRoot)) {
    throw "Payload folder not found: $PayloadRoot"
}

$ManifestPath = Join-Path $PackageRoot "manifests\validation_hotfix_payload_manifest.csv"
if (!(Test-Path $ManifestPath)) {
    throw "Payload manifest not found: $ManifestPath"
}

$Manifest = Import-Csv $ManifestPath

Write-Host ""
Write-Host "Pre-checking payload files..."
foreach ($Item in $Manifest) {
    $Source = Join-Path $PayloadRoot $Item.relative_path
    if (!(Test-Path $Source)) {
        throw "Missing payload file: $($Item.relative_path)"
    }
}

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

Write-Host "Installing payload files..."
foreach ($Item in $Manifest) {
    $Rel = $Item.relative_path
    $Source = Join-Path $PayloadRoot $Rel
    $Dest = Join-Path $RepoPath $Rel
    $DestDir = Split-Path -Parent $Dest

    if (!(Test-Path $DestDir)) {
        New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
    }

    if (Test-Path $Dest) {
        $BackupDest = Join-Path $BackupRoot $Rel
        $BackupDir = Split-Path -Parent $BackupDest
        if (!(Test-Path $BackupDir)) {
            New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
        }
        Copy-Item $Dest $BackupDest -Force
    }

    Copy-Item $Source $Dest -Force
    Write-Host "Installed: $Rel"
}

$InstallReport = Join-Path $RepoPath "F1_1A_CUMULATIVE_VALIDATION_HOTFIX_INSTALL_REPORT_2026-06-11.md"
@"
# F1 1A Cumulative GitHub Installer Validation Hotfix Install Report

Installed UTC: $((Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))

Backup folder:

$BackupRoot

Files installed:

$($Manifest | ForEach-Object { "- " + $_.relative_path } | Out-String)

Stable engine changed: No
Canonical workbook changed: No
Promotion attempted: No

Next validation:
1. Run F1 Forecast Gate Source Writer v1.
2. Run F1 Forecast Bundle Locker v1.
"@ | Set-Content -Path $InstallReport -Encoding UTF8

Write-Host ""
Write-Host "Install complete."
Write-Host "Backup folder: $BackupRoot"
Write-Host "Install report: $InstallReport"
Write-Host ""
Write-Host "Commit and push these changes, then rerun the two validation workflows."
Read-Host "Press Enter to close"
