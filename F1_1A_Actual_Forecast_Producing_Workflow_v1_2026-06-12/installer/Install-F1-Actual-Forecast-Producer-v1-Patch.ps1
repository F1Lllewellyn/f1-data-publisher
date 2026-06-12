param()
$ErrorActionPreference = "Stop"
Write-Host "F1 Actual Forecast Producer v1 Patch" -ForegroundColor Cyan
Write-Host ""
$repo = Read-Host "Paste the full path to your local f1-data-publisher repo"
if (-not (Test-Path -LiteralPath $repo)) {
  Write-Host "Repo path not found: $repo" -ForegroundColor Red
  exit 1
}
$repo = (Resolve-Path -LiteralPath $repo).Path
$patchRoot = Split-Path -Parent $PSScriptRoot
$externalRoot = Join-Path (Split-Path -Parent $repo) ".f1_patch_external_backups"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $externalRoot "actual_forecast_producer_v1_$stamp"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

Write-Host "==== Safety summary ====" -ForegroundColor Cyan
Write-Host "This installs the missing Actual Forecast Producer workflow."
Write-Host "It does not call command-line Git."
Write-Host "It does not change stable engine logic, workbook files, prediction outputs, or promotion status."
Write-Host "Existing files are backed up outside the repo before replacement."
Write-Host ""

$files = @(
  ".github\workflows\f1-actual-forecast-producer-v1.yml",
  "scripts\forecasts\produce_actual_forecast_rows_v1.py",
  "configs\forecasts\actual_forecast_producer_policy_v1.json",
  "docs\F1_ACTUAL_FORECAST_PRODUCER_V1_PATCH_2026-06-12.md"
)

foreach ($rel in $files) {
  $src = Join-Path $patchRoot $rel
  $dst = Join-Path $repo $rel
  if (-not (Test-Path -LiteralPath $src)) {
    Write-Host "Missing package file: $rel" -ForegroundColor Red
    exit 1
  }
  $dstParent = Split-Path -Parent $dst
  New-Item -ItemType Directory -Force -Path $dstParent | Out-Null
  if (Test-Path -LiteralPath $dst) {
    $flat = $rel -replace '[\\/:*?"<>|]', '_'
    Copy-Item -LiteralPath $dst -Destination (Join-Path $backupDir $flat) -Force
  }
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Host "Installed: $rel" -ForegroundColor Green
}

$reportPath = Join-Path $repo "docs\F1_1A_ACTUAL_FORECAST_PRODUCER_V1_INSTALL_REPORT_2026-06-12.md"
$body = @()
$body += "# F1 1A Actual Forecast Producer v1 Install Report"
$body += ""
$body += "Verdict: Pass"
$body += ""
$body += "Installed UTC/local time: $(Get-Date -Format s)"
$body += "Backup folder: $backupDir"
$body += ""
$body += "Installed files:"
foreach ($rel in $files) { $body += "- $rel" }
$body += ""
$body += "Next step: review the diff in GitHub Desktop, commit, and push."
$body | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Host "Wrote report: $reportPath" -ForegroundColor Green
Write-Host ""
Write-Host "Now review the diff in GitHub Desktop, commit, and push." -ForegroundColor Cyan
Write-Host "Suggested commit message: feat: add actual forecast producer workflow"
