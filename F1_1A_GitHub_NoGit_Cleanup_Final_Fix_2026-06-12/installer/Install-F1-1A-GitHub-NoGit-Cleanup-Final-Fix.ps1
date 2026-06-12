param()
$ErrorActionPreference = "Stop"

Write-Host "F1 1A GitHub No-Git Cleanup Final Fix" -ForegroundColor Cyan
Write-Host ""
$RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repo"
$RepoPath = $RepoPath.Trim().Trim('"')

if (-not (Test-Path -LiteralPath $RepoPath)) {
    Write-Host "ERROR: Repo path does not exist: $RepoPath" -ForegroundColor Red
    exit 1
}

function Join-LitPath([string]$Base, [string]$Child) {
    return [System.IO.Path]::Combine($Base, $Child)
}

function To-LongPath([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full.StartsWith('\\?\')) { return $full }
    if ($full.StartsWith('\\')) { return '\\?\UNC\' + $full.Substring(2) }
    return '\\?\' + $full
}

function Remove-PathRobust([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Host "Not present: $Path" -ForegroundColor DarkGray
        return
    }
    Write-Host "Removing: $Path" -ForegroundColor Yellow
    try {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        Write-Host "Removed using Remove-Item." -ForegroundColor Green
        return
    } catch {
        Write-Host "Remove-Item failed, trying long-path form... $($_.Exception.Message)" -ForegroundColor Yellow
    }
    $long = To-LongPath $Path
    try {
        Remove-Item -LiteralPath $long -Recurse -Force -ErrorAction Stop
        Write-Host "Removed using long-path Remove-Item." -ForegroundColor Green
        return
    } catch {
        Write-Host "Long-path Remove-Item failed, trying cmd rmdir... $($_.Exception.Message)" -ForegroundColor Yellow
    }
    try {
        & cmd.exe /c rmdir /s /q "`"$Path`""
        if (Test-Path -LiteralPath $Path) {
            & cmd.exe /c rmdir /s /q "`"$long`""
        }
        if (Test-Path -LiteralPath $Path) {
            throw "Path still exists after rmdir fallback: $Path"
        }
        Write-Host "Removed using cmd rmdir fallback." -ForegroundColor Green
        return
    } catch {
        Write-Host "ERROR: Could not remove $Path" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        throw
    }
}

Write-Host "==== Safety summary ====" -ForegroundColor Cyan
Write-Host "This final fix does not call git at all."
Write-Host "It removes local generated backup folders and the unwanted 2026_next_event placeholder forecast bundles from the working tree."
Write-Host "It updates .gitignore so future installer backups are not tracked."
Write-Host "It does not touch stable engine logic, workbook files, prediction outputs, or promotion status."
Write-Host ""

Write-Host "==== Create external note ====" -ForegroundColor Cyan
$Parent = Split-Path -Parent $RepoPath
$ExternalDir = Join-LitPath $Parent ".f1_patch_external_backups"
New-Item -ItemType Directory -Force -Path $ExternalDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$NotePath = Join-LitPath $ExternalDir "README_nogit_cleanup_final_$stamp.txt"
@"
F1 1A No-Git Cleanup Final Fix
Generated: $(Get-Date -Format o)
Repo: $RepoPath

This installer intentionally did not call git because git is not available in the shell PATH on this machine.
It removed generated local installer backup folders and placeholder forecast-bundle folders from the working tree if present.
Commit/push should be done with GitHub Desktop after reviewing the file changes.
"@ | Set-Content -Path $NotePath -Encoding UTF8
Write-Host "Wrote external note: $NotePath"
Write-Host ""

Write-Host "==== Update .gitignore ====" -ForegroundColor Cyan
$GitIgnore = Join-LitPath $RepoPath ".gitignore"
if (-not (Test-Path -LiteralPath $GitIgnore)) { New-Item -ItemType File -Path $GitIgnore | Out-Null }
$ignoreLines = @(
    "",
    "# F1 1A local installer backups - do not commit",
    ".f1_patch_backups/",
    ".f1_patch_external_backups/",
    "**/.f1_patch_backups/",
    "**/.f1_patch_external_backups/"
)
$current = Get-Content -LiteralPath $GitIgnore -ErrorAction SilentlyContinue
foreach ($line in $ignoreLines) {
    if ($line -eq "") { continue }
    if ($current -notcontains $line) { Add-Content -LiteralPath $GitIgnore -Value $line }
}
Write-Host "Updated .gitignore."
Write-Host ""

Write-Host "==== Remove generated backup folders from repo working tree ====" -ForegroundColor Cyan
Remove-PathRobust (Join-LitPath $RepoPath ".f1_patch_backups")
Remove-PathRobust (Join-LitPath $RepoPath ".f1_patch_external_backups")
Write-Host ""

Write-Host "==== Remove placeholder forecast bundles ====" -ForegroundColor Cyan
Remove-PathRobust (Join-LitPath $RepoPath "latest\forecast_bundles\2026_next_event")
Remove-PathRobust (Join-LitPath $RepoPath "history\forecast_bundles\2026_next_event")
Write-Host ""

Write-Host "==== Final check ====" -ForegroundColor Cyan
$remaining = @()
foreach ($p in @(
    (Join-LitPath $RepoPath ".f1_patch_backups"),
    (Join-LitPath $RepoPath ".f1_patch_external_backups"),
    (Join-LitPath $RepoPath "latest\forecast_bundles\2026_next_event"),
    (Join-LitPath $RepoPath "history\forecast_bundles\2026_next_event")
)) {
    if (Test-Path -LiteralPath $p) { $remaining += $p }
}
if ($remaining.Count -gt 0) {
    Write-Host "WARNING: Some cleanup targets still exist:" -ForegroundColor Yellow
    $remaining | ForEach-Object { Write-Host " - $_" -ForegroundColor Yellow }
    Write-Host "Do not commit until these are removed." -ForegroundColor Yellow
    exit 2
}

Write-Host "Cleanup targets removed or absent." -ForegroundColor Green
Write-Host "Now open GitHub Desktop, review the diff, commit, and push." -ForegroundColor Cyan
Write-Host "Suggested commit message: chore: remove placeholder forecast bundles and ignore installer backups" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close"
