"""Fail-closed custody manifest for one existing manual OpenF1 shadow artifact.

This helper performs local structural and exact-byte validation only.  It does
not request source data, authenticate OpenF1, verify a Sigstore signature or
transparency log, create a scientific receipt, run a producer/model, or confer
production authority.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat

import dr002_openf1_drivers_producer_adapter_v1 as drivers_adapter
import dr002_openf1_historical_rest_capture_v1 as capture_contract
import dr002_openf1_starting_grid_producer_adapter_v1 as grid_adapter
from verify_forecast_integrity_receipts_v1 import (
    ReceiptError,
    canonical_json_bytes,
    sha256,
    validate_receipt_envelope,
    verify_temporal_bindings,
)


SCHEMA_VERSION = "dr002-openf1-manual-shadow-custody-manifest-v1"
METADATA_SCHEMA_VERSION = (
    "dr002-openf1-manual-shadow-github-attestation-metadata-v1"
)
STATUS = "OPENF1_MANUAL_SHADOW_CUSTODY_MANIFEST_PREPARED_UNATTESTED"
CLASSIFICATION = "CUSTODY_ONLY_NON_OPERATIONAL_SOURCE_EVIDENCE_INVENTORY"
WORKFLOW_NAME = "F1 OpenF1 Lightweight Source Closure"
WORKFLOW_PATH = ".github/workflows/f1-openf1-lightweight-source-closure.yml"
MAIN_REF = "refs/heads/main"
API_BASE = "https://api.openf1.org/v1"
ATTESTATION_ACTION = (
    "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
)
BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
HEX40 = re.compile(r"[0-9a-f]{40}")
POSITIVE_DECIMAL = re.compile(r"[1-9][0-9]*")

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
INPUT_EVIDENCE_ROLE = {
    "weather": "PRACTICE_2_WEATHER_SOURCE_CAPTURE",
    "drivers": "PRACTICE_2_DRIVERS_SOURCE_CAPTURE",
    "starting_grid": "QUALIFYING_STARTING_GRID_SOURCE_CAPTURE_FOR_RACE_TARGET",
}
MEMBER_ROLES = {
    "weather.response.json": "original_source_response",
    "drivers.response.json": "original_source_response",
    "starting_grid.response.json": "original_source_response",
    "sessions.response.json": "original_session_discovery_response",
    "source_capture_receipt.json": "canonical_source_capture_receipt",
    "shadow_manifest.json": "publisher_shadow_manifest",
    "shadow_report.md": "publisher_shadow_report",
    "historical_rest_capture_assessment.json": "sanitized_capture_assessment",
}
FALSE_FLAGS = (
    "source_publisher_authenticated",
    "first_observed_clock_authenticated",
    "historical_availability_proven",
    "source_capture_externally_attested_as_first_observed",
    "verified_receipt_bindings_created",
    "official_fia_final_grid_authenticated",
    "revision_completeness_proven",
    "production_authenticated",
    "blind_validation_eligible",
    "producer_execution_attempted",
    "forecast_generated",
    "forecast_locked",
    "stable_engine_execution_proven",
    "dr002_activated",
    "promotion_allowed",
)
LOCAL_ONLY_FALSE_FLAGS = (
    "cryptographic_signature_verified",
    "trusted_tlog_verified",
    "signed_issuer_verified",
    "signed_repository_verified",
    "signed_ref_verified",
    "signed_workflow_verified",
)


class CustodyHold(ValueError):
    """A failed invariant must stop the job before a custody attestation."""


def _require(condition, reason):
    if not condition:
        raise CustodyHold(reason)


def _strict_json_bytes(data, *, expected_type, reason):
    _require(type(data) is bytes and bool(data), reason)

    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value, reason + "_duplicate_key")
            value[key] = item
        return value

    def reject_constant(_value):
        raise CustodyHold(reason + "_nonfinite")

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except CustodyHold:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise CustodyHold(reason) from exc
    _require(type(value) is expected_type, reason)
    return value


def _positive_decimal(value, reason):
    _require(type(value) is str and POSITIVE_DECIMAL.fullmatch(value), reason)
    return value


def _row_decimal(value, reason):
    _require(type(value) in (str, int) and type(value) is not bool, reason)
    text = str(value)
    _require(POSITIVE_DECIMAL.fullmatch(text), reason)
    return text


def _required_text(value, reason):
    _require(type(value) is str and bool(value.strip()), reason)
    return value


def _parse_utc(value, reason):
    _require(type(value) is str, reason)
    if value.endswith("Z"):
        iso_value = value[:-1] + "+00:00"
    else:
        _require(value.endswith("+00:00"), reason)
        iso_value = value
    try:
        parsed = datetime.fromisoformat(iso_value)
    except ValueError as exc:
        raise CustodyHold(reason) from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), reason)
    return parsed.astimezone(timezone.utc)


def _sha256(data):
    _require(type(data) is bytes, "hash_input_not_bytes")
    return hashlib.sha256(data).hexdigest()


def _read_exact_member_directory(artifact_root, endpoint):
    _require(endpoint in EXPECTED_MEMBERS, "unsupported_endpoint")
    root = Path(artifact_root)
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise CustodyHold("artifact_root_missing") from exc
    _require(stat.S_ISDIR(root_stat.st_mode) and not root.is_symlink(),
             "artifact_root_not_regular_directory")
    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        raise CustodyHold("artifact_root_unreadable") from exc
    expected = EXPECTED_MEMBERS[endpoint]
    names = [entry.name for entry in entries]
    _require(len(names) == len(set(names)), "duplicate_artifact_member")
    _require(len(names) == len(expected) and set(names) == expected,
             "artifact_member_set_mismatch")
    members = {}
    total = 0
    for entry in entries:
        _require(
            entry.name in expected
            and "/" not in entry.name
            and "\\" not in entry.name
            and "%" not in entry.name
            and entry.name not in {".", ".."},
            "unsafe_artifact_member_name",
        )
        try:
            before = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise CustodyHold("artifact_member_unreadable") from exc
        _require(not entry.is_symlink() and stat.S_ISREG(before.st_mode),
                 "artifact_member_not_regular_file")
        _require(before.st_nlink == 1, "artifact_member_link_forbidden")
        _require(0 < before.st_size <= MAX_MEMBER_BYTES,
                 "artifact_member_size_out_of_bounds")
        try:
            data = Path(entry.path).read_bytes()
            after = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise CustodyHold("artifact_member_read_failure") from exc
        _require(
            before.st_dev == after.st_dev
            and before.st_ino == after.st_ino
            and before.st_size == after.st_size == len(data)
            and before.st_mtime_ns == after.st_mtime_ns,
            "artifact_member_changed_during_read",
        )
        total += len(data)
        _require(total <= MAX_TOTAL_BYTES, "artifact_total_size_exceeded")
        members[entry.name] = data
    return members


def _validate_execution_identity(manifest, *, repository, workflow,
                                 workflow_ref, git_ref, head_sha, run_id,
                                 run_attempt):
    repository = _required_text(repository, "repository_malformed")
    _require(repository.count("/") == 1, "repository_malformed")
    _require(workflow == WORKFLOW_NAME, "workflow_name_mismatch")
    _require(git_ref == MAIN_REF, "source_ref_not_main")
    _require(
        workflow_ref == f"{repository}/{WORKFLOW_PATH}@{MAIN_REF}",
        "workflow_ref_mismatch",
    )
    _require(type(head_sha) is str and HEX40.fullmatch(head_sha),
             "head_sha_malformed")
    run_id = _positive_decimal(run_id, "run_id_malformed")
    run_attempt = _positive_decimal(run_attempt, "run_attempt_malformed")
    expected = {
        "repository": repository,
        "workflow": workflow,
        "workflow_ref": workflow_ref,
        "ref": git_ref,
        "head_sha": head_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
    }
    for field, value in expected.items():
        _require(manifest.get(field) == value,
                 "shadow_manifest_execution_mismatch:" + field)
    return expected


def _validate_receipt(receipt_bytes, *, raw_bytes, endpoint, session_key):
    receipt = _strict_json_bytes(
        receipt_bytes, expected_type=dict, reason="source_receipt_malformed"
    )
    try:
        validate_receipt_envelope(receipt)
        verify_temporal_bindings(receipt)
    except ReceiptError as exc:
        raise CustodyHold("source_receipt_invalid:" + exc.code) from exc
    _require(receipt.get("receipt_type") == "source_capture",
             "source_receipt_wrong_type")
    _require(receipt.get("parent_receipt_ids") == [],
             "source_receipt_not_parentless")
    _require(canonical_json_bytes(receipt) == receipt_bytes,
             "source_receipt_not_canonical")
    scope = receipt["scope"]
    _require(scope.get("session_id") == session_key,
             "source_receipt_session_mismatch")
    _positive_decimal(scope.get("meeting_id"), "source_receipt_meeting_malformed")
    _required_text(scope.get("event_id"), "source_receipt_event_malformed")
    source_uri = f"{API_BASE}/{endpoint}?session_key={session_key}"
    source_id = "openf1:" + endpoint + ":" + _sha256(source_uri.encode("utf-8"))
    payload = receipt["payload"]
    _require(payload.get("source_uri") == source_uri,
             "source_receipt_uri_mismatch")
    _require(payload.get("source_id") == source_id,
             "source_receipt_source_id_mismatch")
    _require(payload.get("source_sha256") == _sha256(raw_bytes),
             "source_receipt_raw_hash_mismatch")
    identity = {
        key: receipt[key]
        for key in ("receipt_type", "scope", "parent_receipt_ids", "payload")
    }
    expected_id = "source_capture:" + sha256(canonical_json_bytes(identity))
    _require(receipt.get("receipt_id") == expected_id,
             "source_receipt_id_mismatch")
    return receipt, source_uri


def _validate_raw_response(raw_bytes, *, endpoint, scope):
    rows = _strict_json_bytes(
        raw_bytes, expected_type=list, reason="raw_response_malformed"
    )
    _require(bool(rows), "raw_response_empty")
    for row in rows:
        _require(type(row) is dict, "raw_response_row_malformed")
        _require(
            _row_decimal(row.get("meeting_key"), "raw_meeting_key_malformed")
            == scope["meeting_id"],
            "raw_meeting_scope_mismatch",
        )
        _require(
            _row_decimal(row.get("session_key"), "raw_session_key_malformed")
            == scope["session_id"],
            "raw_session_scope_mismatch",
        )
    return rows


def _validate_common_sidecars(members, *, endpoint, session_key, repository,
                              workflow, workflow_ref, git_ref, head_sha, run_id,
                              run_attempt):
    raw = members[RAW_MEMBER[endpoint]]
    receipt_bytes = members["source_capture_receipt.json"]
    manifest = _strict_json_bytes(
        members["shadow_manifest.json"],
        expected_type=dict,
        reason="shadow_manifest_malformed",
    )
    assessment = _strict_json_bytes(
        members["historical_rest_capture_assessment.json"],
        expected_type=dict,
        reason="capture_assessment_malformed",
    )
    _require(
        members["shadow_report.md"].startswith(b"# DR-002 "),
        "shadow_report_malformed",
    )
    receipt, source_uri = _validate_receipt(
        receipt_bytes, raw_bytes=raw, endpoint=endpoint, session_key=session_key
    )
    raw_sha = _sha256(raw)
    receipt_sha = _sha256(receipt_bytes)
    scope = receipt["scope"]
    execution = _validate_execution_identity(
        manifest,
        repository=repository,
        workflow=workflow,
        workflow_ref=workflow_ref,
        git_ref=git_ref,
        head_sha=head_sha,
        run_id=run_id,
        run_attempt=run_attempt,
    )
    _validate_raw_response(raw, endpoint=endpoint, scope=scope)
    expected_manifest = {
        "status": capture_contract.VALIDATED,
        "reason": None,
        "k4r1_status": capture_contract.VALIDATED,
        "event_id": scope["event_id"],
        "meeting_id": scope["meeting_id"],
        "session_id": scope["session_id"],
        "canonical_request_uri": source_uri,
        "raw_response_sha256": raw_sha,
        "receipt_sha256": receipt_sha,
        "receipt_type": "source_capture",
        "first_observed_utc": receipt["payload"]["first_observed_utc"],
        "ingested_utc": receipt["payload"]["ingested_utc"],
        "receipt_created_utc": receipt["receipt_created_utc"],
        "openf1_documented_historical_window_satisfied": True,
        "verified_receipt_bindings_created": False,
        "latest_or_history_written": False,
        "repository_mutation_performed": False,
        "dr002_activated": False,
        "promotion_allowed": False,
    }
    for field, value in expected_manifest.items():
        _require(manifest.get(field) == value,
                 "shadow_manifest_mismatch:" + field)
    expected_assessment = {
        "status": capture_contract.VALIDATED,
        "reason_codes": [],
        "canonical_request_uri": source_uri,
        "raw_response_sha256": raw_sha,
        "receipt_sha256": receipt_sha,
    }
    for field, value in expected_assessment.items():
        _require(assessment.get(field) == value,
                 "capture_assessment_mismatch:" + field)
    _require(
        "raw_response_bytes" not in assessment
        and "source_capture_receipt_bytes" not in assessment,
        "capture_assessment_not_sanitized",
    )
    return {
        "manifest": manifest,
        "assessment": assessment,
        "receipt": receipt,
        "scope": scope,
        "execution": execution,
    }


def _validate_grid(members, common, session_key):
    manifest = common["manifest"]
    scope = common["scope"]
    sessions_bytes = members["sessions.response.json"]
    sessions = _strict_json_bytes(
        sessions_bytes, expected_type=list, reason="sessions_response_malformed"
    )
    _require(bool(sessions), "sessions_response_empty")
    source_id = manifest.get("grid_source_session_id")
    target_id = manifest.get("grid_target_race_session_id")
    _require(
        source_id == session_key
        and type(target_id) is str
        and POSITIVE_DECIMAL.fullmatch(target_id)
        and target_id != source_id,
        "grid_source_target_scope_mismatch",
    )
    required = {
        "selected_endpoint": "starting_grid",
        "raw_response_filename": "starting_grid.response.json",
        "session_discovery_filename": "sessions.response.json",
        "grid_source_session_kind": "Qualifying",
        "grid_target_race_session_kind": "Race",
        "source_to_race_link_evidence_type": "OPENF1_PROVIDER_DISCOVERY_CLAIM",
        "k4r14_status": grid_adapter.VALIDATED,
        "session_discovery_request_attempted": True,
        "starting_grid_request_attempted": True,
        "session_discovery_http_status_code": 200,
        "starting_grid_http_status_code": 200,
        "session_discovery_raw_sha256": _sha256(sessions_bytes),
        "discovery_response_sha256": _sha256(sessions_bytes),
        "starting_grid_raw_sha256": _sha256(
            members["starting_grid.response.json"]
        ),
        "source_session_classification_authenticated": False,
        "target_race_session_classification_authenticated": False,
        "producer_input_csv_is_target_race_scoped": False,
        "cross_session_join_authorized": False,
        "official_fia_grid_authenticated": False,
        "historical_pre_race_availability_proven": False,
        "blind_validation_eligible": False,
        "stable_engine_execution_proven": False,
        "production_forecast_generated": False,
    }
    for field, value in required.items():
        actual = manifest.get(field)
        if field.endswith("http_status_code"):
            _require(type(actual) is int and actual == value,
                     "grid_manifest_mismatch:" + field)
        else:
            _require(actual == value, "grid_manifest_mismatch:" + field)
    source_rows = []
    target_rows = []
    for row in sessions:
        _require(type(row) is dict, "sessions_response_row_malformed")
        key = _row_decimal(row.get("session_key"), "session_key_malformed")
        if key == source_id:
            source_rows.append(row)
        if key == target_id:
            target_rows.append(row)
    _require(len(source_rows) == len(target_rows) == 1,
             "grid_source_target_session_not_unique")
    source, target = source_rows[0], target_rows[0]
    _require(
        source.get("session_name") == source.get("session_type") == "Qualifying",
        "grid_source_not_qualifying",
    )
    _require(
        target.get("session_name") == target.get("session_type") == "Race",
        "grid_target_not_race",
    )
    _require(
        _row_decimal(source.get("meeting_key"), "source_meeting_malformed")
        == _row_decimal(target.get("meeting_key"), "target_meeting_malformed")
        == scope["meeting_id"],
        "grid_source_target_meeting_mismatch",
    )
    for field in ("year", "country_name", "location", "circuit_short_name"):
        _require(source.get(field) == target.get(field),
                 "grid_source_target_event_mismatch:" + field)
    _require(
        _parse_utc(target.get("date_start"), "grid_target_start_malformed")
        > _parse_utc(source.get("date_end"), "grid_source_end_malformed"),
        "grid_target_not_after_source",
    )
    expected_discovery_uri = f"{API_BASE}/sessions?year={source.get('year')}"
    _require(manifest.get("session_discovery_request_uri") == expected_discovery_uri,
             "grid_discovery_uri_mismatch")
    return {
        "source_session_id": source_id,
        "source_session_kind": "Qualifying",
        "target_race_session_id": target_id,
        "target_race_session_kind": "Race",
        "relationship_evidence_type": "OPENF1_PROVIDER_DISCOVERY_CLAIM",
        "cross_session_producer_authorization": False,
    }


def build_custody_manifest_bytes(
    *, artifact_root, endpoint, session_key, repository, workflow,
    workflow_ref, git_ref, head_sha, run_id, run_attempt,
):
    """Return deterministic manifest bytes or raise CustodyHold."""
    _require(endpoint in EXPECTED_MEMBERS, "unsupported_endpoint")
    session_key = _positive_decimal(session_key, "session_key_malformed")
    members = _read_exact_member_directory(artifact_root, endpoint)
    common = _validate_common_sidecars(
        members,
        endpoint=endpoint,
        session_key=session_key,
        repository=repository,
        workflow=workflow,
        workflow_ref=workflow_ref,
        git_ref=git_ref,
        head_sha=head_sha,
        run_id=run_id,
        run_attempt=run_attempt,
    )
    manifest = common["manifest"]
    if endpoint == "drivers":
        _require(
            manifest.get("selected_endpoint") == "drivers"
            and manifest.get("raw_response_filename") == "drivers.response.json"
            and manifest.get("k4r6_status") == drivers_adapter.VALIDATED,
            "drivers_manifest_endpoint_mismatch",
        )
    elif endpoint == "weather":
        _require(manifest.get("selected_endpoint") in (None, "weather"),
                 "weather_manifest_endpoint_mismatch")
    relationship = (
        _validate_grid(members, common, session_key)
        if endpoint == "starting_grid" else None
    )
    inventory = [
        {
            "member_name": name,
            "evidence_role": MEMBER_ROLES[name],
            "sha256": _sha256(members[name]),
            "byte_length": len(members[name]),
        }
        for name in sorted(members)
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "classification": CLASSIFICATION,
        "source_endpoint": endpoint,
        "input_evidence_role": INPUT_EVIDENCE_ROLE[endpoint],
        "source_scope": common["scope"],
        "original_source_receipt_id": common["receipt"]["receipt_id"],
        "original_artifact_member_count": len(inventory),
        "original_artifact_members": inventory,
        "github_execution_claims": {
            **common["execution"],
            "identity_basis": "MATCHED_ORIGINAL_PUBLISHER_SHADOW_MANIFEST_ONLY",
        },
        "source_to_target_relationship": relationship,
        "custody_manifest_contains_no_raw_source_bytes": True,
        "custody_manifest_prepared_for_github_attestation": True,
        "source_session_classification_authenticated": False,
        **{field: False for field in FALSE_FLAGS},
    }
    return canonical_json_bytes(result)


def _write_new(path, data):
    path = Path(path)
    try:
        with path.open("xb") as handle:
            handle.write(data)
        _require(path.read_bytes() == data, "output_readback_mismatch")
    except FileExistsError as exc:
        raise CustodyHold("output_already_exists") from exc
    except OSError as exc:
        raise CustodyHold("output_write_failure") from exc


def prepare_custody_manifest(*, output_dir, **kwargs):
    data = build_custody_manifest_bytes(**kwargs)
    root = Path(output_dir)
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise CustodyHold("output_directory_already_exists") from exc
    except OSError as exc:
        raise CustodyHold("output_directory_create_failure") from exc
    _write_new(root / "custody_manifest.json", data)
    return data


def _decode_bundle_subject(bundle_bytes, expected_digest):
    bundle = _strict_json_bytes(
        bundle_bytes, expected_type=dict, reason="attestation_bundle_malformed"
    )
    _require(bundle.get("mediaType") == BUNDLE_MEDIA_TYPE,
             "attestation_bundle_media_type_mismatch")
    envelope = bundle.get("dsseEnvelope")
    _require(type(envelope) is dict, "attestation_dsse_envelope_malformed")
    _require(envelope.get("payloadType") == DSSE_PAYLOAD_TYPE,
             "attestation_dsse_payload_type_mismatch")
    signatures = envelope.get("signatures")
    _require(type(signatures) is list and bool(signatures),
             "attestation_dsse_signature_missing")
    for signature in signatures:
        _require(type(signature) is dict and type(signature.get("sig")) is str,
                 "attestation_dsse_signature_malformed")
        try:
            decoded_signature = base64.b64decode(
                signature["sig"], validate=True
            )
        except (ValueError, TypeError) as exc:
            raise CustodyHold("attestation_dsse_signature_malformed") from exc
        _require(bool(decoded_signature), "attestation_dsse_signature_malformed")
    payload = envelope.get("payload")
    _require(type(payload) is str and bool(payload),
             "attestation_dsse_payload_missing")
    try:
        statement_bytes = base64.b64decode(payload, validate=True)
    except (ValueError, TypeError) as exc:
        raise CustodyHold("attestation_dsse_payload_malformed") from exc
    statement = _strict_json_bytes(
        statement_bytes, expected_type=dict, reason="attestation_statement_malformed"
    )
    _require(
        statement.get("_type") == STATEMENT_TYPE
        and statement.get("predicateType") == PREDICATE_TYPE,
        "attestation_statement_type_mismatch",
    )
    subjects = statement.get("subject")
    _require(type(subjects) is list and len(subjects) == 1,
             "attestation_subject_count_mismatch")
    subject = subjects[0]
    _require(type(subject) is dict and set(subject) == {"name", "digest"},
             "attestation_subject_malformed")
    name = subject.get("name")
    digest = subject.get("digest")
    _require(type(name) is str and name.endswith("custody_manifest.json"),
             "attestation_subject_name_mismatch")
    _require(
        type(digest) is dict
        and set(digest) == {"sha256"}
        and digest.get("sha256") == expected_digest,
        "attestation_subject_digest_mismatch",
    )
    return name


def preserve_attestation_outputs(
    *, custody_manifest_path, attestation_bundle_path, output_dir,
    attestation_id, attestation_url, repository, workflow, workflow_ref,
    git_ref, head_sha, run_id, run_attempt,
):
    """Preserve action outputs after a local subject-digest consistency check.

    This deliberately does not perform or claim cryptographic/Tlog verification.
    """
    manifest_path = Path(custody_manifest_path)
    bundle_path = Path(attestation_bundle_path)
    try:
        manifest_bytes = manifest_path.read_bytes()
        bundle_bytes = bundle_path.read_bytes()
    except OSError as exc:
        raise CustodyHold("attestation_input_read_failure") from exc
    manifest = _strict_json_bytes(
        manifest_bytes, expected_type=dict, reason="custody_manifest_malformed"
    )
    _require(canonical_json_bytes(manifest) == manifest_bytes,
             "custody_manifest_not_canonical")
    _require(
        manifest.get("schema_version") == SCHEMA_VERSION
        and manifest.get("status") == STATUS,
        "custody_manifest_status_mismatch",
    )
    execution = manifest.get("github_execution_claims")
    _require(type(execution) is dict, "custody_manifest_execution_missing")
    _validate_execution_identity(
        execution,
        repository=repository,
        workflow=workflow,
        workflow_ref=workflow_ref,
        git_ref=git_ref,
        head_sha=head_sha,
        run_id=run_id,
        run_attempt=run_attempt,
    )
    for field in FALSE_FLAGS:
        _require(manifest.get(field) is False,
                 "custody_manifest_forbidden_claim:" + field)
    subject_sha = _sha256(manifest_bytes)
    subject_name = _decode_bundle_subject(bundle_bytes, subject_sha)
    attestation_id = _positive_decimal(attestation_id, "attestation_id_malformed")
    expected_url = f"https://github.com/{repository}/attestations/{attestation_id}"
    _require(attestation_url == expected_url, "attestation_url_mismatch")
    metadata = {
        "schema_version": METADATA_SCHEMA_VERSION,
        "classification": (
            "LOCAL_DSSE_SUBJECT_CONSISTENCY_ONLY_NOT_CRYPTOGRAPHIC_VERIFICATION"
        ),
        "attestation_action": ATTESTATION_ACTION,
        "attestation_id": attestation_id,
        "attestation_url": attestation_url,
        "subject_name_from_dsse": subject_name,
        "subject_sha256": subject_sha,
        "bundle_sha256": _sha256(bundle_bytes),
        "repository": repository,
        "workflow_path": WORKFLOW_PATH,
        "workflow_name": workflow,
        "workflow_ref": workflow_ref,
        "git_ref": git_ref,
        "git_head_sha": head_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "dsse_subject_digest_consistency_checked": True,
        "attestation_bundle_preserved_exactly": True,
        **{field: False for field in FALSE_FLAGS},
        **{field: False for field in LOCAL_ONLY_FALSE_FLAGS},
    }
    metadata_bytes = canonical_json_bytes(metadata)
    root = Path(output_dir)
    _require(root == manifest_path.parent,
             "attestation_output_directory_mismatch")
    _write_new(root / "github_attestation.bundle.json", bundle_bytes)
    _write_new(root / "github_attestation_metadata.json", metadata_bytes)
    _require(manifest_path.read_bytes() == manifest_bytes,
             "custody_manifest_changed_during_preservation")
    return metadata_bytes


def _parser():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--artifact-root", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.add_argument("--endpoint", required=True)
    prepare.add_argument("--session-key", required=True)
    preserve = commands.add_parser("preserve")
    preserve.add_argument("--custody-manifest", required=True)
    preserve.add_argument("--attestation-bundle", required=True)
    preserve.add_argument("--output-dir", required=True)
    preserve.add_argument("--attestation-id", required=True)
    preserve.add_argument("--attestation-url", required=True)
    for command in (prepare, preserve):
        command.add_argument("--repository", required=True)
        command.add_argument("--workflow", required=True)
        command.add_argument("--workflow-ref", required=True)
        command.add_argument("--git-ref", required=True)
        command.add_argument("--head-sha", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--run-attempt", required=True)
    return parser


def main(argv=None):
    args = vars(_parser().parse_args(argv))
    command = args.pop("command")
    if command == "prepare":
        artifact_root = args.pop("artifact_root")
        output_dir = args.pop("output_dir")
        prepare_custody_manifest(
            artifact_root=artifact_root, output_dir=output_dir, **args
        )
    else:
        preserve_attestation_outputs(
            custody_manifest_path=args.pop("custody_manifest"),
            attestation_bundle_path=args.pop("attestation_bundle"),
            **args,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CustodyHold as exc:
        raise SystemExit("HOLD: " + str(exc))
