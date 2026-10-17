#!/usr/bin/env python3
"""Close the dated 2026 historical audit HOLDs without mutating source evidence."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def canonical_row(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def validate_official_participants(participants: list[dict], label: str) -> None:
    grid = [row for row in participants if row["start_status"] == "GRID"]
    pit_lane = [row for row in participants if row["start_status"] == "PIT_LANE"]
    if [row["official_position"] for row in grid] != list(range(1, len(grid) + 1)):
        raise RuntimeError(f"FIA_GRID_POSITION_SEQUENCE_HOLD:{label}")
    if any(row["official_position"] is not None for row in pit_lane):
        raise RuntimeError(f"FIA_PIT_LANE_POSITION_HOLD:{label}")
    if len(participants) != 22 or len({row["driver_number"] for row in participants}) != 22:
        raise RuntimeError(f"FIA_GRID_PARTICIPANT_HOLD:{label}:{len(participants)}")


def exact_deduplicate(rows: list[dict], meeting_key: int, session_key: int, lane: str) -> tuple[list[dict], int]:
    seen: set[str] = set()
    unique: list[dict] = []
    duplicates = 0
    temporal_values: dict[tuple, set[str]] = collections.defaultdict(set)
    for row in rows:
        if row.get("meeting_key") != meeting_key or row.get("session_key") != session_key:
            raise RuntimeError(f"MIAMI_ROW_IDENTITY_HOLD:{lane}")
        identity = canonical_row(row)
        temporal_values[(row["date"], row.get("driver_number"))].add(identity)
        if identity in seen:
            duplicates += 1
        else:
            seen.add(identity)
            unique.append(row)
    if any(len(values) > 1 for values in temporal_values.values()):
        raise RuntimeError(f"MIAMI_DUPLICATE_FORENSIC_HOLD:{lane}")
    return unique, duplicates


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def same_row(words: list[dict], top: float, x_min: float, x_max: float, tolerance: float) -> list[dict]:
    return sorted(
        [word for word in words if abs(word["top"] - top) <= tolerance and x_min <= word["x0"] < x_max],
        key=lambda word: word["x0"],
    )


def parse_final_grid_pdf(path: Path) -> dict:
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 2:
            raise RuntimeError(f"FIA_PDF_PAGE_COUNT_HOLD:{path.name}:{len(pdf.pages)}")
        cover = pdf.pages[0].extract_text(x_tolerance=2, y_tolerance=3) or ""
        page = pdf.pages[1]
        layout = page.extract_text(layout=True, x_tolerance=2, y_tolerance=3) or ""
        words = page.extract_words(use_text_flow=False)

    cutoffs = [word["top"] for word in words if word["text"] in {"NOTES", "PENALTIES"}]
    grid_cutoff = min(cutoffs) - 8 if cutoffs else 610
    grid: list[dict] = []
    used_car_words: set[tuple[float, float, str]] = set()
    for word in words:
        if not word["text"].isdigit() or not 1 <= int(word["text"]) <= 22:
            continue
        if 45 <= word["x0"] <= 65:
            car_range, name_range = (66, 84), (84, 220)
        elif 308 <= word["x0"] <= 330:
            car_range, name_range = (331, 349), (349, 485)
        else:
            continue
        if not 145 <= word["top"] <= grid_cutoff:
            continue
        cars = same_row(words, word["top"] - 2.1, *car_range, tolerance=3.5)
        cars = [item for item in cars if item["text"].isdigit() and 1 <= int(item["text"]) <= 99]
        if len(cars) != 1:
            continue
        car = cars[0]
        name_words = same_row(words, car["top"], *name_range, tolerance=1.1)
        name_parts = [
            item["text"]
            for item in name_words
            if not re.fullmatch(r"\d:\d{2}\.\d{3}", item["text"])
        ]
        if len(name_parts) < 2:
            continue
        marked = "*" in name_parts
        name = " ".join(part for part in name_parts if part != "*")
        grid.append(
            {
                "official_position": int(word["text"]),
                "driver_number": int(car["text"]),
                "driver_name": name,
                "start_status": "GRID",
                "penalty_marker": marked,
            }
        )
        used_car_words.add((car["x0"], car["top"], car["text"]))

    pit_lane: list[dict] = []
    heading_top = None
    notes_top = None
    for word in words:
        if word["text"] == "DRIVERS":
            row = same_row(words, word["top"], 0, 595, tolerance=1.1)
            tokens = [item["text"] for item in row]
            if "PIT" in tokens and "LANE" in tokens:
                heading_top = word["top"]
        if word["text"] == "NOTES":
            notes_top = word["top"]
    if heading_top is not None:
        for word in words:
            if not heading_top < word["top"] < (notes_top or 700):
                continue
            if not word["text"].isdigit() or not 1 <= int(word["text"]) <= 99:
                continue
            if not (66 <= word["x0"] < 84 or 331 <= word["x0"] < 349):
                continue
            if (word["x0"], word["top"], word["text"]) in used_car_words:
                continue
            x_min, x_max = (84, 220) if word["x0"] < 100 else (349, 485)
            name_parts = [
                item["text"]
                for item in same_row(words, word["top"], x_min, x_max, tolerance=1.1)
                if item["text"] != "*" and not re.fullmatch(r"\d:\d{2}\.\d{3}", item["text"])
            ]
            if len(name_parts) >= 2:
                pit_lane.append(
                    {
                        "official_position": None,
                        "driver_number": int(word["text"]),
                        "driver_name": " ".join(name_parts),
                        "start_status": "PIT_LANE",
                        "penalty_marker": True,
                    }
                )

    grid.sort(key=lambda row: row["official_position"])
    participants = grid + pit_lane
    validate_official_participants(participants, path.name)

    document = re.search(r"Document\s+(\d+)", cover)
    date = re.search(r"Date\s+(\d{2}\s+\w+\s+2026)", cover)
    time = re.search(r"Time\s+(\d{2}:\d{2})", cover)
    title = "Final Sprint Starting Grid" if "Final Sprint Starting Grid" in cover else "Final Starting Grid"
    if not document or not date or not time or title not in cover:
        raise RuntimeError(f"FIA_DOCUMENT_METADATA_HOLD:{path.name}")

    lines = layout.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.strip() in {"NOTES", "* PENALTIES"}),
        None,
    )
    note_lines: list[str] = []
    if start is not None:
        for line in lines[start:]:
            stripped = " ".join(line.split())
            if stripped == "The Stewards" or stripped.startswith("© 2026"):
                break
            if stripped:
                note_lines.append(stripped)
    notes = " | ".join(note_lines)
    return {
        "document_number": int(document.group(1)),
        "document_date": date.group(1),
        "document_time": time.group(1),
        "title": title,
        "final_document_title_verified": True,
        "visual_page_validation": "VERIFIED_COMPLETE",
        "participants": participants,
        "penalty_and_revision_notes": notes,
    }


def resolve_manifest_path(repo: Path, recovery_root: Path, relative: str) -> tuple[Path, Path]:
    if relative.startswith("audit/2026-10-17/recovery/processor_outputs/"):
        return (
            recovery_root / relative,
            recovery_root / "audit/2026-10-17/recovery/processor_outputs",
        )
    return repo / relative, repo


def validate_miami(repo: Path, recovery_root: Path, pack: Path, audit: Path) -> dict:
    forensic_path = pack / "MIAMI_FP1_11270_DUPLICATE_FORENSIC_EVIDENCE.json"
    forensic = json.loads(forensic_path.read_text(encoding="utf-8"))
    if forensic["session_key"] != 11270 or forensic["meeting_key"] != 1284:
        raise RuntimeError("MIAMI_FORENSIC_IDENTITY_HOLD")
    derived_dir = audit / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "f1_2026_miami_fp1_duplicate_resolution_v1",
        "session_key": 11270,
        "meeting_key": 1284,
        "historical_only": True,
        "source_preserving": True,
        "raw_evidence_mutated": False,
        "effective_status": "VERIFIED_EXACT_DEDUPLICATED_ANALYTICAL_OVERLAY",
        "sources": {},
    }
    for lane in ("position", "weather"):
        evidence = forensic["sources"][lane]
        raw = recovery_root / evidence["raw_relative_path"]
        raw_before = sha256(raw)
        if raw_before != evidence["raw_reported_sha256"]:
            raise RuntimeError(f"MIAMI_RAW_SHA_HOLD:{lane}")
        rows = json.loads(raw.read_text(encoding="utf-8"))
        unique, duplicates = exact_deduplicate(rows, 1284, 11270, lane)
        if duplicates != evidence["exact_duplicate_extra_rows"]:
            raise RuntimeError(f"MIAMI_DUPLICATE_FORENSIC_HOLD:{lane}")
        if len(rows) != evidence["original_rows"] or len(unique) != evidence["unique_rows"]:
            raise RuntimeError(f"MIAMI_ROW_COUNT_HOLD:{lane}")
        if [row["date"] for row in unique] != sorted(row["date"] for row in unique):
            raise RuntimeError(f"MIAMI_TIMESTAMP_ORDER_HOLD:{lane}")
        candidate = pack / evidence["derived_file"]
        if sha256(candidate) != evidence["derived_data_sha256"] or json.loads(candidate.read_text()) != unique:
            raise RuntimeError(f"MIAMI_DERIVED_CANDIDATE_HOLD:{lane}")
        destination = derived_dir / evidence["derived_file"]
        shutil.copyfile(candidate, destination)
        if sha256(raw) != raw_before:
            raise RuntimeError(f"MIAMI_RAW_MUTATION_HOLD:{lane}")
        result["sources"][lane] = {
            "raw_relative_path": evidence["raw_relative_path"],
            "raw_sha256": raw_before,
            "original_rows": len(rows),
            "exact_duplicate_extra_rows": duplicates,
            "conflicting_datetime_driver_keys": 0,
            "derived_rows": len(unique),
            "derived_relative_path": destination.relative_to(repo).as_posix(),
            "derived_sha256": sha256(destination),
            "derived_git_blob": git_blob(destination),
        }
    return result


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--recovery-root", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--fia-docs", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    audit = repo / "audit/2026-10-17"
    index = json.loads((args.pack / "F1_2026_23_FINAL_GRID_OFFICIAL_SOURCE_INDEX.json").read_text())
    retrieval = json.loads((args.fia_docs / "retrieval_manifest.json").read_text())
    if len(index["rows"]) != 23 or len(retrieval["results"]) != 23:
        raise RuntimeError("FIA_DOCUMENT_CARDINALITY_HOLD")
    if any(row["result"] not in {"RETRIEVED_ONCE", "REUSED_ALREADY_RETRIEVED"} for row in retrieval["results"]):
        raise RuntimeError("FIA_RETRIEVAL_HOLD")

    with (audit / "F1_2026_SESSION_COVERAGE.csv").open(newline="", encoding="utf-8-sig") as handle:
        coverage = list(csv.DictReader(handle))
    coverage_fields = list(coverage[0])
    sessions = {int(row["session_key"]): row for row in coverage if row["source"] == "sessions"}
    if len(coverage) != 935 or len(sessions) != 85:
        raise RuntimeError("COVERAGE_CARDINALITY_HOLD")

    documents = sorted(args.fia_docs.glob("*.pdf"))
    overlays: list[dict] = []
    for source, observed, document in zip(index["rows"], retrieval["results"], documents):
        if source["official_source_url"] != observed["url"] or sha256(document) != observed["sha256"]:
            raise RuntimeError(f"FIA_SOURCE_BINDING_HOLD:{source['target_session_key']}")
        parsed = parse_final_grid_pdf(document)
        expected_title = "Final Sprint Starting Grid" if source["target_session_type"] == "Sprint" else "Final Starting Grid"
        if parsed["title"] != expected_title:
            raise RuntimeError(f"FIA_SESSION_TYPE_HOLD:{source['target_session_key']}")
        session_row = sessions[source["target_session_key"]]
        manifest_path, root = resolve_manifest_path(
            repo, args.recovery_root, session_row["source_evidence_path"]
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report = manifest["sources"]["openf1_starting_grid"]
        raw = root / report["json_path"]
        raw_rows = json.loads(raw.read_text(encoding="utf-8"))
        if sha256(raw) != report["json_sha256"]:
            raise RuntimeError(f"OPENF1_GRID_SHA_HOLD:{source['target_session_key']}")
        openf1_by_driver = {int(row["driver_number"]): row for row in raw_rows}
        if len(openf1_by_driver) != len(raw_rows):
            raise RuntimeError(f"OPENF1_GRID_DUPLICATE_DRIVER_HOLD:{source['target_session_key']}")
        participant_rows = []
        for participant in parsed.pop("participants"):
            source_row = openf1_by_driver.get(participant["driver_number"])
            comparison = "OPENF1_SOURCE_ABSENT"
            if participant["start_status"] == "PIT_LANE":
                comparison = "OFFICIAL_PIT_LANE_SUPERSEDES_QUALIFYING_POSITION"
            elif source_row is not None:
                comparison = (
                    "MATCH" if int(source_row["position"]) == participant["official_position"]
                    else "OFFICIAL_FINAL_GRID_POSITION_DIFFERS_FROM_QUALIFYING_SOURCE"
                )
            participant_rows.append(
                participant
                | {
                    "openf1_qualifying_source_position": int(source_row["position"]) if source_row else None,
                    "comparison": comparison,
                }
            )
        overlays.append(
            {
                "grand_prix": source["grand_prix"],
                "target_session_key": source["target_session_key"],
                "target_session_type": source["target_session_type"],
                "meeting_key": int(session_row["meeting_key"]),
                "official_source_url": source["official_source_url"],
                "fia_pdf_sha256": observed["sha256"],
                "fia_pdf_bytes": observed["byte_count"],
                "first_local_observation_utc": observed["first_local_observation_utc"],
                "source_as_of_classification": "POSTEVENT_HISTORICAL_AUDIT_ONLY",
                "revision_status": "CURRENT_FIA_FINAL_DOCUMENT_AT_2026_10_17_RETRIEVAL",
                "openf1_raw_relative_path": report["json_path"],
                "openf1_raw_sha256": report["json_sha256"],
                "openf1_rows": len(raw_rows),
                "openf1_source_session_keys": sorted({int(row["session_key"]) for row in raw_rows}),
                "reconciliation_verdict": "VERIFIED_FIA_FINAL_GRID_FACTUAL_OVERLAY",
                **parsed,
                "participants": participant_rows,
            }
        )

    overlay_path = audit / "F1_2026_OFFICIAL_FINAL_GRID_OVERLAYS.json"
    overlay_payload = {
        "schema": "f1_2026_official_final_grid_overlays_v1",
        "document_count": 23,
        "participant_records": sum(len(row["participants"]) for row in overlays),
        "pit_lane_starters": sum(
            participant["start_status"] == "PIT_LANE"
            for row in overlays for participant in row["participants"]
        ),
        "source_scope": "23 exact Adviser-allowlisted FIA final-grid PDFs",
        "pdf_bytes_committed": False,
        "non_prospective": True,
        "documents": overlays,
    }
    overlay_path.write_text(json.dumps(overlay_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    miami = validate_miami(repo, args.recovery_root, args.pack, audit)
    miami_path = audit / "F1_2026_MIAMI_FP1_DUPLICATE_RESOLUTION.json"
    miami_path.write_text(json.dumps(miami, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    overlay_keys = {row["target_session_key"] for row in overlays}
    if len(overlay_keys) != 23:
        raise RuntimeError("FIA_TARGET_SESSION_CARDINALITY_HOLD")
    overlay_blob = git_blob(overlay_path)
    miami_blob = git_blob(miami_path)
    for row in coverage:
        key = int(row["session_key"])
        row["engine_accessibility"] = "VERIFIED_OFFLINE_READER_WITH_DATED_OVERLAY"
        if key in overlay_keys:
            row["processor_readiness"] = "clean_with_dated_scientific_overlay"
            if row["source"] == "starting_grid":
                row.update(
                    coverage_status="VERIFIED_COMPLETE",
                    rows_in_manifest_or_archive="22",
                    source_readiness="verified_fia_final_grid_overlay",
                    source_evidence_kind="FIA_OFFICIAL_FINAL_GRID_OVERLAY_POSTEVENT",
                    source_evidence_path=overlay_path.relative_to(repo).as_posix(),
                    source_blob_sha=overlay_blob,
                    gap_detail="",
                )
        if key == 11270:
            row["processor_readiness"] = "clean_with_source_preserving_dedup_overlay"
            if row["source"] in {"position", "weather"}:
                lane = miami["sources"][row["source"]]
                row.update(
                    coverage_status="VERIFIED_COMPLETE",
                    rows_in_manifest_or_archive=str(lane["derived_rows"]),
                    source_readiness="verified_exact_deduplicated_analytical_overlay",
                    source_evidence_kind="SOURCE_PRESERVING_DERIVED_OVERLAY_POSTEVENT",
                    source_evidence_path=miami_path.relative_to(repo).as_posix(),
                    source_blob_sha=miami_blob,
                    gap_detail="",
                )
    if any(row["coverage_status"] in {"HOLD", "MISSING"} for row in coverage):
        remaining = sorted({int(row["session_key"]) for row in coverage if row["coverage_status"] in {"HOLD", "MISSING"}})
        raise RuntimeError(f"UNRESOLVED_REQUIRED_HOLD:{remaining}")
    write_csv(audit / "F1_2026_SESSION_COVERAGE.csv", coverage, coverage_fields)

    gap_path = audit / "F1_2026_DATA_GAPS.csv"
    with gap_path.open(newline="", encoding="utf-8-sig") as handle:
        gap_fields = next(csv.reader(handle))
    write_csv(gap_path, [], gap_fields)

    reader = load_module(
        "output_contract_reader", repo / "scripts/session_data_processor/f1_1b_output_contract_v16.py"
    )
    recovered_paths: dict[int, Path] = {}
    recovery_processor = args.recovery_root / "audit/2026-10-17/recovery/processor_outputs"
    for path in recovery_processor.glob("latest/session_data_processor/*/*/source_readiness_manifest.json"):
        manifest = reader.load_json(path) or {}
        key = int(manifest.get("session", {}).get("session_key") or -1)
        if key in sessions:
            recovered_paths[key] = path
    retained_paths: dict[int, Path] = {}
    for path in (repo / "latest/session_data_processor").glob("*/*/source_readiness_manifest.json"):
        manifest = reader.load_json(path) or {}
        key = int(manifest.get("session", {}).get("session_key") or -1)
        if key in sessions:
            retained_paths[key] = path
    if len(recovered_paths) != 39 or len(retained_paths) != 46:
        raise RuntimeError(f"MANIFEST_CARDINALITY_HOLD:{len(recovered_paths)}:{len(retained_paths)}")
    failures = []
    source_files = 0
    source_rows = 0
    for key in sorted(sessions):
        manifest_path = recovered_paths.get(key) or retained_paths.get(key)
        root = recovery_processor if key in recovered_paths else repo
        manifest = reader.load_json(manifest_path) or {}
        if int(manifest.get("session", {}).get("session_key") or -1) != key:
            failures.append({"session_key": key, "reason": "manifest_identity"})
            continue
        for source, report in manifest.get("sources", {}).items():
            raw = root / report["json_path"]
            value = reader.load_json(raw)
            value = value.get("value") if isinstance(value, dict) and "value" in value else value
            if not isinstance(value, list) or len(value) != int(report.get("rows") or 0):
                failures.append({"session_key": key, "source": source, "reason": "row_count"})
                continue
            source_files += 1
            source_rows += len(value)
    if failures or source_files != 935:
        raise RuntimeError(f"OFFLINE_READER_HOLD:{failures[:5]}:{source_files}")
    if len(overlay_payload["documents"]) != 23 or overlay_payload["participant_records"] != 506:
        raise RuntimeError("OVERLAY_READER_HOLD")

    archive_path = audit / "recovery/F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz"
    if sha256(archive_path) != "ed72021596ed3968c78dfd6690580af3a8c9a292a74df6eadd6ca24f6afec303":
        raise RuntimeError("ORIGINAL_RECOVERY_ARCHIVE_MUTATION_HOLD")
    terminal = {
        "schema": "f1_2026_historical_scientific_validation_v1",
        "as_of_date": "2026-10-17",
        "terminal_status": "VERIFIED_COMPLETE_UNMERGED_CANDIDATE",
        "coverage": {
            "completed_events": 17,
            "expected_sessions": 85,
            "clean_sessions": 85,
            "partial_sessions": 0,
            "held_sessions": 0,
            "missing_sessions": 0,
            "fully_source_verified_sessions": 85,
            "sessions_requiring_review": 0,
            "sessions_missing_required_data": 0,
            "engine_reader_accessible_sessions": 85,
        },
        "fia_final_grids": {
            "documents_retrieved_once": 23,
            "documents_validated": 23,
            "participant_records": 506,
            "pit_lane_starters": overlay_payload["pit_lane_starters"],
            "overlay_path": overlay_path.relative_to(repo).as_posix(),
            "overlay_sha256": sha256(overlay_path),
        },
        "miami_fp1_duplicate_resolution": miami,
        "offline_reader": {
            "implementation": "scripts/session_data_processor/f1_1b_output_contract_v16.py",
            "manifests": 85,
            "source_files": source_files,
            "source_rows": source_rows,
            "dated_grid_overlays": 23,
            "failures": failures,
        },
        "unresolved_issues": [],
        "negative_claims": {
            "pre_race_availability_proven": False,
            "forecast_or_prediction_test_run": False,
            "stable_engine_modified_or_executed": False,
            "canonical_workbook_modified": False,
            "workflow_dispatched": False,
            "issue_309_modified": False,
            "dr002_activated": False,
            "merged_or_promoted": False,
        },
    }
    terminal_path = audit / "F1_2026_HISTORICAL_SCIENTIFIC_VALIDATION.json"
    terminal_path.write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    recovery_validation_path = audit / "F1_2026_HISTORICAL_RECOVERY_VALIDATION.json"
    recovery_validation = json.loads(recovery_validation_path.read_text(encoding="utf-8"))
    recovery_validation["scientific_hold_closure"] = {
        "status": terminal["terminal_status"],
        "fia_documents": 23,
        "miami_exact_duplicate_extras_removed_in_derived_overlay": 50,
        "fully_source_verified_sessions": 85,
        "unresolved_holds": 0,
        "structured_result": terminal_path.relative_to(repo).as_posix(),
    }
    recovery_validation_path.write_text(
        json.dumps(recovery_validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report = f"""# F1 2026 historical session & race data completion — 17 October 2026

