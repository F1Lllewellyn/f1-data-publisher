"""Pure in-memory intake of three OpenF1 GitHub Actions artifact ZIPs.

Archive SHA matching is only a caller-claimed byte binding.  It does not prove
GitHub custody, run identity, source authenticity, or observation time.  This
module performs no network, filesystem, clock, workflow, producer, or model
operation and delegates all source/session/temporal science to unchanged K4R26.
"""
import hashlib
import io
import json
import re
import stat
import zipfile

import dr002_openf1_drivers_producer_adapter_v1 as drivers_adapter
import dr002_openf1_historical_rest_capture_v1 as capture_contract
import dr002_openf1_starting_grid_producer_adapter_v1 as grid_adapter
import dr002_openf1_three_source_precutoff_candidate_v1 as precutoff


SCHEMA_VERSION = "dr002-openf1-three-source-actions-artifact-intake-v1"
VALIDATED = "OPENF1_THREE_SOURCE_ACTIONS_ARTIFACT_INTAKE_CANDIDATE_UNAUTHENTICATED"
CLASSIFICATION = "READ_ONLY_PRIVATE_ARTIFACT_INTAKE_NON_OPERATIONAL_CANDIDATE_ONLY"
HOLD = "HOLD"
HEX64 = re.compile(r"[0-9a-f]{64}")
POSITIVE_DECIMAL = re.compile(r"[1-9][0-9]*")
SAFE_REASON = re.compile(r"[A-Za-z0-9_.:-]{1,200}")

MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 24 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
READ_CHUNK_BYTES = 64 * 1024
ALLOWED_COMPRESSION = frozenset((zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED))

COMMON_MEMBERS = frozenset({
    "source_capture_receipt.json",
    "shadow_manifest.json",
    "shadow_report.md",
    "historical_rest_capture_assessment.json",
})
EXPECTED_MEMBERS = {
    "weather": COMMON_MEMBERS | {"weather.response.json"},
    "drivers": COMMON_MEMBERS | {"drivers.response.json"},
    "starting_grid": COMMON_MEMBERS | {
        "sessions.response.json", "starting_grid.response.json",
    },
}
RAW_MEMBER = {
    "weather": "weather.response.json",
    "drivers": "drivers.response.json",
    "starting_grid": "starting_grid.response.json",
}
FALSE_FLAGS = (
    "source_capture_externally_attested",
    "github_run_identity_verified",
    "openf1_provider_authenticated",
    "historical_availability_proven",
    "official_fia_final_grid_authenticated",
    "production_authenticated",
    "verified_receipt_bindings_created",
    "producer_execution_attempted",
    "forecast_generated",
    "forecast_locked",
    "blind_validation_eligible",
    "dr002_activated",
    "promotion_allowed",
    "stable_engine_execution_proven",
)


class ArtifactIntakeError(ValueError):
    """Any archive or sidecar failure makes the complete intake HOLD."""


def _require(condition, reason):
    if not condition:
        raise ArtifactIntakeError(reason)


def _sha256(data):
    _require(type(data) is bytes, "hash_input_not_bytes")
    return hashlib.sha256(data).hexdigest()


def _bounded_reason(value, fallback="artifact_intake_hold"):
    if type(value) is str and SAFE_REASON.fullmatch(value):
        return value
    return fallback


def _hold(reasons):
    values = reasons if type(reasons) is list else [reasons]
    bounded = [_bounded_reason(value) for value in values[:8]] or [
        "artifact_intake_hold"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": HOLD,
        "reason_codes": bounded,
        **{flag: False for flag in FALSE_FLAGS},
    }


def _strict_json_bytes(data, *, reason):
    _require(type(data) is bytes and bool(data), reason)

    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value, reason + "_duplicate_key")
            value[key] = item
        return value

    def reject_constant(_value):
        raise ArtifactIntakeError(reason + "_nonfinite")

    try:
        value = json.loads(
            data, object_pairs_hook=pairs, parse_constant=reject_constant
        )
    except ArtifactIntakeError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise ArtifactIntakeError(reason) from exc
    _require(type(value) is dict, reason)
    return value


def _claimed_id(value, reason):
    if value is None:
        return None
    _require(type(value) is str and POSITIVE_DECIMAL.fullmatch(value), reason)
    return value


def _archive_digest(value, reason):
    _require(type(value) is str and HEX64.fullmatch(value), reason)
    return value


def _safe_member_name(name, role):
    reason = role + "_archive_member_name_unsafe"
    _require(type(name) is str and bool(name), reason)
    _require("\\" not in name and "%" not in name, reason)
    _require(not name.startswith("/") and "/" not in name, reason)
    _require(name not in {".", ".."} and ":" not in name, reason)


