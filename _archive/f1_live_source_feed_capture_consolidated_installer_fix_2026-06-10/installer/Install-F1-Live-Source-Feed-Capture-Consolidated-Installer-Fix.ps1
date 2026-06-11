param(
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"

if (-not $RepoPath -or $RepoPath.Trim() -eq "") {
    $RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repo"
}

if (-not (Test-Path $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}

$PatchRoot = Split-Path -Parent $PSScriptRoot
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ArchiveDir = Join-Path $RepoPath "_archive/live_source_feed_capture_consolidated_installer_fix_$Stamp"

$Files = @(
    ".github/workflows/f1-live-source-feed-capture-experimental.yml",
    "scripts/live_capture/run_live_source_feed_capture.py",
    "docs/F1_LIVE_SOURCE_FEED_CAPTURE_CONSOLIDATED_VALIDATION_PATCH_2026-06-10.md",
    "docs/F1_LIVE_SOURCE_FEED_CAPTURE_CONSOLIDATED_INSTALLER_FIX_2026-06-10.md",
    "CURRENT_CANONICAL_FILES_LIVE_SOURCE_FEED_CAPTURE_CONSOLIDATED_2026-06-10.md",
    "LIVE_SOURCE_FEED_CAPTURE_CONSOLIDATED_VALIDATION_PATCH_MANIFEST.csv",
    "LIVE_SOURCE_FEED_CAPTURE_CONSOLIDATED_INSTALLER_FIX_MANIFEST.csv"
)

# Preflight: verify every package source exists before copying anything.
$Missing = @()
foreach ($Rel in $Files) {
    $Source = Join-Path $PatchRoot $Rel
    if (-not (Test-Path $Source)) {
        $Missing += $Rel
    }
}

if ($Missing.Count -gt 0) {
    $List = $Missing -join "`n - "
    throw "Patch package is incomplete. Missing package files:`n - $List"
}

if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
    Write-Host "Warning: .git folder was not found at the repo path. Continuing because the path exists." -ForegroundColor Yellow
}

New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null

foreach ($Rel in $Files) {
    $Source = Join-Path $PatchRoot $Rel
    $Target = Join-Path $RepoPath $Rel
    $TargetDir = Split-Path -Parent $Target
    if (-not (Test-Path $TargetDir)) { New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null }
    if (Test-Path $Target) {
        $BackupTarget = Join-Path $ArchiveDir $Rel
        $BackupDir = Split-Path -Parent $BackupTarget
        if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null }
        Copy-Item $Target $BackupTarget -Force
    }
    Copy-Item $Source $Target -Force
}

$Report = @"
# F1 Live Source Feed Capture Consolidated Installer Fix Install Report

Installed: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Repo path: $RepoPath
Backup directory: $ArchiveDir

## Result

Installed cumulative consolidated validation patch with corrected installer file references.

## Previous installer issue fixed

The prior consolidated validation installer referenced legacy latest-preserve documentation filenames that were not included in that package. This installer preflights all package files before copying and uses the correct consolidated file list.

## What changed

- Installed stabilized experimental workflow.
- Installed stabilized live-capture script.
- Added consolidated documentation and manifest files.
- Preserved replaced files in the backup directory above.

## Next step

Commit and push the changes, then rerun the workflow manually with:

- capture_mode: manual
- manual_validation_mode: infrastructure_only
- duration_minutes: 2
- session_label: manual_test
- commit_outputs: true
"@

$ReportPath = Join-Path $RepoPath "docs/F1_LIVE_SOURCE_FEED_CAPTURE_CONSOLIDATED_INSTALLER_FIX_INSTALL_REPORT.md"
$Report | Set-Content -Path $ReportPath -Encoding UTF8

Write-Host "Installed Live Source Feed Capture consolidated installer fix." -ForegroundColor Green
Write-Host "Backup directory: $ArchiveDir"
Write-Host "Next: commit and push the repo changes."
