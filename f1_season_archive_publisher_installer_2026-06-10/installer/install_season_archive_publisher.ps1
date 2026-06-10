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
$ArchiveRoot = Join-Path $Repo ("_archive\season_archive_publisher_patch_" + $Stamp)

Write-Host "F1 Season Archive Publisher Installer"
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
    "configs/archive/season_archive_policy.json",
    "scripts/archive/publish_season_archive_release.py",
    "scripts/admin/create_baseline_tag.ps1",
    ".github/workflows/f1-create-automation-baseline-tag.yml",
    ".github/workflows/f1-season-archive-publisher.yml",
    "docs/F1_SEASON_ARCHIVE_RETENTION_POLICY_2026-06-10.md",
    "docs/F1_SEASON_ARCHIVE_PUBLISHER_RUNBOOK_2026-06-10.md",
    "docs/F1_LONG_TERM_DATA_ARCHIVE_GUIDE_2026-06-10.md",
    "docs/F1_BASELINE_TAG_GUIDE_2026-06-10.md",
    "CURRENT_CANONICAL_FILES_SEASON_ARCHIVE_PUBLISHER_2026-06-10.md",
    "SEASON_ARCHIVE_PUBLISHER_PATCH_MANIFEST.csv"
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
$InstallReport = Join-Path $ReportDir "F1_SEASON_ARCHIVE_PUBLISHER_INSTALL_REPORT.md"
$Lines = @()
$Lines += "# F1 Season Archive Publisher Install Report"
$Lines += ""
$Lines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $Lines += "Mode: APPLY" } else { $Lines += "Mode: DRY RUN" }
$Lines += ""
$Lines += "Installed:"
$Lines += "- Baseline tag workflow"
$Lines += "- Season archive publisher workflow"
$Lines += "- GitHub Release publisher script"
$Lines += "- Long-term retention/archive policy docs"
$Lines += ""
$Lines += "Archived previous copies at:"
$Lines += $ArchiveRoot
$Lines += ""
$Lines += "After commit/push:"
$Lines += "1. Run F1 Create Automation Baseline Tag"
$Lines += "2. Run F1 Season Archive Publisher"
$Lines += ""
$Lines += "No OpenF1 extraction workflow rerun is required."

if ($Apply) {
    if (!(Test-Path $ReportDir)) { New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null }
    Set-Content -Path $InstallReport -Value $Lines -Encoding UTF8
    Write-Host ("Report: " + $InstallReport)
}

Write-Host ""
Write-Host "Season archive publisher patch complete."

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add configs/archive scripts/archive scripts/admin/create_baseline_tag.ps1 .github/workflows/f1-create-automation-baseline-tag.yml .github/workflows/f1-season-archive-publisher.yml docs CURRENT_CANONICAL_FILES_SEASON_ARCHIVE_PUBLISHER_2026-06-10.md SEASON_ARCHIVE_PUBLISHER_PATCH_MANIFEST.csv _archive
        git commit -m "Add F1 season archive publisher and baseline tag workflow"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
