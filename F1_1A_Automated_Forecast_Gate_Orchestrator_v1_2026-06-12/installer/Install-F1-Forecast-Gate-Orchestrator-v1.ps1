param(
  [string]$RepoPath = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptDir
$PayloadRoot = Join-Path $PackageRoot "payload"

Write-Host "F1 Automated Forecast Gate Orchestrator v1 Installer"
Write-Host "Default repo path: $RepoPath"
$inputPath = Read-Host "Repo path (press Enter to use default)"
if (-not [string]::IsNullOrWhiteSpace($inputPath)) {
  $RepoPath = $inputPath
}

if (-not (Test-Path $RepoPath)) {
  throw "Repo path does not exist: $RepoPath"
}

$backupRoot = Join-Path $RepoPath ".f1_patch_external_backups\forecast_gate_orchestrator_v1_$(Get-Date -Format yyyyMMdd_HHmmss)"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$files = @(
  ".github\workflows\f1-automated-forecast-gate-orchestrator-v1.yml",
  "scripts\forecast_bundles\orchestrate_forecast_gate_pipeline_v1.py",
  "configs\forecast_bundles\forecast_gate_orchestrator_policy_v1.json",
  "docs\F1_FORECAST_GATE_ORCHESTRATOR_V1_PATCH_2026-06-12.md"
)

foreach ($rel in $files) {
  $src = Join-Path $PayloadRoot $rel
  $dst = Join-Path $RepoPath $rel
  if (-not (Test-Path $src)) {
    throw "Package payload missing: $rel"
  }
  if (Test-Path $dst) {
    $backup = Join-Path $backupRoot $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
    Copy-Item -LiteralPath $dst -Destination $backup -Force
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Host "Installed: $rel"
}

$gitignore = Join-Path $RepoPath ".gitignore"
if (-not (Test-Path $gitignore)) { New-Item -ItemType File -Path $gitignore | Out-Null }
$ignoreText = Get-Content -Raw -Path $gitignore
foreach ($entry in @(".f1_patch_backups/", ".f1_patch_external_backups/")) {
  if ($ignoreText -notmatch [regex]::Escape($entry)) {
    Add-Content -Path $gitignore -Value $entry
  }
}

$report = Join-Path $RepoPath "F1_FORECAST_GATE_ORCHESTRATOR_V1_INSTALL_REPORT.md"
@"
# F1 Automated Forecast Gate Orchestrator v1 Install Report

Installed: $(Get-Date -Format o)
Repo path: $RepoPath
Backup path: $backupRoot

Installed files:
$($files | ForEach-Object { "- $_" } | Out-String)

No command-line Git was called by this installer.
Commit and push with GitHub Desktop.
"@ | Set-Content -Path $report -Encoding UTF8

Write-Host ""
Write-Host "Install complete. Review changes in GitHub Desktop, then commit and push."
