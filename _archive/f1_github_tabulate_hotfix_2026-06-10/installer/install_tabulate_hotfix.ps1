param(
    [Parameter(Mandatory=$true)]
    [string]$Repo,

    [switch]$Apply,
    [switch]$Commit,
    [switch]$Push
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $Repo)) {
    throw "Repo path does not exist: $Repo"
}
$Repo = (Resolve-Path $Repo).Path

Write-Host "F1 GitHub OpenF1 tabulate hotfix"
Write-Host ("Repo: " + $Repo)
if ($Apply) { Write-Host "Mode: APPLY" } else { Write-Host "Mode: DRY RUN" }

$FilesToPatch = @(
    ".github/workflows/openf1-high-frequency-auto-ingest.yml",
    ".github/workflows/openf1-post-event-reliability-metric.yml",
    ".github/workflows/elite-weekend-engine-run.yml",
    "requirements-openf1-ingest.txt",
    "requirements-f1-engine-automation.txt"
)

$Rows = @()

foreach ($rel in $FilesToPatch) {
    $path = Join-Path $Repo $rel
    if (!(Test-Path $path)) {
        $Rows += [pscustomobject]@{ path=$rel; exists=$false; action="missing" }
        continue
    }

    $txt = Get-Content $path -Raw
    $new = $txt
    $changed = $false

    if ($rel.EndsWith(".yml")) {
        if ($new -notmatch "tabulate") {
            $new = $new -replace "pip install requests pandas pyarrow tqdm python-dateutil numpy", "pip install requests pandas pyarrow tqdm python-dateutil numpy tabulate"
            $new = $new -replace "pip install pandas numpy pyarrow requests tqdm python-dateutil", "pip install pandas numpy pyarrow requests tqdm python-dateutil tabulate"
            if ($new -ne $txt) { $changed = $true }
        }
    } else {
        if ($new -notmatch "(?m)^tabulate\s*$") {
            if (-not $new.EndsWith("`n")) { $new += "`n" }
            $new += "tabulate`n"
            $changed = $true
        }
    }

    if ($Apply -and $changed) {
        Set-Content -Path $path -Value $new -Encoding UTF8
    }

    if ($changed) {
        $Rows += [pscustomobject]@{ path=$rel; exists=$true; action=$(if ($Apply) {"patched"} else {"would_patch"}) }
    } else {
        $Rows += [pscustomobject]@{ path=$rel; exists=$true; action="already_ok_or_no_match_needed" }
    }
}

$Docs = Join-Path $Repo "docs"
$Report = Join-Path $Docs "F1_GITHUB_TABULATE_HOTFIX_REPORT.md"
$ReportLines = @()
$ReportLines += "# F1 GitHub Tabulate Hotfix Report"
$ReportLines += ""
$ReportLines += ("Generated: " + (Get-Date -Format o))
if ($Apply) { $ReportLines += "Mode: APPLY" } else { $ReportLines += "Mode: DRY RUN" }
$ReportLines += ""
$ReportLines += "Purpose: add missing tabulate dependency so pandas DataFrame.to_markdown() works during OpenF1 report generation."
$ReportLines += ""
$ReportLines += "Patched files:"
foreach ($r in $Rows) {
    $ReportLines += ("- " + $r.path + " :: " + $r.action)
}

if ($Apply) {
    if (!(Test-Path $Docs)) { New-Item -ItemType Directory -Force -Path $Docs | Out-Null }
    Set-Content -Path $Report -Value $ReportLines -Encoding UTF8
    Write-Host ("Report: " + $Report)
} else {
    $ReportLines | ForEach-Object { Write-Host $_ }
}

if ($Apply -and $Commit) {
    if (Test-Path (Join-Path $Repo ".git")) {
        Push-Location $Repo
        git status --short
        git add .github/workflows requirements-openf1-ingest.txt requirements-f1-engine-automation.txt docs/F1_GITHUB_TABULATE_HOTFIX_REPORT.md
        git commit -m "Fix OpenF1 workflow report dependency"
        if ($Push) { git push }
        Pop-Location
    } else {
        Write-Host "Not a git repository; skipping commit."
    }
}

Write-Host "Hotfix complete."
