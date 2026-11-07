#!/usr/bin/env python3
"""Reconcile the isolated 2026 historical recovery into the dated audit files."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, quoting=csv.QUOTE_ALL, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    audit = repo / "audit/2026-10-17"
    recovery = audit / "recovery/processor_outputs"
    coverage_path = audit / "F1_2026_SESSION_COVERAGE.csv"
    gaps_path = audit / "F1_2026_DATA_GAPS.csv"
    report_path = audit / "F1_2026_DATA_COMPLETION_REPORT.md"
    evidence_path = audit / "F1_2026_HISTORICAL_RECOVERY_VALIDATION.json"
    archive_path = audit / "recovery/F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz"

    aggregate = load_module(
        "aggregation_v2", repo / "scripts/session_data_processor/source_readiness_aggregation_v2.py"
    )
    reader = load_module(
        "output_contract_reader", repo / "scripts/session_data_processor/f1_1b_output_contract_v16.py"
    )

    with coverage_path.open(newline="", encoding="utf-8-sig") as handle:
        coverage = list(csv.DictReader(handle))
    fields = list(coverage[0])
    session_rows = {int(row["session_key"]): row for row in coverage if row["source"] == "sessions"}
    if len(session_rows) != 85 or len(coverage) != 935:
        raise RuntimeError("AUDIT_CARDINALITY_HOLD")

    recovered_paths: dict[int, Path] = {}
    for path in recovery.glob("latest/session_data_processor/*/*/source_readiness_manifest.json"):
        manifest = reader.load_json(path) or {}
        key = int(manifest.get("session", {}).get("session_key") or -1)
        if key in session_rows:
            recovered_paths[key] = path
    if len(recovered_paths) != 39:
        raise RuntimeError(f"RECOVERY_CARDINALITY_HOLD:{len(recovered_paths)}")

    existing_paths: dict[int, Path] = {}
    for path in (repo / "latest/session_data_processor").glob("*/*/source_readiness_manifest.json"):
        manifest = reader.load_json(path) or {}
        key = int(manifest.get("session", {}).get("session_key") or -1)
        if key in session_rows:
            existing_paths[key] = path
    if len(existing_paths) != 46:
        raise RuntimeError(f"EXISTING_CARDINALITY_HOLD:{len(existing_paths)}")

    manifestations: dict[int, tuple[Path, Path, dict, dict, str]] = {}
    accessible = []
    source_files = 0
    source_rows = 0
    reader_failures = []
    for key in sorted(session_rows):
        path = recovered_paths.get(key) or existing_paths.get(key)
        root = recovery if key in recovered_paths else repo
        if path is None:
            reader_failures.append({"session_key": key, "reason": "manifest_missing"})
            continue
        manifest = reader.load_json(path) or {}
        if manifest.get("_load_error") or int(manifest.get("session", {}).get("session_key") or -1) != key:
            reader_failures.append({"session_key": key, "reason": "manifest_unreadable_or_identity_mismatch"})
            continue
        readiness = manifest.get("readiness_aggregation")
        if not isinstance(readiness, dict):
            readiness = aggregate.aggregate_source_readiness(manifest.get("sources", {}), manifest.get("session", {}))
        for name, source in manifest.get("sources", {}).items():
            raw_ref = source.get("json_path")
            raw = root / raw_ref if raw_ref else None
            parsed = reader.load_json(raw) if raw else None
            value = parsed.get("value") if isinstance(parsed, dict) and "value" in parsed else parsed
            expected = int(source.get("rows") or 0)
            if not isinstance(value, list) or len(value) != expected:
                reader_failures.append({"session_key": key, "source": name, "reason": "raw_row_mismatch"})
                continue
            source_files += 1
            source_rows += len(value)
        accessible.append(key)
        manifestations[key] = (path, root, manifest, readiness, "recovered" if key in recovered_paths else "retained")
    if reader_failures or len(accessible) != 85 or source_files != 935:
        raise RuntimeError(f"ENGINE_READER_HOLD:{reader_failures[:5]}")

    # Update the 39 recovered sessions and the accepted Barcelona FP2
    # reassessment. Other retained source classifications remain unchanged.
    update_keys = set(recovered_paths) | {11301}
    for row in coverage:
        key = int(row["session_key"])
        row["engine_accessibility"] = "VERIFIED_ENGINE_FACING_READER_ACCESSIBLE"
        if key not in update_keys:
            continue
        manifest_path, _, manifest, readiness, origin = manifestations[key]
        source_name = row["source"]
        report = manifest.get("sources", {}).get(f"openf1_{source_name}", {})
        per_source = readiness.get("per_source", {}).get(f"openf1_{source_name}", {})
        role = per_source.get("role", "observed_optional")
        raw_status = str(report.get("status") or "missing")
        effective = str(per_source.get("effective_status") or raw_status)
        classification = str(per_source.get("classification") or raw_status)
        count = int(report.get("rows") or 0)
        overall = str(readiness.get("overall_status") or manifest.get("overall_status") or "missing")
        row["required_by_processor"] = "yes" if role == "required" else "no"
        row["rows_in_manifest_or_archive"] = str(count)
        row["processor_readiness"] = overall
        row["source_readiness"] = raw_status
        row["source_evidence_kind"] = (
            "ISOLATED_RECOVERY_PROCESSOR_MANIFEST" if origin == "recovered"
            else "PROCESSOR_MANIFEST_REASSESSED_AGGREGATION_V2"
        )
        row["source_evidence_path"] = manifest_path.relative_to(repo).as_posix()
        row["source_blob_sha"] = git_blob(manifest_path)
        anomalies = list(report.get("anomalies") or [])
        if classification == "expected_empty":
            row["coverage_status"] = "NOT_APPLICABLE"
            row["gap_detail"] = "expected empty for this session family"
        elif role == "required" and (effective in {"needs_manual_review", "conflicting"} or anomalies):
            row["coverage_status"] = "HOLD"
            if source_name == "starting_grid":
                row["gap_detail"] = (
                    "post-event OpenF1 grid retained; official FIA final-grid authority and revision timing unverified"
                )
            else:
                row["gap_detail"] = "required-source validation review: " + ",".join(anomalies or [effective])
        elif role == "required" and (count == 0 or effective in {"late", "no_data", "missing"}):
            row["coverage_status"] = "MISSING"
            row["gap_detail"] = "required source absent after bounded recovery"
        elif role == "required" and effective == "partial":
            row["coverage_status"] = "PARTIAL"
            row["gap_detail"] = "required source partial but usable"
        elif count > 0 and effective == "clean":
            row["coverage_status"] = "VERIFIED_COMPLETE"
            row["gap_detail"] = ""
        else:
            row["coverage_status"] = "PARTIAL"
            row["gap_detail"] = "optional context absent or non-blocking"

    latest_status: dict[int, str] = {}
    session_evidence: dict[int, str] = {}
    for key, (path, _, manifest, readiness, _) in manifestations.items():
        latest_status[key] = str(readiness.get("overall_status") or manifest.get("overall_status") or "missing")
        session_evidence[key] = path.relative_to(repo).as_posix()
    status_counts = Counter(latest_status.values())
    clean_sessions = sum(1 for value in latest_status.values() if value == "clean")
    review_sessions = sum(1 for value in latest_status.values() if value in {"needs_manual_review", "conflicting", "partial"})
    missing_sessions = sum(1 for value in latest_status.values() if value in {"late", "missing", "no_data"})
    if (clean_sessions, review_sessions, missing_sessions) != (61, 24, 0):
        raise RuntimeError(f"SESSION_CLASSIFICATION_HOLD:{clean_sessions}:{review_sessions}:{missing_sessions}")

    gap_fields = [
        "round", "grand_prix", "meeting_key", "session_key", "session_name", "severity",
        "gap_type", "affected_sources", "evidence", "smallest_safe_remedy", "estimated_steps", "status",
    ]
    gaps = []
    for key in sorted(session_rows, key=lambda item: (int(session_rows[item]["round"]), session_rows[item]["scheduled_start_utc"])):
        if latest_status[key] == "clean":
            continue
        base = session_rows[key]
        _, _, manifest, readiness, _ = manifestations[key]
        issues = list(readiness.get("blocking_issues") or []) + list(readiness.get("critical_late") or [])
        affected = sorted({str(item.get("endpoint") or item.get("source")) for item in issues})
        is_grid = affected == ["starting_grid"]
        gaps.append({
            "round": base["round"], "grand_prix": base["grand_prix"],
            "meeting_key": base["meeting_key"], "session_key": str(key),
            "session_name": base["session_name"], "severity": "HIGH",
            "gap_type": "OFFICIAL_STARTING_GRID_UNVERIFIED" if is_grid else "REQUIRED_SOURCE_VALIDATION_HOLD",
            "affected_sources": ";".join(affected) or "unclassified_required_source",
            "evidence": session_evidence[key],
            "smallest_safe_remedy": (
                "Verify the official FIA final grid and revision timing through a separately authorized approved capture; preserve post-event classification"
                if is_grid else
                "Inspect the retained duplicate-row evidence and authorize only a source-preserving validation correction if confirmed"
            ),
            "estimated_steps": "3", "status": "HOLD",
        })
    if len(gaps) != 24:
        raise RuntimeError(f"GAP_CARDINALITY_HOLD:{len(gaps)}")

    checkpoint = json.loads((recovery / "historical_recovery_checkpoint.json").read_text())
    first_receipt = json.loads(
        (recovery / "batch_receipts/historical_batch_11227_11228_11229.json").read_text()
    )
    batches = [first_receipt] + list(checkpoint.get("batches") or [])
    requests = [request for batch in batches for request in batch.get("provider_requests", [])]
    if len(batches) != 24 or len(requests) != 125:
        raise RuntimeError(f"REQUEST_EVIDENCE_HOLD:{len(batches)}:{len(requests)}")
    if any(len(batch.get("provider_requests", [])) > 8 for batch in batches):
        raise RuntimeError("PROVIDER_BATCH_LIMIT_HOLD")
    if any(len(batch.get("session_keys") or sorted({r["session_key"] for r in batch.get("provider_requests", [])})) > 4 for batch in batches):
        raise RuntimeError("SESSION_BATCH_LIMIT_HOLD")
    if any(request.get("status_code") != 200 or request.get("ok") is not True for request in requests):
        raise RuntimeError("PROVIDER_RESPONSE_HOLD")

    write_csv(coverage_path, coverage, fields)
    write_csv(gaps_path, gaps, gap_fields)

    acquired_rows = sum(int(request.get("rows") or 0) for request in requests)
    endpoint_counts = Counter(request["endpoint"] for request in requests)
    report = f"""# F1 2026 historical session & race data completion — 17 October 2026

