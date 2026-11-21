#!/usr/bin/env python3
"""Fail-closed publisher for normal OpenF1 source-closure outputs.

The source collector writes a complete candidate under ``latest/`` and a
timestamped immutable history directory.  This guard snapshots those bytes,
fetches the current remote branch, makes an explicit freshness decision, and
builds one commit on that fetched head.  It performs at most one ordinary
fast-forward push.  A push race is a HOLD, never a rebase, merge, force-push,
retry, or provider re-download.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Sequence


SCHEMA_VERSION = "f1-source-closure-publish-guard-v1"
HOLD_EXIT = 20
PROFILE = "openf1-lightweight-source-closure"
LATEST_REL = PurePosixPath("latest/openf1_lightweight_source_closure")
ZIP_NAME = "openf1_lightweight_source_closure.zip"
ZIP_SHA_NAME = ZIP_NAME + ".sha256.txt"
LANES = (
    "weather",
    "race_control",
    "intervals",
    "position",
    "stints",
    "pit",
    "starting_grid",
    "drivers",
    "team_radio",
)
EXPECTED_FILES = frozenset(
    {
        "F1_OpenF1_Lightweight_Source_Closure_Summary.xlsx",
        "combined_source_manifest.csv",
        "data/target_sessions.csv",
        "data_readiness.json",
        "latest_manifest.json",
        ZIP_NAME,
        ZIP_SHA_NAME,
        "request_log.csv",
        "source_closure_report.md",
        "source_readiness_summary.csv",
        "zero_lane_diagnostics.csv",
        *(f"data/openf1_{lane}.csv" for lane in LANES),
    }
)
TRACKED_FILES = EXPECTED_FILES - {ZIP_NAME}
HISTORY_PATTERN = re.compile(
    r"history/openf1_lightweight_source_closure/([0-9]{8}_[0-9]{6})"
)
BRANCH_PATTERN = re.compile(r"(?![-/])(?!.*(?:\.\.|//))[A-Za-z0-9._/-]+(?<![./])")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
POSITIVE_INTEGER = re.compile(r"[1-9][0-9]*")


class PublicationHold(RuntimeError):
    """A controlled, fail-closed publication result."""


@dataclass(frozen=True)
class SessionIdentity:
    meeting_key: str
    session_name: str
    session_type: str
    date_start: str
    date_end: str
    circuit_short_name: str
    country_name: str
    location: str
    year: str


@dataclass(frozen=True)
class Candidate:
    latest_root: Path
    history_root: Path
    history_rel: PurePosixPath
    manifest: Mapping[str, Any]
    generated_utc: dt.datetime
    tree_sha256: str
    sessions: Mapping[str, SessionIdentity]
    latest_rel: PurePosixPath = LATEST_REL
    files: frozenset[str] = EXPECTED_FILES


@dataclass(frozen=True)
class RemoteLatest:
    manifest: Mapping[str, Any]
    generated_utc: dt.datetime
    tracked_tree_sha256: str
    sessions: Mapping[str, SessionIdentity]


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise PublicationHold(reason)


def _parse_utc(value: Any, reason: str) -> dt.datetime:
    _require(type(value) is str and bool(value), reason)
    try:
        parsed = dt.datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except (TypeError, ValueError) as exc:
        raise PublicationHold(reason) from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, reason)
    _require(parsed.utcoffset() == dt.timedelta(0), reason)
    return parsed.astimezone(dt.timezone.utc)


def _utc_text(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _clock_utc(clock: Callable[[], dt.datetime]) -> dt.datetime:
    try:
        value = clock()
        _require(
            isinstance(value, dt.datetime)
            and value.tzinfo is not None
            and value.utcoffset() is not None,
            "clock_invalid",
        )
        return value.astimezone(dt.timezone.utc)
    except PublicationHold:
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise PublicationHold("clock_invalid") from exc


def _strict_json_bytes(raw: bytes, reason: str) -> Any:
    def pairs(items: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, reason)
            result[key] = value
        return result

    def reject_constant(_value: str) -> None:
        raise PublicationHold(reason)

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except PublicationHold:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PublicationHold(reason) from exc


def _read_json(path: Path, reason: str) -> Any:
    try:
        return _strict_json_bytes(path.read_bytes(), reason)
    except PublicationHold:
        raise
    except OSError as exc:
        raise PublicationHold(reason) from exc


def _csv_rows(path: Path, reason: str) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            _require(reader.fieldnames is not None, reason)
            fieldnames = list(reader.fieldnames)
            _require(len(fieldnames) == len(set(fieldnames)), reason)
            rows = list(reader)
    except PublicationHold:
        raise
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise PublicationHold(reason) from exc
    _require(all(None not in row for row in rows), reason)
    return fieldnames, rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PublicationHold("candidate_file_unreadable") from exc
    return digest.hexdigest()


def _path_inside(root: Path, path: Path, reason: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PublicationHold(reason) from exc


def _regular_tree_files(root: Path, reason: str) -> set[str]:
    _require(root.exists() and root.is_dir() and not root.is_symlink(), reason)
    files: set[str] = set()
    try:
        for current, directories, filenames in os.walk(root, followlinks=False):
            current_path = Path(current)
            for name in directories:
                child = current_path / name
                _require(not child.is_symlink(), reason)
                _require(stat.S_ISDIR(child.stat(follow_symlinks=False).st_mode), reason)
            for name in filenames:
                child = current_path / name
                mode = child.lstat().st_mode
                _require(not stat.S_ISLNK(mode) and stat.S_ISREG(mode), reason)
                relative = child.relative_to(root).as_posix()
                _require(relative not in files, reason)
                files.add(relative)
    except PublicationHold:
        raise
    except OSError as exc:
        raise PublicationHold(reason) from exc
    return files


def _validate_zip(root: Path, files=EXPECTED_FILES) -> None:
    tracked = files - {ZIP_NAME}
    try:
        archive = root / ZIP_NAME
        checksum = (root / ZIP_SHA_NAME).read_text(encoding="utf-8")
        match = re.fullmatch(
            r"([0-9a-f]{64})  openf1_lightweight_source_closure\.zip\n",
            checksum,
        )
        _require(
            match is not None and match.group(1) == _sha256(archive),
            "zip_checksum_mismatch",
        )
        with zipfile.ZipFile(archive) as bundle:
            infos = bundle.infolist()
            names = [item.filename for item in infos]
            _require(len(names) == len(set(names)), "zip_duplicate_member")
            _require(bundle.testzip() is None, "zip_crc_failure")
            allowed = tracked
            for item in infos:
                pure = PurePosixPath(item.filename)
                _require(
                    not pure.is_absolute()
                    and ".." not in pure.parts
                    and item.filename == pure.as_posix()
                    and item.filename in allowed,
                    "zip_member_invalid",
                )
                mode = item.external_attr >> 16
                _require(not stat.S_ISLNK(mode), "zip_member_symlink")
            required = tracked - {ZIP_SHA_NAME}
            _require(required.issubset(names), "zip_required_member_missing")
            for name in required:
                _require(bundle.read(name) == (root / name).read_bytes(), "zip_member_bytes_mismatch")
    except PublicationHold:
        raise
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, RuntimeError) as exc:
        raise PublicationHold("zip_invalid") from exc


def _integer(value: Any, reason: str, *, minimum: int = 0) -> int:
    _require(type(value) is int and value >= minimum, reason)
    return value


def _manifest_lanes(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = manifest.get("lanes")
    _require(type(raw) is list and len(raw) == len(LANES), "manifest_lanes_invalid")
    lanes: dict[str, Mapping[str, Any]] = {}
    for item in raw:
        _require(type(item) is dict, "manifest_lanes_invalid")
        lane = item.get("lane")
        _require(type(lane) is str and lane in LANES and lane not in lanes, "manifest_lanes_invalid")
        _integer(item.get("rows"), "manifest_lane_rows_invalid")
        _require(item.get("result") in {"pass", "pass_with_warnings", "fail"}, "manifest_lane_result_invalid")
        _require(type(item.get("reason")) is str and bool(item.get("reason")), "manifest_lane_reason_invalid")
        expected_status = "opportunistic" if lane == "team_radio" else "required_lightweight"
        _require(item.get("required_status") == expected_status, "manifest_lane_status_invalid")
        _require(item.get("heavy_endpoint") is False, "manifest_lane_heavy_invalid")
        lanes[lane] = item
    _require(set(lanes) == set(LANES), "manifest_lanes_invalid")
    return lanes


def _validate_manifest(
    manifest: Any,
    *,
    expected_season: int,
    expected_completed_only: bool,
    now: dt.datetime,
    candidate: bool,
    meeting_key: str = "",
) -> tuple[dt.datetime, PurePosixPath, dict[str, Mapping[str, Any]]]:
    prefix = "candidate" if candidate else "remote"
    _require(type(manifest) is dict, f"{prefix}_manifest_invalid")
    _require(manifest.get("artifact_profile") == PROFILE, f"{prefix}_profile_mismatch")
    _require(manifest.get("season") == expected_season, f"{prefix}_season_mismatch")
    _require(manifest.get("completed_only") is expected_completed_only, f"{prefix}_completed_only_mismatch")
    generated = _parse_utc(manifest.get("generated_utc"), f"{prefix}_generated_utc_invalid")
    _require(generated <= now + dt.timedelta(minutes=5), f"{prefix}_generated_utc_in_future")
    pattern = (re.compile(r"history/openf1_event_source_closure/" + re.escape(meeting_key) + r"/([0-9]{8}_[0-9]{6}_[0-9]{6})") if meeting_key else HISTORY_PATTERN)
    history_value = manifest.get("history_path")
    _require(type(history_value) is str and pattern.fullmatch(history_value), f"{prefix}_history_path_invalid")
    history_rel = PurePosixPath(history_value)
    history_clock = dt.datetime.strptime(
        pattern.fullmatch(history_value).group(1), "%Y%m%d_%H%M%S_%f" if meeting_key else "%Y%m%d_%H%M%S"
    ).replace(tzinfo=dt.timezone.utc)
    _require(history_clock <= generated, f"{prefix}_history_clock_after_generation")
    _integer(manifest.get("target_session_count"), f"{prefix}_target_count_invalid")
    lanes = _manifest_lanes(manifest)
    results = [lanes[lane]["result"] for lane in LANES]
    _require(manifest.get("pass_count") == results.count("pass"), f"{prefix}_pass_count_invalid")
    _require(
        manifest.get("pass_with_warnings_count") == results.count("pass_with_warnings"),
        f"{prefix}_warning_count_invalid",
    )
    _require(manifest.get("fail_count") == results.count("fail"), f"{prefix}_fail_count_invalid")
    _require(manifest.get("fail_count") == 0, f"{prefix}_failed_lane_not_publishable")
    _require(manifest.get("latest_zip") == ZIP_NAME, f"{prefix}_latest_zip_invalid")
    _require(
        manifest.get("heavy_endpoints_excluded_by_default") == ["car_data", "location"],
        f"{prefix}_heavy_endpoint_policy_invalid",
    )
    _require(manifest.get("timestamp_policy") == "dt.datetime.now(dt.UTC)", f"{prefix}_timestamp_policy_invalid")
    _require(manifest.get("no_drs_2026_assumption") is True, f"{prefix}_2026_drs_policy_invalid")
    previous = manifest.get("previous_manifest_generated_utc")
    if previous is not None:
        previous_utc = _parse_utc(previous, f"{prefix}_previous_generated_utc_invalid")
        _require(previous_utc < generated, f"{prefix}_previous_generation_not_older")
    if meeting_key:
        _require(manifest.get("collection_scope") == "event" and manifest.get("meeting_key") == meeting_key, "event_scope_mismatch")
        _require(manifest.get("publication_eligible") is True and manifest.get("source_quality_status") == "complete" and manifest.get("source_quality_reasons") == [], "event_quality_hold")
        _require(manifest.get("historical_archive_complete") is False and manifest.get("official_final_grid_verified") is False, "event_scientific_boundary_invalid")
        _require(manifest.get("event_custody_schema") == "openf1-event-byte-custody-v1", "event_custody_schema_missing")
    else:
        _require(manifest.get("collection_scope", "historical_season") == "historical_season", "season_scope_mismatch")
    return generated, history_rel, lanes


def _validate_target_sessions(
    path: Path,
    *,
    manifest: Mapping[str, Any],
    generated: dt.datetime,
    completed_only: bool,
) -> dict[str, SessionIdentity]:
    fields, rows = _csv_rows(path, "target_sessions_csv_invalid")
    required = {
        "session_key", "meeting_key", "session_name", "session_type", "date_start",
        "date_end", "circuit_short_name", "country_name", "location", "year",
        "_completed_session",
    }
    _require(required.issubset(fields), "target_sessions_identity_columns_missing")
    _require(len(rows) == manifest["target_session_count"], "target_session_count_mismatch")
    sessions: dict[str, SessionIdentity] = {}
    for row in rows:
        session = row["session_key"]
        meeting = row["meeting_key"]
        _require(POSITIVE_INTEGER.fullmatch(session or "") is not None, "target_session_key_invalid")
        _require(POSITIVE_INTEGER.fullmatch(meeting or "") is not None, "target_meeting_key_invalid")
        _require(session not in sessions, "target_session_key_duplicate")
        for field in ("session_name", "session_type", "circuit_short_name", "country_name", "location"):
            value = row[field]
            _require(type(value) is str and value.strip() == value and bool(value), "target_session_identity_missing")
        _require(row["year"] == str(manifest["season"]), "target_session_year_mismatch")
        start = _parse_utc(row["date_start"], "target_session_start_invalid")
        end = _parse_utc(row["date_end"], "target_session_end_invalid")
        _require(start <= end, "target_session_chronology_invalid")
        if completed_only:
            _require(row["_completed_session"] == "True", "target_session_not_completed")
            _require(end <= generated, "completed_target_session_after_generation")
        sessions[session] = SessionIdentity(
            meeting_key=meeting,
            session_name=row["session_name"],
            session_type=row["session_type"],
            date_start=_utc_text(start),
            date_end=_utc_text(end),
            circuit_short_name=row["circuit_short_name"],
            country_name=row["country_name"],
            location=row["location"],
            year=row["year"],
        )
    return sessions


def _validate_lane_files(
    root: Path,
    *,
    manifest: Mapping[str, Any],
    lanes: Mapping[str, Mapping[str, Any]],
    sessions: Mapping[str, SessionIdentity],
    generated: dt.datetime,
) -> None:
    fields, source_rows = _csv_rows(root / "combined_source_manifest.csv", "source_manifest_csv_invalid")
    _require(
        {"path", "lane", "rows", "sha256", "result", "reason"}.issubset(fields),
        "source_manifest_columns_missing",
    )
    _require(len(source_rows) == len(LANES), "source_manifest_lane_count_invalid")
    seen: set[str] = set()
    for record in source_rows:
        lane = record["lane"]
        _require(lane in LANES and lane not in seen, "source_manifest_lane_invalid")
        seen.add(lane)
        relative = f"data/openf1_{lane}.csv"
        _require(record["path"] == relative, "source_manifest_path_invalid")
        _require(re.fullmatch(r"[0-9a-f]{64}", record["sha256"] or "") is not None, "source_manifest_sha_invalid")
        _require(record["sha256"] == _sha256(root / relative), "source_manifest_sha_mismatch")
        _require(record["result"] == lanes[lane]["result"], "source_manifest_result_mismatch")
        _require(record["reason"] == lanes[lane]["reason"], "source_manifest_reason_mismatch")
        try:
            declared_rows = int(record["rows"])
        except (TypeError, ValueError) as exc:
            raise PublicationHold("source_manifest_rows_invalid") from exc
        _require(str(declared_rows) == record["rows"] and declared_rows == lanes[lane]["rows"], "source_manifest_rows_mismatch")
        lane_fields, lane_rows = _csv_rows(root / relative, "lane_csv_invalid")
        _require(len(lane_rows) == declared_rows, "lane_csv_row_count_mismatch")
        if lane_rows:
            _require(
                {"session_key", "meeting_key", "source_closure_retrieved_utc"}.issubset(lane_fields),
                "lane_identity_columns_missing",
            )
        for row in lane_rows:
            _require(
                row["session_key"] in sessions
                and sessions[row["session_key"]].meeting_key == row["meeting_key"],
                "lane_session_identity_mismatch",
            )
            observed = _parse_utc(row["source_closure_retrieved_utc"], "lane_source_clock_invalid")
            _require(observed <= generated + dt.timedelta(seconds=5), "lane_source_clock_after_generation")
    _require(seen == set(LANES), "source_manifest_lane_invalid")

    readiness = _read_json(root / "data_readiness.json", "data_readiness_invalid")
    _require(type(readiness) is dict, "data_readiness_invalid")
    readiness_time = _parse_utc(readiness.get("generated_utc"), "data_readiness_clock_invalid")
    _require(abs((readiness_time - generated).total_seconds()) <= 5, "data_readiness_clock_mismatch")
    _require(readiness.get("lanes") == manifest.get("lanes"), "data_readiness_lanes_mismatch")

    summary_fields, summary_rows = _csv_rows(root / "source_readiness_summary.csv", "readiness_summary_invalid")
    _require(
        {"lane", "rows", "result", "reason", "required_status", "heavy_endpoint"}.issubset(summary_fields),
        "readiness_summary_columns_missing",
    )
    _require(len(summary_rows) == len(LANES), "readiness_summary_lane_count_invalid")
    summary_lanes: set[str] = set()
    for row in summary_rows:
        lane = row["lane"]
        _require(
            lane in lanes and lane not in summary_lanes,
            "readiness_summary_lane_invalid",
        )
        summary_lanes.add(lane)
        expected = lanes[lane]
        _require(row["rows"] == str(expected["rows"]), "readiness_summary_rows_mismatch")
        _require(row["result"] == expected["result"], "readiness_summary_result_mismatch")
        _require(row["reason"] == expected["reason"], "readiness_summary_reason_mismatch")
        _require(row["required_status"] == expected["required_status"], "readiness_summary_status_mismatch")
        _require(row["heavy_endpoint"] == "False", "readiness_summary_heavy_mismatch")
    _require(summary_lanes == set(LANES), "readiness_summary_lane_invalid")

    request_fields, request_rows = _csv_rows(root / "request_log.csv", "request_log_invalid")
    _require("timestamp_utc" in request_fields, "request_log_clock_missing")
    _require(bool(request_rows) or manifest["target_session_count"] == 0, "request_log_unexpectedly_empty")
    for row in request_rows:
        observed = _parse_utc(row["timestamp_utc"], "request_log_clock_invalid")
        _require(observed <= generated + dt.timedelta(seconds=5), "request_log_clock_after_generation")


def _tree_digest(root: Path, names: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(names):
        raw = (root / name).read_bytes()
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(len(raw).to_bytes(8, "big") + raw)
    return digest.hexdigest()


def _latest_rel(meeting_key: str) -> PurePosixPath:
    if not meeting_key:
        return LATEST_REL
    _require(POSITIVE_INTEGER.fullmatch(meeting_key) is not None, "event_meeting_key_invalid")
    return PurePosixPath("latest/openf1_event_source_closure") / meeting_key


def _event_file_names(records: Any) -> frozenset[str]:
    _require(type(records) is list and bool(records), "event_raw_index_missing")
    names = set(EXPECTED_FILES) | {"raw_evidence.json"}
    for record in records:
        _require(type(record) is dict, "event_raw_record_invalid")
        digest = record.get("sha256")
        _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest), "event_raw_sha_invalid")
        _require(record.get("path") == f"raw/{digest}.json", "event_raw_path_invalid")
        names.add(record["path"])
    return frozenset(names)


def _event_files(root: Path) -> frozenset[str]:
    return _event_file_names(_read_json(root / "raw_evidence.json", "event_raw_index_invalid"))


def _validate_event_evidence(root, manifest, sessions, generated, expected_session_key):
    """Verify actual retained response bytes and their projection, not row presence.

    This establishes context custody only. GitHub scientific attestation and an
    authenticated executable model remain separate requirements.
    """
    from decimal import Decimal, InvalidOperation

    def norm(value):
        if value is None or value == "":
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True)
        try:
            return Decimal(str(value)).normalize()
        except InvalidOperation:
            return str(value)

    _require(bool(sessions), "event_sessions_empty")
    meeting = manifest["meeting_key"]
    _require(all(s.meeting_key == meeting for s in sessions.values()), "event_session_meeting_mismatch")
    if expected_session_key:
        _require(manifest.get("expected_session_key") == expected_session_key and expected_session_key in sessions,
                 "event_expected_session_mismatch")
    _require(manifest.get("expected_session_key") in sessions, "event_expected_session_missing")
    _require(manifest.get("raw_evidence_sha256") == _sha256(root / "raw_evidence.json"), "event_raw_index_sha_mismatch")
    records = _read_json(root / "raw_evidence.json", "event_raw_index_invalid")
    _event_file_names(records)
    observed_requests = {}
    source_rows = {lane: [] for lane in (*LANES, "sessions")}
    for record in records:
        origin = record.get("origin", {})
        _require(type(origin) is dict and origin.get("repository") == manifest.get("github_origin", {}).get("repository")
                 and re.fullmatch(r"[^/\s]+/[^/\s]+", str(origin.get("repository", "")))
                 and SHA_PATTERN.fullmatch(str(origin.get("head_sha", "")))
                 and POSITIVE_INTEGER.fullmatch(str(origin.get("run_id", "")))
                 and POSITIVE_INTEGER.fullmatch(str(origin.get("run_attempt", ""))), "event_original_run_invalid")
        observed = _parse_utc(record.get("response_observed_utc"), "event_raw_clock_invalid")
        _require(observed <= generated, "event_raw_clock_after_generation")
        raw = (root / record["path"]).read_bytes()
        _require(len(raw) == record.get("bytes") and hashlib.sha256(raw).hexdigest() == record["sha256"], "event_raw_bytes_mismatch")
        endpoint, params = record.get("endpoint"), record.get("params")
        _require(endpoint in source_rows and type(params) is dict, "event_request_identity_invalid")
        status = record.get("status_code")
        _require(type(status) is int and 100 <= status <= 599, "event_http_status_invalid")
        if status != 200:
            continue
        rows = _strict_json_bytes(raw, "event_raw_json_invalid")
        _require(type(rows) is list and all(type(row) is dict for row in rows), "event_raw_schema_invalid")
        for row in rows:
            if endpoint != "sessions":
                if "session_key" in params:
                    _require(str(row.get("session_key")) == str(params["session_key"]), "event_response_wrong_session")
                if "meeting_key" in params:
                    _require(str(row.get("meeting_key")) == str(params["meeting_key"]), "event_response_wrong_meeting")
        identity = (endpoint, json.dumps(params, sort_keys=True), record["response_observed_utc"], len(rows))
        _require(identity not in observed_requests or observed_requests[identity] == rows, "event_request_identity_collision")
        observed_requests[identity] = rows
    _, requests = _csv_rows(root / "request_log.csv", "event_request_log_invalid")
    for request in requests:
        if request.get("status") in {"pass", "zero_rows"}:
            identity = (request["endpoint"], json.dumps(json.loads(request["params_json"]), sort_keys=True), request["timestamp_utc"], int(request["rows"]))
            _require(identity in observed_requests, "event_request_original_bytes_missing")
            source_rows[request["endpoint"]].extend(observed_requests[identity])
    for endpoint in (*LANES, "sessions"):
        name = "data/target_sessions.csv" if endpoint == "sessions" else f"data/openf1_{endpoint}.csv"
        _, rows = _csv_rows(root / name, "event_projection_invalid")
        for row in rows:
            originals = [x for x in source_rows[endpoint] if str(x.get("session_key")) == row.get("session_key")]
            _require(any(all(norm(row.get(k)) == norm(v) for k, v in original.items()) for original in originals),
                     "event_projection_not_in_original_response:" + endpoint)
        if endpoint != "sessions":
            originals = [r for r in source_rows[endpoint] if str(r.get("session_key")) in sessions]
            keys = set().union(*(set(r) for r in originals)) if originals else set()
            _require(all(set(r) <= keys | {"source_closure_retrieved_utc"} for r in rows), "event_projection_extra_fields")
            keys = sorted(keys)
            normalized = lambda items: {tuple(norm(r.get(k)) for k in keys) for r in items}
            _require(normalized(rows) == normalized(originals), "event_projection_coverage_loss:" + endpoint)


def _snapshot_candidate(candidate: Candidate, destination: Path) -> Candidate:
    latest = destination / "latest"
    history = destination / "history"
    try:
        shutil.copytree(candidate.latest_root, latest, symlinks=False)
        shutil.copytree(candidate.history_root, history, symlinks=False)
    except OSError as exc:
        raise PublicationHold("candidate_snapshot_failed") from exc
    _require(
        _regular_tree_files(latest, "candidate_snapshot_unsafe") == candidate.files,
        "candidate_snapshot_file_set_invalid",
    )
    _require(
        _regular_tree_files(history, "candidate_snapshot_unsafe") == candidate.files,
        "candidate_snapshot_file_set_invalid",
    )
    _require(
        _tree_digest(latest, candidate.files) == candidate.tree_sha256,
        "candidate_snapshot_latest_mismatch",
    )
    _require(
        _tree_digest(history, candidate.files)
        == _tree_digest(candidate.history_root, candidate.files),
        "candidate_snapshot_history_mismatch",
    )
    return Candidate(
        latest_root=latest,
        history_root=history,
        history_rel=candidate.history_rel,
        manifest=candidate.manifest,
        generated_utc=candidate.generated_utc,
        tree_sha256=candidate.tree_sha256,
        sessions=candidate.sessions,
        latest_rel=candidate.latest_rel,
        files=candidate.files,
    )


def validate_candidate(
    repo_root: Path,
    *,
    expected_season: int,
    expected_completed_only: bool,
    now: dt.datetime,
    meeting_key: str = "",
    expected_session_key: str = "",
) -> Candidate:
    root = repo_root.resolve(strict=True)
    latest_rel = _latest_rel(meeting_key)
    latest = root.joinpath(*latest_rel.parts)
    expected_files = _event_files(latest) if meeting_key else EXPECTED_FILES
    files = _regular_tree_files(latest, "candidate_latest_tree_unsafe")
    _require(files == expected_files, "candidate_latest_file_set_invalid")
    manifest = _read_json(latest / "latest_manifest.json", "candidate_manifest_invalid")
    generated, history_rel, lanes = _validate_manifest(
        manifest,
        expected_season=expected_season,
        expected_completed_only=expected_completed_only,
        now=now,
        candidate=True,
        meeting_key=meeting_key,
    )
    history = root.joinpath(*history_rel.parts)
    _path_inside(root, history.resolve(strict=True), "candidate_history_outside_repository")
    history_files = _regular_tree_files(history, "candidate_history_tree_unsafe")
    _require(history_files == expected_files, "candidate_history_file_set_invalid")
    history_manifest = _read_json(history / "latest_manifest.json", "candidate_history_manifest_invalid")
    _require(history_manifest == manifest, "candidate_history_manifest_mismatch")

    sessions = _validate_target_sessions(
        latest / "data/target_sessions.csv",
        manifest=manifest,
        generated=generated,
        completed_only=expected_completed_only,
    )
    _validate_lane_files(
        latest,
        manifest=manifest,
        lanes=lanes,
        sessions=sessions,
        generated=generated,
    )
    if meeting_key:
        _validate_event_evidence(latest, manifest, sessions, generated, expected_session_key)
    _validate_zip(latest, expected_files)
    _validate_zip(history, expected_files)
    for name in expected_files - {ZIP_NAME} - {"data_readiness.json", ZIP_SHA_NAME}:
        _require((latest / name).read_bytes() == (history / name).read_bytes(), "candidate_history_bytes_mismatch")
    history_readiness = _read_json(history / "data_readiness.json", "candidate_history_readiness_invalid")
    _require(history_readiness.get("lanes") == manifest.get("lanes"), "candidate_history_readiness_mismatch")
    history_readiness_time = _parse_utc(
        history_readiness.get("generated_utc"), "candidate_history_readiness_clock_invalid"
    )
    _require(abs((history_readiness_time - generated).total_seconds()) <= 5, "candidate_history_readiness_clock_mismatch")
    return Candidate(
        latest_root=latest,
        history_root=history,
        history_rel=history_rel,
        manifest=manifest,
        generated_utc=generated,
        tree_sha256=_tree_digest(latest, expected_files),
        sessions=sessions,
        latest_rel=latest_rel,
        files=expected_files,
    )


def _git(
    root: Path,
    *args: str,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=text,
        )
    except OSError as exc:
        raise PublicationHold("git_command_unavailable") from exc
    if check and completed.returncode:
        raise PublicationHold(f"git_command_failed:{args[0] if args else 'unknown'}")
    return completed


def _validate_repo(repo_root: Path) -> Path:
    try:
        root = repo_root.resolve(strict=True)
    except OSError as exc:
        raise PublicationHold("repository_root_invalid") from exc
    top = _git(root, "rev-parse", "--show-toplevel").stdout.strip()
    _require(Path(top).resolve() == root, "repository_root_mismatch")
    return root


def _status_paths(root: Path) -> list[str]:
    raw = _git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        text=False,
    ).stdout
    entries = raw.split(b"\0")
    paths: list[str] = []
    index = 0
    while index < len(entries) and entries[index]:
        entry = entries[index]
        _require(len(entry) >= 4, "git_status_invalid")
        status_code = entry[:2]
        try:
            path = entry[3:].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PublicationHold("git_status_path_invalid") from exc
        paths.append(path)
        index += 1
        if b"R" in status_code or b"C" in status_code:
            _require(index < len(entries) and entries[index], "git_status_invalid")
            try:
                paths.append(entries[index].decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise PublicationHold("git_status_path_invalid") from exc
            index += 1
    return paths


def _is_under(path: str, root: PurePosixPath) -> bool:
    pure = PurePosixPath(path)
    return pure == root or root in pure.parents


def _validate_candidate_only_dirt(root: Path, candidate: Candidate) -> None:
    paths = _status_paths(root)
    _require(bool(paths), "candidate_worktree_has_no_changes")
    for path in paths:
        _require(
            _is_under(path, candidate.latest_rel) or _is_under(path, candidate.history_rel),
            f"unexpected_worktree_change:{path}",
        )


def _git_tree_names(root: Path, revision: str, relative: PurePosixPath) -> set[str]:
    raw = _git(
        root,
        "ls-tree",
        "-r",
        "-z",
        revision,
        "--",
        relative.as_posix(),
        text=False,
    ).stdout
    result: set[str] = set()
    prefix = relative.as_posix() + "/"
    for item in raw.split(b"\0"):
        if not item:
            continue
        try:
            metadata, raw_name = item.split(b"\t", 1)
            mode, object_type, object_sha = metadata.split(b" ", 2)
            name = raw_name.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise PublicationHold("remote_tree_path_invalid") from exc
        _require(
            mode == b"100644"
            and object_type == b"blob"
            and re.fullmatch(rb"[0-9a-f]{40}", object_sha) is not None,
            "remote_tree_mode_invalid",
        )
        _require(name.startswith(prefix), "remote_tree_path_invalid")
        result.add(name[len(prefix):])
    return result


def _git_blob(root: Path, revision: str, path: PurePosixPath) -> bytes:
    result = _git(root, "show", f"{revision}:{path.as_posix()}", check=False, text=False)
    _require(result.returncode == 0, "remote_blob_unreadable")
    return result.stdout


def _remote_latest(
    root: Path,
    revision: str,
    *,
    expected_season: int,
    expected_completed_only: bool,
    now: dt.datetime,
    meeting_key: str = "",
) -> RemoteLatest | None:
    latest_rel = _latest_rel(meeting_key)
    path = latest_rel / "latest_manifest.json"
    probe = _git(root, "cat-file", "-e", f"{revision}:{path.as_posix()}", check=False)
    if probe.returncode:
        names = _git_tree_names(root, revision, latest_rel)
        _require(not names, "remote_latest_manifest_missing_from_nonempty_tree")
        return None
    try:
        tracked = TRACKED_FILES
        if meeting_key:
            records = _strict_json_bytes(_git_blob(root, revision, latest_rel / "raw_evidence.json"), "remote_raw_index_invalid")
            tracked = _event_file_names(records) - {ZIP_NAME}
        _require(
            _git_tree_names(root, revision, latest_rel) == tracked,
            "remote_latest_file_set_invalid",
        )
        with tempfile.TemporaryDirectory(prefix="f1-source-closure-remote-") as directory:
            remote_root = Path(directory)
            for name in tracked:
                target = remote_root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(_git_blob(root, revision, latest_rel / name))

            manifest = _read_json(
                remote_root / "latest_manifest.json",
                "remote_manifest_invalid",
            )
            generated, _history, lanes = _validate_manifest(
                manifest,
                expected_season=expected_season,
                expected_completed_only=expected_completed_only,
                now=now,
                candidate=False,
                meeting_key=meeting_key,
            )
            sessions = _validate_target_sessions(
                remote_root / "data/target_sessions.csv",
                manifest=manifest,
                generated=generated,
                completed_only=expected_completed_only,
            )
            _validate_lane_files(
                remote_root,
                manifest=manifest,
                lanes=lanes,
                sessions=sessions,
                generated=generated,
            )
            if meeting_key:
                _validate_event_evidence(remote_root, manifest, sessions, generated, "")
            return RemoteLatest(
                manifest=manifest,
                generated_utc=generated,
                tracked_tree_sha256=_tree_digest(remote_root, tracked),
                sessions=sessions,
            )
    except PublicationHold as exc:
        raise PublicationHold(f"remote_latest_invalid:{exc}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise PublicationHold("remote_latest_invalid:materialization_failed") from exc


def _validate_completed_session_coverage(
    remote_sessions: Mapping[str, SessionIdentity],
    candidate_sessions: Mapping[str, SessionIdentity],
) -> None:
    for session_key, remote_identity in remote_sessions.items():
        _require(
            session_key in candidate_sessions,
            f"candidate_completed_session_coverage_regression:{session_key}",
        )
        _require(
            candidate_sessions[session_key] == remote_identity,
            f"candidate_existing_session_identity_changed:{session_key}",
        )


def _tree_matches_candidate(
    root: Path,
    revision: str,
    relative: PurePosixPath,
    candidate_root: Path,
    files=EXPECTED_FILES,
) -> bool:
    tracked = files - {ZIP_NAME}
    if _git_tree_names(root, revision, relative) != tracked:
        return False
    for name in tracked:
        if _git_blob(root, revision, relative / name) != (candidate_root / name).read_bytes():
            return False
    return True


def _copy_tracked_tree(source: Path, destination: Path, files=EXPECTED_FILES) -> None:
    _require(not destination.is_symlink(), "publication_destination_symlink")
    if destination.exists():
        _require(destination.is_dir(), "publication_destination_not_directory")
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name in files - {ZIP_NAME}:
        source_file = source / name
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target, follow_symlinks=False)


def _cleanup_worktree(repo_root: Path, worktree: Path) -> None:
    if worktree.exists():
        _git(repo_root, "worktree", "remove", str(worktree), check=False)


def _base_audit(github_run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "HOLD",
        "reason": None,
        "github_run_id": github_run_id,
        "artifact_upload_precondition": "UNVERIFIED_WORKFLOW_STEP_ASSERTION",
        "candidate": None,
        "remote": None,
        "publication": {
            "commit_sha": None,
            "latest_decision": None,
            "push_attempts": 0,
            "push_succeeded": False,
            "force_push_used": False,
            "rebase_used": False,
            "retry_used": False,
            "provider_requests": 0,
        },
    }


def run_guard(
    *,
    repo_root: Path,
    remote: str,
    branch: str,
    expected_season: int,
    expected_completed_only: bool,
    github_run_id: str,
    artifact_uploaded_for_run: str,
    clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
    before_push: Callable[[], None] | None = None,
    meeting_key: str = "",
    expected_session_key: str = "",
    expected_origin: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    audit = _base_audit(github_run_id)
    worktree: Path | None = None
    worktree_parent: Path | None = None
    candidate_temp: tempfile.TemporaryDirectory[str] | None = None
    try:
        _require(POSITIVE_INTEGER.fullmatch(github_run_id or "") is not None, "github_run_id_invalid")
        _require(artifact_uploaded_for_run == github_run_id, "artifact_upload_precondition_invalid")
        audit["artifact_upload_precondition"] = "ASSERTED_SUCCESS_BEFORE_GUARD"
        _require(type(remote) is str and re.fullmatch(r"[A-Za-z0-9._-]+", remote or ""), "remote_name_invalid")
        _require(type(branch) is str and BRANCH_PATTERN.fullmatch(branch or "") is not None, "branch_name_invalid")
        _require(type(expected_season) is int and 1950 <= expected_season <= 3000, "expected_season_invalid")
        _require(type(expected_completed_only) is bool, "expected_completed_only_invalid")
        now = _clock_utc(clock)
        root = _validate_repo(repo_root)
        candidate = validate_candidate(
            root,
            expected_season=expected_season,
            expected_completed_only=expected_completed_only,
            now=now,
            meeting_key=meeting_key,
            expected_session_key=expected_session_key,
        )
        if meeting_key:
            _require(bool(expected_session_key), "event_expected_session_required")
            _require(candidate.manifest.get("github_origin") == expected_origin and expected_origin.get("run_id") == github_run_id, "event_origin_mismatch")
        audit["candidate"] = {
            "generated_utc": _utc_text(candidate.generated_utc),
            "history_path": candidate.history_rel.as_posix(),
            "tree_sha256": candidate.tree_sha256,
            "season": expected_season,
            "completed_only": expected_completed_only,
            "target_session_count": len(candidate.sessions),
            "source_artifact_or_custody_success_claimed": False,
        }
        _validate_candidate_only_dirt(root, candidate)
        candidate_temp = tempfile.TemporaryDirectory(
            prefix="f1-source-closure-candidate-",
            dir=os.environ.get("RUNNER_TEMP") or None,
        )
        candidate = _snapshot_candidate(candidate, Path(candidate_temp.name))

        remote_ref = f"refs/remotes/{remote}/{branch}"
        fetch = _git(
            root,
            "fetch",
            "--no-tags",
            remote,
            f"refs/heads/{branch}:{remote_ref}",
            check=False,
        )
        _require(fetch.returncode == 0, "remote_fetch_failed")
        remote_sha = _git(root, "rev-parse", "--verify", remote_ref).stdout.strip()
        _require(SHA_PATTERN.fullmatch(remote_sha or "") is not None, "remote_head_invalid")
        remote_latest = _remote_latest(
            root,
            remote_sha,
            expected_season=expected_season,
            expected_completed_only=expected_completed_only,
            now=now,
            meeting_key=meeting_key,
        )
        audit["remote"] = {
            "head_sha": remote_sha,
            "latest_generated_utc": (
                _utc_text(remote_latest.generated_utc) if remote_latest else None
            ),
            "latest_history_path": (
                remote_latest.manifest.get("history_path")
                if remote_latest is not None
                else None
            ),
            "target_session_count": (
                len(remote_latest.sessions) if remote_latest is not None else None
            ),
            "tracked_tree_sha256": (
                remote_latest.tracked_tree_sha256 if remote_latest is not None else None
            ),
            "tracked_data_integrity_validated": remote_latest is not None,
            "zip_integrity_validated": False,
        }

        if remote_latest is None or candidate.generated_utc > remote_latest.generated_utc:
            if remote_latest is not None:
                _validate_completed_session_coverage(
                    remote_latest.sessions,
                    candidate.sessions,
                )
            latest_decision = "PUBLISH_CANDIDATE_LATEST"
            publish_latest = True
        elif candidate.generated_utc < remote_latest.generated_utc:
            latest_decision = "PRESERVE_NEWER_REMOTE_LATEST"
            publish_latest = False
        else:
            _require(
                _tree_matches_candidate(root, remote_sha, candidate.latest_rel, candidate.latest_root, candidate.files),
                "equal_generation_clock_with_different_latest_bytes",
            )
            latest_decision = "IDENTICAL_REMOTE_LATEST"
            publish_latest = False
        audit["publication"]["latest_decision"] = latest_decision

        history_names = _git_tree_names(root, remote_sha, candidate.history_rel)
        if history_names:
            _require(
                _tree_matches_candidate(
                    root,
                    remote_sha,
                    candidate.history_rel,
                    candidate.history_root,
                    candidate.files,
                ),
                "immutable_history_path_collision",
            )
            publish_history = False
        else:
            publish_history = True

        worktree_parent = Path(
            tempfile.mkdtemp(
                prefix="f1-source-closure-publish-",
                dir=os.environ.get("RUNNER_TEMP") or None,
            )
        )
        worktree = worktree_parent / "worktree"
        _git(root, "worktree", "add", "--detach", str(worktree), remote_sha)
        if publish_latest:
            _copy_tracked_tree(candidate.latest_root, worktree.joinpath(*candidate.latest_rel.parts), candidate.files)
        if publish_history:
            history_destination = worktree.joinpath(*candidate.history_rel.parts)
            _require(not history_destination.exists() and not history_destination.is_symlink(), "immutable_history_path_collision")
            _copy_tracked_tree(candidate.history_root, history_destination, candidate.files)

        stage_paths: list[str] = []
        if publish_latest:
            stage_paths.append(candidate.latest_rel.as_posix())
        if publish_history:
            stage_paths.append(candidate.history_rel.as_posix())
        if stage_paths:
            _git(worktree, "add", "-A", "--", *stage_paths)
        staged_raw = _git(
            worktree,
            "diff",
            "--cached",
            "--name-only",
            "-z",
            text=False,
        ).stdout
        staged = {
            item.decode("utf-8")
            for item in staged_raw.split(b"\0")
            if item
        }
        for path in staged:
            _require(
                (publish_latest and _is_under(path, candidate.latest_rel))
                or (publish_history and _is_under(path, candidate.history_rel)),
                f"staged_path_outside_publication_scope:{path}",
            )
        if not publish_latest:
            _require(
                not any(_is_under(path, candidate.latest_rel) for path in staged),
                "non_authoritative_latest_was_staged",
            )

        if not staged:
            audit["status"] = "NO_CHANGES"
            audit["reason"] = "candidate_already_published"
            return audit

        _git(
            worktree,
            "commit",
            "-m",
            f"Update OpenF1 lightweight source closure artifacts (run {github_run_id})",
        )
        commit_sha = _git(worktree, "rev-parse", "HEAD").stdout.strip()
        _require(SHA_PATTERN.fullmatch(commit_sha or "") is not None, "publication_commit_invalid")
        audit["publication"]["commit_sha"] = commit_sha
        if before_push is not None:
            before_push()
        audit["publication"]["push_attempts"] = 1
        pushed = _git(
            worktree,
            "push",
            remote,
            f"HEAD:refs/heads/{branch}",
            check=False,
        )
        _require(pushed.returncode == 0, "push_rejected_after_freshness_decision")
        audit["publication"]["push_succeeded"] = True
        audit["status"] = "PUBLISHED_LATEST_AND_HISTORY" if publish_latest else "PUBLISHED_HISTORY_ONLY"
        audit["reason"] = None
        return audit
    except PublicationHold as exc:
        audit["status"] = "HOLD"
        audit["reason"] = str(exc)
        return audit
    except Exception as exc:  # pragma: no cover - final fail-closed boundary
        audit["status"] = "HOLD"
        audit["reason"] = f"unexpected_guard_exception:{type(exc).__name__}"
        return audit
    finally:
        if worktree is not None:
            try:
                _cleanup_worktree(Path(repo_root).resolve(), worktree)
            except Exception:
                pass
        if worktree_parent is not None:
            try:
                worktree_parent.rmdir()
            except Exception:
                pass
        if candidate_temp is not None:
            try:
                candidate_temp.cleanup()
            except Exception:
                pass


def _completed_only(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--expected-season", type=int, required=True)
    parser.add_argument("--expected-completed-only", type=_completed_only, required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--artifact-uploaded-for-run", required=True)
    parser.add_argument("--meeting-key", default="")
    parser.add_argument("--expected-session-key", default="")
    parser.add_argument("--github-repository", default="")
    parser.add_argument("--github-sha", default="")
    parser.add_argument("--github-run-attempt", default="")
    args = parser.parse_args(argv)
    result = run_guard(
        repo_root=Path(args.repo_root),
        remote=args.remote,
        branch=args.branch,
        expected_season=args.expected_season,
        expected_completed_only=args.expected_completed_only,
        github_run_id=args.github_run_id,
        artifact_uploaded_for_run=args.artifact_uploaded_for_run,
        meeting_key=args.meeting_key,
        expected_session_key=args.expected_session_key,
        expected_origin=dict(repository=args.github_repository, head_sha=args.github_sha,
                             run_id=args.github_run_id, run_attempt=args.github_run_attempt),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in {
        "PUBLISHED_LATEST_AND_HISTORY",
        "PUBLISHED_HISTORY_ONLY",
        "NO_CHANGES",
    } else HOLD_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
