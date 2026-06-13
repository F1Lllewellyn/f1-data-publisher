#!/usr/bin/env python3
"""F1 1B source-readiness patch validation v1."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()


def read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def main() -> int:
    out = {
        "schema_version": "f1_1b_source_readiness_patch_validation_v1",
        "status": "pass",
        "checks": {},
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
    }
    py = sys.executable
    targets = [
        "scripts/session_data_processor/source_readiness_aggregation_v2.py",
        "scripts/session_data_processor/session_data_processor_loop_v1.py",
        "scripts/ops/f1_1b_source_readiness_patch_validation_v1.py",
    ]
    for rel in targets:
        path = ROOT / rel
        out["checks"][f"exists:{rel}"] = path.exists()
        if not path.exists():
            out["status"] = "fail"
    for rel in targets:
        if (ROOT / rel).exists():
            proc = subprocess.run([py, "-m", "py_compile", rel], cwd=str(ROOT), text=True, capture_output=True)
            out["checks"][f"py_compile:{rel}"] = proc.returncode == 0
            if proc.returncode != 0:
                out["status"] = "fail"
                out[f"py_compile_error:{rel}"] = proc.stderr[-2000:]
    proc = subprocess.run([py, "scripts/session_data_processor/source_readiness_aggregation_v2.py"], cwd=str(ROOT), text=True, capture_output=True)
    out["checks"]["aggregation_self_test"] = proc.returncode == 0
    if proc.returncode != 0:
        out["status"] = "fail"
        out["aggregation_self_test_output"] = (proc.stdout + proc.stderr)[-4000:]
    latest = read_json(ROOT / "latest" / "data_readiness.json", {})
    if isinstance(latest, dict):
        out["latest_readiness_fields"] = {
            "overall_status": latest.get("overall_status"),
            "readiness_quality": latest.get("readiness_quality"),
            "needs_manual_review": latest.get("needs_manual_review"),
            "source_needs_manual_review": latest.get("source_needs_manual_review"),
        }
    report_path = ROOT / "latest" / "source_readiness_patch" / "validation_v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
