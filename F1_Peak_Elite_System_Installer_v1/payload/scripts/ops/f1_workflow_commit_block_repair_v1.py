#!/usr/bin/env python3
"""F1 workflow commit-block repair v1.

Repairs the exact class of breakage that blocked workflow-meta-health:
YAML `run: |` Bash blocks ending before their closing `fi`, plus inline
`if ...; then ...; fi` commit-add statements that confuse the lightweight
meta-health counter.

Scope: GitHub workflow syntax only. This script does not touch model logic,
stable engine files, workbooks, source data, forecast outputs, or automations
outside `.github/workflows/*.yml`.
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
OUT = ROOT / "_runtime" / "peak_elite" / "workflow_repair"
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
            blocks.append((i, j, base, "\n".join(block) + "\n"))
            i = j
        else:
            i += 1
    return blocks


def bash_syntax_error(script: str) -> str:
    bash = shutil.which("bash")
    if not bash:
        # On GitHub Ubuntu bash exists. On Windows local installer this script is
        # not required, but fallback to counter-only behavior if called manually.
        if len(re.findall(r"(?m)^\s*if\b", script)) != len(re.findall(r"(?m)^\s*fi\b", script)):
            return "bash_unavailable_counter_imbalance"
        return ""
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


def expand_inline_git_add_if(lines: List[str]) -> Tuple[List[str], int]:
    repaired: List[str] = []
    count = 0
    pattern = re.compile(r'^(\s*)if \[ -e "\$p" \] && ! git check-ignore -q "\$p"; then git add "\$p"; fi\s*$')
    for line in lines:
        match = pattern.match(line)
        if match:
            indent = match.group(1)
            repaired.extend([
                indent + 'if [ -e "$p" ] && ! git check-ignore -q "$p"; then',
                indent + '  git add "$p"',
                indent + 'fi',
            ])
            count += 1
        else:
            repaired.append(line)
    return repaired, count


def repair_file(path: Path, apply: bool) -> Dict[str, Any]:
    original_bytes = path.read_bytes()
    had_bom = original_bytes.startswith(b"\xef\xbb\xbf")
    text = original_bytes.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    actions: List[Dict[str, Any]] = []

    lines, expanded = expand_inline_git_add_if(lines)
    if expanded:
        actions.append({"action": "expanded_inline_git_add_if", "count": expanded})

    # Iteratively append one `fi` at a time to run blocks that fail specifically
    # due to EOF. Retest after each append so we do not over-repair.
    safety = 0
    while safety < 20:
        safety += 1
        changed_this_round = False
        for start, end, base, script in extract_run_blocks(lines):
            error = bash_syntax_error(script)
            if error and ("unexpected end of file" in error or "counter_imbalance" in error):
                if_count = len(re.findall(r"(?m)^\s*if\b", script))
                fi_count = len(re.findall(r"(?m)^\s*fi\b", script))
                if if_count > fi_count or "unexpected end of file" in error:
                    lines[end:end] = [" " * (base + 2) + "fi"]
                    actions.append({
                        "action": "appended_missing_fi",
                        "run_block_line": start + 1,
                        "if_count_before": if_count,
                        "fi_count_before": fi_count,
                    })
                    changed_this_round = True
                    break
        if not changed_this_round:
            break

    final_text = "\n".join(lines) + "\n"
    final_errors = []
    for start, end, base, script in extract_run_blocks(final_text.splitlines()):
        error = bash_syntax_error(script)
        if error:
            final_errors.append({"run_block_line": start + 1, "error": error})

    changed = final_text.encode("utf-8") != original_bytes and final_text != text
    if apply and changed and not final_errors:
        path.write_text(final_text, encoding="utf-8")

    return {
        "file": str(path.relative_to(ROOT)),
        "changed": bool(changed and not final_errors),
        "would_change": bool(actions and not final_errors),
        "had_utf8_bom": had_bom,
        "actions": actions,
        "final_errors": final_errors,
    }


def protected_modified() -> List[str]:
    git = shutil.which("git")
    if not git:
        return []
    try:
        proc = subprocess.run([git, "status", "--porcelain"], cwd=str(ROOT), text=True, capture_output=True)
    except Exception:
        return []
    touched: List[str] = []
    for line in proc.stdout.splitlines():
        path = line[3:].strip() if len(line) > 3 else line.strip()
        for pattern in PROTECTED_PATTERNS:
            if pattern.lower() in path.lower():
                touched.append(path)
    return touched


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write safe workflow syntax repairs.")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    global ROOT, WF_DIR, OUT
    ROOT = Path(args.repo_root).resolve()
    WF_DIR = ROOT / ".github" / "workflows"
    OUT = ROOT / "_runtime" / "peak_elite" / "workflow_repair"
    OUT.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    if WF_DIR.exists():
        for workflow in sorted(WF_DIR.glob("*.yml")):
            results.append(repair_file(workflow, apply=args.apply))

    protected = protected_modified()
    failures = [r for r in results if r.get("final_errors")]
    changed = [r for r in results if r.get("changed") or r.get("would_change")]
    report = {
        "created_utc": iso_now(),
        "mode": "apply" if args.apply else "check",
        "status": "fail" if failures or protected else ("repaired" if args.apply and changed else "pass"),
        "workflow_count": len(results),
        "changed_count": len(changed),
        "failure_count": len(failures),
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "protected_modified": protected,
        "results": results,
    }
    write_json(OUT / "workflow_commit_block_repair_report.json", report)
    md = [
        "# F1 Workflow Commit-Block Repair Report",
        "",
        f"Created UTC: `{report['created_utc']}`",
        f"Mode: `{report['mode']}`",
        f"Status: **{report['status']}**",
        f"Changed workflows: `{report['changed_count']}`",
        f"Failures: `{report['failure_count']}`",
        "",
        "## Governance",
        "- Stable engine modification: **blocked**",
        "- Canonical workbook overwrite: **blocked**",
        "- Model promotion: **blocked**",
        "- Workflow syntax only: **true**",
        "",
        "## Changed / Repairable workflows",
    ]
    for r in changed:
        md.append(f"- `{r['file']}`: " + ", ".join(a.get("action", "unknown") for a in r.get("actions", [])))
    if not changed:
        md.append("- None")
    if failures:
        md.append("\n## Failures")
        for r in failures:
            md.append(f"- `{r['file']}`: `{r['final_errors']}`")
    (OUT / "WORKFLOW_COMMIT_BLOCK_REPAIR_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
