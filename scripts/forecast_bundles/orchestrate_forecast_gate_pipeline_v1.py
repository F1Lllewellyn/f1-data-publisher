#!/usr/bin/env python3
"""Automated forecast gate orchestrator v1.

Purpose:
- Detect real F1 gate windows from public session schedule where possible.
- Report source/engine readiness without substituting the research producer for the protected engine.
- Avoid manual event_id handling for the user.
- Keep acquisition, heuristic production and locking disabled until authentic execution can be proved.

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
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path.cwd()
RUNTIME = ROOT / "_runtime" / "forecast_gate_orchestrator"
POLICY_PATH = ROOT / "configs" / "forecast_bundles" / "forecast_gate_orchestrator_policy_v1.json"
GATES = ["pre_weekend", "post_fp3", "post_qualifying", "race_result", "post_event"]
LANES = ["stable_baseline", "control_room_overlay", "experimental_challenger"]


class ScheduleHold(ValueError):
    """An unavailable or ambiguous catalog is not an inactive gate."""


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
            return None
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return None


def fetch_openf1_sessions(season: int) -> List[Dict[str, Any]]:
    url = f"https://api.openf1.org/v1/sessions?year={season}"
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            if response.status != 200:
                raise ScheduleHold(f"HOLD_SCHEDULE_HTTP_{response.status}")
            raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ScheduleHold("HOLD_SCHEDULE_RESPONSE_TOO_LARGE")
        data = json.loads(raw)
        if not isinstance(data, list) or not data:
            raise ScheduleHold("HOLD_SCHEDULE_EMPTY_OR_INVALID")
        write_json(RUNTIME / "schedule_acquisition.json", {
            "source_url": url, "observed_at_utc": iso_now(),
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "status_code": 200, "sessions": data,
            "official_final_grid_verified": False,
        })
        return data
    except urllib.error.HTTPError as exc:
        raise ScheduleHold(f"HOLD_SCHEDULE_HTTP_{exc.code}") from exc
    except ScheduleHold:
        raise
    except Exception as exc:
        raise ScheduleHold(f"HOLD_SCHEDULE_UNAVAILABLE:{type(exc).__name__}") from exc


def validate_schedule(sessions: List[Dict[str, Any]], season: int) -> None:
    if not isinstance(sessions, list) or not sessions:
        raise ScheduleHold("HOLD_SCHEDULE_EMPTY_OR_INVALID")
    keys = set()
    for row in sessions:
        if not isinstance(row, dict):
            raise ScheduleHold("HOLD_SCHEDULE_ROW_INVALID")
        for field in ("session_key", "meeting_key"):
            if not re.fullmatch(r"[1-9][0-9]*", str(row.get(field, ""))):
                raise ScheduleHold(f"HOLD_SCHEDULE_IDENTITY:{field}")
        key = str(row["session_key"])
        start, end = parse_time(row.get("date_start")), parse_time(row.get("date_end"))
        if key in keys or str(row.get("year")) != str(season):
            raise ScheduleHold("HOLD_SCHEDULE_DUPLICATE_OR_WRONG_SEASON")
        if not row.get("session_name") or not row.get("session_type") or start is None:
            raise ScheduleHold("HOLD_SCHEDULE_IDENTITY_OR_CLOCK")
        if row.get("date_end") and (end is None or end <= start):
            raise ScheduleHold("HOLD_SCHEDULE_CHRONOLOGY")
        keys.add(key)


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
    validate_schedule(sessions, season)
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
        if len(ends) != len(meeting_sessions):
            raise ScheduleHold("HOLD_SCHEDULE_ACTIVE_MEETING_END_UNKNOWN")

        fp3 = find_session(meeting_sessions, ["practice", "3"])
        qualifying = find_session(meeting_sessions, ["qualifying"], exclude=["sprint"])
        race = find_session(meeting_sessions, ["race"], exclude=["sprint"])
        sprint = find_session(meeting_sessions, ["sprint"], exclude=["qualifying", "shootout"])

        def add_gate(gate: str, start: dt.datetime, end: dt.datetime, basis: str) -> None:
            if start <= now < end:
                candidates.append({
                    "gate": gate,
                    "meeting_key": str(meeting_key),
                    "event_id": f"{season}_{meeting_key}_{slugify(meeting_name(meeting_sessions))}",
                    "race_name": meeting_name(meeting_sessions),
                    "window_start_utc": start.isoformat().replace("+00:00", "Z"),
                    "window_end_utc": end.isoformat().replace("+00:00", "Z"),
                    "basis": basis,
                    "schedule_sha256": hashlib.sha256(json.dumps(meeting_sessions, sort_keys=True).encode()).hexdigest(),
                    "session_keys": [str(s["session_key"]) for s in meeting_sessions],
                    "official_final_grid_verified": False,
                })

        # Pre-weekend window: before first session starts.
        pre_start = first_start - dt.timedelta(minutes=int(windows.get("pre_weekend_start_before_first_session", 2880)))
        pre_end = first_start - dt.timedelta(minutes=int(windows.get("pre_weekend_end_before_first_session", 60)))
        add_gate("pre_weekend", pre_start, pre_end, "before_first_session")

        if fp3:
            fp3_end = parse_time(fp3.get("date_end"))
            qual_start = parse_time(qualifying.get("date_start")) if qualifying else None
            if fp3_end and qual_start:
                start = fp3_end + dt.timedelta(minutes=int(windows.get("post_fp3_start_after_fp3", 5)))
                end = (qual_start - dt.timedelta(minutes=int(windows.get("post_fp3_end_before_qualifying", 10)))) if qual_start else (start + dt.timedelta(minutes=120))
                add_gate("post_fp3", start, end, "after_fp3_before_qualifying")

        if qualifying:
            qual_end = parse_time(qualifying.get("date_end"))
            race_start = parse_time(race.get("date_start")) if race else None
            if qual_end and race_start:
                start = qual_end + dt.timedelta(minutes=int(windows.get("post_qualifying_start_after_qualifying", 5)))
                end = (race_start - dt.timedelta(minutes=int(windows.get("post_qualifying_end_before_race", 10)))) if race_start else (start + dt.timedelta(hours=18))
                add_gate("post_qualifying", start, end, "after_qualifying_before_race")

        if race:
            race_end = parse_time(race.get("date_end"))
            if race_end:
                start = race_end + dt.timedelta(minutes=int(windows.get("race_result_start_after_race", 10)))
                end = race_end + dt.timedelta(minutes=int(windows.get("race_result_end_after_race", 180)))
                add_gate("race_result", start, end, "after_race_for_scoring")
                post_start = race_end + dt.timedelta(minutes=int(windows.get("post_event_start_after_race", 180)))
                post_end = race_end + dt.timedelta(minutes=int(windows.get("post_event_end_after_race", 1440)))
                add_gate("post_event", post_start, post_end, "post_event_attribution")

    if candidates:
        if len({c["meeting_key"] for c in candidates}) != 1:
            raise ScheduleHold("HOLD_SCHEDULE_AMBIGUOUS_MEETING")
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
    # Oct5 protected-engine execution-surface assessment found no executable
    # primary stable model. The pinned research producer ranks grid/team priors;
    # neither its lane name nor an existing lock establishes stable invocation.
    # Do not perform season-wide acquisition, run that heuristic, or reach the
    # writer/locker while this missing scientific dependency remains unresolved.
    reason = "HOLD_STABLE_ENGINE_NOT_EXECUTED"
    if gate in {"race_result", "post_event"}:
        reason = "HOLD_POST_OUTCOME_NOT_PROSPECTIVE"
    fingerprints = {}
    for relative in (
        "scripts/forecasts/produce_actual_forecast_rows_v1.py",
        "scripts/forecast_bundles/create_forecast_bundles_v1.py",
        "docs/DR002_PRE2B7G1_STABLE_ENGINE_EXECUTION_SURFACE_2026-10-05.md",
    ):
        path = ROOT / relative
        fingerprints[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return [{
        "label": "Protected stable engine execution preflight",
        "status": "HOLD", "returncode": 2, "reason": reason,
        "event_id": event_id, "gate": gate, "dry_run": dry_run,
        "stable_engine_executed": False, "prediction_locked": False,
        "source_refresh_executed": False,
        "source_refresh_requested": run_source_closure,
        "missing_requirement": "Executable protected stable model with authenticated event/session inputs, cutoff and invocation receipt; FIA final grid where applicable.",
        "research_producer_is_protected_engine": False,
        "dependency_sha256": fingerprints,
    }]


def finish_result(result: Dict[str, Any], strict_exit: int, exit_policy: str) -> int:
    """Monitoring success attests only completed detection/preflight, never a forecast.

    Only the two known, fully evaluated scientific stops can be successful
    monitoring. Provider, custody, dependency and implementation failures remain
    nonzero. Direct callers retain their strict HOLD exit contract.
    """
    steps = result.get("steps", [])
    scientific_stop = (
        result.get("status") == "HOLD"
        and result.get("reason") in {
            "HOLD_STABLE_ENGINE_NOT_EXECUTED", "HOLD_POST_OUTCOME_NOT_PROSPECTIVE"}
        and len(steps) == 1
        and steps[0].get("label") == "Protected stable engine execution preflight"
        and steps[0].get("status") == "HOLD"
        and steps[0].get("returncode") == 2
        and steps[0].get("reason") == result["reason"]
        and all(steps[0].get(k) is False for k in
                ("stable_engine_executed", "prediction_locked", "source_refresh_executed"))
    )
    # A missing dependency is not the established scientific limitation. Do not
    # let a broken checkout silently become a green monitoring run.
    dependencies = steps[0].get("dependency_sha256", {}) if scientific_stop else {}
    dependencies_present = bool(dependencies) and all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in dependencies.values())
    operational_pass = result.get("status") == "no_action" or (scientific_stop and dependencies_present)
    reason = result.get("reason", "HOLD_PIPELINE_NOT_PROVEN")
    if scientific_stop and not dependencies_present:
        failure_class = "IMPLEMENTATION_DEPENDENCY_MISSING"
    elif str(reason).startswith("HOLD_SCHEDULE_HTTP_") or str(reason).startswith("HOLD_SCHEDULE_UNAVAILABLE"):
        failure_class = "EXTERNAL_PROVIDER_RESTRICTION"
    elif str(reason).startswith("HOLD_SCHEDULE_") or reason == "HOLD_EXISTING_BUNDLE_NOT_AUTHENTICATED":
        failure_class = "SOURCE_OR_CUSTODY_NOT_VERIFIED"
    else:
        failure_class = None if operational_pass else "OPERATIONAL_FAILURE"
    result.update(
        operational_status="OPERATIONAL_PASS" if operational_pass else "OPERATIONAL_FAIL",
        operational_scope="schedule_detection_and_scientific_preflight_only",
        scientific_classification="SCIENTIFIC_HOLD",
        forecast_eligible=False, failure_class=failure_class, exit_policy=exit_policy,
    )
    code = strict_exit
    if exit_policy == "monitor":
        code = 0 if operational_pass else (strict_exit or 1)
    result["exit_code"] = code
    write_json(RUNTIME / "orchestrator_result.json", result)
    report = (
        "# Forecast gate monitoring\n\n"
        f"Operational status: **{result['operational_status']}**\n\n"
        "Scope: schedule detection and scientific preflight only; source refresh, "
        "engine execution and prediction locking were not performed.\n\n"
        f"Scientific status: **SCIENTIFIC_HOLD** — `{result.get('scientific_status')}`.\n\n"
        f"Boundary: `{reason}`. Failure class: `{failure_class}`.\n\n"
        "Forecast eligible: **false**. Prediction locked: **false**. Promotion allowed: **false**.\n"
    )
    (RUNTIME / "OPERATOR_STATUS.md").write_text(report, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(report)
    if scientific_stop and operational_pass and exit_policy == "monitor":
        print(f"::warning title=Scientific HOLD::{reason}; forecast_eligible=false; prediction_locked=false")
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="Automate F1 forecast gate production and bundle locking.")
    parser.add_argument("--mode", default="auto", choices=["auto", "force_validation", "dry_run"])
    parser.add_argument("--event-id", default="auto")
    parser.add_argument("--race-name", default="auto")
    parser.add_argument("--gate", default="auto", choices=["auto", "all", *GATES])
    parser.add_argument("--run-source-closure", default="true")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--exit-policy", choices=["strict", "monitor"], default="strict")
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
        "stable_engine_executed": False,
        "prediction_locked": False,
        "scientific_status": "HOLD_STABLE_ENGINE_NOT_EXECUTED",
        "diagnostic_only": True,
        "commit_allowed": False,
    }

    if args.mode == "force_validation":
        event_id = args.event_id if args.event_id != "auto" else "manual_forecast_producer_validation"
        race_name = args.race_name if args.race_name != "auto" else "Manual Forecast Producer Validation"
        gate = args.gate if args.gate != "auto" else "all"
        detection = {"should_run": True, "reason": "force_validation_requested", "event_id": event_id, "race_name": race_name, "gate": gate}
    else:
        try:
            detection = detect_gate_from_schedule(args.season, utc_now(), policy)
        except ScheduleHold as exc:
            result.update(status="HOLD", reason=str(exc))
            return finish_result(result, 2, args.exit_policy)
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
        return finish_result(result, 0, args.exit_policy)

    event_id = str(detection.get("event_id") or "manual_forecast_producer_validation")
    race_name = str(detection.get("race_name") or "Manual Forecast Producer Validation")
    gate = str(detection.get("gate") or "all")

    if gate != "all" and existing_bundle_for(event_id, gate):
        result.update({"status": "HOLD", "reason": "HOLD_EXISTING_BUNDLE_NOT_AUTHENTICATED", "event_id": event_id, "gate": gate})
        return finish_result(result, 2, args.exit_policy)

    try:
        steps = run_pipeline(event_id, race_name, gate, run_source_closure, args.season, dry_run=dry_run)
        result["steps"] = steps
        failed = [s for s in steps if int(s.get("returncode", 0)) != 0]
        result["event_id"] = event_id
        result["race_name"] = race_name
        result["gate"] = gate
        result["status"] = "HOLD"
        result["reason"] = failed[0].get("reason", "HOLD_PIPELINE_NOT_PROVEN") if failed else "HOLD_PIPELINE_NOT_PROVEN"
        return finish_result(result, 2, args.exit_policy)
    except Exception as exc:
        result.update({"status": "fail", "reason": "exception", "error": repr(exc)})
        return finish_result(result, 1, args.exit_policy)


if __name__ == "__main__":
    raise SystemExit(main())
