#!/usr/bin/env python3
"""Health check for forecast/fantasy readiness dashboard connector."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from datetime import datetime, timezone

REQUIRED = [
    "scripts/dashboard_connector/health_check_dashboard_connector_v1.py",
    "scripts/dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py",
    "configs/dashboard_connector/dashboard_connector_policy_v1.json",
    "schemas/dashboard_connector/dashboard_state_schema_v1.json",
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="safe_test")
    ap.add_argument("--runtime-dir", default="_runtime/dashboard_connector")
    args = ap.parse_args()
    root = Path.cwd()
    runtime = root / args.runtime_dir
    runtime.mkdir(parents=True, exist_ok=True)

    missing = [p for p in REQUIRED if not (root / p).is_file()]
    status = "Pass" if not missing else "Fail"
    result = {
        "component": "forecast_fantasy_readiness_dashboard_connector",
        "mode": args.mode,
        "status": status,
        "timestamp_utc": now(),
        "missing_files": missing,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "commit_allowed": False if args.mode == "safe_test" else None,
    }
    (runtime / "health_check_dashboard_connector_v1.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if status == "Pass" else 2

if __name__ == "__main__":
    sys.exit(main())
