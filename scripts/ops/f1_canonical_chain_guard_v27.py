#!/usr/bin/env python3
"""F1 v27 canonical-chain guard.

Decision-only guard used to keep legacy/session workflows from colliding with the
canonical Control Room -> Output Contract -> Context chain.

It never deletes files, never touches .git, never modifies protected workbooks or
Engine_2026-06-07_STABLE, and never activates forecast/promotion gates.
"""
from __future__ import annotations

import argparse
import importlib.util
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


def scheduled_admission(repo_root: Path, now: datetime, catalog=None) -> Dict[str, Any]:
    """A catalog read discovers a completed session; a timestamp is not a receipt.

    Only the accepted budgeted collector reads OpenF1. Existing standalone routes
    remain available to refresh partial evidence; unchanged HOLDs do not repeatedly
    rebuild the workbook or manufacture successful downstream completions.
    """
    spec = importlib.util.spec_from_file_location("peak_admission_processor",
        Path(__file__).resolve().parents[1] / "session_data_processor/session_data_processor_loop_v1.py")
    processor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(processor)
    sessions, meta = catalog if catalog is not None else processor.fetch_sessions(now.year)
    result = dict(action="HOLD_NO_NEW_ELIGIBLE_SOURCE", operational_status="OPERATIONAL_PASS",
                  consumer_eligible=False, scientific_eligible=False, promotion_allowed=False)
    if meta.get("ok") is not True or not sessions:
        return dict(result, action="HOLD_PROVIDER", operational_status="OPERATIONAL_FAIL",
                    reason="Source catalog unavailable; preserve the last verified context.")
    selected = processor.select_recent_completed_session(sessions, now, 36)
    if not selected:
        return dict(result, reason="No unambiguous recently completed provider session.")
    result.update(session_key=selected["session_key"], meeting_key=selected["meeting_key"])
    status = load_json(repo_root / "latest/peak_elite/orchestrator_status.json")
    state = status.get("latest_state", {})
    if str(state.get("session_key")) != str(selected["session_key"]):
        return dict(result, action="RUN", reason="New completed provider session requires capture and verification.")
    selector = load_json(repo_root / "latest/latest_manifest.json")
    if str(selector.get("session_key")) != str(selected["session_key"]):
        return dict(result, action="RUN", reason="Authoritative current session is not selected in published source.")
    import hashlib
    source_path = repo_root / "latest/latest_manifest.json"
    expected = status.get("handoff_fingerprints", {}).get("latest/latest_manifest.json")
    if source_path.is_file() and hashlib.sha256(source_path.read_bytes()).hexdigest() != expected:
        return dict(result, action="RUN", reason="New source publication requires workbook and context verification.")
    if (status.get("downstream_current") is True and status.get("failed_steps") == []
            and status.get("operation") == "full_run_chain"):
        # Rehash all original inputs before deciding this session was processed.
        for relative, sha in status.get("handoff_fingerprints", {}).items():
            p = repo_root / relative
            if (Path(relative).is_absolute() or ".." in Path(relative).parts or p.is_symlink()
                    or not p.resolve().is_relative_to(repo_root.resolve()) or not p.is_file()
                    or hashlib.sha256(p.read_bytes()).hexdigest() != sha):
                return dict(result, action="HOLD_INPUT_INTEGRITY", operational_status="OPERATIONAL_FAIL",
                            reason="Previously verified input changed without a new source publication.")
        return dict(result, action="NOOP_ALREADY_PROCESSED", reason="Exact source/session already processed; no new capture receipt.")
    return dict(result, reason="Same source remains held; await a new verified source publication.")


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
        admission = (scheduled_admission(repo_root, now) if os.environ.get("GITHUB_EVENT_NAME") == "schedule"
                     else {"action": "RUN", "operational_status": "OPERATIONAL_PASS",
                           "reason": "Explicit operation; existing runtime guards remain authoritative."})
        action, reason = admission["action"], admission["reason"]
        should_yield = action != "RUN"
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
        out.update(admission)
        out_path = repo_root / "_runtime" / "peak_elite" / "gate_decision.json"
        write_json(out_path, out)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
                handle.write(f"action={action}\n")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
                handle.write("## Peak admission\n\n```json\n" + json.dumps(out, indent=2) + "\n```\n")
    else:
        slug = args.workflow_name.lower().replace(" ", "-").replace("+", "plus").replace("/", "-")
        slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in slug).strip("-") or "unknown"
        out_path = repo_root / "latest" / "legacy_workflow_hardening" / f"{slug}_guard.json"
        write_json(out_path, out)

    print(json.dumps({"should_yield": should_yield, "action": action, "reason": reason}, sort_keys=True))
    if args.mode == "scheduled_gate" and out.get("operational_status") == "OPERATIONAL_FAIL":
        return 2
    if args.fail_on_issue and args.mode == "static" and not repo_root.exists():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
