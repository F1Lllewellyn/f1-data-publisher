
param(
  [string]$RepoPath
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==== $msg ====" -ForegroundColor Cyan }
function Write-Info($msg) { Write-Host $msg }
function Write-Warn($msg) { Write-Host "WARNING: $msg" -ForegroundColor Yellow }

function Normalize-RepoPath([string]$p) {
  if ([string]::IsNullOrWhiteSpace($p)) { return $null }
  return ($p.Trim().Trim('"').Trim("'"))
}

function Remove-Tree-Safe([string]$PathToRemove) {
  if (-not (Test-Path -LiteralPath $PathToRemove)) {
    Write-Info "Not present: $PathToRemove"
    return
  }
  Write-Info "Removing: $PathToRemove"
  try {
    Remove-Item -LiteralPath $PathToRemove -Recurse -Force -ErrorAction Stop
    return
  } catch {
    Write-Warn "PowerShell Remove-Item failed, trying cmd /c rmdir fallback. $($_.Exception.Message)"
  }

  # Use cmd's rmdir as a fallback. This avoids the null ProcessStartInfo/ArgumentList bug from the prior installer.
  $escaped = $PathToRemove
  cmd.exe /c "rmdir /s /q `"$escaped`"" | Out-Null
  if (Test-Path -LiteralPath $PathToRemove) {
    throw "Failed to remove path after fallback: $PathToRemove"
  }
}

function Run-Git([string[]]$ArgsArray, [switch]$AllowFail) {
  # No ProcessStartInfo, no .ArgumentList usage; this avoids the null-valued expression failure.
  $psiArgs = @('-c','core.longpaths=true') + $ArgsArray
  & git @psiArgs
  $code = $LASTEXITCODE
  if (($code -ne 0) -and (-not $AllowFail)) {
    throw "git command failed ($code): git $($psiArgs -join ' ')"
  }
  return $code
}

Write-Host "F1 1A GitHub Long-Path Cleanup FINAL Fix" -ForegroundColor Green

if (-not $RepoPath) {
  $RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repo"
}
$RepoPath = Normalize-RepoPath $RepoPath
if (-not (Test-Path -LiteralPath $RepoPath)) { throw "Repo path not found: $RepoPath" }
Set-Location -LiteralPath $RepoPath

Write-Step "Safety summary"
Write-Info "This final fix removes generated local backup folders from the repo working tree."
Write-Info "It removes the previously committed 2026_next_event placeholder forecast bundles if present."
Write-Info "It sets Git longpaths locally for this repository."
Write-Info "It does not touch stable engine logic, workbook files, or prediction outputs."

Write-Step "Set Git longpaths for this repo"
try { Run-Git @('config','core.longpaths','true') | Out-Null } catch { Write-Warn "Could not set core.longpaths, continuing. $($_.Exception.Message)" }

Write-Step "Create external note"
$externalRoot = Join-Path (Split-Path -Parent $RepoPath) ".f1_patch_external_backups"
New-Item -ItemType Directory -Force -Path $externalRoot | Out-Null
$notePath = Join-Path $externalRoot ("README_longpath_cleanup_final_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".txt")
@"
F1 1A GitHub Long-Path Cleanup Final Fix
Generated: $(Get-Date -Format o)
Repo: $RepoPath

This patch intentionally does not place deep backups under the repository.
Prior installer attempts placed .f1_patch_backups inside the repo, which caused Git/Windows path-length commit failures.
This final fix removes that generated repo-local backup folder and ignores it going forward.
"@ | Set-Content -LiteralPath $notePath -Encoding UTF8
Write-Info "Wrote external note: $notePath"

Write-Step "Update .gitignore"
$gitignore = Join-Path $RepoPath ".gitignore"
if (-not (Test-Path -LiteralPath $gitignore)) { New-Item -ItemType File -Path $gitignore | Out-Null }
$existing = Get-Content -LiteralPath $gitignore -Raw -ErrorAction SilentlyContinue
$linesToAdd = @(
  "",
  "# F1 1A local installer backups - generated, do not commit",
  ".f1_patch_backups/",
  ".f1_patch_external_backups/"
)
foreach ($line in $linesToAdd) {
  if ($line -eq "") { continue }
  if ($existing -notmatch [regex]::Escape($line)) {
    Add-Content -LiteralPath $gitignore -Value $line
  }
}
Write-Info "Updated .gitignore."

Write-Step "Untrack generated backup folder if Git saw it"
Run-Git @('rm','-r','--cached','--ignore-unmatch','.f1_patch_backups') -AllowFail | Out-Null

Write-Step "Remove generated repo-local backup folder"
Remove-Tree-Safe (Join-Path $RepoPath ".f1_patch_backups")

Write-Step "Remove previously committed placeholder forecast bundles"
Remove-Tree-Safe (Join-Path $RepoPath "latest\forecast_bundles\2026_next_event")
Remove-Tree-Safe (Join-Path $RepoPath "history\forecast_bundles\2026_next_event")

Write-Step "Stage cleanup changes"
Run-Git @('add','.gitignore') -AllowFail | Out-Null
Run-Git @('add','-u','latest/forecast_bundles/2026_next_event') -AllowFail | Out-Null
Run-Git @('add','-u','history/forecast_bundles/2026_next_event') -AllowFail | Out-Null
Run-Git @('status','--short') -AllowFail | Out-Null

Write-Step "Done"
Write-Host "Cleanup completed. Review Git changes, then commit and push." -ForegroundColor Green
Write-Host "Suggested commit message:" -ForegroundColor Green
Write-Host "chore: remove placeholder forecast bundles and ignore installer backups" -ForegroundColor Green
