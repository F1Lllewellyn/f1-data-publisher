$ErrorActionPreference = "Stop"
function Write-Step($m){ Write-Host "[F1DashRepair] $m" }

$defaultRepo = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
$inputPath = Read-Host "Repo path [$defaultRepo]"
if ([string]::IsNullOrWhiteSpace($inputPath)) { $repo = $defaultRepo } else { $repo = $inputPath }
$repo = [System.IO.Path]::GetFullPath($repo)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$payload = Join-Path $here "payload"

Write-Step "Using repo: $repo"
if (!(Test-Path -LiteralPath $repo -PathType Container)) { throw "Repo folder not found: $repo" }
if (!(Test-Path -LiteralPath $payload -PathType Container)) { throw "Payload folder not found: $payload" }

$dirs = @(
  ".github\workflows",
  "scripts\dashboard_connector",
  "configs\dashboard_connector",
  "schemas\dashboard_connector"
)
foreach ($d in $dirs) {
  $target = Join-Path $repo $d
  if (!(Test-Path -LiteralPath $target)) {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
  }
}

Write-Step "Copying dashboard connector payload with quoted PowerShell paths..."
$files = @(
  ".github\workflows\f1-forecast-fantasy-readiness-dashboard-safe-test.yml",
  ".github\workflows\f1-forecast-fantasy-readiness-dashboard-run-now.yml",
  ".github\workflows\f1-forecast-fantasy-readiness-dashboard-scheduled.yml",
  "scripts\dashboard_connector\health_check_dashboard_connector_v1.py",
  "scripts\dashboard_connector\publish_forecast_fantasy_readiness_dashboards_v1.py",
  "configs\dashboard_connector\dashboard_connector_policy_v1.json",
  "schemas\dashboard_connector\dashboard_state_schema_v1.json"
)

foreach ($rel in $files) {
  $src = Join-Path $payload $rel
  $dst = Join-Path $repo $rel
  if (!(Test-Path -LiteralPath $src -PathType Leaf)) { throw "Payload missing: $src" }
  $parent = Split-Path -Parent $dst
  if (!(Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  Copy-Item -LiteralPath $src -Destination $dst -Force
}

Write-Step "Verifying required files now exist in repo..."
$missing = @()
foreach ($rel in $files) {
  $dst = Join-Path $repo $rel
  if (Test-Path -LiteralPath $dst -PathType Leaf) { Write-Host "OK: $rel" } else { Write-Host "MISSING: $dst"; $missing += $dst }
}
if ($missing.Count -gt 0) { throw "Missing required files after copy: $($missing -join '; ')" }

Write-Step "Running local syntax checks..."
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
  & python -m py_compile (Join-Path $repo "scripts\dashboard_connector\health_check_dashboard_connector_v1.py")
  & python -m py_compile (Join-Path $repo "scripts\dashboard_connector\publish_forecast_fantasy_readiness_dashboards_v1.py")
  if ($LASTEXITCODE -ne 0) { throw "Python compile check failed." }
} else {
  Write-Host "Python not found locally; skipping local compile check. GitHub will run it."
}

Write-Step "Install complete."
exit 0
