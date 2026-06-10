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
$ArchiveRoot = Join-Path $Repo ("_archive\elite_v2_artifact_download_401_hotfix_" + $Stamp)

Write-Host "F1 Elite v2 Artifact Download 401 Hotfix"
Write-Host ("Repo: " + $Repo)
if ($Apply) { Write-Host "Mode: APPLY" } else { Write-Host "Mode: DRY RUN" }

function New-ParentFolder($Path) {
    $parent = Split-Path -Parent $Path
    if ($parent -and !(Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
}

$Files = @(
    "scripts/elite/download_latest_openf1_artifacts.py",
    ".github/workflows/elite-weekend-engine-run.yml",
    "docs/F1_ELITE_V2_ARTIFACT_DOWNLOAD_401_HOTFIX.md",
    "ELITE_V2_ARTIFACT_DOWNLOAD_401_HOTFIX_MANIFEST.csv"
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
$InstallReport = Join-Path $ReportDir "F1_ELITE_V2_ARTIFACT_DOWNLOAD_401_HOTFIX_INSTALL_REPORT.md"
$Lines = @()
$Lines += "# F1 Elite v2 Artifact Download 401 Hotfix Install Report"
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
$Lines += "Expected result:"
$Lines += "- Elite workflow can download latest GitHub Actions artifacts without HTTP 401."
$Lines += "- It should then build real Elite v2 control-room outputs."

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
        git add scripts/elite/download_latest_openf1_artifacts.py .github/workflows/elite-weekend-engine-run.yml docs/F1_ELITE_V2_ARTIFACT_DOWNLOAD_401_HOTFIX.md docs/F1_ELITE_V2_ARTIFACT_DOWNLOAD_401_HOTFIX_INSTALL_REPORT.md ELITE_V2_ARTIFACT_DOWNLOAD_401_HOTFIX_MANIFEST.csv _archive
        git commit -m "Fix Elite v2 artifact download authentication redirect"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
