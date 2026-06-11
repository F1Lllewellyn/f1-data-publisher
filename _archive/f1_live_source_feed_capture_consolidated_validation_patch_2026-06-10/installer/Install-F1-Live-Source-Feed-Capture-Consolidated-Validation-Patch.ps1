
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
$ArchiveDir = Join-Path $RepoPath "_archive/live_source_feed_capture_latest_preserve_hotfix_$Stamp"
New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null

$Files = @(
    "scripts/live_capture/run_live_source_feed_capture.py",
    "docs/F1_LIVE_SOURCE_FEED_CAPTURE_LATEST_PRESERVE_HOTFIX_2026-06-10.md",
    "CURRENT_CANONICAL_FILES_LIVE_SOURCE_FEED_CAPTURE_LATEST_PRESERVE_2026-06-10.md",
    "LIVE_SOURCE_FEED_CAPTURE_LATEST_PRESERVE_HOTFIX_MANIFEST.csv"
)

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
# F1 Live Source Feed Capture Consolidated Validation Patch Install Report

Installed: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Repo path: $RepoPath
Backup directory: $ArchiveDir

## Result

Installed latest-preserve hotfix for the experimental live source-feed capture layer.

## What changed

Manual infrastructure-only and non-evidence validation runs now write to history and latest status, but do not overwrite/delete latest evidence-bearing live capture outputs.

## Next step

Commit and push the changes, then rerun the workflow manually with:

- capture_mode: manual
- manual_validation_mode: infrastructure_only
- duration_minutes: 2
- session_label: manual_test
- commit_outputs: true
"@

$ReportPath = Join-Path $RepoPath "docs/F1_LIVE_SOURCE_FEED_CAPTURE_LATEST_PRESERVE_HOTFIX_INSTALL_REPORT.md"
$Report | Set-Content -Path $ReportPath -Encoding UTF8

Write-Host "Installed Live Source Feed Capture latest-preserve hotfix." -ForegroundColor Green
Write-Host "Backup directory: $ArchiveDir"
Write-Host "Next: commit and push the repo changes."
