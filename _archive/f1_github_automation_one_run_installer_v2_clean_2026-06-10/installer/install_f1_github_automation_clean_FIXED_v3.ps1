param(
    [Parameter(Mandatory=$true)]
    [string]$Repo,

    [switch]$Apply,
    [switch]$NoCleanOld,
    [switch]$Commit,
    [switch]$Push
)

$ErrorActionPreference = "Stop"

$InstallerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $InstallerDir
$PayloadRoot = Join-Path $PackageRoot "payload"
$CleanupJson = Join-Path $PayloadRoot "CLEANUP_TARGETS.json"
$GitignoreBlockFile = Join-Path $PayloadRoot "F1_GITIGNORE_BLOCK.txt"

if (!(Test-Path $Repo)) {
    throw "Repo path does not exist: $Repo"
}

$Repo = (Resolve-Path $Repo).Path
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ArchiveRoot = Join-Path $Repo ("_archive\f1_github_automation_preinstall_cleanup_" + $Stamp)

Write-Host "F1 GitHub automation CLEAN installer - FIXED v3"
Write-Host ("Repo: " + $Repo)
if ($Apply) { Write-Host "Mode: APPLY" } else { Write-Host "Mode: DRY RUN" }
if ($NoCleanOld) { Write-Host "Clean old paths: False" } else { Write-Host "Clean old paths: True" }
Write-Host ""

$SkipPayloadFiles = @("PAYLOAD_MANIFEST.csv", "F1_GITIGNORE_BLOCK.txt", "CLEANUP_TARGETS.json")

