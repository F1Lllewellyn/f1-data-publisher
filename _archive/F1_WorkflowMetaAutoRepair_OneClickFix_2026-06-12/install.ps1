$ErrorActionPreference = "Stop"
Write-Host "F1 Workflow Meta-AutoRepair One-Click Fix"
Write-Host "-------------------------------------------"
$defaultRepo = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
$repo = Read-Host "Repo path [$defaultRepo]"
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $defaultRepo }
$repo = $repo.Trim('"')
if (!(Test-Path -LiteralPath $repo)) { throw "Repo path not found: $repo" }
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$payload = Join-Path $root "payload"
if (!(Test-Path -LiteralPath $payload)) { throw "Payload missing: $payload" }
Write-Host "Copying fixed workflow/meta-health payload..."
Copy-Item -Path (Join-Path $payload "*") -Destination $repo -Recurse -Force

$required = @(
  ".github\workflows\f1-workbook-kpi-refresh-scheduled.yml",
  ".github\workflows\f1-workflow-meta-health-safe-test-button.yml",
  "scripts\ops\safe_git_push_rebase_retry.sh",
  "scripts\ops\f1_workflow_meta_health_check_v1.py"
)
$missing = @()
foreach ($rel in $required) {
  $full = Join-Path $repo $rel
  if (!(Test-Path -LiteralPath $full)) { $missing += $rel }
}
if ($missing.Count -gt 0) {
  Write-Host "INSTALL CHECK FAILED"
  $missing | ForEach-Object { Write-Host "Missing: $_" }
  throw "Install check failed."
}

# Lightweight local text check only. No Python/Git required.
$wf = Join-Path $repo ".github\workflows\f1-workbook-kpi-refresh-scheduled.yml"
$txt = Get-Content -LiteralPath $wf -Raw
if ($txt -notmatch "safe_git_push_rebase_retry\.sh") { throw "Scheduled workflow does not use safe push helper." }
if (($txt -split "`n" | Where-Object { $_ -match "^\s*if\s" }).Count -ne ($txt -split "`n" | Where-Object { $_ -match "^\s*fi\s*$" }).Count) {
  throw "Scheduled workflow appears to have if/fi imbalance."
}

$reportDir = Join-Path $repo "latest\installer_reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$report = Join-Path $reportDir "workflow_meta_autorepair_oneclick_fix_install_report.txt"
@(
  "F1 Workflow Meta-AutoRepair One-Click Fix install report",
  "Installed UTC: $([DateTime]::UtcNow.ToString('o'))",
  "Repo: $repo",
  "",
  "Installed:",
  " - fixed f1-workbook-kpi-refresh-scheduled.yml",
  " - scripts/ops/safe_git_push_rebase_retry.sh",
  " - scripts/ops/f1_workflow_meta_health_check_v1.py",
  " - F1 Workflow Meta-Health - Safe Test Button",
  "",
  "Stable engine modified: false",
  "Canonical workbook overwritten: false",
  "Promotion allowed: false",
  "",
  "INSTALL CHECK PASSED"
) | Set-Content -LiteralPath $report -Encoding UTF8
Write-Host ""
Write-Host "INSTALL CHECK PASSED"
Write-Host "Next: commit/push in GitHub Desktop, then run F1 Workflow Meta-Health - Safe Test Button."
