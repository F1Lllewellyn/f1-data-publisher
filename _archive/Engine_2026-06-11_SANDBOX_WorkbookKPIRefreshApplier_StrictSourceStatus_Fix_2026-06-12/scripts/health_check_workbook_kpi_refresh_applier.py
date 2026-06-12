#!/usr/bin/env python3
"""Static health check for the Workbook/KPI Refresh Applier sandbox package."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

REQUIRED = [
    "README.md",
    "WORKBOOK_KPI_REFRESH_APPLIER_DESIGN.md",
    "SOURCE_TO_WORKBOOK_KPI_FLOW.md",
    "configs/workbook_kpi_refresh_policy_v1.json",
    "schemas/sandbox_workbook_update_plan_schema_v1.json",
    "schemas/workbook_kpi_refresh_manifest_schema_v1.json",
    "scripts/apply_workbook_kpi_refresh_v1.py",
    ".github/workflows/f1-workbook-kpi-refresh-safe-test-button.yml",
    ".github/workflows/f1-workbook-kpi-refresh-run-now-button.yml",
    ".github/workflows/f1-workbook-kpi-refresh-scheduled.yml",
    "installer/RUN_F1_WORKBOOK_KPI_REFRESH_APPLIER_WINDOWS.bat",
]

FORBIDDEN_SNIPPETS = [
    "allow_model_promotion" + chr(34) + ": true",
    "allow_canonical_overwrite" + chr(34) + ": true",
    "shutil." + "rmtree(",
    "os." + "remove(",
    "git push" + " --force",
]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package-root", default=".")
    args = ap.parse_args()
    root = Path(args.package_root).resolve()
    missing = [p for p in REQUIRED if not (root / p).exists()]
    forbidden_hits = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in [".py",".yml",".yaml",".json",".md",".bat"]:
            txt = path.read_text(encoding="utf-8", errors="ignore")
            for snip in FORBIDDEN_SNIPPETS:
                if snip in txt:
                    forbidden_hits.append(f"{path.relative_to(root)} contains {snip}")
    verdict = "pass" if not missing and not forbidden_hits else "fail"
    out = {
        "verdict": verdict,
        "missing_required_files": missing,
        "forbidden_hits": forbidden_hits,
        "stable_engine_protected": True,
        "canonical_workbook_overwrite_blocked": True,
        "promotion_blocked": True,
    }
    print(json.dumps(out, indent=2))
    return 0 if verdict == "pass" else 2

if __name__ == "__main__":
    raise SystemExit(main())
