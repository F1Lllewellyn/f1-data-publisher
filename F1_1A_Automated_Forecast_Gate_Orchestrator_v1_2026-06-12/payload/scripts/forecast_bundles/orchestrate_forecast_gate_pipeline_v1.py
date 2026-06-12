#!/usr/bin/env python3
"""Automated forecast gate orchestrator v1.

Purpose:
- Detect real F1 gate windows from public session schedule where possible.
- Run source closure, forecast production, source writer, readiness validation, and bundle locking in one safe chain.
- Avoid manual event_id handling for the user.
- Avoid placeholder bundle commits by default.

This script never promotes a model and never edits stable engine logic.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path.cwd()
RUNTIME = ROOT / "_runtime" / "forecast_gate_orchestrator"
POLICY_PATH = ROOT / "configs" / "forecast_bundles" / "forecast_gate_orchestrator_policy_v1.json"
GATES = ["pre_weekend", "post_fp3", "post_qualifying", "race_result", "post_event"]
LANES = ["stable_baseline", "control_room_overlay", "experimental_challenger"]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def slugify(value: Any) -> str:
    s = str(value or "unknown")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s or "unknown"


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def parse_time(value: Any) -> Optional[dt.datetime]:
    if value is None or value == "":
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return None


def fetch_openf1_sessions(season: int) -> List[Dict[str, Any]]:
    url = f"https://api.openf1.org/v1/sessions?year={season}"
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception as exc:
        print(f"OpenF1 schedule fetch unavailable: {exc!r}")
        return []


def group_sessions_by_meeting(sessions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for s in sessions:
        key = str(s.get("meeting_key") or s.get("meeting_name") or s.get("location") or "unknown")
        grouped.setdefault(key, []).append(s)
    for key in grouped:
        grouped[key].sort(key=lambda x: str(x.get("date_start") or ""))
    return grouped


def session_label(session: Dict[str, Any]) -> str:
    return f"{session.get('session_name','')} {session.get('session_type','')}".lower()


def find_session(meeting_sessions: List[Dict[str, Any]], keywords: List[str], exclude: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    exclude = exclude or []
    for s in meeting_sessions:
        label = session_label(s)
        if all(k in label for k in keywords) and not any(e in label for e in exclude):
            return s
    return None


def meeting_name(meeting_sessions: List[Dict[str, Any]]) -> str:
    first = meeting_sessions[0] if meeting_sessions else {}
    parts = [first.get("country_name"), first.get("location"), first.get("circuit_short_name")]
    clean = [str(p) for p in parts if p]
    return " - ".join(clean) if clean else "F1 Event"


def detect_gate_from_schedule(season: int, now: dt.datetime, policy: Dict[str, Any]) -> Dict[str, Any]:
    sessions = fetch_openf1_sessions(season)
    grouped = group_sessions_by_meeting(sessions)
    windows = policy.get("gate_windows_minutes", {})

    candidates: List[Dict[str, Any]] = []
    for meeting_key, meeting_sessions in grouped.items():
        starts = [parse_time(s.get("date_start")) for s in meeting_sessions]
        ends = [parse_time(s.get("date_end")) for s in meeting_sessions]
        starts = [x for x in starts if x]
        ends = [x for x in ends if x]
        if not starts:
            continue
        first_start = min(starts)
        last_end = max(ends) if ends else max(starts)
        # Ignore meetings far away from now.
        if not (first_start - dt.timedelta(days=3) <= now <= last_end + dt.timedelta(days=2)):
            continue

        fp3 = find_session(meeting_sessions, ["practice", "3"])
        if fp3 is None:
            fp3 = find_session(meeting_sessions, ["practice"], exclude=["1", "2"])
        qualifying = find_session(meeting_sessions, ["qualifying"], exclude=["sprint"])
        race = find_session(meeting_sessions, ["race"], exclude=["sprint"])
        sprint = find_session(meeting_sessions, ["sprint"], exclude=["qualifying", "shootout"])

        def add_gate(gate: str, start: dt.datetime, end: dt.datetime, basis: str) -> None:
            if start <= now <= end:
                candidates.append({
                    "gate": gate,
                    "meeting_key": str(meeting_key),
                    "event_id": f"{season}_{meeting_key}_{slugify(meeting_name(meeting_sessions))}",
                    "race_name": meeting_name(meeting_sessions),
                    "window_start_utc": start.isoformat().replace("+00:00", "Z"),
                    "window_end_utc": end.isoformat().replace("+00:00", "Z"),
                    "basis": basis,
                })

        # Pre-weekend window: before first session starts.
        pre_start = first_start - dt.timedelta(minutes=int(windows.get("pre_weekend_start_before_first_session", 2880)))
        pre_end = first_start - dt.timedelta(minutes=int(windows.get("pre_weekend_end_before_first_session", 60)))
        add_gate("pre_weekend", pre_start, pre_end, "before_first_session")

        if fp3:
            fp3_end = parse_time(fp3.get("date_end")) or parse_time(fp3.get("date_start"))
            qual_start = parse_time(qualifying.get("date_start")) if qualifying else None
            if fp3_end:
                start = fp3_end + dt.timedelta(minutes=int(windows.get("post_fp3_start_after_fp3", 5)))
                end = (qual_start - dt.timedelta(minutes=int(windows.get("post_fp3_end_before_qualifying", 10)))) if qual_start else (start + dt.timedelta(minutes=120))
                add_gate("post_fp3", start, end, "after_fp3_before_qualifying")

        if qualifying:
            qual_end = parse_time(qualifying.get("date_end")) or parse_time(qualifying.get("date_start"))
            race_start = parse_time(race.get("date_start")) if race else (parse_time(sprint.get("date_start")) if sprint else None)
            if qual_end:
                start = qual_end + dt.timedelta(minutes=int(windows.get("post_qualifying_start_after_qualifying", 5)))
                end = (race_start - dt.timedelta(minutes=int(windows.get("post_qualifying_end_before_race", 10)))) if race_start else (start + dt.timedelta(hours=18))
                add_gate("post_qualifying", start, end, "after_qualifying_before_race")

        if race:
            race_end = parse_time(race.get("date_end")) or parse_time(race.get("date_start"))
            if race_end:
                start = race_end + dt.timedelta(minutes=int(windows.get("race_result_start_after_race", 10)))
                end = race_end + dt.timedelta(minutes=int(windows.get("race_result_end_after_race", 180)))
                add_gate("race_result", start, end, "after_race_for_scoring")
                post_start = race_end + dt.timedelta(minutes=int(windows.get("post_event_start_after_race", 180)))
                post_end = race_end + dt.timedelta(minutes=int(windows.get("post_event_end_after_race", 1440)))
                add_gate("post_event", post_start, post_end, "post_event_attribution")

    if candidates:
        # Prefer the most specific/post-session gate if overlapping.
        order = {"pre_weekend": 0, "post_fp3": 1, "post_qualifying": 2, "race_result": 3, "post_event": 4}
        candidates.sort(key=lambda x: order.get(str(x.get("gate")), -1), reverse=True)
        result = candidates[0]
        result.update({"should_run": True, "reason": "active_gate_window_detected"})
        return result

    return {"should_run": False, "reason": "no_active_gate_window_detected", "gate": "none", "event_id": "none", "race_name": "none"}


def source_digest(paths: List[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        if p.exists() and p.is_file():
            h.update(str(p.relative_to(ROOT)).encode("utf-8", errors="replace"))
            h.update(p.read_bytes())
    return h.hexdigest()


def existing_bundle_for(event_id: str, gate: str) -> bool:
    base = ROOT / "latest" / "forecast_bundles" / event_id / gate
    if not base.exists():
        return False
    for lane in LANES:
        if not (base / lane / "bundle_lock_manifest.json").exists():
            return False
    return True


def run_command(label: str, cmd: List[str], dry_run: bool = False) -> Dict[str, Any]:
    print(f"\n--- {label} ---")
    print(" ".join(cmd))
    if dry_run:
        return {"label": label, "cmd": cmd, "returncode": 0, "dry_run": True}
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(proc.stdout)
    return {"label": label, "cmd": cmd, "returncode": proc.returncode, "output_tail": proc.stdout[-4000:]}


def ensure_script(path: str) -> None:
    full = ROOT / path
    if not full.exists():
        raise FileNotFoundError(f"Required script missing: {path}")


def run_pipeline(event_id: str, race_name: str, gate: str, run_source_closure: bool, season: int, dry_run: bool) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    python = sys.executable

    # Required scripts. The source-closure script is optional based on flag.
    ensure_script("scripts/forecasts/produce_actual_forecast_rows_v1.py")
    ensure_script("scripts/forecast_bundles/write_gate_forecast_rows_v1.py")
    ensure_script("scripts/forecast_bundles/validate_forecast_chain_readiness_v1.py")
    ensure_script("scripts/forecast_bundles/create_forecast_bundles_v1.py")

    if run_source_closure:
        if (ROOT / "scripts" / "openf1" / "publish_openf1_lightweight_source_closure.py").exists():
            results.append(run_command("OpenF1 Lightweight Source Closure", [
                python, "scripts/openf1/publish_openf1_lightweight_source_closure.py",
                "--season", str(season),
                "--completed-only", "true",
                "--output-root", ".",
            ], dry_run=dry_run))
        else:
            results.append({"label": "OpenF1 Lightweight Source Closure", "returncode": 0, "skipped": True, "reason": "script_missing_optional"})

    results.append(run_command("Actual Forecast Producer", [
        python, "scripts/forecasts/produce_actual_forecast_rows_v1.py",
        "--event-id", event_id,
        "--race-name", race_name,
        "--gate", gate,
        "--lane", "all",
        "--repo-root", ".",
    ], dry_run=dry_run))
    if results[-1].get("returncode") != 0:
        return results

    results.append(run_command("Forecast Gate Source Writer", [
        python, "scripts/forecast_bundles/write_gate_forecast_rows_v1.py",
        "--repo-root", ".",
        "--event-id", event_id,
        "--gate", gate,
        "--lane", "all",
    ], dry_run=dry_run))
    if results[-1].get("returncode") != 0:
        return results

    results.append(run_command("Forecast Chain Readiness Validator", [
        python, "scripts/forecast_bundles/validate_forecast_chain_readiness_v1.py",
        "--repo", ".",
        "--event-id", event_id,
        "--gate", gate,
        "--lane", "all",
    ], dry_run=dry_run))
    if results[-1].get("returncode") != 0:
        return results

    # Do not pass --allow-structural-placeholders. No-source guard remains active by default.
    results.append(run_command("Forecast Bundle Locker", [
        python, "scripts/forecast_bundles/create_forecast_bundles_v1.py",
        "--repo-root", ".",
        "--event-id", event_id,
        "--race-name", race_name,
        "--gate", gate,
        "--source-root", ".",
    ], dry_run=dry_run))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Automate F1 forecast gate production and bundle locking.")
    parser.add_argument("--mode", default="auto", choices=["auto", "force_validation", "dry_run"])
    parser.add_argument("--event-id", default="auto")
    parser.add_argument("--race-name", default="auto")
    parser.add_argument("--gate", default="auto", choices=["auto", "all", *GATES])
    parser.add_argument("--run-source-closure", default="true")
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    RUNTIME.mkdir(parents=True, exist_ok=True)
    policy = read_json(POLICY_PATH, {})
    dry_run = args.mode == "dry_run"
    run_source_closure = str(args.run_source_closure).lower() in {"true", "1", "yes"}

    result: Dict[str, Any] = {
        "created_utc": iso_now(),
        "mode": args.mode,
        "requested_event_id": args.event_id,
        "requested_race_name": args.race_name,
        "requested_gate": args.gate,
        "run_source_closure": run_source_closure,
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_modified": False,
    }

    if args.mode == "force_validation":
        event_id = args.event_id if args.event_id != "auto" else "manual_forecast_producer_validation"
        race_name = args.race_name if args.race_name != "auto" else "Manual Forecast Producer Validation"
        gate = args.gate if args.gate != "auto" else "all"
        detection = {"should_run": True, "reason": "force_validation_requested", "event_id": event_id, "race_name": race_name, "gate": gate}
    else:
        detection = detect_gate_from_schedule(args.season, utc_now(), policy)
        if args.event_id != "auto":
            detection["event_id"] = args.event_id
        if args.race_name != "auto":
            detection["race_name"] = args.race_name
        if args.gate != "auto":
            detection["gate"] = args.gate
            detection["should_run"] = True
            detection["reason"] = "manual_gate_override"

    result["gate_detection"] = detection
    write_json(RUNTIME / "gate_detection.json", detection)

    if not detection.get("should_run"):
        result.update({"status": "no_action", "reason": detection.get("reason", "not_detected")})
        write_json(RUNTIME / "orchestrator_result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    event_id = str(detection.get("event_id") or "manual_forecast_producer_validation")
    race_name = str(detection.get("race_name") or "Manual Forecast Producer Validation")
    gate = str(detection.get("gate") or "all")

    if gate != "all" and existing_bundle_for(event_id, gate):
        result.update({"status": "no_action", "reason": "bundle_already_exists_for_gate", "event_id": event_id, "gate": gate})
        write_json(RUNTIME / "orchestrator_result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    try:
        steps = run_pipeline(event_id, race_name, gate, run_source_closure, args.season, dry_run=dry_run)
        result["steps"] = steps
        failed = [s for s in steps if int(s.get("returncode", 0)) != 0]
        result["event_id"] = event_id
        result["race_name"] = race_name
        result["gate"] = gate
        result["status"] = "fail" if failed else ("dry_run_pass" if dry_run else "pass")
        result["reason"] = "step_failed" if failed else "pipeline_completed"
        write_json(RUNTIME / "orchestrator_result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if failed else 0
    except Exception as exc:
        result.update({"status": "fail", "reason": "exception", "error": repr(exc)})
        write_json(RUNTIME / "orchestrator_result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
