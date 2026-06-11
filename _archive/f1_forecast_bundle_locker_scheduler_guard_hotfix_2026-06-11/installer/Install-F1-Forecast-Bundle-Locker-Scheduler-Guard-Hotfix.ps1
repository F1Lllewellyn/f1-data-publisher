param([string]$RepoPath)
$ErrorActionPreference = "Stop"
if (-not $RepoPath -or !(Test-Path $RepoPath)) { throw "Repo path not found: $RepoPath" }
$PatchRoot = Split-Path -Parent $PSScriptRoot
$Files = @(
  @{Source=".github\workflows\f1-forecast-bundle-locker-v1.yml"; Dest=".github\workflows\f1-forecast-bundle-locker-v1.yml"},
  @{Source="scripts\forecast_bundles\create_forecast_bundles_v1.py"; Dest="scripts\forecast_bundles\create_forecast_bundles_v1.py"},
  @{Source="configs\forecast_bundles\forecast_bundle_policy_v1.json"; Dest="configs\forecast_bundles\forecast_bundle_policy_v1.json"},
  @{Source="docs\F1_FORECAST_BUNDLE_LOCKER_SCHEDULER_GUARD_HOTFIX_2026-06-11.md"; Dest="docs\F1_FORECAST_BUNDLE_LOCKER_SCHEDULER_GUARD_HOTFIX_2026-06-11.md"}
)
foreach ($f in $Files) {
  $src = Join-Path $PatchRoot $f.Source
  if (!(Test-Path $src)) { throw "Package missing expected file: $($f.Source)" }
}
$BackupRoot = Join-Path $RepoPath ("_backup_forecast_bundle_locker_scheduler_guard_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
foreach ($f in $Files) {
  $src = Join-Path $PatchRoot $f.Source
  $dst = Join-Path $RepoPath $f.Dest
  $dstDir = Split-Path -Parent $dst
  New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
  if (Test-Path $dst) {
    $backupDst = Join-Path $BackupRoot $f.Dest
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupDst) | Out-Null
    Copy-Item $dst $backupDst -Force
  }
  Copy-Item $src $dst -Force
}
$Report = Join-Path $RepoPath "FORECAST_BUNDLE_LOCKER_SCHEDULER_GUARD_INSTALL_REPORT_2026-06-11.txt"
"F1 Forecast Bundle Locker Scheduler Guard hotfix installed at $(Get-Date -Format o). Backup: $BackupRoot" | Out-File -Encoding UTF8 $Report
Write-Host "Installed F1 Forecast Bundle Locker Scheduler Guard hotfix. Backup: $BackupRoot"
