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
$ArchiveRoot = Join-Path $Repo ("_archive\postrace_empty_feature_validator_hotfix_" + $Stamp)

Write-Host "F1 OpenF1 Post-Race Empty Feature Validator Hotfix"
Write-Host ("Repo: " + $Repo)
if ($Apply) { Write-Host "Mode: APPLY" } else { Write-Host "Mode: DRY RUN" }

function New-ParentFolder($Path) {
    $parent = Split-Path -Parent $Path
    if ($parent -and !(Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
}

$Files = @(
    "tests/validate_openf1_high_frequency_output.py",
    ".github/workflows/openf1-post-race-auto-reliability.yml",
    "docs/F1_OPENF1_POSTRACE_EMPTY_FEATURE_HOTFIX.md"
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
$InstallReport = Join-Path $ReportDir "F1_OPENF1_POSTRACE_EMPTY_FEATURE_HOTFIX_INSTALL_REPORT.md"
$Lines = @()
$Lines += "# F1 OpenF1 Post-Race Empty Feature Validator Hotfix Install Report"
$Lines += ""
$Lines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $Lines += "Mode: APPLY" } else { $Lines += "Mode: DRY RUN" }
$Lines += ""
$Lines += "Patched files:"
foreach ($rel in $Files) { $Lines += "- " + $rel }
$Lines += ""
$Lines += "Archived previous copies at:"
$Lines += $ArchiveRoot
$Lines += ""
$Lines += "Expected behavior:"
$Lines += "- Post-race race-mode runs with successful extraction but zero feature rows now return PASS_WITH_WARNINGS."
$Lines += "- Pre-race and full-historical runs remain strict."
$Lines += "- Zero-feature post-race runs are not valid forecast/fantasy/stable-rank signals."

if ($Apply) {
    if (!(Test-Path $ReportDir)) { New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null }
    Set-Content -Path $InstallReport -Value $Lines -Encoding UTF8
    Write-Host ("Report: " + $InstallReport)
}

Write-Host "Hotfix complete."

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add tests/validate_openf1_high_frequency_output.py .github/workflows/openf1-post-race-auto-reliability.yml docs/F1_OPENF1_POSTRACE_EMPTY_FEATURE_HOTFIX.md docs/F1_OPENF1_POSTRACE_EMPTY_FEATURE_HOTFIX_INSTALL_REPORT.md _archive
        git commit -m "Relax post-race validator for empty feature checkpoints"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