def _regular_member(info, role):
    _safe_member_name(info.filename, role)
    _require(not info.is_dir() and not info.filename.endswith("/"),
             role + "_archive_directory_forbidden")
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    _require(file_type in (0, stat.S_IFREG),
             role + "_archive_special_entry_forbidden")
    _require(not (info.flag_bits & 0x1), role + "_archive_encrypted")
    _require(info.compress_type in ALLOWED_COMPRESSION,
             role + "_archive_compression_unsupported")
    _require(0 <= info.compress_size <= MAX_MEMBER_BYTES,
             role + "_archive_compressed_member_too_large")
    _require(0 <= info.file_size <= MAX_MEMBER_BYTES,
             role + "_archive_member_too_large")
    if info.file_size:
        _require(info.compress_size > 0, role + "_archive_invalid_size_ratio")
        _require(info.file_size <= info.compress_size * MAX_COMPRESSION_RATIO,
                 role + "_archive_compression_ratio_exceeded")


def _read_member(archive, info, role):
    chunks = []
    total = 0
    try:
        with archive.open(info, "r") as source:
            while True:
                chunk = source.read(READ_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                _require(total <= MAX_MEMBER_BYTES,
                         role + "_archive_member_too_large")
                chunks.append(chunk)
    except RuntimeError as exc:
        raise ArtifactIntakeError(role + "_archive_encrypted") from exc
    except (zipfile.BadZipFile, EOFError, OSError, ValueError) as exc:
        raise ArtifactIntakeError(role + "_archive_crc_or_read_failure") from exc
    data = b"".join(chunks)
    _require(len(data) == info.file_size,
             role + "_archive_member_size_mismatch")
    return data


def _strict_zip_container(data, archive, role):
    reason = role + "_archive_container_ambiguous"
    offset = data.rfind(b"PK\x05\x06", max(0, len(data) - 65557))
    _require(offset >= 0 and offset + 22 <= len(data), reason)
    disk_number = int.from_bytes(data[offset + 4:offset + 6], "little")
    central_disk = int.from_bytes(data[offset + 6:offset + 8], "little")
    disk_entries = int.from_bytes(data[offset + 8:offset + 10], "little")
    total_entries = int.from_bytes(data[offset + 10:offset + 12], "little")
    central_size = int.from_bytes(data[offset + 12:offset + 16], "little")
    central_offset = int.from_bytes(data[offset + 16:offset + 20], "little")
    comment_size = int.from_bytes(data[offset + 20:offset + 22], "little")
    _require(
        disk_number == central_disk == 0
        and disk_entries == total_entries == len(archive.infolist())
        and central_offset + central_size == offset
        and comment_size == 0
        and offset + 22 == len(data)
        and archive.comment == b"",
        reason,
    )
    infos = archive.infolist()
    _require(bool(infos) and min(info.header_offset for info in infos) == 0, reason)


def _preflight_archive(data, expected_digest, role):
    _require(type(data) is bytes and bool(data), role + "_archive_not_nonempty_bytes")
    _require(len(data) <= MAX_ARCHIVE_BYTES, role + "_archive_too_large")
    digest = _archive_digest(expected_digest, role + "_archive_sha256_malformed")
    _require(_sha256(data) == digest, role + "_archive_sha256_mismatch")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data), "r")
    except (zipfile.BadZipFile, EOFError, OSError, ValueError) as exc:
        raise ArtifactIntakeError(role + "_archive_malformed") from exc
    try:
        _strict_zip_container(data, archive, role)
        infos = archive.infolist()
        expected = EXPECTED_MEMBERS[role]
        names = [info.filename for info in infos]
        _require(len(set(names)) == len(names), role + "_archive_duplicate_member")
        _require(len(infos) == len(expected), role + "_archive_member_count_mismatch")
        for info in infos:
            _regular_member(info, role)
        _require(set(names) == expected, role + "_archive_member_set_mismatch")
        _require(sum(info.file_size for info in infos)
                 <= MAX_TOTAL_UNCOMPRESSED_BYTES,
                 role + "_archive_total_size_exceeded")
        members = {
            info.filename: _read_member(archive, info, role) for info in infos
        }
        _require(all(bool(value) for value in members.values()),
                 role + "_archive_empty_member")
        return members, digest
    finally:
        archive.close()


