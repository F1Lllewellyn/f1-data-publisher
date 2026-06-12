#!/usr/bin/env python3
"""F1 1A cleanup + maintenance script.

Safe operations:
- Locally backs up known placeholder bundle folders.
- Removes placeholder bundle folders from the working tree so git can record deletion.
- Updates common GitHub Actions uses to Node-24-era major versions where safe.
- Writes maintenance reports.

It does not touch workbooks, prediction output files outside the targeted placeholder folders,
or stable engine logic.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
from pathlib import Path

TARGET_PLACEHOLDER_DIRS = [
    Path("latest/forecast_bundles/2026_next_event"),
    Path("history/forecast_bundles/2026_next_event"),
]
ACTION_VERSION_TARGETS = {
    "actions/checkout": "v6",
    "actions/setup-python": "v6",
    "actions/upload-artifact": "v6",
}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def copytree_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return True


def update_workflow_actions(repo: Path) -> list[dict]:
    workflows = repo / ".github" / "workflows"
    changes = []
    if not workflows.exists():
        return changes
    pattern_cache = {
        action: re.compile(rf"({re.escape(action)}@)v\d+(?:\.\d+)*(?:-[A-Za-z0-9._-]+)?")
        for action in ACTION_VERSION_TARGETS
    }
    for yml in sorted(list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml"))):
        before = yml.read_text(encoding="utf-8", errors="replace")
        after = before
        file_updates = []
        for action, target in ACTION_VERSION_TARGETS.items():
            pat = pattern_cache[action]
            matches = pat.findall(after)
            if matches:
                after2 = pat.sub(rf"\g<1>{target}", after)
                if after2 != after:
                    file_updates.append({"action": action, "target": target})
                    after = after2
        if after != before:
            yml.write_text(after, encoding="utf-8")
            changes.append({"workflow": str(yml.relative_to(repo)), "updates": file_updates})
    return changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".", help="Repository root")
    ap.add_argument("--backup-root", default=None, help="Backup root; defaults to .f1_patch_backups")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = Path(args.backup_root).resolve() if args.backup_root else repo / ".f1_patch_backups" / f"cleanup_maintenance_{stamp}"
    report_dir = repo / "latest" / "maintenance" / "f1_1a_github_cleanup_maintenance"
    report_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "run_timestamp_utc": now_utc(),
        "status": "pass_with_warnings",
        "dry_run": bool(args.dry_run),
        "repo": str(repo),
        "stable_engine_changed": False,
        "canonical_workbook_changed": False,
        "promotion_performed": False,
        "placeholder_cleanup": [],
        "workflow_action_updates": [],
        "notes": [],
    }

    backup_root.mkdir(parents=True, exist_ok=True)

    for rel in TARGET_PLACEHOLDER_DIRS:
        src = repo / rel
        item = {"target": str(rel), "existed": src.exists(), "backed_up": False, "removed_from_worktree": False}
        if src.exists():
            backup_dst = backup_root / rel
            item["backed_up"] = copytree_if_exists(src, backup_dst)
            if not args.dry_run:
                if src.is_dir():
                    shutil.rmtree(src)
                else:
                    src.unlink()
                item["removed_from_worktree"] = True
        report["placeholder_cleanup"].append(item)

    if not args.dry_run:
        report["workflow_action_updates"] = update_workflow_actions(repo)
    else:
        report["notes"].append("Dry run: workflow files were not edited.")

    # Keep a small committed report. The local backup is intentionally not committed.
    report_path = report_dir / "cleanup_maintenance_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# F1 1A GitHub Cleanup + Maintenance Report",
        "",
        f"Run timestamp UTC: {report['run_timestamp_utc']}",
        "",
        "## Placeholder cleanup",
        "",
    ]
    for item in report["placeholder_cleanup"]:
        md_lines.append(f"- `{item['target']}`: existed={item['existed']}, backed_up={item['backed_up']}, removed={item['removed_from_worktree']}")
    md_lines += ["", "## Workflow action updates", ""]
    if report["workflow_action_updates"]:
        for ch in report["workflow_action_updates"]:
            updates = ", ".join(f"{u['action']}->{u['target']}" for u in ch["updates"])
            md_lines.append(f"- `{ch['workflow']}`: {updates}")
    else:
        md_lines.append("- No workflow action updates were needed or workflows were not present.")
    md_lines += ["", "## Guardrails", "", "- Stable engine changed: false", "- Canonical workbook changed: false", "- Promotion performed: false", ""]
    (report_dir / "cleanup_maintenance_report.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
