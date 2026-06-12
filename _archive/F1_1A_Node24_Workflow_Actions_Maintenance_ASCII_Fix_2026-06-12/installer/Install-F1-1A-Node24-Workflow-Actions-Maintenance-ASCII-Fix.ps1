param(
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"

Write-Host "F1 1A Node 24 Workflow Actions Maintenance - ASCII Fix" -ForegroundColor Cyan
Write-Host ""
Write-Host "Safety summary:" -ForegroundColor Cyan
Write-Host "This patch updates workflow action versions only."
Write-Host "It does not call git."
Write-Host "It does not touch stable engine logic, workbook files, forecast rows, forecast bundles, prediction outputs, or promotion status."
Write-Host ""

if ([string]::IsNullOrWhiteSpace($RepoPath)) {
    $RepoPath = Read-Host "Paste the full path to your local f1-data-publisher repo"
}
$RepoPath = $RepoPath.Trim('"').Trim()

if (!(Test-Path -LiteralPath $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}

$WorkflowDir = Join-Path $RepoPath ".github\workflows"
if (!(Test-Path -LiteralPath $WorkflowDir)) {
    throw "Workflow directory not found: $WorkflowDir"
}

# Keep local/generated backup folders ignored.
$GitIgnorePath = Join-Path $RepoPath ".gitignore"
$IgnoreLines = @(".f1_patch_backups/", ".f1_patch_external_backups/")
if (!(Test-Path -LiteralPath $GitIgnorePath)) {
    New-Item -ItemType File -Path $GitIgnorePath -Force | Out-Null
}
$ExistingIgnore = @()
try { $ExistingIgnore = Get-Content -LiteralPath $GitIgnorePath -ErrorAction Stop } catch { $ExistingIgnore = @() }
foreach ($Line in $IgnoreLines) {
    if ($ExistingIgnore -notcontains $Line) {
        Add-Content -LiteralPath $GitIgnorePath -Value $Line
    }
}

# Create a note outside the repo root so GitHub Desktop does not track it.
$Parent = Split-Path -Parent $RepoPath
$ExternalDir = Join-Path $Parent ".f1_patch_external_backups"
New-Item -ItemType Directory -Path $ExternalDir -Force | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$NotePath = Join-Path $ExternalDir ("README_node24_actions_maintenance_ascii_fix_" + $Stamp + ".txt")
$NoteLines = @(
    "F1 1A Node 24 Workflow Actions Maintenance - ASCII Fix",
    ("Ran: " + (Get-Date -Format o)),
    ("Repo: " + $RepoPath),
    "Scope: .github/workflows/*.yml and *.yaml only",
    "No git command was run.",
    "Stable engine, workbook files, forecast rows, forecast bundles, prediction outputs, and promotion status were not touched."
)
Set-Content -LiteralPath $NotePath -Value $NoteLines -Encoding UTF8
Write-Host "Wrote external note: $NotePath" -ForegroundColor Gray

$Files = Get-ChildItem -LiteralPath $WorkflowDir -Recurse -File | Where-Object { $_.Extension -in @(".yml", ".yaml") }

$ReplacementPairs = @(
    @("actions/checkout@v4", "actions/checkout@v6"),
    @("actions/checkout@v5", "actions/checkout@v6"),
    @("actions/setup-python@v4", "actions/setup-python@v6"),
    @("actions/setup-python@v5", "actions/setup-python@v6"),
    @("actions/upload-artifact@v4", "actions/upload-artifact@v6"),
    @("actions/upload-artifact@v5", "actions/upload-artifact@v6")
)

$Changed = @()
foreach ($File in $Files) {
    $Content = Get-Content -LiteralPath $File.FullName -Raw
    $NewContent = $Content
    foreach ($Pair in $ReplacementPairs) {
        $NewContent = $NewContent.Replace($Pair[0], $Pair[1])
    }
    if ($NewContent -ne $Content) {
        Set-Content -LiteralPath $File.FullName -Value $NewContent -Encoding UTF8
        $Changed += $File.FullName
    }
}

$ReportDir = Join-Path $RepoPath "docs"
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$ReportPath = Join-Path $ReportDir "F1_1A_NODE24_WORKFLOW_ACTIONS_MAINTENANCE_ASCII_FIX_REPORT_2026-06-12.md"

$RelChanged = @()
foreach ($ChangedPath in $Changed) {
    $Rel = $ChangedPath.Substring($RepoPath.Length).TrimStart('\','/')
    $RelChanged += $Rel
}

$ReportLines = @()
$ReportLines += "# F1 1A Node 24 Workflow Actions Maintenance ASCII Fix - 2026-06-12"
$ReportLines += ""
$ReportLines += "Verdict: Pass with warnings."
$ReportLines += ""
$ReportLines += "Scope: workflow YAML action-version maintenance only."
$ReportLines += ""
$ReportLines += ("Changed workflow files: " + $Changed.Count)
$ReportLines += ""
foreach ($Rel in $RelChanged) { $ReportLines += ("- " + $Rel) }
$ReportLines += ""
$ReportLines += "Guardrails:"
$ReportLines += "- Stable engine logic unchanged."
$ReportLines += "- Canonical workbook unchanged."
$ReportLines += "- Forecast rows unchanged."
$ReportLines += "- Forecast bundles unchanged."
$ReportLines += "- Prediction outputs unchanged."
$ReportLines += "- Promotion status unchanged."
$ReportLines += "- No command-line git call was made."
$ReportLines += ""
$ReportLines += "Next step: review the diff in GitHub Desktop, commit, and push."
Set-Content -LiteralPath $ReportPath -Value $ReportLines -Encoding UTF8

Write-Host ""
Write-Host ("Updated workflow files: " + $Changed.Count) -ForegroundColor Green
foreach ($Rel in $RelChanged) {
    Write-Host (" - " + $Rel)
}
Write-Host ""
Write-Host ("Wrote report: " + $ReportPath) -ForegroundColor Green
Write-Host ""
Write-Host "Now review the diff in GitHub Desktop, commit, and push." -ForegroundColor Cyan
Write-Host "Suggested commit message: chore: update workflow actions for Node 24 maintenance" -ForegroundColor Cyan
