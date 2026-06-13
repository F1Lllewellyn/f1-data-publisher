#!/usr/bin/env python3
"""F1 repository canonicalization v1.

Controlled cleanup and inventory for the F1 Prediction Engine repository.
This is not a purge. It deletes only generated junk and writes a reversible
canonicalization plan for legacy artifacts.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

PROTECTED_MARKERS = [
    "Engine_2026-06-07_STABLE",
    "F1_2026_Prediction_Model_Data_Workbook.xlsx",
    "F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated.xlsx",
]
ACTIVE_ROOTS = {".github", "configs", "data", "docs", "history", "latest", "ledgers", "manifests", "schemas", "scripts", "templates", "tests", "workbook_bridge", "workbooks"}
GENERATED_SUFFIXES = {".pyc", ".pyo", ".pyd"}
GITIGNORE_LINES = [
    "__pycache__/",
    "*.py[cod]",
    "*.pyo",
    "*.pyd",
    ".pytest_cache/",
    "scripts/**/__pycache__/",
    "_runtime/**/__pycache__/",
    "_archive/*/REMOVED_GENERATED_PYTHON_CACHES/",
    "_archive/F1_PEAK_ELITE_HYGIENE_PREINSTALL_BACKUP_*/",
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def rel(repo: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def is_protected_path(path: Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    return any(marker.lower() in text for marker in PROTECTED_MARKERS)


def classify_file(repo: Path, p: Path) -> Dict[str, Any]:
    r = rel(repo, p)
    parts = Path(r).parts
    top = parts[0] if parts else r
    suffix = p.suffix.lower()
    category = "active_or_unknown"
    action = "keep"
    reason = "Not classified as generated junk or obvious legacy installer artifact."
    if ".git" in parts:
        category = "git_internal"; action = "ignore"; reason = "Git internal file."
    elif "__pycache__" in parts or suffix in GENERATED_SUFFIXES:
        category = "generated_python_cache"; action = "delete_safe"; reason = "Generated Python bytecode/cache; disposable."
    elif is_protected_path(p):
        category = "protected_engine_or_workbook"; action = "keep_protected"; reason = "Protected by project governance."
    elif top in ACTIVE_ROOTS:
        category = "active_architecture"; action = "keep"; reason = "Inside active architecture root."
    elif top == "_archive":
        category = "archive"; action = "keep"; reason = "Archive/historical area; review before deeper moves."
    elif re.search(r"installer|install_report|patch_manifest|hotfix_manifest|payload_manifest", r, re.I):
        category = "legacy_installer_or_patch_artifact"; action = "recommend_archive_only"; reason = "Likely legacy installer/patch artifact; do not delete automatically."
    elif suffix in {".zip", ".tmp", ".bak"}:
        category = "packaged_or_temp_artifact"; action = "recommend_archive_only"; reason = "Packaged/temp artifact; should be reviewed before archive move."
    return {"path": r, "size_bytes": p.stat().st_size if p.exists() else None, "category": category, "recommended_action": action, "reason": reason, "path_length": len(str(p))}


def ensure_gitignore(repo: Path) -> List[str]:
    path = repo / ".gitignore"
    existing = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    added = []
    if not path.exists():
        path.write_text("", encoding="utf-8")
    for line in GITIGNORE_LINES:
        if line not in existing:
            with path.open("a", encoding="utf-8", newline="\n") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write(line + "\n")
            existing += ("\n" if existing and not existing.endswith("\n") else "") + line + "\n"
            added.append(line)
    return added


def remove_generated(repo: Path) -> Dict[str, Any]:
    removed_dirs: List[str] = []
    removed_files: List[str] = []
    failures: List[Dict[str, str]] = []
    # Delete pycache dirs deepest first.
    pycache_dirs = sorted([p for p in repo.rglob("__pycache__") if ".git" not in p.parts], key=lambda p: len(str(p)), reverse=True)
    for d in pycache_dirs:
        if is_protected_path(d):
            continue
        try:
            shutil.rmtree(d)
            removed_dirs.append(rel(repo, d))
        except Exception as exc:
            failures.append({"path": rel(repo, d), "error": repr(exc)})
    for p in list(repo.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        if p.suffix.lower() in GENERATED_SUFFIXES and not is_protected_path(p):
            try:
                p.unlink()
                removed_files.append(rel(repo, p))
            except Exception as exc:
                failures.append({"path": rel(repo, p), "error": repr(exc)})
    return {"removed_cache_dirs": removed_dirs, "removed_cache_files": removed_files, "failures": failures}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--mode", choices=["report_only", "safe_apply"], default="report_only")
    args = ap.parse_args()
    repo = Path(args.repo_root).resolve()
    latest = repo / "latest" / "repo_canonicalization"
    runtime = repo / "_runtime" / "repo_canonicalization"
    latest.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)

    gitignore_added = ensure_gitignore(repo) if args.mode == "safe_apply" else []
    cleanup = remove_generated(repo) if args.mode == "safe_apply" else {"removed_cache_dirs": [], "removed_cache_files": [], "failures": []}

    records: List[Dict[str, Any]] = []
    file_count = 0
    total_bytes = 0
    long_paths = []
    bom_files = []
    for p in sorted(repo.rglob("*")):
        if ".git" in p.parts or not p.is_file():
            continue
        file_count += 1
        try:
            total_bytes += p.stat().st_size
        except Exception:
            pass
        rec = classify_file(repo, p)
        records.append(rec)
        if rec["path_length"] >= 220:
            long_paths.append(rec["path"])
        try:
            with p.open("rb") as f:
                if f.read(3) == b"\xef\xbb\xbf":
                    bom_files.append(rec["path"])
        except Exception:
            pass

    by_category: Dict[str, int] = {}
    by_action: Dict[str, int] = {}
    for rec in records:
        by_category[rec["category"]] = by_category.get(rec["category"], 0) + 1
        by_action[rec["recommended_action"]] = by_action.get(rec["recommended_action"], 0) + 1

    workflows = sorted(rel(repo, p) for p in (repo / ".github" / "workflows").glob("*.yml")) if (repo / ".github" / "workflows").exists() else []
    report = {
        "schema_version": "repo_canonicalization_v1",
        "created_utc": iso_now(),
        "mode": args.mode,
        "status": "pass" if not cleanup.get("failures") else "pass_with_warnings",
        "repo_root": str(repo),
        "file_count": file_count,
        "total_bytes": total_bytes,
        "workflow_count": len(workflows),
        "category_counts": by_category,
        "recommended_action_counts": by_action,
        "gitignore_added": gitignore_added,
        "generated_cleanup": cleanup,
        "long_paths_over_220_chars": long_paths[:200],
        "utf8_bom_files_sample": bom_files[:200],
        "protected_markers": PROTECTED_MARKERS,
        "protected_assets_touched": False,
        "deletion_policy": "safe_apply deletes only generated Python caches/bytecode. Legacy installers/reports are inventoried for a later reviewed archive move.",
        "phase2_recommendation": "After source classifier stabilizes, move legacy installer/patch/report artifacts into _archive/repository_canonicalization/ using a reviewed manifest, not blind deletion.",
    }
    write_json(latest / "repo_canonicalization_report.json", report)
    write_json(runtime / "repo_canonicalization_report.json", report)

    csv_path = latest / "repo_canonicalization_inventory.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["path", "size_bytes", "category", "recommended_action", "reason", "path_length"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    (runtime / "repo_canonicalization_inventory.csv").write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")

    md = [
        "# F1 Repository Canonicalization Report",
        "",
        f"Created UTC: `{report['created_utc']}`",
        f"Mode: `{args.mode}`",
        f"Status: **{report['status']}**",
        "",
        "## Confirmed Data",
        f"- Files inventoried: `{file_count}`",
        f"- Workflows: `{len(workflows)}`",
        f"- Generated cache directories removed: `{len(cleanup.get('removed_cache_dirs', []))}`",
        f"- Generated bytecode files removed: `{len(cleanup.get('removed_cache_files', []))}`",
        f"- Long paths over 220 chars: `{len(long_paths)}`",
        f"- UTF-8 BOM sample count: `{len(bom_files[:200])}`",
        "",
        "## Cleanup boundary",
        "- Deleted automatically: generated Python cache/bytecode only.",
        "- Not deleted automatically: engines, workbooks, reports, archives, forecast bundles, source artifacts, installers.",
        "- Legacy cleanup is staged as a reviewable Phase 2 plan, not a blind purge.",
        "",
        "## Phase 2 recommendation",
        report["phase2_recommendation"],
    ]
    (latest / "REPO_CANONICALIZATION_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (runtime / "REPO_CANONICALIZATION_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] in {"pass", "pass_with_warnings"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
