param(
  [string]$RepoPath = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher",
  [string]$Branch = "main",
  [string]$GitHubRepoUrl = "https://github.com/F1Lllewellyn/f1-data-publisher"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $PSScriptRoot
$payloadRoot = Join-Path $scriptRoot "payload"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportLines = New-Object System.Collections.Generic.List[string]

function Add-ReportLine([string]$line) {
  $reportLines.Add($line) | Out-Null
  Write-Host $line
}

function Copy-FileSafe([string]$source, [string]$target, [string]$backupRoot) {
  $targetDir = Split-Path -Parent $target
  if (!(Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
  }
  if (Test-Path $target) {
    $relative = Resolve-Path -LiteralPath $target -Relative
    $safeRelative = $relative.TrimStart('.\').TrimStart('./')
    $backupTarget = Join-Path $backupRoot $safeRelative
    $backupDir = Split-Path -Parent $backupTarget
    if (!(Test-Path $backupDir)) {
      New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }
    Copy-Item -LiteralPath $target -Destination $backupTarget -Force
  }
  Copy-Item -LiteralPath $source -Destination $target -Force
}

Add-ReportLine "F1 Peak-Elite System Installer v1"
Add-ReportLine "Started: $(Get-Date -Format o)"
Add-ReportLine "RepoPath: $RepoPath"
Add-ReportLine "PayloadRoot: $payloadRoot"

if (!(Test-Path $payloadRoot)) {
  throw "Payload folder missing: $payloadRoot"
}
if (!(Test-Path $RepoPath)) {
  throw "Repository path not found: $RepoPath"
}
if (!(Test-Path (Join-Path $RepoPath ".github\workflows"))) {
  throw "Repository does not look like f1-data-publisher: .github\workflows not found."
}

Set-Location $RepoPath
$backupRoot = Join-Path $RepoPath "_archive\F1_PEAK_ELITE_PREINSTALL_BACKUP_$timestamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
Add-ReportLine "BackupRoot: $backupRoot"

$payloadFiles = Get-ChildItem -Path $payloadRoot -Recurse -File
foreach ($file in $payloadFiles) {
  $relative = $file.FullName.Substring($payloadRoot.Length).TrimStart('\','/')
  $target = Join-Path $RepoPath $relative
  Copy-FileSafe -source $file.FullName -target $target -backupRoot $backupRoot
  Add-ReportLine "Installed: $relative"
}

$installReportDir = Join-Path $RepoPath "latest\installer_reports"
New-Item -ItemType Directory -Path $installReportDir -Force | Out-Null
$installReportPath = Join-Path $installReportDir "F1_PEAK_ELITE_SYSTEM_INSTALL_REPORT_$timestamp.txt"

$git = Get-Command git -ErrorAction SilentlyContinue
if ($null -eq $git) {
  Add-ReportLine "Git not found on PATH. Files were installed locally, but not committed/pushed."
} else {
  Add-ReportLine "Git found: $($git.Source)"
  try {
    git status --short | Out-String | ForEach-Object { Add-ReportLine $_.TrimEnd() }
    git add .github/workflows/f1-autorepair-run-now-button-v1.yml `
            .github/workflows/f1-autorepair-scheduled-session-workbook-recovery-v1.yml `
            .github/workflows/f1-black-box-temporal-validation-harness-v1.yml `
            .github/workflows/f1-experimental-challenger-v2-1-calibrated-stack.yml `
            .github/workflows/f1-forecast-bundle-locker-v1.yml `
            .github/workflows/f1-forecast-chain-readiness-validator-v1.yml `
            .github/workflows/f1-forecast-fantasy-readiness-dashboard-run-now.yml `
            .github/workflows/f1-forecast-fantasy-readiness-dashboard-scheduled.yml `
            .github/workflows/f1-forecast-gate-source-writer-v1.yml `
            .github/workflows/f1-openf1-lightweight-source-closure.yml `
            .github/workflows/f1-session-autorepair-integrated-loop-v1.yml `
            .github/workflows/f1-session-autorepair-integrated-run-now-button-v1.yml `
            .github/workflows/f1-workbook-kpi-refresh-run-now-button.yml `
            .github/workflows/f1-peak-elite-control-room-one-click-v1.yml `
            scripts/ops/f1_workflow_commit_block_repair_v1.py `
            scripts/ops/f1_workflow_static_validator_v2.py `
            scripts/ops/f1_peak_elite_cleanup_report_v1.py `
            scripts/ops/f1_peak_elite_health_v1.py `
            scripts/ops/f1_peak_elite_orchestrator_v1.py `
            configs/peak_elite/peak_elite_policy_v1.json `
            docs/F1_PEAK_ELITE_SYSTEM_2026-06-13.md `
            latest/installer_reports

    $cached = git diff --cached --name-only
    if ([string]::IsNullOrWhiteSpace($cached)) {
      Add-ReportLine "No staged changes after install. Nothing to commit."
    } else {
      Add-ReportLine "Staged files:"
      $cached.Split("`n") | ForEach-Object { if ($_.Trim()) { Add-ReportLine "  $_" } }
      git commit -m "chore: install peak elite F1 control room" | Out-String | ForEach-Object { Add-ReportLine $_.TrimEnd() }
      git push origin HEAD:$Branch | Out-String | ForEach-Object { Add-ReportLine $_.TrimEnd() }
      Add-ReportLine "Committed and pushed to $Branch."
    }
  } catch {
    Add-ReportLine "Git commit/push step hit an error: $($_.Exception.Message)"
    Add-ReportLine "Files are still installed locally and backed up. Review git status manually if needed."
  }
}

$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($null -ne $gh) {
  Add-ReportLine "GitHub CLI found: $($gh.Source)"
  try {
    gh workflow run f1-peak-elite-control-room-one-click-v1.yml -f operation=full_safe_chain -f commit_outputs=true -f run_forecast_gate=false | Out-String | ForEach-Object { Add-ReportLine $_.TrimEnd() }
    Add-ReportLine "Triggered F1 Peak Elite Control Room - One Click v1 with operation=full_safe_chain."
  } catch {
    Add-ReportLine "Could not trigger workflow through GitHub CLI: $($_.Exception.Message)"
    Add-ReportLine "Opening Actions page instead."
    Start-Process "$GitHubRepoUrl/actions/workflows/f1-peak-elite-control-room-one-click-v1.yml"
  }
} else {
  Add-ReportLine "GitHub CLI not found. Opening the workflow page so you can click Run workflow."
  Start-Process "$GitHubRepoUrl/actions/workflows/f1-peak-elite-control-room-one-click-v1.yml"
}

Add-ReportLine "Finished: $(Get-Date -Format o)"
$reportLines | Set-Content -Path $installReportPath -Encoding UTF8
Copy-Item -LiteralPath $installReportPath -Destination (Join-Path $scriptRoot "INSTALL_REPORT_LAST_RUN.txt") -Force
Add-ReportLine "Install report saved: $installReportPath"
Add-ReportLine "Local copy saved: $(Join-Path $scriptRoot 'INSTALL_REPORT_LAST_RUN.txt')"