**Disposition: PARTIAL / HOLD; not 100% complete.** The 39 missing processor snapshots were recovered, but 24 sessions retain evidence-backed review holds. Issue #309 and Austin's prospective workflow were not changed or dispatched.

## Result

| Measure | Verified result |
|---|---:|
| Officially completed Grands Prix through 17 October | 17 |
| Expected completed sessions | 85 |
| Fully source-verified sessions | {clean_sessions} |
| Sessions still requiring review | {review_sessions} |
| Sessions missing required retrieved data | {missing_sessions} |
| Sessions successfully resolved by the existing engine-facing reader | 85 |
| Source files parsed and row-count checked | {source_files} |
| Source rows parsed by the reader check | {source_rows:,} |

Every expected session now has a retained processor manifest: 46 pre-existing and 39 isolated recovery manifests. The accepted aggregation-v2 policy reclassifies Barcelona FP2 (session 11301) as `clean / usable_with_optional_context_gaps`; its four required sources remain unchanged and clean.

## Bounded recovery

- Direct provider: only `https://api.openf1.org/v1/`, enforced by the recovery wrapper allowlist.
- Batches: {len(batches)} terminal receipts; no batch exceeded four sessions or eight provider GETs.
- Provider requests: {len(requests)}, all HTTP 200, no automatic retry. Endpoint counts: {json.dumps(dict(sorted(endpoint_counts.items())))}.
- Newly retrieved provider rows: {acquired_rows:,}. Existing retained OpenF1 rows were reused before retrieval.
- Recovered session results: 27 clean and 12 review-required. The five initially absent Race/Sprint grids were fetched once each from their exact qualifying source session after a confirmed wrapper defect was repaired; no completed lane was downloaded again.
- Review package: `audit/2026-10-17/recovery/F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz`. Extracting it at repository root restores `audit/2026-10-17/recovery/processor_outputs/`, including response hashes, observation timestamps, per-session raw rows, validations, manifests, checkpoint and batch receipts.

