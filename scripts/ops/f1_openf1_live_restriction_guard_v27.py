#!/usr/bin/env python3
"""Classify OpenF1 live-session 401 restrictions as deferred, not failed.

This script is intentionally narrow. It only reads a workflow log and writes a
small defer report under latest/legacy_workflow_hardening/. It never fetches
sources, never writes model/workbook files, and never changes gates.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

RESTRICTED_MARKERS = (
    "401",
    "unauthorized",
    "restricted to authenticated users",
    "live f1 session in progress",
    "global api access",
)


def is_restricted(text: str) -> bool:
    lower = text.lower()
    return ("401" in lower or "unauthorized" in lower) and any(m in lower for m in RESTRICTED_MARKERS[2:])


def write_json(path: Path, data: Dict[str, object]) -> None:
    if ".git" in path.parts:
        raise RuntimeError(f"Refusing to write inside .git: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--workflow-name", default="OpenF1 Pre-Race Auto Ingest")
    ap.add_argument("--github-run-id", default="unknown")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    log_path = Path(args.log)
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    deferred = is_restricted(text)
    now = datetime.now(timezone.utc).isoformat()
    report = {
        "guard_version": "v27",
        "workflow_name": args.workflow_name,
        "github_run_id": args.github_run_id,
        "generated_utc": now,
        "deferred": deferred,
        "classification": "source_temporarily_restricted" if deferred else "not_live_restriction",
        "reason": "OpenF1 live-session unauthenticated 401 restriction; defer instead of failing legacy prereace workflow." if deferred else "Failure did not match live-session 401 restriction markers.",
        "forecast_gate_activated": False,
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "log_path": str(log_path),
    }
    write_json(repo / "latest" / "legacy_workflow_hardening" / "openf1_prerace_live_restriction_defer_report.json", report)
    print("deferred=true" if deferred else "deferred=false")
    return 0 if deferred else 2


if __name__ == "__main__":
    raise SystemExit(main())
