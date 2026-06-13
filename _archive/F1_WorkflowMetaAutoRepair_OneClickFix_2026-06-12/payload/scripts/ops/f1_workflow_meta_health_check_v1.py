#!/usr/bin/env python3
"""F1 workflow meta-health checker.
Sandbox/governance utility: detects fragile workflow patterns without changing model logic.
"""
from __future__ import annotations
import json, os, re, sys
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
WF_DIR = REPO / ".github" / "workflows"
OUT = REPO / "_runtime" / "workflow_meta_health"
OUT.mkdir(parents=True, exist_ok=True)

issues = []
checks = []

def add_issue(severity, file, message, line=None):
    issues.append({"severity": severity, "file": str(file), "line": line, "message": message})

def check_shell_balance(file: Path, text: str):
    # Extract YAML run: | blocks by indentation. Lightweight, intentionally conservative.
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if re.match(r"^\s*run:\s*\|\s*$", lines[i]):
            base_indent = len(lines[i]) - len(lines[i].lstrip())
            block = []
            j = i + 1
            while j < len(lines):
                line = lines[j]
                if line.strip() == "":
                    block.append("")
                    j += 1
                    continue
                indent = len(line) - len(line.lstrip())
                if indent <= base_indent:
                    break
                block.append(line[base_indent+2:] if len(line) >= base_indent+2 else line.lstrip())
                j += 1
            script = "\n".join(block)
            if_count = len(re.findall(r"(?m)^\s*if\b", script))
            fi_count = len(re.findall(r"(?m)^\s*fi\b", script))
            if if_count != fi_count:
                add_issue("fail", file, f"Bash if/fi imbalance in run block: if={if_count}, fi={fi_count}", i+1)
            checks.append({"file": str(file), "run_block_line": i+1, "if_count": if_count, "fi_count": fi_count})
            i = j
        else:
            i += 1

def check_raw_push(file: Path, text: str):
    for n, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("git push"):
            add_issue("warn", file, "Raw git push detected; prefer scripts/ops/safe_git_push_rebase_retry.sh", n)

if not WF_DIR.exists():
    add_issue("fail", WF_DIR, "Workflow directory missing")
else:
    for file in sorted(WF_DIR.glob("*.yml")):
        text = file.read_text(encoding="utf-8", errors="replace")
        check_shell_balance(file, text)
        check_raw_push(file, text)

required_files = [
    REPO / "scripts" / "ops" / "safe_git_push_rebase_retry.sh",
    REPO / ".github" / "workflows" / "f1-workbook-kpi-refresh-scheduled.yml",
]
for path in required_files:
    if not path.exists():
        add_issue("fail", path, "Required workflow-stability file missing")

status = "Pass"
if any(i["severity"] == "fail" for i in issues):
    status = "Fail"
elif issues:
    status = "Pass with warnings"

result = {
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "issue_count": len(issues),
    "issues": issues,
    "checks_count": len(checks),
    "stable_engine_modified": False,
    "canonical_workbook_overwrite": False,
    "promotion_allowed": False,
    "commit_allowed": False,
}
(OUT / "workflow_meta_health.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
(OUT / "WORKFLOW_META_HEALTH_REPORT.md").write_text("\n".join([
    "# F1 Workflow Meta-Health Report",
    "",
    f"Status: **{status}**",
    f"Issues: {len(issues)}",
    "",
    "## Issues",
    *(f"- {i['severity'].upper()}: {i['file']}:{i.get('line') or ''} — {i['message']}" for i in issues),
    "",
    "Stable engine modified: false",
    "Canonical workbook overwritten: false",
    "Promotion allowed: false",
]), encoding="utf-8")
print(json.dumps(result, indent=2))
sys.exit(0 if status != "Fail" else 1)
