$ErrorActionPreference = "Stop"

$DefaultRepo = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
Write-Host "F1 Forecast Chain One-Click Boolean Flag Final Fix" -ForegroundColor Cyan
Write-Host "Default repo path: $DefaultRepo"
$Repo = Read-Host "Press Enter to use default, or paste a different repo path"
if ([string]::IsNullOrWhiteSpace($Repo)) { $Repo = $DefaultRepo }
$Repo = $Repo.Trim('"')

if (!(Test-Path $Repo)) {
  throw "Repo path not found: $Repo"
}

$PatchRoot = Split-Path -Parent $PSScriptRoot
$Files = @(
  @{ Source = ".github\workflows\f1-forecast-chain-one-click-validation-v1.yml"; Target = ".github\workflows\f1-forecast-chain-one-click-validation-v1.yml" },
  @{ Source = "docs\F1_FORECAST_CHAIN_ONECLICK_BOOLEAN_FLAG_FINAL_FIX_2026-06-12.md"; Target = "docs\F1_FORECAST_CHAIN_ONECLICK_BOOLEAN_FLAG_FINAL_FIX_2026-06-12.md" }
)

$BackupRoot = Join-Path $env:TEMP ("F1_1A_patch_backup_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

foreach ($f in $Files) {
  $SourcePath = Join-Path $PatchRoot $f.Source
  $TargetPath = Join-Path $Repo $f.Target
  if (!(Test-Path $SourcePath)) { throw "Patch payload missing: $SourcePath" }

  if (Test-Path $TargetPath) {
    $BackupPath = Join-Path $BackupRoot $f.Target
    $BackupParent = Split-Path -Parent $BackupPath
    New-Item -ItemType Directory -Force -Path $BackupParent | Out-Null
    Copy-Item -Force $TargetPath $BackupPath
  }

  $TargetParent = Split-Path -Parent $TargetPath
  New-Item -ItemType Directory -Force -Path $TargetParent | Out-Null
  Copy-Item -Force $SourcePath $TargetPath
  Write-Host "Installed: $($f.Target)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Install complete." -ForegroundColor Green
Write-Host "Backup folder: $BackupRoot"
Write-Host "Review the diff in GitHub Desktop, then commit and push."
