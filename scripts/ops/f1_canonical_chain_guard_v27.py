#!/usr/bin/env python3
"""F1 v27 canonical-chain guard.

Decision-only guard used to keep legacy/session workflows from colliding with the
canonical Control Room -> Output Contract -> Context chain.

It never deletes files, never touches .git, never modifies protected workbooks or
Engine_2026-06-07_STABLE, and never activates forecast/promotion gates.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PROTECTED_MARKERS = (
    ".git",
    "Engine_2026-06-07_STABLE",
    "F1_2026_Prediction_Model_Data_Workbook.xlsx",
    "F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated.xlsx",
)

TIMESTAMP_HINTS = ("utc", "timestamp", "time", "completed", "created", "updated", "run_started", "run_completed")

INPUT_CANDIDATES = (
    "latest/1b_output_contract/control_room_bridge_v25_completion_report.json",
    "latest/1b_output_contract/control_room_bridge_v25_trigger_report.json",
    "latest/consumer_trigger_governor/trigger_decision.json",
    "latest/notification_routing/notification_decision.json",
    "latest/material_change/material_change_report.json",
    "latest/forecast_bundle_ledger/latest_bundle_snapshot.json",
    "latest/last_good_state.json",
    "latest/peak_elite/orchestrator_summary.json",
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    candidates = [s]
    if s.endswith("Z"):
        candidates.append(s[:-1] + "+00:00")
    for c in candidates:
        try:
            dt = datetime.fromisoformat(c)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return None


def load_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {"value": data}
    except FileNotFoundError:
        return {"_missing": True}
    except Exception as exc:
        return {"_read_error": str(exc)}


def walk_timestamps(data: Any, prefix: str = "") -> Iterable[Tuple[str, datetime]]:
    if isinstance(data, dict):
        for k, v in data.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            lk = str(k).lower()
            if any(h in lk for h in TIMESTAMP_HINTS):
                dt = parse_dt(v)
                if dt is not None:
                    yield p, dt
            yield from walk_timestamps(v, p)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            yield from walk_timestamps(v, f"{prefix}[{i}]")


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def safe_output_path(path: Path) -> None:
    parts = set(path.parts)
    if ".git" in parts:
        raise RuntimeError(f"Refusing to write inside .git: {path}")
    norm = path.as_posix()
    for marker in PROTECTED_MARKERS[1:]:
        if marker in norm:
            raise RuntimeError(f"Refusing to write protected path: {path}")


def write_json(path: Path, data: Dict[str, Any]) -> None:
    safe_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def latest_canonical_signal(repo_root: Path, now: datetime) -> Dict[str, Any]:
    observed: List[Dict[str, Any]] = []
    newest: Optional[Tuple[datetime, str, str]] = None
    for candidate in INPUT_CANDIDATES:
        path = repo_root / candidate
        data = load_json(path)
        item: Dict[str, Any] = {"path": candidate, "exists": path.exists()}
        timestamps = []
        if path.exists():
            for key, dt in walk_timestamps(data):
                age_minutes = max(0.0, (now - dt).total_seconds() / 60.0)
                timestamps.append({"key": key, "timestamp_utc": dt.isoformat(), "age_minutes": round(age_minutes, 3)})
                if newest is None or dt > newest[0]:
                    newest = (dt, candidate, key)
        item["timestamps"] = timestamps[:10]
        observed.append(item)
    if newest is None:
        return {"has_signal": False, "observed_inputs": observed}
    dt, path, key = newest
    return {
        "has_signal": True,
        "newest_timestamp_utc": dt.isoformat(),
        "newest_signal_path": path,
        "newest_signal_key": key,
        "newest_signal_age_minutes": round(max(0.0, (now - dt).total_seconds() / 60.0), 3),
        "observed_inputs": observed,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--mode", choices=["legacy_yield", "scheduled_gate", "static"], default="legacy_yield")
    ap.add_argument("--workflow-name", default="unknown")
    ap.add_argument("--recent-minutes", type=int, default=90)
    ap.add_argument("--fail-on-issue", action="store_true")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    now = utcnow()
    signal = latest_canonical_signal(repo_root, now)
    recent = bool(signal.get("has_signal") and float(signal.get("newest_signal_age_minutes", 10**9)) <= args.recent_minutes)

    if args.mode == "legacy_yield":
        should_yield = recent
        action = "yield_to_canonical_control_room" if should_yield else "legacy_allowed_no_recent_canonical_run"
        reason = "Recent canonical Control Room/output-contract state exists; avoid duplicate processor/workbook push collision." if should_yield else "No recent canonical state detected inside guard window."
    elif args.mode == "scheduled_gate":
        should_yield = False
        action = "scheduled_full_run_chain_enabled"
        reason = "Control Room scheduled runs may execute full_run_chain with forecast gate off; orchestrator/session filter still determines if new source data exists."
    else:
        should_yield = False
        action = "static_validation_only"
        reason = "Static guard validation passed."

    out = {
        "guard_version": "v27",
        "workflow_name": args.workflow_name,
        "mode": args.mode,
        "generated_utc": now.isoformat(),
        "recent_minutes": args.recent_minutes,
        "should_yield": should_yield,
        "action": action,
        "reason": reason,
        "forecast_gate_activated": False,
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "source_signal": signal,
    }

    if args.mode == "scheduled_gate":
        out_path = repo_root / "latest" / "session_gate_watch_v27" / "gate_decision.json"
        hist_path = repo_root / "history" / "session_gate_watch_v27" / now.strftime("%Y%m%dT%H%M%SZ") / "gate_decision.json"
        write_json(out_path, out)
        write_json(hist_path, out)
    else:
        slug = args.workflow_name.lower().replace(" ", "-").replace("+", "plus").replace("/", "-")
        slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in slug).strip("-") or "unknown"
        out_path = repo_root / "latest" / "legacy_workflow_hardening" / f"{slug}_guard.json"
        write_json(out_path, out)

    print(json.dumps({"should_yield": should_yield, "action": action, "reason": reason}, sort_keys=True))
    if args.fail_on_issue and args.mode == "static" and not repo_root.exists():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
