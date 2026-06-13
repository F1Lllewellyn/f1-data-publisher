#!/usr/bin/env python3
"""Source readiness classifier v2 for the F1 Session Data Processor.

Purpose:
- Distinguish expected-empty OpenF1 endpoints from missing-critical endpoints.
- Prevent practice-session optional endpoints such as starting_grid and intervals
  from incorrectly forcing needs_manual_review.
- Preserve project guardrails: no stable-engine change, no workbook overwrite,
  no prediction promotion.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from typing import Any, Dict, List, Optional

EXPECTED_EMPTY_BY_PHASE = {
    "practice": {
        "starting_grid": "Practice sessions do not have a starting grid.",
        "intervals": "OpenF1 intervals can be empty in practice without blocking readiness.",
        "pit": "Pit rows can be empty or sparse in practice and are context-only.",
        "stints": "Stint rows can be empty or sparse in practice and are context-only.",
        "race_control": "Uneventful practice sessions may have no race-control rows.",
    },
    "qualifying": {
        "starting_grid": "Starting grid is a race/pre-race artifact, not a strict qualifying endpoint.",
        "pit": "Pit rows are not a strict qualifying readiness input.",
        "stints": "Stint rows are not a strict qualifying readiness input.",
    },
    "sprint_qualifying": {
        "starting_grid": "Starting grid is not a strict sprint-qualifying endpoint.",
        "pit": "Pit rows are not a strict sprint-qualifying readiness input.",
        "stints": "Stint rows are not a strict sprint-qualifying readiness input.",
    },
    "sprint": {
        "pit": "Pit rows may be absent in sprint sessions; treat as context unless other core sources fail.",
        "stints": "Stint rows may be sparse in sprint sessions; treat as context unless other core sources fail.",
    },
}

CORE_EMPTY_BLOCKERS_BY_PHASE = {
    "practice": {"sessions", "drivers", "laps", "position", "weather", "session_result"},
    "qualifying": {"sessions", "drivers", "laps", "position", "weather", "session_result"},
    "sprint_qualifying": {"sessions", "drivers", "laps", "position", "weather", "session_result"},
    "sprint": {"sessions", "drivers", "laps", "position", "weather", "session_result", "starting_grid"},
    "race": {"sessions", "drivers", "laps", "position", "weather", "session_result", "starting_grid", "intervals"},
    "unknown": {"sessions", "drivers", "laps", "position", "weather", "session_result"},
}

OPTIONAL_CONTEXT_ENDPOINTS = {"pit", "stints", "race_control", "intervals", "starting_grid"}


def parse_time(value: Any) -> Optional[dt.datetime]:
    if value in (None, ""):
        return None
    try:
        d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc)
    except Exception:
        return None


def session_phase(session: Dict[str, Any]) -> str:
    name = str(session.get("session_name") or "").lower().strip()
    stype = str(session.get("session_type") or "").lower().strip()
    combined = f"{name} {stype}"
    if "sprint qualifying" in combined or "sprint shootout" in combined:
        return "sprint_qualifying"
    if "qualifying" in combined:
        return "qualifying"
    if "practice" in combined or name.startswith("fp") or "free practice" in combined:
        return "practice"
    # check race after qualifying so sprint qualifying doesn't become sprint/race.
    if "sprint" in combined:
        return "sprint"
    if "race" in combined or "grand prix" in combined:
        return "race"
    return "unknown"


def minutes_since_session_end(session: Dict[str, Any]) -> Optional[float]:
    end = parse_time(session.get("date_end")) or parse_time(session.get("date_start"))
    if not end:
        return None
    return (dt.datetime.now(dt.timezone.utc) - end).total_seconds() / 60.0


def classify_openf1_endpoint_v2(
    *,
    endpoint: str,
    rows: List[Dict[str, Any]],
    session: Dict[str, Any],
    fetch_meta: Dict[str, Any],
    required_missing: List[str],
    anomalies: List[str],
    baseline_status: str,
    expected_late: bool = False,
    late_grace_minutes: int = 90,
) -> Dict[str, Any]:
    """Return source-readiness classification metadata for one OpenF1 endpoint.

    The returned `status` intentionally stays within v1-compatible values:
    clean, partial, late, conflicting, needs_manual_review.
    More detail is carried in `empty_classification`, `criticality`, and
    `blocking_for_forecast` so downstream consumers do not break on new statuses.
    """
    endpoint = str(endpoint or "").replace("openf1_", "")
    phase = session_phase(session)
    row_count = len(rows or [])
    fetch_ok = bool(fetch_meta.get("ok"))
    age_minutes = minutes_since_session_end(session)
    empty_policy = EXPECTED_EMPTY_BY_PHASE.get(phase, {}).get(endpoint)
    core_blockers = CORE_EMPTY_BLOCKERS_BY_PHASE.get(phase, CORE_EMPTY_BLOCKERS_BY_PHASE["unknown"])

    out: Dict[str, Any] = {
        "schema_version": "source_readiness_classifier_v2",
        "endpoint": endpoint,
        "session_phase": phase,
        "session_name": session.get("session_name"),
        "session_type": session.get("session_type"),
        "row_count": row_count,
        "baseline_status": baseline_status,
        "status": baseline_status,
        "criticality": "critical" if endpoint in core_blockers else "context",
        "empty_classification": None,
        "blocking_for_forecast": baseline_status in {"conflicting", "needs_manual_review"},
        "reason": None,
        "age_minutes_since_session_end": round(age_minutes, 2) if age_minutes is not None else None,
    }

    if not fetch_ok:
        # Recent/just-completed sessions are late, not automatically broken.
        if expected_late or (age_minutes is not None and age_minutes <= late_grace_minutes):
            out.update({
                "status": "late",
                "criticality": "critical" if endpoint in core_blockers else "context",
                "empty_classification": "fetch_late_or_unavailable_recent_session",
                "blocking_for_forecast": endpoint in core_blockers,
                "reason": "Fetch failed or source unavailable inside late-source grace window.",
            })
        else:
            out.update({
                "status": "needs_manual_review" if endpoint in core_blockers else "partial",
                "blocking_for_forecast": endpoint in core_blockers,
                "reason": "Fetch failed outside late-source grace window.",
            })
        return out

    if anomalies:
        if any(str(a).startswith(("wrong_session_key_rows", "wrong_meeting_key_rows")) for a in anomalies):
            out.update({"status": "conflicting", "blocking_for_forecast": True, "reason": "Rows contain wrong session or meeting keys."})
            return out
        # Duplicate/bad timestamp issues are review items for core sources; context sources can be partial.
        out.update({
            "status": "needs_manual_review" if endpoint in core_blockers else "partial",
            "blocking_for_forecast": endpoint in core_blockers,
            "reason": "Anomalies present: " + ", ".join(map(str, anomalies[:5])),
        })
        return out

    if row_count == 0:
        if empty_policy:
            out.update({
                "status": "clean",
                "criticality": "expected_empty" if endpoint == "starting_grid" else "optional_context",
                "empty_classification": "expected_empty" if endpoint == "starting_grid" else "optional_empty",
                "blocking_for_forecast": False,
                "reason": empty_policy,
            })
            return out
        if endpoint not in core_blockers or endpoint in OPTIONAL_CONTEXT_ENDPOINTS:
            out.update({
                "status": "clean",
                "criticality": "optional_context",
                "empty_classification": "optional_empty",
                "blocking_for_forecast": False,
                "reason": f"{endpoint} is not a blocking source for {phase} sessions.",
            })
            return out
        # Core source empty: late when recent, review when stale.
        if expected_late or (age_minutes is not None and age_minutes <= late_grace_minutes):
            out.update({
                "status": "late",
                "empty_classification": "critical_empty_but_recent",
                "blocking_for_forecast": True,
                "reason": f"Critical {phase} endpoint empty inside late-source grace window.",
            })
            return out
        out.update({
            "status": "needs_manual_review",
            "empty_classification": "critical_empty",
            "blocking_for_forecast": True,
            "reason": f"Critical {phase} endpoint is empty outside late-source grace window.",
        })
        return out

    if required_missing:
        if endpoint in core_blockers:
            out.update({"status": "partial", "blocking_for_forecast": True, "reason": "Missing required columns on core source."})
        else:
            out.update({"status": "partial", "blocking_for_forecast": False, "reason": "Missing required columns on context source."})
        return out

    out.update({
        "status": "clean",
        "blocking_for_forecast": False,
        "reason": "Rows present, required columns satisfied, no blocking anomalies.",
    })
    return out


def run_self_test() -> int:
    session = {
        "session_name": "Practice 2",
        "session_type": "Practice",
        "date_end": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
    }
    tests = [
        ("starting_grid", [], "clean", "expected_empty"),
        ("intervals", [], "clean", "optional_empty"),
        ("laps", [], "late", "critical_empty_but_recent"),
        ("drivers", [{"session_key": 1, "meeting_key": 2, "driver_number": 1}], "clean", None),
    ]
    failures = []
    for endpoint, rows, expected_status, expected_empty in tests:
        rec = classify_openf1_endpoint_v2(
            endpoint=endpoint,
            rows=rows,
            session=session,
            fetch_meta={"ok": True},
            required_missing=[],
            anomalies=[],
            baseline_status="needs_manual_review" if not rows else "clean",
        )
        if rec["status"] != expected_status or rec.get("empty_classification") != expected_empty:
            failures.append({"endpoint": endpoint, "expected_status": expected_status, "expected_empty": expected_empty, "got": rec})
    report = {"status": "pass" if not failures else "fail", "failures": failures, "test_count": len(tests)}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        raise SystemExit(run_self_test())
    print(json.dumps({"status": "ok", "module": "source_readiness_classifier_v2"}, indent=2))
