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
$ArchiveRoot = Join-Path $Repo ("_archive\season_archive_expanded_operational_artifacts_patch_" + $Stamp)

Write-Host "F1 Season Archive Expanded Operational Artifacts Patch"
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
    "scripts/archive/publish_season_archive_release.py",
    "configs/archive/season_archive_policy.json",
    "docs/F1_SEASON_ARCHIVE_EXPANDED_OPERATIONAL_ARTIFACTS_2026-06-10.md",
    "CURRENT_CANONICAL_FILES_SEASON_ARCHIVE_EXPANDED_2026-06-10.md",
    "SEASON_ARCHIVE_EXPANDED_PATCH_MANIFEST.csv"
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
$InstallReport = Join-Path $ReportDir "F1_SEASON_ARCHIVE_EXPANDED_PATCH_INSTALL_REPORT.md"
$Lines = @()
$Lines += "# F1 Season Archive Expanded Operational Artifacts Patch Install Report"
$Lines += ""
$Lines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $Lines += "Mode: APPLY" } else { $Lines += "Mode: DRY RUN" }
$Lines += ""
$Lines += "Updated archive publisher to include:"
$Lines += "- f1-forecast-use-dry-review"
$Lines += "- f1-race-weekend-operating-rhythm"
$Lines += "- f1-post-race-scoring-loop"
$Lines += ""
$Lines += "Archived previous copies at:"
$Lines += $ArchiveRoot
$Lines += ""
$Lines += "After commit/push:"
$Lines += "- Run F1 Season Archive Publisher once."
$Lines += "- Do not rerun OpenF1 extraction workflows."

if ($Apply) {
    if (!(Test-Path $ReportDir)) { New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null }
    Set-Content -Path $InstallReport -Value $Lines -Encoding UTF8
    Write-Host ("Report: " + $InstallReport)
}

Write-Host ""
Write-Host "Expanded archive patch complete."

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add scripts/archive/publish_season_archive_release.py configs/archive/season_archive_policy.json docs/F1_SEASON_ARCHIVE_EXPANDED_OPERATIONAL_ARTIFACTS_2026-06-10.md docs/F1_SEASON_ARCHIVE_EXPANDED_PATCH_INSTALL_REPORT.md CURRENT_CANONICAL_FILES_SEASON_ARCHIVE_EXPANDED_2026-06-10.md SEASON_ARCHIVE_EXPANDED_PATCH_MANIFEST.csv _archive
        git commit -m "Expand F1 season archive to include operational artifacts"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
