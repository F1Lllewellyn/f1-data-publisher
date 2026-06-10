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
$ArchiveRoot = Join-Path $Repo ("_archive\control_room_forecast_scoring_patch_" + $Stamp)

Write-Host "F1 Control Room + Forecast Review + Post-Race Scoring Installer"
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
    "workbooks/F1_2026_Prediction_Model_Data_Workbook_OPERATIONAL_CONTROL_ROOM_READY_2026-06-10.xlsx",
    "configs/forecast/forecast_review_policy.json",
    "configs/scoring/post_race_scoring_policy.json",
    "scripts/forecast/build_forecast_use_dry_review.py",
    "scripts/scoring/build_post_race_scoring_loop.py",
    ".github/workflows/f1-forecast-use-dry-review.yml",
    ".github/workflows/f1-post-race-scoring-loop.yml",
    ".github/workflows/f1-race-weekend-operating-rhythm.yml",
    "docs/F1_OPERATIONAL_CONTROL_ROOM_WORKBOOK_READY_2026-06-10.md",
    "docs/F1_FORECAST_USE_DRY_REVIEW_READY_2026-06-10.md",
    "docs/F1_POST_RACE_SCORING_LOOP_READY_2026-06-10.md",
    "docs/F1_RACE_WEEKEND_OPERATING_RHYTHM_READY_2026-06-10.md",
    "docs/F1_NO_V_VERSION_WORKBOOK_NAMING_NOTE_2026-06-10.md",
    "CURRENT_CANONICAL_FILES_CONTROL_ROOM_FORECAST_SCORING_2026-06-10.md",
    "CONTROL_ROOM_FORECAST_SCORING_PATCH_MANIFEST.csv"
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
$InstallReport = Join-Path $ReportDir "F1_CONTROL_ROOM_FORECAST_SCORING_INSTALL_REPORT.md"
$Lines = @()
$Lines += "# F1 Control Room + Forecast Review + Post-Race Scoring Install Report"
$Lines += ""
$Lines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $Lines += "Mode: APPLY" } else { $Lines += "Mode: DRY RUN" }
$Lines += ""
$Lines += "Installed:"
$Lines += "- Operational control-room workbook, no v18/v-version naming"
$Lines += "- Forecast-use dry review workflow"
$Lines += "- Race weekend operating rhythm workflow"
$Lines += "- Post-race scoring loop workflow"
$Lines += "- Forecast/scoring policy files and docs"
$Lines += ""
$Lines += "Archived previous copies at:"
$Lines += $ArchiveRoot
$Lines += ""
$Lines += "After commit/push, run only these small workflows:"
$Lines += "- F1 Forecast Use Dry Review"
$Lines += "- F1 Race Weekend Operating Rhythm"
$Lines += "- F1 Post-Race Scoring Loop"
$Lines += ""
$Lines += "Do not rerun large OpenF1 extraction workflows."

if ($Apply) {
    if (!(Test-Path $ReportDir)) { New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null }
    Set-Content -Path $InstallReport -Value $Lines -Encoding UTF8
    Write-Host ("Report: " + $InstallReport)
}

Write-Host ""
Write-Host "Control room / forecast / scoring patch complete."

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add workbooks configs/forecast/forecast_review_policy.json configs/scoring scripts/forecast scripts/scoring .github/workflows/f1-forecast-use-dry-review.yml .github/workflows/f1-post-race-scoring-loop.yml .github/workflows/f1-race-weekend-operating-rhythm.yml docs CURRENT_CANONICAL_FILES_CONTROL_ROOM_FORECAST_SCORING_2026-06-10.md CONTROL_ROOM_FORECAST_SCORING_PATCH_MANIFEST.csv _archive
        git commit -m "Add operational control room workbook, forecast review, and scoring loop"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
