param()
$ErrorActionPreference = "Stop"
$DefaultRepo = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
Write-Host "F1 Actual Forecast Producer Source Discovery Hotfix" -ForegroundColor Cyan
Write-Host ""
$repo = Read-Host "Repo path [press Enter for $DefaultRepo]"
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $DefaultRepo }
if (-not (Test-Path -LiteralPath $repo)) {
  Write-Host "Repo path not found: $repo" -ForegroundColor Red
  exit 1
}
$repo = (Resolve-Path -LiteralPath $repo).Path
$patchRoot = Split-Path -Parent $PSScriptRoot
$externalRoot = Join-Path (Split-Path -Parent $repo) ".f1_patch_external_backups"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $externalRoot "actual_forecast_producer_source_discovery_hotfix_$stamp"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

Write-Host "==== Safety summary ====" -ForegroundColor Cyan
Write-Host "This hotfix updates Actual Forecast Producer source discovery."
Write-Host "It defaults to your repo path and does not call command-line Git."
Write-Host "It does not change stable engine logic, workbook files, prediction outputs, or promotion status."
Write-Host "Existing files are backed up outside the repo before replacement."
Write-Host ""

$files = @(
  ".github\workflows\f1-actual-forecast-producer-v1.yml",
  "scripts\forecasts\produce_actual_forecast_rows_v1.py",
  "docs\F1_ACTUAL_FORECAST_PRODUCER_SOURCE_DISCOVERY_HOTFIX_2026-06-12.md"
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
    $flat = $rel -replace '[\/:*?"<>|]', '_'
    Copy-Item -LiteralPath $dst -Destination (Join-Path $backupDir $flat) -Force
  }
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Host "Installed: $rel" -ForegroundColor Green
}

$reportPath = Join-Path $repo "docs\F1_1A_ACTUAL_FORECAST_PRODUCER_SOURCE_DISCOVERY_HOTFIX_INSTALL_REPORT_2026-06-12.md"
$body = @(
  "# F1 1A Actual Forecast Producer Source Discovery Hotfix Install Report",
  "",
  "Verdict: Pass",
  "",
  "Installed local time: $(Get-Date -Format s)",
  "Backup folder: $backupDir",
  "",
  "Installed files:"
)
foreach ($rel in $files) { $body += "- $rel" }
$body += ""
$body += "Next step: review the diff in GitHub Desktop, commit, and push."
$body | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Host "Wrote report: $reportPath" -ForegroundColor Green
Write-Host ""
Write-Host "Now review the diff in GitHub Desktop, commit, and push." -ForegroundColor Cyan
Write-Host "Suggested commit message: fix: update forecast producer source discovery"
