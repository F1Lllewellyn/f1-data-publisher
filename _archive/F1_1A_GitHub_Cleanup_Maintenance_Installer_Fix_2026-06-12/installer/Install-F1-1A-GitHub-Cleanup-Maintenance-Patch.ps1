param(
    [string]$RepoPath = ""
)

$ErrorActionPreference = "Stop"
$PatchRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Copy-FileSafe {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    $parent = Split-Path -Parent $Destination
    if ($parent -and !(Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Backup-PathSafe {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    if (!(Test-Path -LiteralPath $Source)) {
        return $false
    }
    $destParent = Split-Path -Parent $Destination
    if ($destParent -and !(Test-Path -LiteralPath $destParent)) {
        New-Item -ItemType Directory -Force -Path $destParent | Out-Null
    }

    if (Test-Path -LiteralPath $Source -PathType Container) {
        if (!(Test-Path -LiteralPath $Destination)) {
            New-Item -ItemType Directory -Force -Path $Destination | Out-Null
        }
        # Robocopy is used for directory backups because Copy-Item can fail on nested
        # placeholder bundle trees if the destination branch does not exist yet.
        $null = robocopy $Source $Destination /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
        $rc = $LASTEXITCODE
        if ($rc -ge 8) {
            throw "Robocopy backup failed with exit code $rc for $Source"
        }
        # Robocopy uses non-zero success codes; reset so PowerShell does not treat it as failure later.
        $global:LASTEXITCODE = 0
    } else {
        Copy-FileSafe -Source $Source -Destination $Destination
    }
    return $true
}

if ([string]::IsNullOrWhiteSpace($RepoPath)) {
    $RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repo"
}
$RepoPath = (Resolve-Path $RepoPath).Path

if (!(Test-Path (Join-Path $RepoPath ".git"))) {
    throw "Repo path does not appear to be a Git repository: $RepoPath"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $RepoPath ".f1_patch_backups\install_cleanup_maintenance_$timestamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$targetsToBackup = @(
    ".github\workflows",
    "scripts\maintenance",
    "scripts\forecast_bundles",
    "configs\maintenance",
    "docs",
    "latest\forecast_bundles\2026_next_event",
    "history\forecast_bundles\2026_next_event"
)

foreach ($rel in $targetsToBackup) {
    $src = Join-Path $RepoPath $rel
    if (Test-Path -LiteralPath $src) {
        $dst = Join-Path $backupRoot $rel
        $ok = Backup-PathSafe -Source $src -Destination $dst
        if ($ok) {
            Write-Host "Backed up: $rel"
        }
    }
}

$payloadFiles = @(
    ".github\workflows\f1-forecast-chain-readiness-validator-v1.yml",
    "scripts\maintenance\cleanup_placeholder_bundles_and_node_actions_v1.py",
    "scripts\forecast_bundles\validate_forecast_chain_readiness_v1.py",
    "configs\maintenance\f1_1a_cleanup_maintenance_policy_v1.json",
    "docs\F1_1A_GITHUB_CLEANUP_MAINTENANCE_PATCH_2026-06-12.md"
)

foreach ($rel in $payloadFiles) {
    $src = Join-Path $PatchRoot $rel
    if (!(Test-Path -LiteralPath $src)) {
        throw "Missing payload file in patch package: $rel"
    }
}

foreach ($rel in $payloadFiles) {
    $src = Join-Path $PatchRoot $rel
    $dst = Join-Path $RepoPath $rel
    Copy-FileSafe -Source $src -Destination $dst
    Write-Host "Installed payload: $rel"
}

python (Join-Path $RepoPath "scripts\maintenance\cleanup_placeholder_bundles_and_node_actions_v1.py") --repo $RepoPath

Write-Host ""
Write-Host "F1 1A GitHub Cleanup + Maintenance Patch installed."
Write-Host "Local backup: $backupRoot"
Write-Host "Next: review git diff, then commit and push."
