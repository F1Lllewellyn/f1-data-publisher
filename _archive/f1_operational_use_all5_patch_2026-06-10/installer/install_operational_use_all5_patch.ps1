param(
    [Parameter(Mandatory=$true)]
    [string]$Repo,

    [switch]$Apply,
    [switch]$Commit,
    [switch]$Push
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $Repo)) {
    throw "Repo path does not exist: $Repo"
}

$Repo = (Resolve-Path $Repo).Path
$InstallerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $InstallerDir
$PayloadRoot = Join-Path $PackageRoot "payload"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ArchiveRoot = Join-Path $Repo ("_archive\operational_use_all5_patch_" + $Stamp)

Write-Host "F1 Operational Use All-5 Patch Installer"
Write-Host ("Repo: " + $Repo)
if ($Apply) { Write-Host "Mode: APPLY" } else { Write-Host "Mode: DRY RUN" }
Write-Host ""

function New-ParentFolder($Path) {
    $parent = Split-Path -Parent $Path
    if ($parent -and !(Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
}

$Files = @(
    "configs/forecast/forecast_consumption_policy.json",
    "scripts/admin/create_automation_baseline_snapshot.py",
    "scripts/admin/create_baseline_tag.ps1",
    "scripts/elite/download_latest_elite_artifact.py",
    "scripts/workbook/build_workbook_control_room_bridge.py",
    "scripts/forecast/build_dry_forecast_cycle.py",
    ".github/workflows/f1-automation-baseline-snapshot.yml",
    ".github/workflows/f1-workbook-control-room-bridge.yml",
    ".github/workflows/f1-dry-forecast-cycle.yml",
    "docs/F1_AUTOMATION_RELEASE_BASELINE_2026-06-10_READY.md",
    "docs/F1_FORECAST_CONSUMPTION_RULES_2026-06-10.md",
    "docs/F1_OPERATIONAL_USE_RUNBOOK_2026-06-10.md",
    "docs/F1_WORKBOOK_BRIDGE_IMPORT_GUIDE_2026-06-10.md",
    "docs/F1_DRY_FORECAST_CYCLE_GUIDE_2026-06-10.md",
    "CURRENT_CANONICAL_FILES_OPERATIONAL_USE_PATCH_2026-06-10.md",
    "OPERATIONAL_USE_ALL5_PATCH_MANIFEST.csv"
)

foreach ($rel in $Files) {
    $src = Join-Path $PayloadRoot $rel
    $dst = Join-Path $Repo $rel

    if (!(Test-Path $src)) {
        throw "Missing payload file: $rel"
    }

    if ((Test-Path $dst) -and $Apply) {
        $arch = Join-Path $ArchiveRoot $rel
        New-ParentFolder $arch
        Copy-Item -Force -Path $dst -Destination $arch
    }

    if ($Apply) {
        New-ParentFolder $dst
        Copy-Item -Force -Path $src -Destination $dst
    }

    Write-Host ("patched: " + $rel)
}

$ReportDir = Join-Path $Repo "docs"
$InstallReport = Join-Path $ReportDir "F1_OPERATIONAL_USE_ALL5_PATCH_INSTALL_REPORT.md"
$Lines = @()
$Lines += "# F1 Operational Use All-5 Patch Install Report"
$Lines += ""
$Lines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $Lines += "Mode: APPLY" } else { $Lines += "Mode: DRY RUN" }
$Lines += ""
$Lines += "Completed items:"
$Lines += "1. Release baseline/snapshot workflow and tag helper"
$Lines += "2. Workbook/control-room bridge workflow"
$Lines += "3. Forecast-consumption policy"
$Lines += "4. Dry forecast cycle workflow"
$Lines += "5. Next race-weekend operational runbook"
$Lines += ""
$Lines += "Archived previous copies at:"
$Lines += $ArchiveRoot
$Lines += ""
$Lines += "After commit/push, run only these small workflows:"
$Lines += "- F1 Automation Baseline Snapshot"
$Lines += "- F1 Workbook Control Room Bridge"
$Lines += "- F1 Dry Forecast Cycle"
$Lines += ""
$Lines += "Do not rerun large OpenF1 extraction workflows."

if ($Apply) {
    if (!(Test-Path $ReportDir)) { New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null }
    Set-Content -Path $InstallReport -Value $Lines -Encoding UTF8
    Write-Host ("Report: " + $InstallReport)
}

Write-Host ""
Write-Host "Operational use all-5 patch complete."

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add configs/forecast scripts/admin scripts/elite/download_latest_elite_artifact.py scripts/workbook scripts/forecast .github/workflows/f1-automation-baseline-snapshot.yml .github/workflows/f1-workbook-control-room-bridge.yml .github/workflows/f1-dry-forecast-cycle.yml docs CURRENT_CANONICAL_FILES_OPERATIONAL_USE_PATCH_2026-06-10.md OPERATIONAL_USE_ALL5_PATCH_MANIFEST.csv _archive
        git commit -m "Add F1 operational baseline, workbook bridge, and dry forecast cycle"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