def _sidecar_preflight(members, *, role, event_id, meeting_id, session_id):
    raw = members[RAW_MEMBER[role]]
    receipt_bytes = members["source_capture_receipt.json"]
    assessment = _strict_json_bytes(
        members["historical_rest_capture_assessment.json"],
        reason=role + "_assessment_malformed",
    )
    manifest = _strict_json_bytes(
        members["shadow_manifest.json"],
        reason=role + "_shadow_manifest_malformed",
    )
    receipt = _strict_json_bytes(
        receipt_bytes, reason=role + "_source_receipt_malformed"
    )
    report = members["shadow_report.md"]
    _require(report.startswith(b"# DR-002 "), role + "_shadow_report_malformed")

    raw_sha = _sha256(raw)
    receipt_sha = _sha256(receipt_bytes)
    _require(assessment.get("status") == capture_contract.VALIDATED,
             role + "_assessment_not_validated")
    _require(assessment.get("raw_response_sha256") == raw_sha,
             role + "_assessment_raw_hash_mismatch")
    _require(assessment.get("receipt_sha256") == receipt_sha,
             role + "_assessment_receipt_hash_mismatch")
    _require(type(assessment.get("canonical_request_uri")) is str,
             role + "_assessment_source_uri_missing")

    required_manifest = {
        "status": capture_contract.VALIDATED,
        "k4r1_status": capture_contract.VALIDATED,
        "event_id": event_id,
        "meeting_id": meeting_id,
        "session_id": session_id,
        "raw_response_sha256": raw_sha,
        "receipt_sha256": receipt_sha,
        "receipt_type": "source_capture",
        "verified_receipt_bindings_created": False,
        "latest_or_history_written": False,
        "repository_mutation_performed": False,
        "dr002_activated": False,
        "promotion_allowed": False,
    }
    for field, expected in required_manifest.items():
        _require(manifest.get(field) == expected,
                 role + "_shadow_manifest_mismatch:" + field)
    _require(manifest.get("canonical_request_uri")
             == assessment.get("canonical_request_uri"),
             role + "_sidecar_source_uri_mismatch")
    _require(receipt.get("receipt_created_utc")
             == manifest.get("receipt_created_utc"),
             role + "_sidecar_receipt_created_mismatch")
    payload = receipt.get("payload")
    _require(type(payload) is dict, role + "_source_receipt_payload_malformed")
    _require(payload.get("source_sha256") == raw_sha,
             role + "_source_receipt_raw_hash_mismatch")
    _require(payload.get("source_uri") == manifest.get("canonical_request_uri"),
             role + "_source_receipt_uri_mismatch")
    _require(payload.get("first_observed_utc") == manifest.get("first_observed_utc")
             and payload.get("ingested_utc") == manifest.get("ingested_utc"),
             role + "_sidecar_capture_time_mismatch")

    if role == "drivers":
        _require(manifest.get("selected_endpoint") == "drivers"
                 and manifest.get("raw_response_filename") == RAW_MEMBER[role]
                 and manifest.get("k4r6_status") == drivers_adapter.VALIDATED,
                 "drivers_shadow_manifest_endpoint_mismatch")
    elif role == "starting_grid":
        _require(manifest.get("selected_endpoint") == "starting_grid"
                 and manifest.get("raw_response_filename") == RAW_MEMBER[role]
                 and manifest.get("session_discovery_filename")
                 == "sessions.response.json"
                 and manifest.get("k4r14_status") == grid_adapter.VALIDATED,
                 "starting_grid_shadow_manifest_endpoint_mismatch")
        for field in (
            "session_discovery_request_attempted",
            "starting_grid_request_attempted",
        ):
            _require(manifest.get(field) is True,
                     "starting_grid_shadow_manifest_mismatch:" + field)
        for field in (
            "session_discovery_http_status_code",
            "starting_grid_http_status_code",
        ):
            _require(type(manifest.get(field)) is int
                     and manifest.get(field) == 200,
                     "starting_grid_shadow_manifest_mismatch:" + field)
    else:
        _require(manifest.get("selected_endpoint") in (None, "weather"),
                 "weather_shadow_manifest_endpoint_mismatch")
    return {
        "raw": raw,
        "receipt": receipt_bytes,
        "manifest": members["shadow_manifest.json"],
        "sessions": members.get("sessions.response.json"),
    }


