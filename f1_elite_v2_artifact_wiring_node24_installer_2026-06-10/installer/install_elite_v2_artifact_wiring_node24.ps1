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
$ArchiveRoot = Join-Path $Repo ("_archive\elite_v2_artifact_wiring_node24_patch_" + $Stamp)

Write-Host "F1 Elite v2 Artifact Wiring + Node24 Installer"
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
    ".github/workflows/openf1-prerace-auto-ingest.yml",
    ".github/workflows/openf1-full-historical-auto-ingest.yml",
    ".github/workflows/openf1-post-race-auto-reliability.yml",
    ".github/workflows/elite-weekend-engine-run.yml",
    "scripts/openf1/openf1_high_frequency_extract_checkpoint.py",
    "scripts/openf1/openf1_high_frequency_report_only.py",
    "scripts/elite/download_latest_openf1_artifacts.py",
    "scripts/elite/elite_weekend_engine_v2.py",
    "docs/F1_ELITE_V2_ARTIFACT_WIRING_NODE24_PATCH.md",
    "ELITE_V2_NODE24_PAYLOAD_MANIFEST.csv"
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

$ReqFiles = @(
    "requirements-openf1-ingest.txt",
    "requirements-f1-engine-automation.txt"
)

foreach ($rel in $ReqFiles) {
    $path = Join-Path $Repo $rel
    if (Test-Path $path) {
        $txt = Get-Content $path -Raw
    } else {
        $txt = ""
    }

    $changed = $false
    foreach ($dep in @("requests", "pandas", "pyarrow", "tqdm", "python-dateutil", "numpy", "tabulate")) {
        if ($txt -notmatch ("(?m)^" + [regex]::Escape($dep) + "\s*$")) {
            if ($txt.Length -gt 0 -and -not $txt.EndsWith("`n")) { $txt += "`n" }
            $txt += $dep + "`n"
            $changed = $true
        }
    }

    if ($Apply -and $changed) {
        Set-Content -Path $path -Value $txt -Encoding UTF8
    }
    Write-Host ("requirements checked: " + $rel)
}

$ReportDir = Join-Path $Repo "docs"
$InstallReport = Join-Path $ReportDir "F1_ELITE_V2_ARTIFACT_WIRING_NODE24_INSTALL_REPORT.md"
$Lines = @()
$Lines += "# F1 Elite v2 Artifact Wiring + Node24 Install Report"
$Lines += ""
$Lines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $Lines += "Mode: APPLY" } else { $Lines += "Mode: DRY RUN" }
$Lines += ""
$Lines += "Installed:"
$Lines += "- Elite Weekend Engine Run v2 artifact consumer"
$Lines += "- Latest OpenF1 artifact downloader"
$Lines += "- Real control-room output builder"
$Lines += "- Node 24 opt-in on OpenF1 and Elite workflows"
$Lines += ""
$Lines += "Archived previous copies at:"
$Lines += $ArchiveRoot
$Lines += ""
$Lines += "Expected Elite output:"
$Lines += "- source_readiness_board.csv"
$Lines += "- reliability_warning_board.csv"
$Lines += "- dnf_all_precursor_board.csv"
$Lines += "- fantasy_risk_board.csv"
$Lines += "- model_disagreement_board.csv"
$Lines += "- promotion_demotion_gate.csv"
$Lines += "- locked_forecast_ledger_snapshot.json"
$Lines += "- elite_weekend_engine_v2_report.md"
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
Write-Host "Elite v2 + Node24 patch complete."

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add .github/workflows scripts/openf1 scripts/elite docs requirements-openf1-ingest.txt requirements-f1-engine-automation.txt ELITE_V2_NODE24_PAYLOAD_MANIFEST.csv _archive
        git commit -m "Wire Elite Weekend Engine to OpenF1 artifacts and opt into Node24"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
