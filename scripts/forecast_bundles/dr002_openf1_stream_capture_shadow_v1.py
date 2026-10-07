"""Credential-safe bounded OpenF1 stream-capture shadow capability.

The live path is manual-only through its workflow. Tests inject token and MQTT
transports, so importing or testing this module performs no network operation.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from dr002_openf1_stream_version_evidence_v1 import (
    HOLD as K2_HOLD,
    SCHEMA_VERSION as K2_SCHEMA_VERSION,
    VALIDATED as K2_VALIDATED,
    assess_openf1_stream_version_evidence,
)


PROVIDER = "openf1"
TOKEN_ENDPOINT = "https://api.openf1.org/token"
TOKEN_CONTENT_TYPE = "application/x-www-form-urlencoded"
MQTT_BROKER = "mqtt.openf1.org"
MQTT_PORT = 8883
MQTT_TOPIC = "v1/weather"
MQTT_CLIENT_USERNAME = "f1-data-publisher-shadow"
CAPTURE_MAX_SECONDS = 180
CAPTURE_MAX_MESSAGES = 500
WORKFLOW_PATH = ".github/workflows/dr002-openf1-stream-capture-shadow.yml"
RUNTIME_ROOT = Path("_runtime/dr002_pre2b7k_openf1_stream_capture_shadow")
SUCCESS = "SHADOW_OPENF1_STREAM_CAPTURE_SUCCESS_NOT_PRODUCTION"
HOLD = "HOLD"

TRUST_CEILINGS = (
    "openf1_message_publisher_authenticated",
    "openf1_official_f1_source",
    "observation_clock_authenticated",
    "publisher_revision_completeness_proven",
    "global_observation_completeness_proven",
    "message_loss_ruled_out",
    "historical_availability_proven",
    "production_revision_tracking_proven",
    "full_gate2b1_chain_verified",
    "stable_engine_execution_proven",
    "blind_validation_eligible",
    "production_forecast_locked",
    "production_outcome_boundary_proven",
    "dr002_activated",
    "promotion_allowed",
)


class CaptureHold(RuntimeError):
    """A sanitized fail-closed reason safe for reports and manifests."""


def _canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _require(condition, reason):
    if not condition:
        raise CaptureHold(reason)


def _identity(environ):
    repository = environ.get("GITHUB_REPOSITORY", "")
    workflow_name = environ.get("GITHUB_WORKFLOW", "")
    workflow_ref = environ.get("GITHUB_WORKFLOW_REF", "")
    git_ref = environ.get("GITHUB_REF", "")
    head_sha = environ.get("GITHUB_SHA", "")
    run_id = environ.get("GITHUB_RUN_ID", "")
    run_attempt = environ.get("GITHUB_RUN_ATTEMPT", "")
    _require(repository and "/" in repository, "invalid_repository_identity")
    _require(workflow_name, "invalid_workflow_name")
    _require(git_ref == "refs/heads/main", "workflow_ref_not_main")
    expected_workflow_ref = repository + "/" + WORKFLOW_PATH + "@refs/heads/main"
    _require(workflow_ref == expected_workflow_ref, "workflow_identity_mismatch")
    _require(re.fullmatch(r"[0-9a-f]{40}", head_sha) is not None, "invalid_head_sha")
    _require(run_id.isdigit() and run_attempt.isdigit(), "invalid_run_identity")
    return {
        "repository": repository,
        "workflow_path": WORKFLOW_PATH,
        "workflow_name": workflow_name,
        "workflow_ref": workflow_ref,
        "git_ref": git_ref,
        "implementation_git_sha": head_sha,
        "github_run_id": run_id,
        "github_run_attempt": run_attempt,
        "run_scoped_id": "gha-" + run_id + "-" + run_attempt,
    }


def acquire_openf1_token(username, password):
    """Acquire a short-lived token without logging or serializing secrets."""
    _require(isinstance(username, str) and username, "missing_openf1_username")
    _require(isinstance(password, str) and password, "missing_openf1_password")
    encoded = urllib.parse.urlencode({"username": username, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=encoded,
        headers={"Content-Type": TOKEN_CONTENT_TYPE},
        method="POST",
    )
    try:
        context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=30, context=context) as response:
            body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise CaptureHold("token_response_too_large")
        value = json.loads(body)
    except CaptureHold:
        raise
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        raise CaptureHold("openf1_token_request_failed")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        raise CaptureHold("openf1_token_response_invalid")
    _require(isinstance(value, dict), "openf1_token_response_invalid")
    token = value.get("access_token")
    _require(isinstance(token, str) and token, "openf1_access_token_missing")
    expires = value.get("expires_in")
    if expires is not None:
        _require(not isinstance(expires, bool), "openf1_token_expiry_invalid")
        if isinstance(expires, str):
            _require(re.fullmatch(r"[0-9]+", expires) is not None,
                     "openf1_token_expiry_invalid")
            expires = int(expires)
        _require(isinstance(expires, int) and expires > 0, "openf1_token_expiry_invalid")
    return token, expires


def capture_openf1_mqtt(access_token, *, monotonic=time.monotonic):
    """Capture one bounded TLS MQTT subscription with automatic reconnect off."""
    _require(isinstance(access_token, str) and access_token, "openf1_access_token_missing")
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        raise CaptureHold("mqtt_client_dependency_missing")

    records = []
    state = {"connected": False, "subscribed": False, "failure": None}

    def on_connect(client, userdata, flags, reason_code, properties):
        if getattr(reason_code, "is_failure", bool(reason_code)):
            state["failure"] = "mqtt_auth_or_connection_failed"
            return
        state["connected"] = True
        result, _ = client.subscribe(MQTT_TOPIC, qos=0)
        if result != mqtt.MQTT_ERR_SUCCESS:
            state["failure"] = "mqtt_subscription_failed"

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        if any(getattr(code, "is_failure", False) for code in reason_codes):
            state["failure"] = "mqtt_subscription_failed"
        else:
            state["subscribed"] = True

    def on_message(client, userdata, message):
        if message.topic != MQTT_TOPIC:
            state["failure"] = "unexpected_mqtt_topic"
            client.disconnect()
            return
        payload = bytes(message.payload)
        records.append({
            "topic": message.topic,
            "raw_json_bytes": payload,
            "received_order_index": len(records),
        })
        if len(records) >= CAPTURE_MAX_MESSAGES:
            client.disconnect()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        protocol=mqtt.MQTTv5,
        reconnect_on_failure=False,
    )
    client.username_pw_set(MQTT_CLIENT_USERNAME, access_token)
    client.tls_set_context(ssl.create_default_context())
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    try:
        result = client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        _require(result == mqtt.MQTT_ERR_SUCCESS, "mqtt_connection_failed")
        deadline = monotonic() + CAPTURE_MAX_SECONDS
        while monotonic() < deadline and len(records) < CAPTURE_MAX_MESSAGES and not state["failure"]:
            remaining = max(0.0, deadline - monotonic())
            result = client.loop(timeout=min(1.0, remaining))
            if result != mqtt.MQTT_ERR_SUCCESS:
                state["failure"] = "mqtt_connection_failed"
                break
    except CaptureHold:
        raise
    except Exception:
        raise CaptureHold("mqtt_connection_or_capture_failed")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
    _require(state["failure"] is None, state["failure"] or "mqtt_capture_failed")
    _require(state["connected"] and state["subscribed"], "mqtt_subscription_not_confirmed")
    return {"connection_outcome": "CONNECTED_AND_SUBSCRIBED", "messages": records}


def _hold_k2(reason):
    result = {
        "schema_version": K2_SCHEMA_VERSION,
        "assessment_type": "OPENF1_STREAM_VERSION_EVIDENCE",
        "status": K2_HOLD,
        "reason_codes": [reason],
        "declared_window_schedule_coverage_proven": False,
        "k1_observer_coverage_supplied": False,
    }
    return result


def _write_runtime_package(root, manifest, k2_result, messages):
    root.mkdir(parents=True, exist_ok=False)
    message_dir = root / "messages"
    message_dir.mkdir()
    for item in messages:
        target = root / item["relative_path"]
        target.write_bytes(item["raw_json_bytes"])
        _require(target.read_bytes() == item["raw_json_bytes"], "message_readback_mismatch")
    k2_bytes = _canonical_bytes(k2_result)
    _require(_sha256(k2_bytes) == manifest["k2_result_sha256"], "k2_result_hash_mismatch")
    (root / "stream_version_evidence.json").write_bytes(k2_bytes)
    manifest_bytes = _canonical_bytes(manifest)
    (root / "capture_execution_manifest.json").write_bytes(manifest_bytes)
    report = (
        "# DR-002 OpenF1 stream capture shadow\n\n"
        "Status: " + manifest["status"] + "\n\n"
        "Connection outcome: " + manifest["connection_outcome"] + "\n\n"
        "Observed messages: " + str(manifest["message_count"]) + "\n\n"
        "K2 status: " + k2_result["status"] + "\n\n"
        "This is shadow evidence only. No official-source, clock, completeness, production, activation, or promotion claim is made.\n"
    ).encode("utf-8")
    (root / "capture_report.md").write_bytes(report)
    return manifest_bytes


def execute_capture_shadow(
    *,
    environ=None,
    token_fetcher=acquire_openf1_token,
    transport=capture_openf1_mqtt,
    output_base=RUNTIME_ROOT,
    utc_now=_utc_now,
    unsupported_claims=None,
):
    """Execute one bounded capture; injected dependencies keep tests offline."""
    environ = dict(os.environ if environ is None else environ)
    identity = _identity(environ)
    root = Path(output_base) / identity["run_scoped_id"]
    _require(not root.exists(), "run_scoped_output_already_exists")
    assertions = {} if unsupported_claims is None else unsupported_claims
    connection_outcome = "NOT_ATTEMPTED"
    token_expiry = None
    captured = []
    started_utc = utc_now()
    k2_result = None
    reason = None
    try:
        _require(isinstance(assertions, dict), "malformed_unsupported_claims")
        _require(all(field in TRUST_CEILINGS and isinstance(value, bool)
                     for field, value in assertions.items()), "malformed_unsupported_claims")
        _require(not any(assertions.values()), "unsupported_trust_assertion")
        username = environ.get("OPENF1_USERNAME")
        password = environ.get("OPENF1_PASSWORD")
        _require(isinstance(username, str) and username, "missing_openf1_username")
        _require(isinstance(password, str) and password, "missing_openf1_password")
        token, token_expiry = token_fetcher(username, password)
        _require(isinstance(token, str) and token, "openf1_access_token_missing")
        transport_result = transport(token)
        _require(isinstance(transport_result, dict)
                 and set(transport_result) == {"connection_outcome", "messages"},
                 "malformed_transport_result")
        connection_outcome = transport_result["connection_outcome"]
        _require(connection_outcome == "CONNECTED_AND_SUBSCRIBED", "mqtt_capture_failed")
        captured = transport_result["messages"]
        _require(isinstance(captured, list), "malformed_transport_messages")
        _require(len(captured) <= CAPTURE_MAX_MESSAGES, "message_bound_exceeded")
        _require(bool(captured), "zero_messages_captured")
        ended_utc = utc_now()
        k2_result = assess_openf1_stream_version_evidence(
            provider=PROVIDER,
            subscription_topics=[MQTT_TOPIC],
            connection_window={
                "connection_id": identity["run_scoped_id"],
                "window_start_utc": started_utc,
                "window_end_utc": ended_utc,
            },
            messages=captured,
        )
        _require(k2_result["status"] == K2_VALIDATED, "k2_stream_evidence_hold")
        _require(k2_result["k1_observer_coverage_supplied"] is False
                 and k2_result["declared_window_schedule_coverage_proven"] is False,
                 "k1_coverage_fabricated")
        status = SUCCESS
    except CaptureHold as exc:
        reason = str(exc) or "capture_hold"
        if connection_outcome == "NOT_ATTEMPTED" and reason.startswith("mqtt_"):
            connection_outcome = "CONNECTION_FAILED"
        k2_result = _hold_k2(reason) if k2_result is None else k2_result
        status = HOLD
        ended_utc = utc_now()
    except Exception:
        reason = "sanitized_capture_failure"
        k2_result = _hold_k2(reason)
        status = HOLD
        ended_utc = utc_now()

    runtime_messages = []
    for index, record in enumerate(captured):
        raw_bytes = record.get("raw_json_bytes") if isinstance(record, dict) else None
        if not isinstance(raw_bytes, bytes):
            raw_bytes = b""
        runtime_messages.append({
            "relative_path": "messages/message-" + str(index).zfill(6) + ".bin",
            "topic": record.get("topic") if isinstance(record, dict) else None,
            "received_order_index": record.get("received_order_index") if isinstance(record, dict) else None,
            "raw_json_sha256": _sha256(raw_bytes),
            "raw_json_bytes": raw_bytes,
        })
    k2_bytes = _canonical_bytes(k2_result)
    manifest_messages = [
        {key: value for key, value in item.items() if key != "raw_json_bytes"}
        for item in runtime_messages
    ]
    manifest = {
        "schema_version": "dr002-openf1-stream-capture-shadow-manifest-v1",
        "status": status,
        "reason_codes": [] if reason is None else [reason],
        **identity,
        "provider": PROVIDER,
        "broker": MQTT_BROKER,
        "port": MQTT_PORT,
        "topic": MQTT_TOPIC,
        "capture_max_seconds": CAPTURE_MAX_SECONDS,
        "capture_max_messages": CAPTURE_MAX_MESSAGES,
        "runner_capture_started_utc": started_utc,
        "runner_capture_ended_utc": ended_utc,
        "connection_outcome": connection_outcome,
        "token_declared_expires_in_seconds": token_expiry,
        "message_count": len(runtime_messages),
        "k2_result_relative_path": "stream_version_evidence.json",
        "k2_result_sha256": _sha256(k2_bytes),
        "messages": manifest_messages,
        "min_observed_id": k2_result.get("min_observed_id"),
        "max_observed_id": k2_result.get("max_observed_id"),
        "received_order_id_strictly_increasing": k2_result.get("received_order_id_strictly_increasing", False),
        "numeric_id_gaps_observed": k2_result.get("numeric_id_gaps_observed", False),
        "k1_observer_coverage_supplied": False,
        "declared_window_schedule_coverage_proven": False,
        "future_attestation_subject_relative_path": "capture_execution_manifest.json",
        **{field: False for field in TRUST_CEILINGS},
    }
    manifest_bytes = _write_runtime_package(root, manifest, k2_result, runtime_messages)
    return {
        "status": status,
        "root": root,
        "manifest": manifest,
        "manifest_sha256": _sha256(manifest_bytes),
        "k2_result": k2_result,
    }


def preserve_attestation_from_env(environ=None, output_base=RUNTIME_ROOT):
    """Preserve the action bundle unchanged after local subject consistency checks."""
    environ = dict(os.environ if environ is None else environ)
    identity = _identity(environ)
    root = Path(output_base) / identity["run_scoped_id"]
    subject = root / "capture_execution_manifest.json"
    subject_bytes = subject.read_bytes()
    manifest = json.loads(subject_bytes)
    _require(manifest["status"] == SUCCESS, "attestation_subject_not_successful")
    _require(manifest["future_attestation_subject_relative_path"] == subject.name,
             "attestation_subject_path_mismatch")
    for field, value in identity.items():
        _require(manifest[field] == value, "attestation_subject_identity_mismatch")
    for field in TRUST_CEILINGS:
        _require(manifest[field] is False, "unsupported_trust_claim")
    digest = _sha256(subject_bytes)
    bundle_source = Path(environ.get("ATTESTATION_BUNDLE_PATH", ""))
    bundle_bytes = bundle_source.read_bytes()
    bundle = json.loads(bundle_bytes)
    statement = json.loads(base64.b64decode(bundle["dsseEnvelope"]["payload"], validate=True))
    subjects = statement["subject"]
    _require(len(subjects) == 1 and subjects[0]["digest"].get("sha256") == digest,
             "attestation_subject_digest_mismatch")
    attestation_id = environ.get("ATTESTATION_ID", "")
    attestation_url = environ.get("ATTESTATION_URL", "")
    _require(attestation_id.isdigit(), "invalid_attestation_id")
    _require(attestation_url == "https://github.com/" + identity["repository"]
             + "/attestations/" + attestation_id, "invalid_attestation_url")
    target = root / "github_attestation.bundle.json"
    target.write_bytes(bundle_bytes)
    _require(target.read_bytes() == bundle_bytes, "attestation_bundle_readback_mismatch")
    metadata = {
        "schema_version": "dr002-openf1-stream-capture-shadow-attestation-metadata-v1",
        "attestation_id": attestation_id,
        "attestation_url": attestation_url,
        "subject_relative_path": subject.relative_to(root).as_posix(),
        "subject_sha256": digest,
        **identity,
        "future_tlog_time_does_not_authenticate_internal_receive_clock": True,
        "consistency_check_only_not_cryptographic_verification": True,
        **{field: False for field in TRUST_CEILINGS},
    }
    metadata_target = root / "github_attestation_metadata.json"
    metadata_target.write_bytes(_canonical_bytes(metadata))
    _require(subject.read_bytes() == subject_bytes, "attestation_subject_mutated")
    return metadata


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "preserve-attestation":
        preserve_attestation_from_env()
        return 0
    if len(sys.argv) != 1:
        return 2
    result = execute_capture_shadow()
    return 0 if result["status"] == SUCCESS else 1


if __name__ == "__main__":
    raise SystemExit(main())
