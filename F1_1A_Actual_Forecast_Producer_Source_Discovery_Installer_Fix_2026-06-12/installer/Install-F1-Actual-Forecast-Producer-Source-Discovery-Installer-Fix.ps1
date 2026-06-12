$ErrorActionPreference = "Stop"

$DefaultRepoPath = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"

Write-Host "F1 Actual Forecast Producer Source Discovery Installer Fix" -ForegroundColor Cyan
Write-Host "This defaults to $DefaultRepoPath" -ForegroundColor White
Write-Host ""
$RepoInput = Read-Host "Repo path [press Enter for $DefaultRepoPath]"
if ([string]::IsNullOrWhiteSpace($RepoInput)) {
    $RepoPath = $DefaultRepoPath
} else {
    $RepoPath = $RepoInput.Trim().Trim('"')
}

if (-not (Test-Path -LiteralPath $RepoPath -PathType Container)) {
    throw "Repo path does not exist: $RepoPath"
}

$PatchRoot = Split-Path -Parent $PSScriptRoot
$ExternalBackupRoot = Join-Path (Split-Path -Parent $RepoPath) ".f1_patch_external_backups"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path $ExternalBackupRoot "actual_forecast_producer_source_discovery_installer_fix_$Stamp"
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

Write-Host "==== Safety summary ====" -ForegroundColor Cyan
Write-Host "This installer updates Actual Forecast Producer source discovery."
Write-Host "It defaults to your repo path and does not call command-line Git."
Write-Host "It does not change stable engine logic, workbook files, prediction outputs, or promotion status."
Write-Host "Existing files are backed up outside the repo before replacement."
Write-Host "Backup folder: $BackupRoot"
Write-Host ""

$Mappings = @(
    @{ Rel = "docs\F1_ACTUAL_FORECAST_PRODUCER_SOURCE_DISCOVERY_HOTFIX_2026-06-12.md"; Dest = "docs\F1_ACTUAL_FORECAST_PRODUCER_SOURCE_DISCOVERY_HOTFIX_2026-06-12.md" },
    @{ Rel = "manifests\patch_manifest.csv"; Dest = "manifests\actual_forecast_producer_source_discovery_patch_manifest.csv" },
    @{ Rel = "configs\forecasts\actual_forecast_producer_policy_v1.json"; Dest = "configs\forecasts\actual_forecast_producer_policy_v1.json" },
    @{ Rel = "scripts\forecasts\produce_actual_forecast_rows_v1.py"; Dest = "scripts\forecasts\produce_actual_forecast_rows_v1.py" },
    @{ Rel = ".github\workflows\f1-actual-forecast-producer-v1.yml"; Dest = ".github\workflows\f1-actual-forecast-producer-v1.yml" }
)

$Installed = @()
foreach ($m in $Mappings) {
    $src = Join-Path $PatchRoot $m.Rel
    $dst = Join-Path $RepoPath $m.Dest

    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) {
        throw "Patch payload missing: $src"
    }

    $dstParent = Split-Path -Parent $dst
    if (-not (Test-Path -LiteralPath $dstParent -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $dstParent | Out-Null
    }

    if (Test-Path -LiteralPath $dst -PathType Leaf) {
        $backupDst = Join-Path $BackupRoot $m.Dest
        $backupParent = Split-Path -Parent $backupDst
        if (-not (Test-Path -LiteralPath $backupParent -PathType Container)) {
            New-Item -ItemType Directory -Force -Path $backupParent | Out-Null
        }
        Copy-Item -LiteralPath $dst -Destination $backupDst -Force
    }

    Copy-Item -LiteralPath $src -Destination $dst -Force
    $Installed += $m.Dest
    Write-Host "Installed: $($m.Dest)" -ForegroundColor Green
}

$ReportPath = Join-Path $RepoPath "docs\F1_1A_ACTUAL_FORECAST_PRODUCER_SOURCE_DISCOVERY_INSTALLER_FIX_REPORT_2026-06-12.md"
$ReportParent = Split-Path -Parent $ReportPath
if (-not (Test-Path -LiteralPath $ReportParent -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $ReportParent | Out-Null
}

$ReportLines = @()
$ReportLines += "# F1 1A Actual Forecast Producer Source Discovery Installer Fix 2026-06-12"
$ReportLines += ""
$ReportLines += "Verdict: Pass after install."
$ReportLines += ""
$ReportLines += "This installer replaces the failed backup-copy installer."
$ReportLines += "It creates backup parent folders before copying existing files."
$ReportLines += "It does not call command-line Git."
$ReportLines += "It does not touch stable engine logic, workbook files, prediction outputs, or promotion status."
$ReportLines += ""
$ReportLines += "Default repo path used or offered: $DefaultRepoPath"
$ReportLines += "Repo path installed to: $RepoPath"
$ReportLines += "Backup root: $BackupRoot"
$ReportLines += ""
$ReportLines += "## Installed files"
foreach ($item in $Installed) { $ReportLines += "- $item" }
$ReportLines += ""
$ReportLines += "## Next validation"
$ReportLines += "Run workflow: F1 Actual Forecast Producer v1"
$ReportLines += "Inputs: event_id=manual_forecast_producer_validation, race_name=Manual Forecast Producer Validation, gate=all, lane=all, strict_source=false, commit_outputs=true"

Set-Content -LiteralPath $ReportPath -Value $ReportLines -Encoding UTF8
Write-Host ""
Write-Host "Wrote install report: $ReportPath" -ForegroundColor Green
Write-Host ""
Write-Host "Now review the diff in GitHub Desktop, commit, and push." -ForegroundColor Cyan
Write-Host "Suggested commit message: chore: fix actual forecast producer source discovery" -ForegroundColor Cyan
