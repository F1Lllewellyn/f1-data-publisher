#!/usr/bin/env python3
"""F1 workflow static validator v2.

No-dependency validator for GitHub Actions YAML shell safety. It checks every
`.github/workflows/*.yml` `run: |` block with `bash -n`, catches meta-health
if/fi imbalance patterns, flags raw git push, and verifies the stable-engine /
canonical-workbook governance guard.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
WF_DIR = ROOT / ".github" / "workflows"
OUT = ROOT / "_runtime" / "peak_elite" / "workflow_static_validation"
PROTECTED_PATTERNS = [
    "Engine_2026-06-07_STABLE",
    "F1_2026_Prediction_Model_Data_Workbook.xlsx",
    "F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated.xlsx",
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def extract_run_blocks(lines: List[str]) -> List[Tuple[int, int, int, str]]:
    blocks: List[Tuple[int, int, int, str]] = []
    i = 0
    while i < len(lines):
        if re.match(r"^\s*run:\s*\|\s*$", lines[i]):
            base = len(lines[i]) - len(lines[i].lstrip())
            block: List[str] = []
            j = i + 1
            while j < len(lines):
                line = lines[j]
                if line.strip() == "":
                    block.append("")
                    j += 1
                    continue
                indent = len(line) - len(line.lstrip())
                if indent <= base:
                    break
                block.append(line[base + 2:] if len(line) >= base + 2 else line.lstrip())
                j += 1
            blocks.append((i + 1, j, base, "\n".join(block) + "\n"))
            i = j
        else:
            i += 1
    return blocks


def bash_validate(script: str) -> str:
    bash = shutil.which("bash")
    if not bash:
        return "bash_unavailable"
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh", encoding="utf-8") as f:
        f.write(script)
        tmp = f.name
    try:
        proc = subprocess.run([bash, "-n", tmp], text=True, capture_output=True)
        return proc.stderr.strip() if proc.returncode else ""
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def protected_modified(root: Path) -> List[str]:
    git = shutil.which("git")
    if not git:
        return []
    try:
        proc = subprocess.run([git, "status", "--porcelain"], cwd=str(root), text=True, capture_output=True)
    except Exception:
        return []
    touched = []
    for line in proc.stdout.splitlines():
        path = line[3:].strip() if len(line) > 3 else line.strip()
        for pattern in PROTECTED_PATTERNS:
            if pattern.lower() in path.lower():
                touched.append(path)
    return touched


def validate_workflow(path: Path) -> Dict[str, Any]:
    data = path.read_bytes()
    text = data.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    issues: List[Dict[str, Any]] = []

    if data.startswith(b"\xef\xbb\xbf"):
        issues.append({"severity": "warn", "line": 1, "message": "utf8_bom_present"})
    for required in ["name:", "on:", "jobs:"]:
        if not re.search(rf"(?m)^\s*{re.escape(required)}", text):
            issues.append({"severity": "fail", "line": None, "message": f"missing_required_key_{required.rstrip(':')}"})

    run_blocks = extract_run_blocks(lines)
    for line_no, _end, _base, script in run_blocks:
        error = bash_validate(script)
        if error and error != "bash_unavailable":
            issues.append({"severity": "fail", "line": line_no, "message": "bash_n_failed", "detail": error[-1200:]})
        if_count = len(re.findall(r"(?m)^\s*if\b", script))
        fi_count = len(re.findall(r"(?m)^\s*fi\b", script))
        if if_count != fi_count:
            issues.append({"severity": "fail", "line": line_no, "message": f"meta_if_fi_imbalance if={if_count} fi={fi_count}"})
        for n, script_line in enumerate(script.splitlines(), start=line_no):
            stripped = script_line.strip()
            if stripped.startswith("git push"):
                issues.append({"severity": "warn", "line": n, "message": "raw_git_push_detected_prefer_safe_push_retry"})
            if "--force" in stripped and "git push" in stripped:
                issues.append({"severity": "fail", "line": n, "message": "force_push_detected"})

    return {
        "file": str(path.relative_to(ROOT)),
        "run_block_count": len(run_blocks),
        "issue_count": len(issues),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    global ROOT, WF_DIR, OUT
    ROOT = Path(args.repo_root).resolve()
    WF_DIR = ROOT / ".github" / "workflows"
    OUT = ROOT / "_runtime" / "peak_elite" / "workflow_static_validation"
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    if not WF_DIR.exists():
        results.append({"file": str(WF_DIR), "run_block_count": 0, "issue_count": 1, "issues": [{"severity": "fail", "message": "workflow_dir_missing"}]})
    else:
        for path in sorted(WF_DIR.glob("*.yml")):
            results.append(validate_workflow(path))

    protected = protected_modified(ROOT)
    issue_count = sum(r["issue_count"] for r in results) + len(protected)
    fail_count = sum(1 for r in results for i in r["issues"] if i.get("severity") == "fail") + len(protected)
    warn_count = sum(1 for r in results for i in r["issues"] if i.get("severity") == "warn")
    report = {
        "created_utc": iso_now(),
        "status": "fail" if fail_count else ("pass_with_warnings" if warn_count else "pass"),
        "workflow_count": len(results),
        "run_block_count": sum(r["run_block_count"] for r in results),
        "issue_count": issue_count,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "stable_engine_modified": bool([p for p in protected if "Engine_2026-06-07_STABLE" in p]),
        "canonical_workbook_overwrite": bool([p for p in protected if "Workbook" in p]),
        "promotion_allowed": False,
        "protected_modified": protected,
        "results": results,
    }
    write_json(OUT / "workflow_static_validation.json", report)
    md = [
        "# F1 Workflow Static Validation v2",
        "",
        f"Created UTC: `{report['created_utc']}`",
        f"Status: **{report['status']}**",
        f"Workflows: `{report['workflow_count']}`",
        f"Run blocks checked: `{report['run_block_count']}`",
        f"Failures: `{report['fail_count']}`",
        f"Warnings: `{report['warn_count']}`",
        "",
        "## Issues",
    ]
    any_issue = False
    for r in results:
        for issue in r["issues"]:
            any_issue = True
            md.append(f"- {issue.get('severity','?').upper()}: `{r['file']}`:{issue.get('line') or ''} — {issue.get('message')} {issue.get('detail','')}")
    if not any_issue:
        md.append("- None")
    md += [
        "",
        "## Governance",
        "- Stable engine modified: `false`" if not report["stable_engine_modified"] else "- Stable engine modified: `true`",
        "- Canonical workbook overwrite: `false`" if not report["canonical_workbook_overwrite"] else "- Canonical workbook overwrite: `true`",
        "- Promotion allowed: `false`",
    ]
    (OUT / "WORKFLOW_STATIC_VALIDATION.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