## Validation and accessibility

The existing `f1_1b_output_contract_v16` reader loaded all 85 manifests and all 935 referenced JSON sources. Every raw list length matched its manifest row count; no session identity or path resolution failed. This proves repository reader accessibility only. It is not a model run, accuracy backtest, forecast, promotion, or stable-engine execution.

## Remaining holds

- 23 Race/Sprint sessions retain `openf1_starting_grid` review because post-event OpenF1 rows do not authenticate the official FIA final grid or establish revision timing. Singapore remains included in this HOLD group.
- One recovered Practice 1 session retains required-source duplicate-row anomalies in position/weather and is not force-cleaned.
- No required retrieved lane is missing, but the 24 review holds prevent a 100% completion claim. `F1_2026_DATA_GAPS.csv` lists the precise evidence and smallest safe remedy for each.

## Scientific and operational boundaries

All new observations are post-event historical recovery. They do not prove pre-race availability for earlier races and cannot be promoted as contemporaneous forecast evidence. No FIA PDF was downloaded, no alternate provider or scraper was used, no workflow was dispatched, no producer/model/backtest ran, no canonical workbook or stable engine changed, and DR-002 remains proposed—not activated.

## Evidence

- `audit/2026-10-17/F1_2026_SESSION_COVERAGE.csv` — 935 event/session/source rows.
- `audit/2026-10-17/F1_2026_DATA_GAPS.csv` — {len(gaps)} unresolved HOLD sessions only.
- `audit/2026-10-17/F1_2026_HISTORICAL_RECOVERY_VALIDATION.json` — request, checkpoint, reader and output hashes.
- `audit/2026-10-17/recovery/F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz` — lossless extracted evidence tree; terminal checkpoint is 39 attempted, 39 processed, zero failed.
"""
    report_path.write_text(report, encoding="utf-8", newline="\n")

    evidence = {
        "schema_version": "f1_2026_historical_recovery_validation_v1",
        "as_of_date": "2026-10-17",
        "scope": {"completed_events": 17, "expected_sessions": 85, "expected_source_rows": 935},
        "recovery": {
            "audited_missing_sessions": 39,
            "attempted_sessions": len(checkpoint.get("attempted") or []),
            "processed_sessions": len(checkpoint.get("processed") or []),
            "failed_sessions": len(checkpoint.get("failed") or []),
            "batch_receipts": len(batches),
            "provider_requests": len(requests),
            "provider_http_200": sum(1 for item in requests if item.get("status_code") == 200),
            "provider_rows": acquired_rows,
            "endpoint_request_counts": dict(sorted(endpoint_counts.items())),
            "no_automatic_retries": True,
            "source_policy": "direct_api.openf1.org_v1_only",
        },
        "classification": {
            "verified_complete_sessions": clean_sessions,
            "review_hold_sessions": review_sessions,
            "missing_required_data_sessions": missing_sessions,
            "status_counts": dict(sorted(status_counts.items())),
            "barcelona_fp2_reassessed_clean": True,
        },
        "engine_reader": {
            "implementation": "scripts/session_data_processor/f1_1b_output_contract_v16.py",
            "accessible_sessions": len(accessible),
            "source_files_parsed": source_files,
            "source_rows_parsed": source_rows,
            "failures": reader_failures,
        },
        "negative_claims": {
            "historical_pre_race_availability_proven": False,
            "forecast_produced": False,
            "stable_engine_executed_or_modified": False,
            "canonical_workbook_modified": False,
            "workflow_dispatched": False,
            "issue_309_modified": False,
            "dr002_activated": False,
        },
        "artifacts": {
            coverage_path.relative_to(repo).as_posix(): {"sha256": sha256(coverage_path), "git_blob": git_blob(coverage_path)},
            gaps_path.relative_to(repo).as_posix(): {"sha256": sha256(gaps_path), "git_blob": git_blob(gaps_path)},
            report_path.relative_to(repo).as_posix(): {"sha256": sha256(report_path), "git_blob": git_blob(report_path)},
            (recovery / "historical_recovery_checkpoint.json").relative_to(repo).as_posix(): {
                "sha256": sha256(recovery / "historical_recovery_checkpoint.json"),
                "git_blob": git_blob(recovery / "historical_recovery_checkpoint.json"),
            },
            archive_path.relative_to(repo).as_posix(): {
                "sha256": sha256(archive_path),
                "git_blob": git_blob(archive_path),
                "size_bytes": archive_path.stat().st_size,
                "extract_at": "repository_root",
            },
        },
    }
    evidence_path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
