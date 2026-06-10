param(
    [string]$Repo = "C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher",
    [string]$TagName = "F1_Automation_Baseline_2026-06-10_READY"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $Repo)) {
    throw "Repo path does not exist: $Repo"
}

function Find-Git {
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $ghGit = Get-ChildItem "$env:LOCALAPPDATA\GitHubDesktop" -Recurse -Filter git.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    if ($ghGit) { return $ghGit }

    throw "Could not find git.exe. Install Git or GitHub Desktop."
}

$git = Find-Git

Push-Location $Repo

Write-Host "Using git: $git"
Write-Host "Repo: $Repo"
Write-Host "Tag: $TagName"

& $git fetch --tags origin

$existing = & $git tag --list $TagName
if ($existing -eq $TagName) {
    Write-Host "Tag already exists locally: $TagName"
} else {
    & $git tag -a $TagName -m "F1 automation operational baseline READY 2026-06-10"
    Write-Host "Created local tag: $TagName"
}

& $git push origin $TagName

Pop-Location
Write-Host "Baseline tag pushed: $TagName"
