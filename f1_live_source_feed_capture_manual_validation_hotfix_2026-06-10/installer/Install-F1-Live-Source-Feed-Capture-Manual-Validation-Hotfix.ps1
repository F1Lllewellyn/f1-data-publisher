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
$ArchiveDir = Join-Path $RepoPath "_archive/live_source_feed_capture_manual_validation_hotfix_$Stamp"
New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null

$Files = @(
    ".github/workflows/f1-live-source-feed-capture-experimental.yml",
    "scripts/live_capture/run_live_source_feed_capture.py",
    "docs/F1_LIVE_SOURCE_FEED_CAPTURE_MANUAL_VALIDATION_HOTFIX_2026-06-10.md",
    "CURRENT_CANONICAL_FILES_LIVE_SOURCE_FEED_CAPTURE_MANUAL_VALIDATION_2026-06-10.md",
    "LIVE_SOURCE_FEED_CAPTURE_MANUAL_VALIDATION_HOTFIX_MANIFEST.csv"
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
# F1 Live Source Feed Capture Manual Validation Hotfix Install Report

Installed: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Repo path: $RepoPath
Backup directory: $ArchiveDir

## Result

Installed manual validation and source-feed handshake classification hotfix.

## Next step

Commit and push the changes, then run the workflow manually with:

- capture_mode: manual
- manual_validation_mode: infrastructure_only
- duration_minutes: 2
- session_label: manual_test
- commit_outputs: true
"@

$ReportPath = Join-Path $RepoPath "docs/F1_LIVE_SOURCE_FEED_CAPTURE_MANUAL_VALIDATION_HOTFIX_INSTALL_REPORT.md"
$Report | Set-Content -Path $ReportPath -Encoding UTF8

Write-Host "Installed Live Source Feed Capture manual validation hotfix." -ForegroundColor Green
Write-Host "Backup directory: $ArchiveDir"
Write-Host "Next: commit and push the repo changes."
