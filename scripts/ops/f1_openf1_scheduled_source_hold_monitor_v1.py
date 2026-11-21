#!/usr/bin/env python3
"""Truthful scheduled OpenF1 source-closure HOLD, never source promotion.

Only a verified historical-provider No Results (HTTP 404) coverage gap may be
reported as an *operationally completed* scheduled collection. Every other
incomplete/invalid source, origin, request-budget or data-integrity condition
remains an ordinary failing GitHub Actions job. This tool NEVER publishes data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path


class UnsafeSourceHold(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise UnsafeSourceHold(reason)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(root: Path) -> dict:
    require(root.is_dir() and not root.is_symlink(), "missing_source_diagnostics")
    manifest = json.loads((root / "latest_manifest.json").read_text(encoding="utf-8"))
    require(type(manifest) is dict, "manifest_invalid")
    require(manifest.get("collection_scope") == "historical_season", "not_historical_archive")
    require(manifest.get("completed_only") is True, "unbounded_or_incomplete_collection")
    require(manifest.get("publication_eligible") is False, "not_an_unpublished_hold")
    require(manifest.get("source_quality_status") == "hold", "not_a_source_quality_hold")
    require(manifest.get("historical_archive_complete") is False, "archive_claimed_complete")
    require(manifest.get("official_final_grid_verified") is False, "grid_authority_misrepresented")
    require(manifest.get("session_discovery_status") == "pass", "session_discovery_failed")
    reasons = manifest.get("source_quality_reasons")
    require(type(reasons) is list and len(reasons) == 1, "multiple_or_unclassified_hold_reasons")
    require(
        type(reasons[0]) is str and reasons[0].startswith("required_lane_session_failures:"),
        "not_an_explicit_required_lane_hold",
    )
    normal = manifest.get("normal_collection")
    require(type(normal) is dict and normal.get("source_readiness_promoted") is False,
            "source_readiness_promotion_invalid")
    require(normal.get("prospective_forecast_eligibility_established") is False,
            "forecast_eligibility_invalid")
    budget = normal.get("request_budget")
    require(type(budget) is dict and not budget.get("deferred_reason")
            and budget.get("restriction_events") == [], "provider_or_budget_restriction")
    # Verify the exact original locally generated evidence before classification.
    hashes = {
        "request_log_sha256": "request_log.csv",
        "zero_lane_diagnostics_sha256": "zero_lane_diagnostics.csv",
        "target_sessions_sha256": "data/target_sessions.csv",
        "combined_source_manifest_sha256": "combined_source_manifest.csv",
    }
    for field, relative in hashes.items():
        p = root / relative
        require(p.is_file() and not p.is_symlink(), "missing_evidence:" + relative)
        require(normal.get(field) == sha256(p), "modified_evidence:" + relative)
    with (root / "zero_lane_diagnostics.csv").open(newline="", encoding="utf-8") as f:
        diagnostics = list(csv.DictReader(f))
    failures = [row for row in diagnostics if row.get("status") == "fail"]
    require(bool(failures), "no_original_required_lane_failures")
    for row in failures:
        require(
            row.get("reason") == "required_session_http_404"
            and "http_404" in row.get("request_statuses", "").split(","),
            "material_non_404_source_failure",
        )
    lanes = manifest.get("lanes")
    require(type(lanes) is list, "missing_lane_aggregates")
    failing_lanes = [row for row in lanes if row.get("result") == "fail"]
    require(bool(failing_lanes) and len(failing_lanes) == manifest.get("fail_count"),
            "lane_fail_count_mismatch")
    require(reasons == [f"required_lane_session_failures:{len(failing_lanes)}"],
            "reason_lane_count_mismatch")
    require(any(row.get("lane") == "starting_grid" for row in failures),
            "not_the_proven_historical_grid_coverage_hold")
    # A successful monitoring result is never a source/publication readiness signal.
    return {
        "status": "HOLD_HISTORICAL_PROVIDER_404",
        "operational_execution": "completed",
        "publication_eligible": False,
        "historical_archive_complete": False,
        "forecast_eligible": False,
        "prediction_locked": False,
        "failed_required_lanes": len(failing_lanes),
        "missing_provider_rows": len(failures),
        "source_quality_reasons": reasons,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    try:
        result = assess(args.root)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("OPERATIONAL_FAIL_SOURCE_HOLD_UNVERIFIED: " + str(exc))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    message = (
        "OpenF1 historical-source HOLD: " + str(result["missing_provider_rows"])
        + " missing provider result(s) in " + str(result["failed_required_lanes"])
        + " required lane(s); no publication, forecast or promotion. "
        + "Original source artifact retained for audit."
    )
    print("::warning::" + message)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("## OpenF1 historical-source HOLD (not publication)\n\n" + message + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("publish_eligible=false\nsource_status=HOLD_HISTORICAL_PROVIDER_404\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
