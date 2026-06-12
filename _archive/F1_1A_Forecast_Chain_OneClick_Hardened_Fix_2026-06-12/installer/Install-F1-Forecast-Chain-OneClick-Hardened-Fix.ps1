param(
    [string]$RepoPath = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
)

$ErrorActionPreference = "Stop"

Write-Host "F1 Forecast Chain One-Click Hardened Fix installer"
Write-Host "Default repo path: $RepoPath"

$inputPath = Read-Host "Press Enter to use the default path, or paste a different repo path"
if (-not [string]::IsNullOrWhiteSpace($inputPath)) {
    $RepoPath = $inputPath.Trim()
}

if (-not (Test-Path $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}

$PackageRoot = Split-Path -Parent $PSScriptRoot
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path $RepoPath ".f1_patch_external_backups\forecast_chain_one_click_hardened_fix_$timestamp"

$files = @(
    ".github\workflows\f1-forecast-chain-one-click-validation-v1.yml",
    "docs\F1_FORECAST_CHAIN_ONE_CLICK_HARDENED_FIX_2026-06-12.md",
    "manifests\FORECAST_CHAIN_ONE_CLICK_HARDENED_FIX_MANIFEST.csv"
)

foreach ($rel in $files) {
    $src = Join-Path $PackageRoot $rel
    if (-not (Test-Path $src)) {
        throw "Package file missing: $src"
    }
}

foreach ($rel in $files) {
    $dest = Join-Path $RepoPath $rel
    $backup = Join-Path $BackupRoot $rel

    if (Test-Path $dest) {
        $backupParent = Split-Path -Parent $backup
        New-Item -ItemType Directory -Force -Path $backupParent | Out-Null
        Copy-Item -LiteralPath $dest -Destination $backup -Force
    }

    $destParent = Split-Path -Parent $dest
    New-Item -ItemType Directory -Force -Path $destParent | Out-Null
    Copy-Item -LiteralPath (Join-Path $PackageRoot $rel) -Destination $dest -Force
    Write-Host "Installed: $rel"
}

$gitignore = Join-Path $RepoPath ".gitignore"
$ignoreLines = @(".f1_patch_backups/", ".f1_patch_external_backups/")
if (-not (Test-Path $gitignore)) {
    New-Item -ItemType File -Path $gitignore | Out-Null
}
$current = Get-Content -LiteralPath $gitignore -ErrorAction SilentlyContinue
foreach ($line in $ignoreLines) {
    if ($current -notcontains $line) {
        Add-Content -LiteralPath $gitignore -Value $line
    }
}

Write-Host ""
Write-Host "Install complete."
Write-Host "Review in GitHub Desktop, then commit and push."
Write-Host "Suggested commit: chore: harden one-click forecast chain validation"
