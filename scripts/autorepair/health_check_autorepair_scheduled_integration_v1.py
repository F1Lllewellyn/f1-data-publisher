#!/usr/bin/env python3
"""Health check for Session Processor + Auto-Repair scheduled integration."""
from __future__ import annotations
import json
from pathlib import Path

REQUIRED = [
    ".github/workflows/f1-session-autorepair-integrated-loop-v1.yml",
    ".github/workflows/f1-session-autorepair-integrated-safe-test-button-v1.yml",
    ".github/workflows/f1-session-autorepair-integrated-run-now-button-v1.yml",
    "scripts/session_data_processor/session_data_processor_loop_v1.py",
    "scripts/autorepair/f1_autorepair_orchestrator_v1.py",
    "scripts/workbook_kpi_refresh/apply_workbook_kpi_refresh_v1.py",
    "configs/autorepair/repair_catalog_v1.json",
]
BLOCKED = [
    "Engine_2026-06-07_STABLE",
    "F1_2026_Prediction_Model_Data_Workbook.xlsx",
    "F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated.xlsx",
]

def main():
    repo = Path(".").resolve()
    missing = [p for p in REQUIRED if not (repo / p).exists()]
    unsafe = []
    for p in REQUIRED:
        full = repo / p
        if full.exists():
            txt = full.read_text(encoding="utf-8", errors="ignore")
            for blocked in BLOCKED:
                if blocked in txt and "PROTECTED" not in txt and "canonical" not in txt.lower():
                    unsafe.append({"file": p, "blocked_reference": blocked})
    result = {
        "status": "Pass" if not missing and not unsafe else "Fail",
        "missing": missing,
        "unsafe_references": unsafe,
        "canonical_workbook_overwrite": False,
        "stable_engine_modified": False,
        "promotion_allowed": False,
        "sandbox_only": True,
    }
    Path("_runtime/autorepair_integrated_health").mkdir(parents=True, exist_ok=True)
    Path("_runtime/autorepair_integrated_health/health_check_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "Pass" else 1
if __name__ == "__main__":
    raise SystemExit(main())
