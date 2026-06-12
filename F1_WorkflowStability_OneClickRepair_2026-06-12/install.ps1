$ErrorActionPreference = "Stop"

Write-Host "F1 Workflow Stability One-Click Repair"
Write-Host "-------------------------------------"

$defaultRepo = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
$repo = Read-Host "Repo path [$defaultRepo]"
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $defaultRepo }
$repo = $repo.Trim('"')

if (!(Test-Path $repo)) {
  throw "Repo path not found: $repo"
}

$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$payload = Join-Path $patchRoot "payload"
if (!(Test-Path $payload)) {
  throw "Payload folder missing: $payload"
}

Write-Host "Copying payload files..."
Copy-Item -Path (Join-Path $payload "*") -Destination $repo -Recurse -Force

# Patch commit-producing workflows to use safe push and serialization.
$workflowDir = Join-Path $repo ".github\workflows"
$patchedFiles = @()

if (Test-Path $workflowDir) {
  Get-ChildItem $workflowDir -Filter "*.yml" | ForEach-Object {
    $path = $_.FullName
    $text = Get-Content $path -Raw

    $original = $text

    # Replace raw git push commands with governed safe push helper.
    $text = [regex]::Replace($text, "(?m)^(\s*)git push(\s.*)?$", '$1bash scripts/ops/safe_git_push_rebase_retry.sh')

    # Add shared write serialization only to workflows that push/commit to repo.
    if (($text -match "safe_git_push_rebase_retry\.sh" -or $text -match "git commit") -and ($text -notmatch "(?m)^concurrency:\s*$")) {
      $text = [regex]::Replace($text, "(?m)^jobs:\s*$", "concurrency:`n  group: f1-main-write-serialization`n  cancel-in-progress: false`n`njobs:", 1)
    }

    if ($text -ne $original) {
      Set-Content -Path $path -Value $text -Encoding UTF8
      $patchedFiles += $path
    }
  }
}

# Validate required files exist.
$required = @(
  "scripts\ops\safe_git_push_rebase_retry.sh",
  "scripts\microdelta\run_cross_car_microdelta_forensics_v0.py",
  ".github\workflows\f1-cross-car-microdelta-forensics-v0-experimental.yml"
)

$missing = @()
foreach ($rel in $required) {
  $full = Join-Path $repo $rel
  if (!(Test-Path $full)) { $missing += $rel }
}

if ($missing.Count -gt 0) {
  Write-Host "INSTALL CHECK FAILED. Missing files:"
  $missing | ForEach-Object { Write-Host " - $_" }
  throw "Install failed: missing required files."
}

$reportDir = Join-Path $repo "latest\installer_reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$reportPath = Join-Path $reportDir "workflow_stability_oneclick_repair_install_report.txt"

@(
  "F1 Workflow Stability One-Click Repair install report",
  "Installed UTC: $([DateTime]::UtcNow.ToString('o'))",
  "Repo: $repo",
  "",
  "Files copied:",
  " - scripts/ops/safe_git_push_rebase_retry.sh",
  " - scripts/microdelta/run_cross_car_microdelta_forensics_v0.py",
  " - .github/workflows/f1-cross-car-microdelta-forensics-v0-experimental.yml",
  "",
  "Workflow files patched for safe push / write serialization:",
  ($patchedFiles | ForEach-Object { " - $_" }),
  "",
  "Stable engine modified: false",
  "Canonical workbook overwritten: false",
  "Promotion allowed: false",
  "",
  "INSTALL CHECK PASSED"
) | Set-Content -Path $reportPath -Encoding UTF8

Write-Host ""
Write-Host "INSTALL CHECK PASSED"
Write-Host "Patched workflow files:"
$patchedFiles | ForEach-Object { Write-Host " - $_" }
Write-Host ""
Write-Host "Next: commit and push in GitHub Desktop, then validate the two failed workflows."