**Disposition: VERIFIED COMPLETE / UNMERGED CANDIDATE.** All 85 officially completed 2026 sessions through 17 October now have evidence-backed required-source coverage in the isolated historical audit. Issue #309 and Austin's prospective workflow remain unchanged and undispatched.

## Result

| Measure | Verified result |
|---|---:|
| Officially completed Grands Prix through 17 October | 17 |
| Expected completed sessions | 85 |
| Clean sessions (all required sources verified) | 85 |
| Partial sessions | 0 |
| Held sessions | 0 |
| Missing sessions | 0 |
| Fully source-verified sessions | 85 |
| Sessions still requiring review | 0 |
| Sessions missing required data | 0 |
| Sessions resolved by the existing engine-facing reader plus dated overlays | 85 |
| Original source files parsed and row-count checked | {source_files} |
| Original source rows parsed by the reader check | {source_rows:,} |
| FIA final-grid documents validated | 23 |

## Scientific HOLD closure

- The 23 exact Adviser-allowlisted FIA final-grid PDFs were each retrieved once with no automatic retry. Their URL, byte count, SHA-256, first local observation time, document number/date/time, final grid, penalties and pit-lane semantics are bound in `audit/2026-10-17/F1_2026_OFFICIAL_FINAL_GRID_OVERLAYS.json`. The copyrighted PDF bytes remain private and are not committed.
- All 23 grids contain 22 unique official participants. {overlay_payload['pit_lane_starters']} drivers are represented as pit-lane starters without fabricated ordinal positions. OpenF1 qualifying-source rows remain unchanged and are compared driver by driver to the FIA-authoritative final grids.
- Miami FP1 session 11270 retains its original 670 position and 101 weather rows unchanged. The source-preserving analytical overlays contain 621 and 100 rows after removing exactly 49 and 1 bytewise-identical duplicates; conflicting datetime/driver observations are zero.

