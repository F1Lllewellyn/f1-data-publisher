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
$ArchiveRoot = Join-Path $Repo ("_archive\all5_operational_baseline_patch_" + $Stamp)

Write-Host "F1 All-5 Operational Baseline Patch Installer"
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
    "docs/F1_AUTOMATION_OPERATIONAL_BASELINE_2026-06-10.md",
    "docs/F1_NEXT_FORECAST_CYCLE_RUNBOOK_2026-06-10.md",
    "docs/F1_WORKBOOK_CONTROL_ROOM_BRIDGE_2026-06-10.md",
    "scripts/openf1/openf1_feature_fallback.py",
    "scripts/openf1/openf1_high_frequency_extract_checkpoint.py",
    "scripts/elite/elite_weekend_engine_v2.py",
    ".github/workflows/openf1-post-race-auto-reliability.yml",
    ".github/workflows/elite-weekend-engine-run.yml",
    "CURRENT_CANONICAL_FILES_AUTOMATION_OPERATIONAL_BASELINE_2026-06-10.md",
    "ALL5_OPERATIONAL_PATCH_MANIFEST.csv"
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
$InstallReport = Join-Path $ReportDir "F1_ALL5_OPERATIONAL_PATCH_INSTALL_REPORT.md"
$Lines = @()
$Lines += "# F1 All-5 Operational Patch Install Report"
$Lines += ""
$Lines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $Lines += "Mode: APPLY" } else { $Lines += "Mode: DRY RUN" }
$Lines += ""
$Lines += "Completed items:"
$Lines += "1. Locked automation baseline"
$Lines += "2. Added post-race zero-feature fallback feature builder"
$Lines += "3. Added workbook/control-room bridge exports"
$Lines += "4. Improved Elite GitHub summary reporting"
$Lines += "5. Added next forecast-cycle runbook"
$Lines += ""
$Lines += "Archived previous copies at:"
$Lines += $ArchiveRoot
$Lines += ""
$Lines += "Validation recommendation:"
$Lines += "- Run OpenF1 Post-Race Auto Reliability once."
$Lines += "- Then run Elite Weekend Engine Run once."
$Lines += "- Do not rerun OpenF1 Full Historical Auto Ingest unless explicitly needed."
$Lines += ""
$Lines += "Guardrails:"
$Lines += "- Public/proxy OpenF1 data only."
$Lines += "- No automatic stable race P1-P20 rank changes."
$Lines += "- No automatic qualifying P1-P5 rank changes."
$Lines += "- DNF_ALL broad precursor-search policy preserved."
$Lines += "- 2026 no-DRS rule preserved."

if ($Apply) {
    if (!(Test-Path $ReportDir)) { New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null }
    Set-Content -Path $InstallReport -Value $Lines -Encoding UTF8
    Write-Host ("Report: " + $InstallReport)
}

Write-Host ""
Write-Host "All-5 operational patch complete."

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add docs scripts/openf1 scripts/elite .github/workflows/openf1-post-race-auto-reliability.yml .github/workflows/elite-weekend-engine-run.yml CURRENT_CANONICAL_FILES_AUTOMATION_OPERATIONAL_BASELINE_2026-06-10.md ALL5_OPERATIONAL_PATCH_MANIFEST.csv _archive
        git commit -m "Complete F1 automation operational baseline and workbook bridge"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
