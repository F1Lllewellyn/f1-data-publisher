param(
  [string]$RepoPath = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
)
$ErrorActionPreference = "Stop"
Write-Host "F1 Session Data Processor Loop installer"
Write-Host "Default repo path: $RepoPath"
$inputPath = Read-Host "Press Enter to use default, or paste repo path"
if ($inputPath.Trim().Length -gt 0) { $RepoPath = $inputPath.Trim() }
if (!(Test-Path $RepoPath)) { throw "Repo path not found: $RepoPath" }
$PackageRoot = Split-Path -Parent $PSScriptRoot
$Payload = Join-Path $PackageRoot "payload"
if (!(Test-Path $Payload)) { throw "Payload folder not found: $Payload" }
$BackupRoot = Join-Path $RepoPath ".f1_patch_backups\session_data_processor_loop_2026-06-12"
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
Write-Host "Backing up files that will be replaced..."
Get-ChildItem -Path $Payload -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring($Payload.Length).TrimStart('\','/')
  $dest = Join-Path $RepoPath $rel
  if (Test-Path $dest) {
    $bk = Join-Path $BackupRoot $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
    Copy-Item -LiteralPath $dest -Destination $bk -Force
  }
}
Write-Host "Installing payload..."
Get-ChildItem -Path $Payload -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring($Payload.Length).TrimStart('\','/')
  $dest = Join-Path $RepoPath $rel
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
  Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
  Write-Host "Installed: $rel"
}
Write-Host "Install complete. Open GitHub Desktop, review changes, commit, and push."
Write-Host "Then run: F1 Session Data Processor - Safe Test Button"
