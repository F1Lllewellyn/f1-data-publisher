$ErrorActionPreference = "Stop"
function Step($m){ Write-Host "[F1DashNoPy] $m" }
function Fail($m){ throw "[F1DashNoPy] $m" }

$defaultRepo = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
$inputPath = Read-Host "Repo path [$defaultRepo]"
if ([string]::IsNullOrWhiteSpace($inputPath)) { $repo = $defaultRepo } else { $repo = $inputPath }
$repo = [System.IO.Path]::GetFullPath($repo)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$payload = Join-Path $here "payload"
$installReport = Join-Path $here "install_report.txt"

Step "Using repo: $repo"
if (!(Test-Path -LiteralPath $repo -PathType Container)) { Fail "Repo folder not found: $repo" }
if (!(Test-Path -LiteralPath $payload -PathType Container)) { Fail "Payload folder not found: $payload" }

$required = @(
  ".github\workflows\f1-forecast-fantasy-readiness-dashboard-safe-test.yml",
  ".github\workflows\f1-forecast-fantasy-readiness-dashboard-run-now.yml",
  ".github\workflows\f1-forecast-fantasy-readiness-dashboard-scheduled.yml",
  "scripts\dashboard_connector\health_check_dashboard_connector_v1.py",
  "scripts\dashboard_connector\publish_forecast_fantasy_readiness_dashboards_v1.py",
  "configs\dashboard_connector\dashboard_connector_policy_v1.json",
  "schemas\dashboard_connector\dashboard_state_schema_v1.json"
)

Step "Creating destination folders with safe quoted paths..."
foreach ($rel in $required) {
  $dst = Join-Path $repo $rel
  $parent = Split-Path -Parent $dst
  if (!(Test-Path -LiteralPath $parent -PathType Container)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
}

Step "Copying complete dashboard connector payload..."
foreach ($rel in $required) {
  $src = Join-Path $payload $rel
  $dst = Join-Path $repo $rel
  if (!(Test-Path -LiteralPath $src -PathType Leaf)) { Fail "Payload missing: $src" }
  Copy-Item -LiteralPath $src -Destination $dst -Force
}

Step "Verifying required files now exist in repo..."
$missing = @()
foreach ($rel in $required) {
  $dst = Join-Path $repo $rel
  if (Test-Path -LiteralPath $dst -PathType Leaf) { Write-Host "OK: $rel" } else { Write-Host "MISSING: $dst"; $missing += $dst }
}
if ($missing.Count -gt 0) { Fail "Missing required files after copy: $($missing -join '; ')" }

# No local Python requirement. GitHub Actions owns Python runtime validation.
# This avoids Windows Microsoft Store Python alias failures on non-developer machines.
Step "Skipping local Python compile check by design. GitHub Safe Test will validate runtime."

$report = @()
$report += "F1 Dashboard Connector No-Local-Python Installer"
$report += "Timestamp: $(Get-Date -Format o)"
$report += "Repo: $repo"
$report += "Result: INSTALL_CHECK_PASSED"
$report += "Local Python required: false"
$report += "Files installed:"
foreach ($rel in $required) { $report += "- $rel" }
Set-Content -LiteralPath $installReport -Value ($report -join [Environment]::NewLine) -Encoding UTF8

Step "INSTALL CHECK PASSED. Open GitHub Desktop, commit, and push."
exit 0
