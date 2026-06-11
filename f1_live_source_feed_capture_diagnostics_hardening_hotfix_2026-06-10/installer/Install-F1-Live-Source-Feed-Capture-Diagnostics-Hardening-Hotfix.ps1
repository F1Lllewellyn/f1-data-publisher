param(
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"

Write-Host "F1 Live Source Feed Capture Diagnostics Hardening Hotfix"
Write-Host "This hotfix replaces the live capture runner script and adds clearer diagnostics."
Write-Host ""

if (-not $RepoPath -or $RepoPath.Trim() -eq "") {
    $RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repo"
}

$RepoPath = $RepoPath.Trim('"')
if (-not (Test-Path $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}

$PatchRoot = Split-Path -Parent $PSScriptRoot
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ArchiveDir = Join-Path $RepoPath "_archive\live_source_feed_capture_diagnostics_hardening_hotfix_$Timestamp"
New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null

$FilesToInstall = @(
    "scripts/live_capture/run_live_source_feed_capture.py",
    "docs/F1_LIVE_SOURCE_FEED_CAPTURE_DIAGNOSTICS_HARDENING_HOTFIX_2026-06-10.md",
    "CURRENT_CANONICAL_FILES_LIVE_SOURCE_FEED_CAPTURE_DIAGNOSTICS_HARDENING_2026-06-10.md",
    "LIVE_SOURCE_FEED_CAPTURE_DIAGNOSTICS_HARDENING_HOTFIX_MANIFEST.csv"
)

foreach ($RelPath in $FilesToInstall) {
    $Source = Join-Path $PatchRoot $RelPath
    $Dest = Join-Path $RepoPath $RelPath

    if (-not (Test-Path $Source)) {
        throw "Patch source file missing: $Source"
    }

    if (Test-Path $Dest) {
        $Backup = Join-Path $ArchiveDir $RelPath
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Backup) | Out-Null
        Copy-Item $Dest $Backup -Force
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dest) | Out-Null
    Copy-Item $Source $Dest -Force
    Write-Host "Installed: $RelPath"
}

$ReportPath = Join-Path $RepoPath "docs\F1_LIVE_SOURCE_FEED_CAPTURE_DIAGNOSTICS_HARDENING_HOTFIX_INSTALL_REPORT.md"
$Report = @"
# F1 Live Source Feed Capture Diagnostics Hardening Hotfix Install Report

Installed at: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Repo path: $RepoPath
Backup folder: $ArchiveDir

## Installed files

$($FilesToInstall | ForEach-Object { "- $_" } | Out-String)

## What to do next

1. Commit and push these changes.
2. Run GitHub Actions workflow: F1 Live Source Feed Capture Experimental.
3. Use a short manual validation capture first.
4. Confirm the log shows recording_status, recording_error, raw_size_bytes, and line_count.
5. Upload the logs back into ChatGPT 1A if anything fails or stays warning-level.
"@
$Report | Out-File -Encoding utf8 -FilePath $ReportPath
Write-Host "Install report written: $ReportPath"
Write-Host ""
Write-Host "Hotfix installed. Please commit and push the repo changes."
