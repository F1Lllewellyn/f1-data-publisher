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
$ArchiveRoot = Join-Path $Repo ("_archive\openf1_autopilot_workflow_patch_" + $Stamp)

Write-Host "F1 OpenF1 Autopilot Workflow Installer"
Write-Host ("Repo: " + $Repo)
if ($Apply) { Write-Host "Mode: APPLY" } else { Write-Host "Mode: DRY RUN" }
Write-Host ""

function New-ParentFolder($Path) {
    $parent = Split-Path -Parent $Path
    if ($parent -and !(Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
}

function Copy-PayloadFile($RelativePath) {
    $src = Join-Path $PayloadRoot $RelativePath
    $dst = Join-Path $Repo $RelativePath

    if (!(Test-Path $src)) {
        throw "Missing payload file: $RelativePath"
    }

    if ($Apply) {
        New-ParentFolder $dst
        Copy-Item -Force -Path $src -Destination $dst
    }

    Write-Host ("copy: " + $RelativePath)
}

$OldWorkflowPaths = @(
    ".github/workflows/openf1-high-frequency-auto-ingest.yml",
    ".github/workflows/openf1-post-event-reliability-metric.yml"
)

foreach ($rel in $OldWorkflowPaths) {
    $old = Join-Path $Repo $rel
    if (Test-Path $old) {
        $archived = Join-Path $ArchiveRoot $rel
        if ($Apply) {
            New-ParentFolder $archived
            Move-Item -Force -Path $old -Destination $archived
        }
        Write-Host ("archive old workflow: " + $rel)
    } else {
        Write-Host ("old workflow not present: " + $rel)
    }
}

$FilesToCopy = @(
    ".github/workflows/openf1-prerace-auto-ingest.yml",
    ".github/workflows/openf1-full-historical-auto-ingest.yml",
    ".github/workflows/openf1-post-race-auto-reliability.yml",
    "scripts/openf1/openf1_high_frequency_extract_checkpoint.py",
    "scripts/openf1/openf1_high_frequency_report_only.py",
    "docs/README_OPENF1_AUTOPILOT_WORKFLOWS.md",
    "AUTOPILOT_PAYLOAD_MANIFEST.csv"
)

foreach ($f in $FilesToCopy) {
    Copy-PayloadFile $f
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
$Report = Join-Path $ReportDir "F1_OPENF1_AUTOPILOT_WORKFLOW_PATCH_REPORT.md"
$ReportLines = @()
$ReportLines += "# F1 OpenF1 Autopilot Workflow Patch Report"
$ReportLines += ""
$ReportLines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $ReportLines += "Mode: APPLY" } else { $ReportLines += "Mode: DRY RUN" }
$ReportLines += ""
$ReportLines += "Installed dedicated automated workflows:"
$ReportLines += "- OpenF1 Pre-Race Auto Ingest"
$ReportLines += "- OpenF1 Full Historical Auto Ingest"
$ReportLines += "- OpenF1 Post-Race Auto Reliability"
$ReportLines += ""
$ReportLines += "Checkpoint architecture:"
$ReportLines += "- extract_and_checkpoint job uploads extraction checkpoint immediately after the expensive pull."
$ReportLines += "- validate_report_and_upload job downloads the checkpoint and writes/validates reports without re-extracting."
$ReportLines += ""
$ReportLines += "Archived old workflows:"
foreach ($rel in $OldWorkflowPaths) {
    $ReportLines += "- " + $rel
}
$ReportLines += ""
$ReportLines += "Archive root:"
$ReportLines += $ArchiveRoot
$ReportLines += ""
$ReportLines += "Guardrails:"
$ReportLines += "- Public/proxy OpenF1 data only."
$ReportLines += "- No automatic stable race P1-P20 rank changes."
$ReportLines += "- No automatic qualifying P1-P5 rank changes."
$ReportLines += "- DNF_ALL precursor-search policy preserved."
$ReportLines += "- 2026 no-DRS rule preserved."

if ($Apply) {
    if (!(Test-Path $ReportDir)) { New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null }
    Set-Content -Path $Report -Value $ReportLines -Encoding UTF8
    Write-Host ("Report: " + $Report)
} else {
    $ReportLines | ForEach-Object { Write-Host $_ }
}

Write-Host ""
Write-Host "Autopilot workflow patch complete."

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add .github/workflows scripts/openf1 docs requirements-openf1-ingest.txt requirements-f1-engine-automation.txt AUTOPILOT_PAYLOAD_MANIFEST.csv _archive
        git commit -m "Add OpenF1 autopilot workflows with extraction checkpoints"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