function New-ParentFolder($Path) {
    $parent = Split-Path -Parent $Path
    if ($parent -and !(Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
}

function Get-UniquePath($Path) {
    if (!(Test-Path $Path)) { return $Path }
    $i = 1
    while ($true) {
        $Candidate = $Path + "__" + $i
        if (!(Test-Path $Candidate)) { return $Candidate }
        $i = $i + 1
    }
}

$CleanupRows = @()

if (-not $NoCleanOld) {
    $CleanupConfig = Get-Content $CleanupJson -Raw | ConvertFrom-Json
    $CleanupTargets = $CleanupConfig.targets

    foreach ($rel in $CleanupTargets) {
        $target = Join-Path $Repo $rel
        if (Test-Path $target) {
            $archiveTarget = Get-UniquePath (Join-Path $ArchiveRoot $rel)
            if ($Apply) {
                New-ParentFolder $archiveTarget
                Move-Item -Force -Path $target -Destination $archiveTarget
                $action = "archived_and_removed"
            } else {
                $action = "would_archive_and_remove"
            }
            $CleanupRows += [pscustomobject]@{
                path = $rel
                exists = $true
                action = $action
                archive = $archiveTarget
            }
        } else {
            $CleanupRows += [pscustomobject]@{
                path = $rel
                exists = $false
                action = "not_present"
                archive = ""
            }
        }
    }

    if ($Apply) {
        New-Item -ItemType Directory -Force -Path $ArchiveRoot | Out-Null
        $CleanupRows | Export-Csv -NoTypeInformation -Path (Join-Path $ArchiveRoot "CLEANUP_MANIFEST.csv")
    }
}

$CopyRows = @()

Get-ChildItem -Path $PayloadRoot -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($PayloadRoot.Length).TrimStart('\','/')
    if ($SkipPayloadFiles -contains $_.Name) { return }

    $dest = Join-Path $Repo $rel
    if ($Apply) {
        New-ParentFolder $dest
        Copy-Item -Force -Path $_.FullName -Destination $dest
        $action = "copied"
    } else {
        $action = "would_copy"
    }

    $CopyRows += [pscustomobject]@{
        source = $rel
        target = $dest
        action = $action
    }
}

$Gitignore = Join-Path $Repo ".gitignore"
$Block = Get-Content $GitignoreBlockFile -Raw

if (Test-Path $Gitignore) {
    $Existing = Get-Content $Gitignore -Raw
} else {
    $Existing = ""
}

if ($Existing -like "*# --- F1 Prediction Engine generated outputs ---*") {
    $GitignoreAction = "already_present"
} elseif ($Apply) {
    Add-Content -Path $Gitignore -Value ""
    Add-Content -Path $Gitignore -Value $Block
    $GitignoreAction = "appended"
} else {
    $GitignoreAction = "would_append"
}

$Required = @(
    ".github/workflows/openf1-high-frequency-auto-ingest.yml",
    ".github/workflows/openf1-post-event-reliability-metric.yml",
    ".github/workflows/elite-weekend-engine-run.yml",
    "scripts/openf1/openf1_high_frequency_auto_ingest.py",
    "scripts/weekend_run_orchestrator.py",
    "tests/validate_openf1_high_frequency_output.py",
    "configs/openf1/openf1_high_frequency_ingest_policy.json",
    "configs/elite/elite_operational_proof_pattern_control_full7_policy.json",
    "schemas/locked_forecast_ledger_v2_schema.json",
    "templates/dnf_all_precursor_board_template.csv",
    "workbook_bridge/elite_control_room_export_manifest.csv"
)

$ValidationRows = @()
foreach ($r in $Required) {
    $ValidationRows += [pscustomobject]@{
        path = $r
        exists = (Test-Path (Join-Path $Repo $r))
    }
}

$Missing = @($ValidationRows | Where-Object { -not $_.exists })
$CleanedCount = @($CleanupRows | Where-Object { $_.exists }).Count
$DocsDir = Join-Path $Repo "docs"
$Report = Join-Path $DocsDir "F1_GITHUB_AUTOMATION_INSTALL_REPORT.md"

$ReportLines = @()
$ReportLines += "# F1 GitHub Automation Install Report"
$ReportLines += ""
$ReportLines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $ReportLines += "Mode: APPLY" } else { $ReportLines += "Mode: DRY RUN" }
if ($Apply -and $Missing.Count -eq 0) {
    $ReportLines += "Result: PASS"
} elseif (-not $Apply) {
    $ReportLines += "Result: DRY RUN COMPLETE"
} else {
    $ReportLines += "Result: CHECK REQUIRED"
}
$ReportLines += ""
$ReportLines += ("Existing old/conflicting paths found: " + $CleanedCount)
$ReportLines += ("Archive location: " + $ArchiveRoot)
$ReportLines += ("Gitignore: " + $GitignoreAction)
$ReportLines += ""
$ReportLines += "Validation:"
foreach ($r in $ValidationRows) {
    $ReportLines += ("- " + $r.path + " = " + $r.exists)
}
$ReportLines += ""
$ReportLines += "Guardrails:"
$ReportLines += "- Generated high-frequency outputs are ignored by Git."
$ReportLines += "- No raw telemetry should be committed by default."
$ReportLines += "- No automatic stable race P1-P20 rank changes are enabled."
$ReportLines += "- No automatic qualifying P1-P5 rank changes are enabled."

if ($Apply) {
    if (!(Test-Path $DocsDir)) { New-Item -ItemType Directory -Force -Path $DocsDir | Out-Null }
    Set-Content -Path $Report -Value $ReportLines -Encoding UTF8
} else {
    $ReportLines | ForEach-Object { Write-Host $_ }
}

Write-Host ""
Write-Host ("Cleanup targets checked: " + $CleanupRows.Count)
Write-Host ("Old active paths archived/queued: " + $CleanedCount)
Write-Host ("Payload files queued/copied: " + $CopyRows.Count)
Write-Host ("Gitignore: " + $GitignoreAction)

if ($Apply) {
    Write-Host ("Archive folder: " + $ArchiveRoot)
    Write-Host ("Install report: " + $Report)
    if ($Missing.Count -gt 0) {
        Write-Host "Missing after install:"
        $Missing | ForEach-Object { Write-Host $_.path }
        exit 2
    }
    Write-Host "Validation: PASS"
}

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add .github scripts tests configs schemas templates workbook_bridge docs requirements-f1-engine-automation.txt requirements-openf1-ingest.txt .gitignore ledgers _archive
        git commit -m "Clean install F1 OpenF1 automation and elite engine workflows"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}
