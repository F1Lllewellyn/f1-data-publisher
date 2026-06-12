param(
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"

function Write-Section($Text) {
    Write-Host ""
    Write-Host "==== $Text ===="
}

function Get-LongPath($Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full.StartsWith("\\?\")) { return $full }
    if ($full.StartsWith("\\")) {
        return "\\?\UNC\" + $full.TrimStart("\")
    }
    return "\\?\" + $full
}

function Remove-DirectoryRobust($Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $full = [System.IO.Path]::GetFullPath($Path)
    Write-Host "Removing directory: $full"

    # First try normal PowerShell.
    try {
        Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
        return
    } catch {
        Write-Host "Normal Remove-Item failed; retrying with long-path rmdir..."
    }

    # Retry using cmd /c rmdir with the \\?\ prefix for long Windows paths.
    $lp = Get-LongPath $full
    & cmd.exe /c "rmdir /s /q ""$lp"""
    if (Test-Path -LiteralPath $full) {
        throw "Unable to remove directory after long-path retry: $full"
    }
}

function Run-Git($ArgsArray, [switch]$AllowFail) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "git"
    $psi.WorkingDirectory = $RepoPath
    foreach ($a in $ArgsArray) { [void]$psi.ArgumentList.Add($a) }
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    if ($stdout) { Write-Host $stdout.TrimEnd() }
    if ($stderr) { Write-Host $stderr.TrimEnd() }
    if ($p.ExitCode -ne 0 -and -not $AllowFail) {
        throw "git $($ArgsArray -join ' ') failed with exit code $($p.ExitCode)"
    }
    return $p.ExitCode
}

if (-not $RepoPath -or $RepoPath.Trim() -eq "") {
    $RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repo"
}
$RepoPath = $RepoPath.Trim('"').Trim()

if (-not (Test-Path -LiteralPath $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $RepoPath ".git"))) {
    throw "This folder does not look like a Git repo: $RepoPath"
}

Write-Section "Safety summary"
Write-Host "This fix removes the generated .f1_patch_backups folder from the working tree so Git can commit again."
Write-Host "It also removes placeholder forecast bundles for 2026_next_event if present."
Write-Host "It does not touch stable engine logic, workbook files, or prediction outputs."

Write-Section "Create external note"
$parent = Split-Path -Parent $RepoPath
$externalBackupRoot = Join-Path $parent ".f1_patch_external_backups"
New-Item -ItemType Directory -Force -Path $externalBackupRoot | Out-Null
$notePath = Join-Path $externalBackupRoot "README_longpath_cleanup_$((Get-Date).ToString('yyyyMMdd_HHmmss')).txt"
@"
F1 1A long-path backup cleanup note
Created: $((Get-Date).ToString("s"))

The generated in-repo .f1_patch_backups folder caused Windows/Git long-path commit failures.
The folder is generated installer backup material, not source data.
This cleanup keeps future backup material out of Git by adding .f1_patch_backups/ to .gitignore.

Stable engine: unchanged.
Canonical workbook: unchanged.
Prediction outputs: unchanged.
"@ | Set-Content -Path $notePath -Encoding UTF8
Write-Host "Wrote external note: $notePath"

Write-Section "Update .gitignore"
$gitignore = Join-Path $RepoPath ".gitignore"
if (-not (Test-Path -LiteralPath $gitignore)) {
    New-Item -ItemType File -Force -Path $gitignore | Out-Null
}
$gitignoreText = Get-Content -LiteralPath $gitignore -Raw -ErrorAction SilentlyContinue
$needed = @(
    "",
    "# F1 1A local installer backups - never commit generated backup trees",
    ".f1_patch_backups/",
    ".f1_patch_external_backups/",
    "_runtime/",
    "*.tmp"
)
$changed = $false
foreach ($line in $needed) {
    if ($line -eq "") { continue }
    if ($gitignoreText -notmatch [regex]::Escape($line)) {
        Add-Content -LiteralPath $gitignore -Value $line
        $changed = $true
    }
}
if ($changed) { Write-Host "Updated .gitignore." } else { Write-Host ".gitignore already contains required entries." }

Write-Section "Untrack generated backup folder if Git saw it"
Run-Git @("rm","-r","--cached","--ignore-unmatch",".f1_patch_backups") -AllowFail | Out-Null

Write-Section "Remove in-repo generated backup folder"
Remove-DirectoryRobust (Join-Path $RepoPath ".f1_patch_backups")

Write-Section "Remove placeholder forecast bundle folders"
$placeholderPaths = @(
    "latest/forecast_bundles/2026_next_event",
    "history/forecast_bundles/2026_next_event"
)
foreach ($rel in $placeholderPaths) {
    $full = Join-Path $RepoPath ($rel -replace "/", [System.IO.Path]::DirectorySeparatorChar)
    # Stage deletion if tracked.
    Run-Git @("rm","-r","--ignore-unmatch",$rel) -AllowFail | Out-Null
    # Remove from working tree if still present/untracked.
    Remove-DirectoryRobust $full
}

Write-Section "Stage safe maintenance files"
Run-Git @("add",".gitignore") -AllowFail | Out-Null

Write-Section "Final git status"
Run-Git @("status","--short") -AllowFail | Out-Null

Write-Host ""
Write-Host "Fix complete. Review the Git diff, then commit and push."
Write-Host "Recommended commit message:"
Write-Host "chore: cleanup placeholder bundles and ignore local patch backups"