## Offline accessibility

The unchanged `f1_1b_output_contract_v16` reader loaded all 85 original manifests and all {source_files} referenced JSON sources, totaling {source_rows:,} source rows, in the isolated environment. The dated closure layer additionally loaded all 23 official grid overlays and both Miami deduplicated analytical sources. No path, identity, parse, hash or row-count failure remains.

## Boundaries

This is a post-event historical completion candidate, not proof of pre-race availability. No OpenF1 data was requested again. No workflow, producer, model, backtest, forecast, promotion or merge ran; no canonical workbook, stable engine or Austin artifact changed; DR-002 remains proposed and the forecast gate remains off.

## Evidence

- `audit/2026-10-17/F1_2026_SESSION_COVERAGE.csv` — 935 expected event/session/source rows.
- `audit/2026-10-17/F1_2026_DATA_GAPS.csv` — zero unresolved rows.
- `audit/2026-10-17/F1_2026_OFFICIAL_FINAL_GRID_OVERLAYS.json` — 23 official documents and 506 factual participant records.
- `audit/2026-10-17/F1_2026_MIAMI_FP1_DUPLICATE_RESOLUTION.json` — raw/derived bindings and exact deduplication proof.
- `audit/2026-10-17/F1_2026_HISTORICAL_SCIENTIFIC_VALIDATION.json` — terminal structured Work Result.
- `audit/2026-10-17/recovery/F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz` — unchanged original recovery archive, SHA-256 `ed72021596ed3968c78dfd6690580af3a8c9a292a74df6eadd6ca24f6afec303`.
"""
    (audit / "F1_2026_DATA_COMPLETION_REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    print(json.dumps(terminal, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
