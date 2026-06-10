param(
  [string]$RepoPath = ""
)

$ErrorActionPreference = "Stop"

Write-Host "F1 Live Source Feed Capture Patch Installer" -ForegroundColor Cyan
Write-Host "This installer backs up replaced files and installs the experimental GitHub workflow/scripts." -ForegroundColor Cyan

if ([string]::IsNullOrWhiteSpace($RepoPath)) {
  $RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repo"
}

if (!(Test-Path $RepoPath)) {
  throw "Repo path does not exist: $RepoPath"
}

$PatchRoot = Split-Path -Parent $PSScriptRoot
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ArchiveDir = Join-Path $RepoPath "_archive\live_source_feed_capture_patch_$Timestamp"
New-Item -ItemType Directory -Path $ArchiveDir -Force | Out-Null

$Files = @(
  ".github\workflows\f1-live-source-feed-capture-experimental.yml",
  "scripts\live_capture\run_live_source_feed_capture.py",
  "configs\live_capture\live_source_feed_capture_policy.json",
  "docs\F1_LIVE_SOURCE_FEED_CAPTURE_PATCH_2026-06-10.md",
  "CURRENT_CANONICAL_FILES_LIVE_SOURCE_FEED_CAPTURE_2026-06-10.md",
  "LIVE_SOURCE_FEED_CAPTURE_PATCH_MANIFEST.csv"
)

$Installed = @()
$BackedUp = @()

foreach ($Rel in $Files) {
  $Source = Join-Path $PatchRoot $Rel
  $Dest = Join-Path $RepoPath $Rel
  if (!(Test-Path $Source)) {
    throw "Patch file missing: $Source"
  }
  $DestParent = Split-Path -Parent $Dest
  New-Item -ItemType Directory -Path $DestParent -Force | Out-Null
  if (Test-Path $Dest) {
    $Backup = Join-Path $ArchiveDir $Rel
    $BackupParent = Split-Path -Parent $Backup
    New-Item -ItemType Directory -Path $BackupParent -Force | Out-Null
    Copy-Item $Dest $Backup -Force
    $BackedUp += $Rel
  }
  Copy-Item $Source $Dest -Force
  $Installed += $Rel
}

$ReportPath = Join-Path $RepoPath "docs\F1_LIVE_SOURCE_FEED_CAPTURE_PATCH_INSTALL_REPORT.md"
$Report = @()
$Report += "# F1 Live Source Feed Capture Patch Install Report"
$Report += ""
$Report += "Installed UTC/local timestamp: $(Get-Date -Format o)"
$Report += "Repo path: $RepoPath"
$Report += "Backup folder: $ArchiveDir"
$Report += ""
$Report += "## Installed files"
foreach ($Item in $Installed) { $Report += "- $Item" }
$Report += ""
$Report += "## Backed up replaced files"
if ($BackedUp.Count -eq 0) { $Report += "- None" } else { foreach ($Item in $BackedUp) { $Report += "- $Item" } }
$Report += ""
$Report += "## Next steps"
$Report += "1. Review git status."
$Report += "2. Commit and push the patch."
$Report += "3. Run the GitHub workflow manually with a 2-5 minute test capture."
$Report += "4. Do not promote live capture evidence into stable logic without reconciliation."

$Report | Set-Content -Path $ReportPath -Encoding UTF8

Write-Host "Install complete." -ForegroundColor Green
Write-Host "Backup folder: $ArchiveDir" -ForegroundColor Yellow
Write-Host "Install report: $ReportPath" -ForegroundColor Yellow
Write-Host "Next: commit/push, then run 'F1 Live Source Feed Capture Experimental' manually for a short test." -ForegroundColor Cyan
