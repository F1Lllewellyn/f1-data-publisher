param(
    [string]$RepoPath = ""
)

$ErrorActionPreference = "Stop"
$PatchRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

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
    if (Test-Path $src) {
        $dst = Join-Path $backupRoot $rel
        $dstParent = Split-Path -Parent $dst
        New-Item -ItemType Directory -Force -Path $dstParent | Out-Null
        Copy-Item -Path $src -Destination $dst -Recurse -Force
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
    if (!(Test-Path $src)) {
        throw "Missing payload file in patch package: $rel"
    }
}

foreach ($rel in $payloadFiles) {
    $src = Join-Path $PatchRoot $rel
    $dst = Join-Path $RepoPath $rel
    $dstParent = Split-Path -Parent $dst
    New-Item -ItemType Directory -Force -Path $dstParent | Out-Null
    Copy-Item -Path $src -Destination $dst -Force
}

python (Join-Path $RepoPath "scripts\maintenance\cleanup_placeholder_bundles_and_node_actions_v1.py") --repo $RepoPath

Write-Host ""
Write-Host "F1 1A GitHub Cleanup + Maintenance Patch installed."
Write-Host "Local backup: $backupRoot"
Write-Host "Next: review git diff, then commit and push."
