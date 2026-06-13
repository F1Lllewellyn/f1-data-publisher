#!/usr/bin/env python3
"""F1 1B source-readiness aggregation v2.

Session-aware source-readiness aggregation for the autonomous Session Data
Processor Loop. It prevents expected-empty or optional-context Practice-session
sources, such as starting_grid and intervals, from downgrading the whole system
into manual-review or partial state when core Practice data is usable.

This module is sandbox/readiness-only. It does not promote forecasts, modify the
stable engine, or overwrite canonical workbooks.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Set

CLEANISH = {"clean"}
PARTIALISH = {"partial"}
LATEISH = {"late", "no_data"}
MANUALISH = {"needs_manual_review", "manual_review", "needs-review", "needs_manual"}
CONFLICTING = {"conflicting", "conflict"}

PRACTICE_REQUIRED = {"drivers", "laps", "position", "weather"}
PRACTICE_OPTIONAL_CONTEXT = {"intervals", "pit", "stints", "race_control", "session_result"}
PRACTICE_EXPECTED_EMPTY = {"starting_grid"}

QUALIFYING_REQUIRED = {"drivers", "laps", "position", "session_result", "weather"}
QUALIFYING_OPTIONAL_CONTEXT = {"intervals", "pit", "stints", "race_control", "starting_grid"}
QUALIFYING_EXPECTED_EMPTY: Set[str] = set()

RACE_REQUIRED = {"drivers", "laps", "position", "race_control", "session_result", "starting_grid", "weather"}
RACE_OPTIONAL_CONTEXT = {"intervals", "pit", "stints"}
RACE_EXPECTED_EMPTY: Set[str] = set()

DEFAULT_REQUIRED = {"drivers", "laps", "position", "weather"}
DEFAULT_OPTIONAL_CONTEXT = {"intervals", "pit", "stints", "race_control", "session_result", "starting_grid"}
DEFAULT_EXPECTED_EMPTY: Set[str] = set()


def canonical_endpoint(name: str) -> str:
    n = str(name or "").strip().lower()
    if n.startswith("openf1_"):
        n = n[len("openf1_"):]
    return n


def normalize_status(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_") or "missing"


def infer_session_family(session: Mapping[str, Any]) -> str:
    raw = f"{session.get('session_name', '')} {session.get('session_type', '')}".lower()
    if "practice" in raw or "fp1" in raw or "fp2" in raw or "fp3" in raw:
        return "practice"
    if "sprint qualifying" in raw or "sprint_shootout" in raw:
        return "qualifying"
    if "qualifying" in raw:
        return "qualifying"
    if "sprint" in raw and "qual" not in raw:
        return "race"
    if "race" in raw:
        return "race"
    return "other"


def policy_for_family(family: str) -> Dict[str, Set[str]]:
    if family == "practice":
        return {"required": PRACTICE_REQUIRED, "optional_context": PRACTICE_OPTIONAL_CONTEXT, "expected_empty": PRACTICE_EXPECTED_EMPTY}
    if family == "qualifying":
        return {"required": QUALIFYING_REQUIRED, "optional_context": QUALIFYING_OPTIONAL_CONTEXT, "expected_empty": QUALIFYING_EXPECTED_EMPTY}
    if family == "race":
        return {"required": RACE_REQUIRED, "optional_context": RACE_OPTIONAL_CONTEXT, "expected_empty": RACE_EXPECTED_EMPTY}
    return {"required": DEFAULT_REQUIRED, "optional_context": DEFAULT_OPTIONAL_CONTEXT, "expected_empty": DEFAULT_EXPECTED_EMPTY}


def aggregate_source_readiness(source_reports: Mapping[str, Mapping[str, Any]], session: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    session = session or {}
    family = infer_session_family(session)
    policy = policy_for_family(family)
    required = set(policy["required"])
    optional_context = set(policy["optional_context"])
    expected_empty = set(policy["expected_empty"])

    per_source: Dict[str, Dict[str, Any]] = {}
    blocking_issues: List[Dict[str, Any]] = []
    optional_context_gaps: List[Dict[str, Any]] = []
    expected_empty_sources: List[Dict[str, Any]] = []
    critical_partial: List[Dict[str, Any]] = []
    critical_late: List[Dict[str, Any]] = []

    endpoints_seen = set()
    for original_name, report in source_reports.items():
        endpoint = canonical_endpoint(original_name)
        endpoints_seen.add(endpoint)
        status = normalize_status(report.get("status"))
        rows = int(report.get("rows") or 0)
        missing_cols = list(report.get("missing_required_columns") or [])
        anomalies = list(report.get("anomalies") or [])
        role = "required" if endpoint in required else "optional_context" if endpoint in optional_context else "expected_empty" if endpoint in expected_empty else "observed_optional"
        effective_status = status
        classification = status
        blocking = False
        reason = ""

        if endpoint in expected_empty and rows == 0:
            effective_status = "clean"
            classification = "expected_empty"
            reason = "expected_empty_for_session_type"
            expected_empty_sources.append({"source": original_name, "endpoint": endpoint, "status": status, "rows": rows, "reason": reason})
        elif endpoint in optional_context and rows == 0 and status in (LATEISH | PARTIALISH | CLEANISH):
            effective_status = "clean"
            classification = "optional_empty"
            reason = "optional_context_empty_for_session_type"
            optional_context_gaps.append({"source": original_name, "endpoint": endpoint, "status": status, "rows": rows, "reason": reason})
        elif endpoint in required:
            if status in CONFLICTING:
                effective_status = "conflicting"
                blocking = True
                reason = "required_source_conflicting"
                blocking_issues.append({"source": original_name, "endpoint": endpoint, "status": status, "rows": rows, "reason": reason, "anomalies": anomalies})
            elif status in MANUALISH:
                effective_status = "needs_manual_review"
                blocking = True
                reason = "required_source_needs_manual_review"
                blocking_issues.append({"source": original_name, "endpoint": endpoint, "status": status, "rows": rows, "reason": reason, "anomalies": anomalies})
            elif rows == 0 or status in LATEISH:
                effective_status = "late"
                blocking = True
                reason = "required_source_late_or_empty"
                critical_late.append({"source": original_name, "endpoint": endpoint, "status": status, "rows": rows, "reason": reason})
            elif status in PARTIALISH or missing_cols:
                effective_status = "partial"
                classification = "critical_partial"
                reason = "required_source_partial_but_usable"
                critical_partial.append({"source": original_name, "endpoint": endpoint, "status": status, "rows": rows, "missing_required_columns": missing_cols, "reason": reason})
            else:
                effective_status = "clean"
                classification = "critical_clean"
                reason = "required_source_clean"
        else:
            if status in CONFLICTING or status in MANUALISH:
                effective_status = "partial"
                classification = "optional_context_warning"
                reason = "optional_source_warning_non_blocking"
                optional_context_gaps.append({"source": original_name, "endpoint": endpoint, "status": status, "rows": rows, "reason": reason})
            elif rows == 0 and status in (LATEISH | PARTIALISH):
                effective_status = "clean"
                classification = "optional_empty"
                reason = "optional_source_empty_non_blocking"
                optional_context_gaps.append({"source": original_name, "endpoint": endpoint, "status": status, "rows": rows, "reason": reason})
            else:
                classification = "optional_observed"
                reason = "optional_source_observed"

        per_source[original_name] = {
            "endpoint": endpoint,
            "role": role,
            "raw_status": status,
            "effective_status": effective_status,
            "classification": classification,
            "rows": rows,
            "blocking": blocking,
            "reason": reason,
            "missing_required_columns": missing_cols,
            "anomalies": anomalies,
        }

    missing_required = sorted(required - endpoints_seen)
    for endpoint in missing_required:
        critical_late.append({"source": f"openf1_{endpoint}", "endpoint": endpoint, "status": "missing", "rows": 0, "reason": "required_source_not_fetched"})

    if any(item.get("reason") == "required_source_conflicting" for item in blocking_issues):
        overall = "conflicting"
    elif blocking_issues:
        overall = "needs_manual_review"
    elif critical_late:
        overall = "late"
    elif critical_partial:
        overall = "partial"
    elif optional_context_gaps or expected_empty_sources:
        overall = "clean"
    else:
        overall = "clean" if source_reports else "no_data"

    needs_manual_review = overall in {"conflicting", "needs_manual_review"}
    if overall == "clean" and (optional_context_gaps or expected_empty_sources):
        quality = "usable_with_optional_context_gaps"
    elif overall == "clean":
        quality = "usable_clean"
    elif overall == "partial":
        quality = "usable_with_required_source_partial"
    elif overall == "late":
        quality = "not_ready_required_source_late"
    elif overall == "conflicting":
        quality = "blocked_conflicting_required_source"
    elif overall == "needs_manual_review":
        quality = "blocked_manual_review_required_source"
    else:
        quality = "not_ready_no_data"

    return {
        "schema_version": "source_readiness_aggregation_v2",
        "session_family": family,
        "overall_status": overall,
        "readiness_quality": quality,
        "needs_manual_review": needs_manual_review,
        "promotion_allowed": False,
        "critical_endpoints": sorted(required),
        "optional_context_endpoints": sorted(optional_context),
        "expected_empty_endpoints": sorted(expected_empty),
        "missing_required_endpoints": missing_required,
        "blocking_issues": blocking_issues,
        "critical_late": critical_late,
        "critical_partial": critical_partial,
        "optional_context_gaps": optional_context_gaps,
        "expected_empty_sources": expected_empty_sources,
        "source_effective_statuses": {k: v["effective_status"] for k, v in per_source.items()},
        "per_source": per_source,
    }


def _self_test() -> int:
    practice_session = {"session_name": "Practice 2", "session_type": "Practice"}
    sources = {
        "openf1_drivers": {"status": "clean", "rows": 20},
        "openf1_laps": {"status": "clean", "rows": 300},
        "openf1_position": {"status": "clean", "rows": 4000},
        "openf1_weather": {"status": "clean", "rows": 90},
        "openf1_intervals": {"status": "late", "rows": 0},
        "openf1_starting_grid": {"status": "late", "rows": 0},
    }
    agg = aggregate_source_readiness(sources, practice_session)
    assert agg["overall_status"] == "clean", agg
    assert agg["readiness_quality"] == "usable_with_optional_context_gaps", agg
    assert agg["needs_manual_review"] is False, agg
    sources_bad = dict(sources)
    sources_bad["openf1_laps"] = {"status": "late", "rows": 0}
    agg_bad = aggregate_source_readiness(sources_bad, practice_session)
    assert agg_bad["overall_status"] == "late", agg_bad
    assert agg_bad["needs_manual_review"] is False, agg_bad
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
