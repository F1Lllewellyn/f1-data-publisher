"""Bind one accepted synthetic producer-shadow payload with the Gate 2B-4 lock.

This wrapper creates unbound runtime evidence only. It does not authenticate a
clock, verify a full receipt graph, publish a forecast, or invoke production paths.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dr002_frozen_producer_shadow_pilot_v1 as producer_shadow
import dr002_lock_boundary_revision_v1 as lock_contract
import verify_forecast_integrity_receipts_v1 as receipt_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCER_RUNTIME_ROOT = REPO_ROOT / "_runtime/dr002_pre2b7c_frozen_producer_shadow"
LOCK_RUNTIME_ROOT = REPO_ROOT / "_runtime/dr002_pre2b7h_forecast_lock_shadow"
PRODUCER_PATH = REPO_ROOT / "scripts/forecasts/produce_actual_forecast_rows_v1.py"
WORKFLOW_PATH = ".github/workflows/dr002-forecast-lock-shadow-pilot.yml"
SCHEMA = "dr002-forecast-lock-shadow-pilot-v1"
STATUS = "SHADOW_FORECAST_LOCK_ONLY_NOT_PRODUCTION"
MODE = "manual_github_synthetic_forecast_lock_shadow"
FALSE_FLAGS = (
    "producer_receipt_externally_bound",
    "lock_receipt_externally_bound",
    "lock_clock_authenticated",
    "durable_storage_proven",
    "full_gate2b1_chain_verified",
    "production_authenticated",
    "historical_availability_proven",
    "stable_engine_execution_proven",
    "blind_validation_eligible",
    "production_forecast_locked",
    "dr002_activated",
    "promotion_allowed",
)


class LockShadowError(ValueError):
    """HOLD: no successful lock-execution manifest."""


def require(condition, reason):
    if not condition:
        raise LockShadowError(reason)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def utcnow():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def strict_json(data):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    return json.loads(data, object_pairs_hook=object_pairs)


def json_file_bytes(value):
    return receipt_contract.canonical_json_bytes(value) + b"\n"


def read_file(path, root):
    require(path.is_file() and not path.is_symlink(), "missing_or_ambiguous_evidence")
    require(path.resolve().is_relative_to(root.resolve()), "evidence_path_escape")
    return path.read_bytes()


def persist_checked(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    require(path.read_bytes() == data, "evidence_readback_failed")
    return sha256(data)


def validate_workflow_ref(workflow_ref, repository, git_ref):
    """Return the truthful normalized caller workflow path or fail closed."""
    require(isinstance(workflow_ref, str) and workflow_ref, "malformed_workflow_ref")
    require("\\" not in workflow_ref, "malformed_workflow_ref")
    match = re.fullmatch(
        r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/([^@]+)@(.+)", workflow_ref
    )
    require(match is not None, "malformed_workflow_ref")
    caller_repository, workflow_path, caller_ref = match.groups()
    require(caller_repository == repository, "workflow_repository_mismatch")
    require(caller_ref == git_ref, "workflow_ref_mismatch")
    parts = workflow_path.split("/")
    require(
        len(parts) == 3
        and parts[:2] == [".github", "workflows"]
        and all(part not in ("", ".", "..") for part in parts),
        "workflow_path_not_normalized",
    )
    require(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:yml|yaml)", parts[2])
        is not None,
        "malformed_workflow_filename",
    )
    return "/".join(parts)


def producer_receipt(forecast, manifest, payload_sha):
    payload = {
        "implementation": manifest["producer_implementation"],
        "git_commit": manifest["implementation_git_sha"],
        "code_sha256": manifest["producer_code_sha256"],
        "execution_id": manifest["producer_run_id"],
        "forecast_generation_utc": manifest["forecast_generation_utc"],
        "input_manifest_sha256": lock_contract.input_manifest_sha256(forecast),
        "input_receipt_manifest_sha256": receipt_contract.input_receipt_manifest_sha256(
            []
        ),
        "forecast_payload_sha256": payload_sha,
        "engine_implementation": None,
        "engine_receipt_id": None,
        "engine_result_sha256": None,
    }
    identity = {
        "receipt_type": "producer_execution",
        "scope": lock_contract.scope(forecast),
        "parent_receipt_ids": [],
        "payload": payload,
    }
    receipt = {
        "schema_version": receipt_contract.VERSION,
        "receipt_id": "producer_execution:"
        + receipt_contract.sha256(receipt_contract.canonical_json_bytes(identity)),
        "receipt_created_utc": manifest["forecast_generation_utc"],
        **identity,
    }
    receipt_contract.validate_receipt_envelope(receipt)
    receipt_contract.verify_temporal_bindings(receipt)
    return receipt


def build_forecast_manifest(manifest, lock_utc, payload_sha):
    generation = manifest["forecast_generation_utc"]
    evidence = []
    for source in manifest["declared_sources"]:
        evidence.append(
            {
                "event_id": manifest["event_id"],
                "meeting_id": manifest["meeting_id"],
                "session_id": manifest["session_id"],
                "source_id": source["source_id"],
                "source_uri": "runtime-artifact:evidence/" + source["relative_path"],
                "source_sha256": source["source_sha256"],
                "event_time_utc": None,
                "publisher_time_utc": None,
                "first_observed_utc": generation,
                "ingested_utc": generation,
                "capture_evidence_ref": "unbound-synthetic-shadow:"
                + source["source_id"],
                "ingestion_required_at_cutoff": True,
            }
        )
    evidence.sort(key=lambda item: item["source_id"])
    forecast = {
        "schema_version": "dr002-integrity-v1",
        "legacy": False,
        "execution_mode": "manual_validation",
        "contract_approved": False,
        "forecast_id": "synthetic-lock-shadow:"
        + manifest["producer_run_id"]
        + ":"
        + payload_sha[:16],
        "product_id": "dr002-synthetic-lock-shadow",
        "product_contract_id": "dr002-pre2b7h-synthetic-lock-shadow-v1",
        "gate": manifest["gate"],
        "lane_name": manifest["lane_name"],
        "event_id": manifest["event_id"],
        "meeting_id": manifest["meeting_id"],
        "session_id": manifest["session_id"],
        "allowed_session_ids": [manifest["session_id"]],
        "evidence_cutoff_utc": generation,
        "forecast_deadline_utc": lock_utc,
        "forecast_generation_utc": generation,
        "mandatory_source_ids": sorted(
            source["source_id"] for source in manifest["declared_sources"]
        ),
        "revision_policy": "synthetic_shadow_no_revisions",
        "evidence": evidence,
    }
    return forecast


def verify_producer_shadow(run_id, implementation_git_sha):
    root = PRODUCER_RUNTIME_ROOT / run_id
    require(root.is_dir() and not root.is_symlink(), "producer_shadow_missing")
    manifest_bytes = read_file(root / "execution_manifest.json", root)
    manifest = strict_json(manifest_bytes)
    require(manifest.get("status") == producer_shadow.STATUS, "producer_shadow_not_successful")
    require(
        manifest.get("execution_mode") == "manual_github_synthetic_frozen_shadow",
        "producer_shadow_mode_mismatch",
    )
    require(manifest.get("run_id") == run_id, "producer_shadow_run_mismatch")
    require(
        manifest.get("implementation_git_sha") == implementation_git_sha,
        "producer_shadow_head_mismatch",
    )
    require(
        manifest.get("producer_implementation")
        == "scripts/forecasts/produce_actual_forecast_rows_v1.py"
        and manifest.get("producer_git_blob_sha") == producer_shadow.PRODUCER_BLOB_SHA,
        "producer_identity_mismatch",
    )
    require(
        manifest.get("event_id") == producer_shadow.EVENT_ID
        and manifest.get("meeting_id") == producer_shadow.MEETING_ID
        and manifest.get("session_id") == producer_shadow.SESSION_ID
        and manifest.get("gate") == producer_shadow.GATE
        and manifest.get("lane_name") == producer_shadow.LANE,
        "producer_scope_mismatch",
    )
    require(
        manifest.get("synthetic_inputs") is True
        and manifest.get("producer_output_sandbox_disposed") is True
        and manifest.get("producer_audit_broad_discovery_used") is False,
        "producer_shadow_ceiling_mismatch",
    )
    for field in (
        *producer_shadow.FALSE_FLAGS,
        "production_forecast_generated",
        "checkout_production_outputs_written",
        "blind_validation_eligible",
    ):
        require(manifest.get(field) is False, "unsupported_producer_trust_claim")
    require("verified_receipt_bindings" not in manifest, "manufactured_verified_binding")
    require("engine_execution" not in manifest, "unexpected_engine_execution")

    evidence_root = root / "evidence"
    declared_hashes = manifest.get("evidence_sha256")
    require(isinstance(declared_hashes, dict), "missing_producer_evidence_hashes")
    frozen_bytes = read_file(evidence_root / "frozen_input_manifest.json", evidence_root)
    frozen = strict_json(frozen_bytes)
    source_names = {source["source_name"] for source in manifest["declared_sources"]}
    expected_files = {
        "producer_audit.json",
        "source_snapshot_manifest.csv",
        "forecast_rows.csv",
        "forecast_metadata.json",
        "frozen_input_manifest.json",
        "producer_code.py",
        *(source["relative_path"] for source in manifest["declared_sources"]),
    }
    require(set(declared_hashes) == expected_files, "producer_evidence_set_mismatch")
    evidence_bytes = {}
    for name, digest in declared_hashes.items():
        require(
            isinstance(name, str)
            and re.fullmatch(r"[A-Za-z0-9_.-]+", name)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest),
            "malformed_producer_evidence_identity",
        )
        data = read_file(evidence_root / name, evidence_root)
        require(sha256(data) == digest, "producer_evidence_hash_mismatch")
        evidence_bytes[name] = data

    require(
        sha256(frozen_bytes) == manifest["frozen_manifest_sha256"],
        "frozen_manifest_hash_mismatch",
    )
    require(
        frozen.get("event_id") == manifest["event_id"]
        and frozen.get("meeting_id") == manifest["meeting_id"]
        and frozen.get("session_id") == manifest["session_id"],
        "frozen_manifest_scope_mismatch",
    )
    frozen_sources = frozen.get("sources")
    require(
        isinstance(frozen_sources, list)
        and {
            (
                source["source_name"],
                source["source_id"],
                source["relative_path"],
                source["source_sha256"],
            )
            for source in frozen_sources
        }
        == {
            (
                source["source_name"],
                source["source_id"],
                source["relative_path"],
                source["source_sha256"],
            )
            for source in manifest["declared_sources"]
        },
        "frozen_source_manifest_mismatch",
    )
    require(source_names == set(producer_shadow.SYNTHETIC_BYTES), "synthetic_source_set_mismatch")
    for source in frozen_sources:
        require(
            evidence_bytes[source["relative_path"]]
            == producer_shadow.SYNTHETIC_BYTES[source["source_name"]],
            "synthetic_source_bytes_mismatch",
        )

    checkout_code = PRODUCER_PATH.read_bytes()
    copied_code = evidence_bytes["producer_code.py"]
    require(checkout_code == copied_code, "producer_code_copy_mismatch")
    require(
        git_blob_sha(copied_code) == producer_shadow.PRODUCER_BLOB_SHA
        and sha256(copied_code) == manifest["producer_code_sha256"],
        "producer_fingerprint_changed",
    )
    audit = strict_json(evidence_bytes["producer_audit.json"])
    metadata = strict_json(evidence_bytes["forecast_metadata.json"])
    rows = producer_shadow.read_rows(evidence_bytes["forecast_rows.csv"])
    snapshot = producer_shadow.read_rows(evidence_bytes["source_snapshot_manifest.csv"])
    sources, readiness = producer_shadow.verify_outputs(
        audit, metadata, rows, snapshot, frozen, frozen_bytes
    )
    require(
        sources == manifest["declared_sources"]
        and readiness == manifest["source_readiness"]
        and audit.get("run_id") == manifest["producer_run_id"]
        and metadata.get("run_id") == manifest["producer_run_id"]
        and metadata.get("generated_utc") == manifest["forecast_generation_utc"],
        "producer_manifest_consistency_mismatch",
    )
    require(
        sha256(evidence_bytes["forecast_rows.csv"])
        == declared_hashes["forecast_rows.csv"],
        "forecast_payload_hash_mismatch",
    )
    return root, manifest, manifest_bytes, evidence_bytes["forecast_rows.csv"]


def run_lock_shadow(
    *,
    run_id,
    implementation_git_sha,
    repository,
    workflow,
    workflow_ref,
    git_ref,
    github_run_id,
    github_run_attempt,
    clock=utcnow,
):
    require(
        isinstance(github_run_id, str) and github_run_id.isdigit(),
        "invalid_github_run_id",
    )
    require(
        isinstance(github_run_attempt, str) and github_run_attempt.isdigit(),
        "invalid_github_run_attempt",
    )
    require(
        run_id == "gha-" + github_run_id + "-" + github_run_attempt,
        "run_identity_mismatch",
    )
    require(
        isinstance(implementation_git_sha, str)
        and re.fullmatch(r"[0-9a-f]{40}", implementation_git_sha),
        "invalid_implementation_git_sha",
    )
    require(
        isinstance(repository, str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository),
        "invalid_repository",
    )
    require(
        isinstance(workflow, str) and workflow.strip() and git_ref == "refs/heads/main",
        "invalid_workflow_or_ref",
    )
    workflow_path = validate_workflow_ref(workflow_ref, repository, git_ref)
    producer_root, shadow_manifest, shadow_manifest_bytes, forecast_bytes = (
        verify_producer_shadow(run_id, implementation_git_sha)
    )
    generation = receipt_contract._time(shadow_manifest["forecast_generation_utc"])
    lock_utc = clock()
    receipt_created_utc = clock()
    require(
        generation <= receipt_contract._time(lock_utc)
        <= receipt_contract._time(receipt_created_utc),
        "invalid_shadow_lock_timeline",
    )

    LOCK_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    require(not LOCK_RUNTIME_ROOT.is_symlink(), "ambiguous_lock_runtime_root")
    output = LOCK_RUNTIME_ROOT / run_id
    output.mkdir()
    try:
        payload_sha = sha256(forecast_bytes)
        forecast = build_forecast_manifest(shadow_manifest, lock_utc, payload_sha)
        producer = producer_receipt(forecast, shadow_manifest, payload_sha)
        forecast["producer"] = {
            key: producer["payload"][key]
            for key in receipt_contract.PRODUCER_KEYS
        }
        storage_ref = (
            "artifact-relative:_runtime/dr002_pre2b7h_forecast_lock_shadow/"
            + run_id
            + "/forecast_payload.csv"
        )
        lock = lock_contract.build_forecast_lock(
            forecast,
            producer,
            forecast_bytes,
            lock_utc=lock_utc,
            receipt_created_utc=receipt_created_utc,
            storage_ref=storage_ref,
        )
        require(
            lock["parent_receipt_ids"] == [producer["receipt_id"]],
            "lock_parent_mismatch",
        )
        require(
            lock["payload"]["forecast_payload_sha256"]
            == lock["payload"]["stored_payload_sha256"]
            == payload_sha,
            "lock_payload_mismatch",
        )

        pre_attestation = {
            "forecast_payload.csv": forecast_bytes,
            "producer_execution_receipt.json": json_file_bytes(producer),
            "forecast_lock_receipt.json": json_file_bytes(lock),
        }
        report = (
            "# Synthetic forecast-lock shadow\n\n"
            + STATUS
            + "\n\n"
            + "The exact persisted forecast payload is hash-bound by the unchanged "
            + "Gate 2B-4 lock constructor. Receipt bindings, lock-clock authentication "
            + "and durable production storage remain unproven.\n\n"
            + "Internal lock_utc: "
            + lock_utc
            + "\n\nReceipt creation time: "
            + receipt_created_utc
            + "\n\nStorage reference: "
            + storage_ref
            + "\n"
        ).encode("utf-8")
        pre_attestation["lock_report.md"] = report
        evidence_hashes = {
            name: persist_checked(output / name, data)
            for name, data in sorted(pre_attestation.items())
        }
        manifest = {
            "schema_version": SCHEMA,
            "status": STATUS,
            "execution_mode": MODE,
            "repository": repository,
            "workflow_path": workflow_path,
            "workflow_name": workflow,
            "workflow_ref": workflow_ref,
            "git_ref": git_ref,
            "implementation_git_sha": implementation_git_sha,
            "github_run_id": github_run_id,
            "github_run_attempt": github_run_attempt,
            "run_id": run_id,
            "producer_shadow_manifest_sha256": sha256(shadow_manifest_bytes),
            "forecast_payload_sha256": payload_sha,
            "producer_receipt_sha256": receipt_contract.receipt_sha256(producer),
            "lock_receipt_sha256": receipt_contract.receipt_sha256(lock),
            "producer_execution_id": shadow_manifest["producer_run_id"],
            "forecast_generation_utc": shadow_manifest["forecast_generation_utc"],
            "internal_lock_utc": lock_utc,
            "lock_receipt_created_utc": receipt_created_utc,
            "storage_ref": storage_ref,
            "evidence_sha256": evidence_hashes,
            "synthetic_inputs": True,
            "exact_forecast_payload_bound": True,
            "gate2b4_lock_constructor_used": True,
            **{field: False for field in FALSE_FLAGS},
            "claim_limit": (
                "Synthetic shadow evidence only. GitHub attestation may later bind this "
                "manifest's bytes; it does not authenticate the internal lock clock, "
                "producer receipt, lock receipt, historical availability or storage durability."
            ),
        }
        persist_checked(
            output / "lock_execution_manifest.json", json_file_bytes(manifest)
        )
        return manifest
    except Exception as exc:
        final = output / "lock_execution_manifest.json"
        if final.exists():
            final.unlink()
        (output / "hold_report.md").write_text(
            "HOLD\n\n" + type(exc).__name__ + ": " + str(exc) + "\n",
            encoding="utf-8",
        )
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Synthetic forecast-lock shadow; no production publication."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--implementation-git-sha", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--github-run-attempt", required=True)
    args = parser.parse_args()
    result = run_lock_shadow(**vars(args))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