def assess_openf1_three_source_actions_artifact_intake(
    *,
    weather_artifact_zip_bytes,
    weather_archive_sha256,
    drivers_artifact_zip_bytes,
    drivers_archive_sha256,
    grid_artifact_zip_bytes,
    grid_archive_sha256,
    event_id,
    meeting_id,
    practice_session_id,
    qualifying_source_session_id,
    target_race_session_id,
    forecast_cutoff_utc,
    weather_claimed_run_id=None,
    weather_claimed_artifact_id=None,
    drivers_claimed_run_id=None,
    drivers_claimed_artifact_id=None,
    grid_claimed_run_id=None,
    grid_claimed_artifact_id=None,
):
    """Validate three private ZIP byte strings and invoke K4R26 exactly once."""
    try:
        claimed = {
            "weather": {
                "claimed_run_id": _claimed_id(
                    weather_claimed_run_id, "weather_claimed_run_id_malformed"
                ),
                "claimed_artifact_id": _claimed_id(
                    weather_claimed_artifact_id,
                    "weather_claimed_artifact_id_malformed",
                ),
            },
            "drivers": {
                "claimed_run_id": _claimed_id(
                    drivers_claimed_run_id, "drivers_claimed_run_id_malformed"
                ),
                "claimed_artifact_id": _claimed_id(
                    drivers_claimed_artifact_id,
                    "drivers_claimed_artifact_id_malformed",
                ),
            },
            "starting_grid": {
                "claimed_run_id": _claimed_id(
                    grid_claimed_run_id, "grid_claimed_run_id_malformed"
                ),
                "claimed_artifact_id": _claimed_id(
                    grid_claimed_artifact_id,
                    "grid_claimed_artifact_id_malformed",
                ),
            },
        }
        archives = {}
        for role, data, digest in (
            ("weather", weather_artifact_zip_bytes, weather_archive_sha256),
            ("drivers", drivers_artifact_zip_bytes, drivers_archive_sha256),
            ("starting_grid", grid_artifact_zip_bytes, grid_archive_sha256),
        ):
            members, checked_digest = _preflight_archive(data, digest, role)
            archives[role] = {
                "members": members, "archive_sha256": checked_digest,
            }

        weather = _sidecar_preflight(
            archives["weather"]["members"],
            role="weather",
            event_id=event_id,
            meeting_id=meeting_id,
            session_id=practice_session_id,
        )
        drivers = _sidecar_preflight(
            archives["drivers"]["members"],
            role="drivers",
            event_id=event_id,
            meeting_id=meeting_id,
            session_id=practice_session_id,
        )
        grid = _sidecar_preflight(
            archives["starting_grid"]["members"],
            role="starting_grid",
            event_id=event_id,
            meeting_id=meeting_id,
            session_id=qualifying_source_session_id,
        )
        _require(type(grid["sessions"]) is bytes and bool(grid["sessions"]),
                 "starting_grid_sessions_bytes_missing")

        candidate = precutoff.assess_openf1_three_source_precutoff_candidate(
            weather_source_capture_receipt_bytes=weather["receipt"],
            raw_weather_response_bytes=weather["raw"],
            drivers_source_capture_receipt_bytes=drivers["receipt"],
            raw_drivers_response_bytes=drivers["raw"],
            starting_grid_source_capture_receipt_bytes=grid["receipt"],
            raw_starting_grid_response_bytes=grid["raw"],
            sessions_response_bytes=grid["sessions"],
            grid_shadow_manifest_bytes=grid["manifest"],
            event_id=event_id,
            meeting_id=meeting_id,
            practice_session_id=practice_session_id,
            qualifying_source_session_id=qualifying_source_session_id,
            target_race_session_id=target_race_session_id,
            forecast_cutoff_utc=forecast_cutoff_utc,
        )
        _require(type(candidate) is dict, "k4r26_result_malformed")
        if candidate.get("status") != precutoff.VALIDATED:
            reasons = candidate.get("reason_codes")
            values = reasons if type(reasons) is list and reasons else ["unspecified"]
            return _hold([
                "k4r26_hold:" + _bounded_reason(value, "underlying_candidate_hold")
                for value in values
            ])
        for flag in precutoff.FALSE_FLAGS:
            _require(candidate.get(flag) is False,
                     "k4r26_forbidden_claim:" + flag)

        archive_bindings = {}
        for role in ("weather", "drivers", "starting_grid"):
            archive_bindings[role] = {
                "archive_sha256": archives[role]["archive_sha256"],
                **claimed[role],
                "claimed_identity_status": "UNVERIFIED_CALLER_ASSERTION",
                "archive_sha256_matches_caller_claim": True,
                "github_identity_verified": False,
                "archive_digest_is_github_custody_attestation": False,
            }
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": VALIDATED,
            "reason_codes": [],
            "classification": CLASSIFICATION,
            "archive_bindings": archive_bindings,
            "original_source_to_session_provenance": {
                "weather": {
                    "session_id": practice_session_id,
                    "session_kind": "Practice 2",
                },
                "drivers": {
                    "session_id": practice_session_id,
                    "session_kind": "Practice 2",
                },
                "starting_grid": {
                    "session_id": qualifying_source_session_id,
                    "session_kind": "Qualifying",
                    "target_race_session_id": target_race_session_id,
                    "target_session_kind": "Race",
                },
            },
            "candidate_result": candidate,
            "candidate_content_is_in_memory_only": True,
            **{flag: False for flag in FALSE_FLAGS},
        }
        return result
    except (
        ArtifactIntakeError,
        TypeError,
        ValueError,
        KeyError,
        UnicodeDecodeError,
        OverflowError,
        AttributeError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        return _hold(str(exc) or type(exc).__name__)
