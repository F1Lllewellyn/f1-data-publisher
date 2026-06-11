param([string]$RepoPath)
$ErrorActionPreference = "Stop"
$PatchRoot = Split-Path -Parent $PSScriptRoot
$PayloadRoot = Join-Path $PatchRoot "payload"
$ManifestPath = Join-Path $PatchRoot "manifests/cumulative_github_payload_manifest.csv"
if (-not $RepoPath) { $RepoPath = Read-Host "Paste the full local path to your f1-data-publisher repo" }
if (-not (Test-Path $RepoPath)) { throw "Repo path not found: $RepoPath" }
if (-not (Test-Path (Join-Path $RepoPath ".git"))) { Write-Warning "This path does not contain a .git folder. Continuing only if this is intentional." }
$manifest = Import-Csv $ManifestPath
if ($manifest.Count -eq 0) { throw "Manifest is empty." }
foreach ($row in $manifest) {
  $src = Join-Path $PayloadRoot $row.relative_path
  if (-not (Test-Path $src)) { throw "Missing payload file before copy: $src" }
}
$BackupRoot = Join-Path $RepoPath ".f1_patch_backups/F1_1A_CUMULATIVE_GITHUB_PRODUCTION_V2_1_2026-06-11"
$installed = New-Object System.Collections.Generic.List[string]
foreach ($row in $manifest) {
  $rel = $row.relative_path
  $src = Join-Path $PayloadRoot $rel
  $dst = Join-Path $RepoPath $rel
  $dstDir = Split-Path -Parent $dst
  New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
  if (Test-Path $dst) {
    $bak = Join-Path $BackupRoot $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bak) | Out-Null
    Copy-Item -Force $dst $bak
  }
  Copy-Item -Force $src $dst
  $installed.Add($rel) | Out-Null
}
$ReportDir = Join-Path $RepoPath "install_reports"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$ReportPath = Join-Path $ReportDir "F1_1A_CUMULATIVE_GITHUB_PRODUCTION_V2_1_2026-06-11_install_report.md"
@"
# F1 1A Cumulative GitHub Production v2.1 Install Report

Installed: $(Get-Date -Format o)

Files installed: $($installed.Count)

No files deleted. Existing files were backed up under:

`$BackupRoot`

Stable engine logic was not changed by this installer. Canonical workbook was not touched. Experimental layers remain separate from stable exact P1-P20 outputs.

## Installed files
$($installed | ForEach-Object { "- $_" } | Out-String)
"@ | Set-Content -Encoding UTF8 $ReportPath
Write-Host "Cumulative GitHub installer completed successfully."
Write-Host "Installed files: $($installed.Count)"
Write-Host "Install report: $ReportPath"
