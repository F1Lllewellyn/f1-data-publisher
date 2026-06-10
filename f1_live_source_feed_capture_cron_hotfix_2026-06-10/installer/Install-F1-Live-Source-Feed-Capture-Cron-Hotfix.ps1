
param(
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"

Write-Host "F1 Live Source Feed Capture Cron Hotfix Installer" -ForegroundColor Cyan
Write-Host "This hotfix fixes the invalid GitHub Actions cron schedule." -ForegroundColor Cyan

if ([string]::IsNullOrWhiteSpace($RepoPath)) {
    $RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repo"
}

if (!(Test-Path $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}

$repo = Resolve-Path $RepoPath
$patchRoot = Split-Path -Parent $PSScriptRoot
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$archiveDir = Join-Path $repo "_archive\live_source_feed_capture_cron_hotfix_$timestamp"
New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null

$files = @(
    ".github\workflows\f1-live-source-feed-capture-experimental.yml"
)

foreach ($rel in $files) {
    $target = Join-Path $repo $rel
    if (Test-Path $target) {
        $backupTarget = Join-Path $archiveDir $rel
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupTarget) | Out-Null
        Copy-Item $target $backupTarget -Force
        Write-Host "Backed up existing: $rel"
    }
}

# Copy workflow
$workflowSource = Join-Path $patchRoot ".github\workflows\f1-live-source-feed-capture-experimental.yml"
$workflowTarget = Join-Path $repo ".github\workflows\f1-live-source-feed-capture-experimental.yml"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $workflowTarget) | Out-Null
Copy-Item $workflowSource $workflowTarget -Force
Write-Host "Installed fixed workflow: .github/workflows/f1-live-source-feed-capture-experimental.yml"

# Copy docs/register/manifest into repo root/docs
$docsSource = Join-Path $patchRoot "docs\F1_LIVE_SOURCE_FEED_CAPTURE_CRON_HOTFIX_2026-06-10.md"
$docsTarget = Join-Path $repo "docs\F1_LIVE_SOURCE_FEED_CAPTURE_CRON_HOTFIX_2026-06-10.md"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $docsTarget) | Out-Null
Copy-Item $docsSource $docsTarget -Force
Copy-Item (Join-Path $patchRoot "CURRENT_CANONICAL_FILES_LIVE_SOURCE_FEED_CAPTURE_CRON_HOTFIX_2026-06-10.md") (Join-Path $repo "CURRENT_CANONICAL_FILES_LIVE_SOURCE_FEED_CAPTURE_CRON_HOTFIX_2026-06-10.md") -Force
Copy-Item (Join-Path $patchRoot "LIVE_SOURCE_FEED_CAPTURE_CRON_HOTFIX_MANIFEST.csv") (Join-Path $repo "LIVE_SOURCE_FEED_CAPTURE_CRON_HOTFIX_MANIFEST.csv") -Force

$report = @"
# F1 Live Source Feed Capture Cron Hotfix Install Report

Installed at: $(Get-Date -Format o)
Repo path: $repo
Backup folder: $archiveDir

## Fixed issue
Replaced invalid four-field cron:

````text
*/15 * * 5,6,0
````

with valid five-field GitHub Actions cron:

````text
*/15 * * * 5,6,0
````

## Next manual steps
1. Review `git status`.
2. Commit and push this hotfix.
3. Re-open GitHub Actions and confirm the workflow no longer has the invalid cron annotation.
4. Run a short manual test capture before relying on scheduled capture.
"@

$reportPath = Join-Path $repo "docs\F1_LIVE_SOURCE_FEED_CAPTURE_CRON_HOTFIX_INSTALL_REPORT.md"
$report | Set-Content -Path $reportPath -Encoding UTF8
Write-Host "Install report created: docs/F1_LIVE_SOURCE_FEED_CAPTURE_CRON_HOTFIX_INSTALL_REPORT.md"

Write-Host "Hotfix installation complete." -ForegroundColor Green
Write-Host "No canonical workbook or stable engine files were touched." -ForegroundColor Green
