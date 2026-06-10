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
$ArchiveRoot = Join-Path $Repo "_archive\f1_github_automation_preinstall_cleanup_$Stamp"

Write-Host "F1 GitHub automation CLEAN installer — PowerShell no-Python version"
Write-Host "Repo: $Repo"
Write-Host "Mode: $(if ($Apply) {'APPLY'} else {'DRY RUN'})"
Write-Host "Clean old paths: $(-not $NoCleanOld)"
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
        $Candidate = "$Path`__$i"
        if (!(Test-Path $Candidate)) { return $Candidate }
        $i++
    }
}

$CleanupRows = @()

if (-not $NoCleanOld) {
    $CleanupTargets = (Get-Content $CleanupJson -Raw | ConvertFrom-Json).targets
    foreach ($rel in $CleanupTargets) {
        $target = Join-Path $Repo $rel
        if (Test-Path $target) {
            $archiveTarget = Get-UniquePath (Join-Path $ArchiveRoot $rel)
            $CleanupRows += [pscustomobject]@{
                path = $rel
                exists = $true
                action = $(if ($Apply) {"archived_and_removed"} else {"would_archive_and_remove"})
                archive = $archiveTarget
            }
            if ($Apply) {
                New-ParentFolder $archiveTarget
                Move-Item -Force -Path $target -Destination $archiveTarget
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
    $rel = Resolve-Path -Relative $_.FullName
    # Resolve-Path -Relative can be relative to cwd; use substring instead.
    $rel = $_.FullName.Substring($PayloadRoot.Length).TrimStart('\','/')
    if ($SkipPayloadFiles -contains $_.Name) { return }

    $dest = Join-Path $Repo $rel
    $CopyRows += [pscustomobject]@{
        source = $rel
        target = $dest
        action = $(if ($Apply) {"copied"} else {"would_copy"})
    }

    if ($Apply) {
        New-ParentFolder $dest
        Copy-Item -Force -Path $_.FullName -Destination $dest
    }
}

$Gitignore = Join-Path $Repo ".gitignore"
$GitignoreAction = ""
$Block = Get-Content $GitignoreBlockFile -Raw

if (Test-Path $Gitignore) {
    $Existing = Get-Content $Gitignore -Raw
} else {
    $Existing = ""
}

if ($Existing -like "*# --- F1 Prediction Engine generated outputs ---*") {
    $GitignoreAction = "already_present"
} elseif ($Apply) {
    Add-Content -Path $Gitignore -Value "`n$Block"
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

$ReportText = @"
# F1 GitHub Automation Install Report

Generated: $(Get-Date -Format o)

Mode: $(if ($Apply) {'APPLY'} else {'DRY RUN'})

## Result

$(if ($Apply -and $Missing.Count -eq 0) {'PASS'} elseif (-not $Apply) {'DRY RUN COMPLETE'} else {'CHECK REQUIRED'})

## Pre-install cleanup

Existing old/conflicting paths found: $CleanedCount

Old active files/folders were moved to archive before installation.

Archive location:

```
$ArchiveRoot
```

## Gitignore

- $GitignoreAction

## Validation

| Path | Exists |
|---|---:|
"@

foreach ($r in $ValidationRows) {
    $ReportText += "`n| ``$($r.path)`` | $($r.exists) |"
}

$ReportText += @"

## Guardrails

- Generated high-frequency outputs are ignored by Git.
- No raw telemetry should be committed by default.
- No automatic stable race P1-P20 rank changes are enabled.
- No automatic qualifying P1-P5 rank changes are enabled.
"@

if ($Apply) {
    if (!(Test-Path $DocsDir)) { New-Item -ItemType Directory -Force -Path $DocsDir | Out-Null }
    Set-Content -Path $Report -Value $ReportText -Encoding UTF8
} else {
    Write-Host $ReportText
}

Write-Host ""
Write-Host "Cleanup targets checked: $($CleanupRows.Count)"
Write-Host "Payload files queued/copied: $($CopyRows.Count)"
Write-Host "Gitignore: $GitignoreAction"

if ($Apply) {
    Write-Host "Archive folder: $ArchiveRoot"
    Write-Host "Install report: $Report"
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
