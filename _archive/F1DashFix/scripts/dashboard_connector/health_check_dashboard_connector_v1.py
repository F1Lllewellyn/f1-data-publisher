#!/usr/bin/env python3
from pathlib import Path
import json, sys

root = Path(__file__).resolve().parents[2]
required = [
    'scripts/dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py',
    'configs/dashboard_connector/dashboard_connector_policy_v1.json',
    'schemas/dashboard_connector/dashboard_state_schema_v1.json',
    '.github/workflows/f1-forecast-fantasy-readiness-dashboard-safe-test.yml',
    '.github/workflows/f1-forecast-fantasy-readiness-dashboard-run-now.yml',
    '.github/workflows/f1-forecast-fantasy-readiness-dashboard-scheduled.yml',
]
missing = [p for p in required if not (root/p).exists()]
print(json.dumps({
    'status': 'Pass' if not missing else 'Fail',
    'missing': missing,
    'canonical_workbook_overwrite': False,
    'stable_engine_modified': False,
    'promotion_allowed': False,
}, indent=2))
sys.exit(0 if not missing else 1)
