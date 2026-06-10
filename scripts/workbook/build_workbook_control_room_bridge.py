#!/usr/bin/env python3
"""
Build a workbook/control-room bridge package from the latest Elite artifact.

Input is an extracted Elite artifact directory. Output is a clean package of
workbook-ready files and a manifest. No large OpenF1 extraction is performed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import shutil
import pandas as pd


EXPECTED = [
    "F1_Source_Readiness_Board.csv",
    "F1_Reliability_Warnings.csv",
    "F1_DNF_ALL_Precursor_Board.csv",
    "F1_Fantasy_Risk_Board.csv",
    "F1_Model_Disagreement_Board.csv",
    "F1_Promotion_Gate.csv",
    "F1_Locked_Forecast_Ledger_Snapshot.json",
    "workbook_bridge_manifest.csv",
]


def find_workbook_exports(root: Path) -> Path | None:
    hits = list(root.rglob("workbook_exports"))
    if not hits:
        return None
    hits.sort(key=lambda p: len(str(p)))
    return hits[0]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--elite-artifact-dir", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()

    elite_root = Path(args.elite_artifact_dir)
    out = Path(args.output_dir)
    bridge = out / "workbook_control_room_bridge"
    bridge.mkdir(parents=True, exist_ok=True)

    wb_src = find_workbook_exports(elite_root)
    rows = []

    if wb_src is None:
        status = "NO_WORKBOOK_EXPORTS_FOUND"
    else:
        status = "PASS"
        for name in EXPECTED:
            src = wb_src / name
            dst = bridge / name
            row = {
                "file": name,
                "found": src.exists(),
                "source": str(src),
                "export": str(dst),
                "status": "copied" if src.exists() else "missing",
            }
            if src.exists():
                shutil.copy2(src, dst)
            rows.append(row)

    pd.DataFrame(rows).to_csv(bridge / "workbook_control_room_bridge_validation.csv", index=False)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source_workbook_exports": str(wb_src) if wb_src else "",
        "output_dir": str(bridge),
        "expected_files": EXPECTED,
        "missing_files": [r["file"] for r in rows if not r["found"]],
        "usage": "Import these files into the workbook/control room; GitHub remains heavy compute."
    }
    (bridge / "workbook_control_room_bridge_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# Workbook Control-Room Bridge Package",
        "",
        f"Generated UTC: {summary['generated_utc']}",
        f"Status: `{summary['status']}`",
        "",
        "## Files",
        "",
        "| File | Status |",
        "|---|---:|",
    ]
    for r in rows:
        report.append(f"| {r['file']} | {r['status']} |")
    report += [
        "",
        "## Guardrail",
        "",
        "This package is a workbook/view layer. It does not authorize automatic stable rank changes.",
        "",
    ]
    (bridge / "workbook_control_room_bridge_report.md").write_text("\n".join(report), encoding="utf-8")

    if status != "PASS":
        raise SystemExit("Workbook exports missing from Elite artifact.")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
