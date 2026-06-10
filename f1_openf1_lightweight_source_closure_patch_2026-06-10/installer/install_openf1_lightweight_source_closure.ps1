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
$ArchiveRoot = Join-Path $Repo ("_archive\openf1_lightweight_source_closure_patch_" + $Stamp)

Write-Host "F1 OpenF1 Lightweight Source Closure + Zero-Lane Diagnostics Patch"
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
    ".github/workflows/f1-openf1-lightweight-source-closure.yml",
    "scripts/openf1/publish_openf1_lightweight_source_closure.py",
    "configs/openf1/openf1_lightweight_source_closure_policy.json",
    "docs/F1_OPENF1_LIGHTWEIGHT_SOURCE_CLOSURE_PATCH_2026-06-10.md",
    "CURRENT_CANONICAL_FILES_OPENF1_LIGHTWEIGHT_SOURCE_CLOSURE_2026-06-10.md",
    "OPENF1_LIGHTWEIGHT_SOURCE_CLOSURE_PATCH_MANIFEST.csv"
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
$InstallReport = Join-Path $ReportDir "F1_OPENF1_LIGHTWEIGHT_SOURCE_CLOSURE_PATCH_INSTALL_REPORT.md"
$Lines = @()
$Lines += "# F1 OpenF1 Lightweight Source Closure Patch Install Report"
$Lines += ""
$Lines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $Lines += "Mode: APPLY" } else { $Lines += "Mode: DRY RUN" }
$Lines += ""
$Lines += "Installed source-closure workflow and publisher for:"
$Lines += "- weather"
$Lines += "- race control"
$Lines += "- intervals"
$Lines += "- position"
$Lines += "- stints"
$Lines += "- pit"
$Lines += "- starting grid"
$Lines += "- drivers"
$Lines += "- team radio when available"
$Lines += ""
$Lines += "Heavy OpenF1 car_data and location are excluded by default."
$Lines += ""
$Lines += "Archived previous copies at:"
$Lines += $ArchiveRoot
$Lines += ""
$Lines += "After commit/push:"
$Lines += "- Run the GitHub workflow: F1 OpenF1 Lightweight Source Closure"
$Lines += "- Verify latest/openf1_lightweight_source_closure/latest_manifest.json exists after the run."
$Lines += "- Verify source_readiness_summary.csv and zero_lane_diagnostics.csv exist."
$Lines += "- Do not rerun heavy OpenF1 car/location extraction unless specifically needed."

if ($Apply) {
    if (!(Test-Path $ReportDir)) { New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null }
    Set-Content -Path $InstallReport -Value $Lines -Encoding UTF8
    Write-Host ("Report: " + $InstallReport)
}

Write-Host ""
Write-Host "OpenF1 lightweight source closure patch complete."

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add .github/workflows/f1-openf1-lightweight-source-closure.yml scripts/openf1/publish_openf1_lightweight_source_closure.py configs/openf1/openf1_lightweight_source_closure_policy.json docs/F1_OPENF1_LIGHTWEIGHT_SOURCE_CLOSURE_PATCH_2026-06-10.md docs/F1_OPENF1_LIGHTWEIGHT_SOURCE_CLOSURE_PATCH_INSTALL_REPORT.md CURRENT_CANONICAL_FILES_OPENF1_LIGHTWEIGHT_SOURCE_CLOSURE_2026-06-10.md OPENF1_LIGHTWEIGHT_SOURCE_CLOSURE_PATCH_MANIFEST.csv _archive
        git commit -m "Add OpenF1 lightweight source closure workflow"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
