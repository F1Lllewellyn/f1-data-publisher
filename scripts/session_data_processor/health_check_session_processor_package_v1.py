#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path.cwd()
REQUIRED = [
    "scripts/session_data_processor/session_data_processor_loop_v1.py",
    "configs/session_data_processor/session_data_processor_policy_v1.json",
    "schemas/session_readiness_manifest_v1.schema.json",
    ".github/workflows/f1-session-data-processor-loop-v1.yml",
    ".github/workflows/f1-session-data-processor-safe-test-button-v1.yml",
    ".github/workflows/f1-session-data-processor-run-now-button-v1.yml",
]

def main() -> int:
    checks = {p: (ROOT / p).exists() for p in REQUIRED}
    policy_path = ROOT / "configs/session_data_processor/session_data_processor_policy_v1.json"
    schema_path = ROOT / "schemas/session_readiness_manifest_v1.schema.json"
    errors = []
    for p, ok in checks.items():
        if not ok: errors.append(f"missing:{p}")
    for p in [policy_path, schema_path]:
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"json_error:{p}:{exc}")
    result = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "checks": checks,
        "stable_engine_modified": False,
        "canonical_workbook_modified": False,
        "promotion_allowed": False,
    }
    out = ROOT / "_runtime" / "session_data_processor" / "package_health_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1
if __name__ == "__main__":
    raise SystemExit(main())
