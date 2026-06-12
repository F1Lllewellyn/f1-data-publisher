$ErrorActionPreference = "Stop"
$DefaultRepo = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
Write-Host "F1 Forecast Chain Event Context Fix" -ForegroundColor Cyan
Write-Host "This defaults to $DefaultRepo"
$repo = Read-Host "Repo path [press Enter for $DefaultRepo]"
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $DefaultRepo }
$repo = $repo.Trim().Trim('"')
if (!(Test-Path -LiteralPath $repo)) { throw "Repo path not found: $repo" }
$Root = Split-Path -Parent $PSScriptRoot
$Payload = Join-Path $Root "payload"
$BackupRoot = Join-Path (Split-Path -Parent $repo) ".f1_patch_external_backups"
$BackupDir = Join-Path $BackupRoot "forecast_chain_event_context_fix_20260612"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$files = @(
  ".github\workflows\f1-forecast-gate-source-writer-v1.yml",
  ".github\workflows\f1-forecast-chain-readiness-validator-v1.yml",
  ".github\workflows\f1-forecast-bundle-locker-v1.yml",
  ".github\workflows\f1-forecast-chain-one-click-validation-v1.yml",
  "docs\F1_FORECAST_CHAIN_EVENT_CONTEXT_FIX_2026-06-12.md"
)
Write-Host "Safety summary" -ForegroundColor Cyan
Write-Host "This patch aligns forecast workflow default labels and adds a one-click chain validation workflow."
Write-Host "It does not call command-line Git. Commit and push with GitHub Desktop."
Write-Host "It does not touch stable engine logic, workbook files, prediction outputs, or promotion status."
foreach ($f in $files) {
  $src = Join-Path $Payload $f
  $dst = Join-Path $repo $f
  if (!(Test-Path -LiteralPath $src)) { throw "Payload file missing: $src" }
  if (Test-Path -LiteralPath $dst) {
    $backupDst = Join-Path $BackupDir $f
    $backupParent = Split-Path -Parent $backupDst
    New-Item -ItemType Directory -Force -Path $backupParent | Out-Null
    Copy-Item -LiteralPath $dst -Destination $backupDst -Force
  }
  $dstParent = Split-Path -Parent $dst
  New-Item -ItemType Directory -Force -Path $dstParent | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Host "Installed: $f" -ForegroundColor Green
}
Write-Host "Done. Review the diff in GitHub Desktop, commit, and push." -ForegroundColor Cyan
Write-Host "Suggested commit message: chore: align forecast chain validation labels" -ForegroundColor Cyan
