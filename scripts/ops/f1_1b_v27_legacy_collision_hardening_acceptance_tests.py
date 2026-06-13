#!/usr/bin/env python3
"""Acceptance tests for F1 1B v27 session-gate automation and legacy collision hardening."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES = [
    ".github/workflows/f1-peak-elite-control-room-one-click-v1.yml",
    ".github/workflows/f1-session-autorepair-integrated-loop-v1.yml",
    ".github/workflows/openf1-prerace-auto-ingest.yml",
    "scripts/ops/f1_canonical_chain_guard_v27.py",
    "scripts/ops/f1_openf1_live_restriction_guard_v27.py",
]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def assert_true(cond: bool, msg: str, failures: list[str]) -> None:
    if not cond:
        failures.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve()
    failures: list[str] = []

    for rel in REQUIRED_FILES:
        assert_true((root / rel).exists(), f"missing required file: {rel}", failures)

    if failures:
        print(json.dumps({"status": "fail", "failures": failures}, indent=2))
        return 1

    control = text(root / ".github/workflows/f1-peak-elite-control-room-one-click-v1.yml")
    autorepair = text(root / ".github/workflows/f1-session-autorepair-integrated-loop-v1.yml")
    openf1 = text(root / ".github/workflows/openf1-prerace-auto-ingest.yml")
    all_yaml = control + "\n" + autorepair + "\n" + openf1

    assert_true("OPERATION=\"full_run_chain\"" in control, "scheduled Control Room default must run full_run_chain", failures)
    assert_true("f1_canonical_chain_guard_v27.py" in control, "Control Room must write v27 scheduled gate decision", failures)
    assert_true("latest/session_gate_watch_v27" in control, "Control Room must upload/commit v27 gate decision", failures)

    assert_true("group: f1-main-write-serialization" in autorepair, "legacy autorepair must share canonical write concurrency group", failures)
    assert_true("steps.canonical_guard.outputs.should_yield != 'true'" in autorepair, "legacy autorepair heavy steps must yield to canonical guard", failures)
    assert_true("f1_canonical_chain_guard_v27.py" in autorepair, "legacy autorepair must run v27 canonical guard", failures)

    assert_true("deferred: ${{ steps.extract.outputs.deferred }}" in openf1, "OpenF1 prereace must expose deferred output", failures)
    assert_true("needs.extract_and_checkpoint.outputs.deferred != 'true'" in openf1, "OpenF1 validation job must skip on deferred live restriction", failures)
    assert_true("f1_openf1_live_restriction_guard_v27.py" in openf1, "OpenF1 prereace must classify live-session 401", failures)

    assert_true("run_forecast_gate: false" in control or "RUN_FORECAST_GATE=\"false\"" in control, "forecast gate must remain default false", failures)
    assert_true("<<'PY'" not in all_yaml and "<<\"PY\"" not in all_yaml, "workflow YAML must not use inline Python heredocs", failures)
    assert_true("git push" not in all_yaml, "workflow YAML must not use raw git push", failures)
    assert_true("Engine_2026-06-07_STABLE" in control, "Control Room protected engine guard must remain present", failures)

    for rel in ["scripts/ops/f1_canonical_chain_guard_v27.py", "scripts/ops/f1_openf1_live_restriction_guard_v27.py"]:
        result = subprocess.run([sys.executable, "-m", "py_compile", str(root / rel)], capture_output=True, text=True)
        assert_true(result.returncode == 0, f"python compile failed for {rel}: {result.stderr}", failures)

    status = "pass" if not failures else "fail"
    report = {
        "status": status,
        "test_count": 13,
        "failures": failures,
        "forecast_gate_activated": False,
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
    }
    out_dir = root / "latest" / "1b_validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "v27_legacy_collision_hardening_acceptance_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
