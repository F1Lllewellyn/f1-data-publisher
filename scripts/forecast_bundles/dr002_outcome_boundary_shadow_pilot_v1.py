"""Build one synthetic outcome boundary from an accepted same-run lock shadow.

This wrapper creates unbound runtime evidence only. It does not authenticate an
outcome clock or publisher, observe a real result, verify a receipt graph, or
invoke any production path.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dr002_forecast_lock_shadow_pilot_v1 as lock_shadow
import dr002_lock_boundary_revision_v1 as boundary_contract
import verify_forecast_integrity_receipts_v1 as receipt_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_RUNTIME_ROOT = REPO_ROOT / "_runtime/dr002_pre2b7h_forecast_lock_shadow"
OUTCOME_RUNTIME_ROOT = REPO_ROOT / "_runtime/dr002_pre2b7i_outcome_boundary_shadow"
WORKFLOW_PATH = ".github/workflows/dr002-outcome-boundary-shadow-pilot.yml"
SCHEMA = "dr002-outcome-boundary-shadow-pilot-v1"
STATUS = "SHADOW_OUTCOME_BOUNDARY_ONLY_NOT_PRODUCTION"
MODE = "manual_github_synthetic_outcome_boundary_shadow"
SOURCE_ID = "synthetic:dr002:outcome_result"
SOURCE_URI = "synthetic://dr002/outcome-result/v1"
POLICY_REF = "synthetic:dr002:outcome-boundary-policy-v1"
IMPLEMENTATION = "scripts/forecast_bundles/dr002_outcome_boundary_shadow_pilot_v1.py"
FALSE_FLAGS = (
    "outcome_capture_externally_bound",
    "outcome_boundary_receipt_externally_bound",
    "outcome_clock_authenticated",
    "outcome_source_publisher_authenticated",
    "observation_completeness_proven",
    "revision_proof_completed",
    "durable_storage_proven",
    "full_gate2b1_chain_verified",
    "production_authenticated",
    "historical_availability_proven",
    "stable_engine_execution_proven",
    "blind_validation_eligible",
    "production_forecast_locked",
    "production_outcome_boundary_proven",
    "dr002_activated",
    "promotion_allowed",
)
SYNTHETIC_OUTCOME = {
    "classification": "SYNTHETIC_ONLY_NOT_REAL_RACE_RESULT",
    "event_id": lock_shadow.producer_shadow.EVENT_ID,
    "meeting_id": lock_shadow.producer_shadow.MEETING_ID,
    "result": [
        {"classified_position": 1, "driver_id": "synthetic-driver-01"},
        {"classified_position": 2, "driver_id": "synthetic-driver-02"},
    ],
    "session_id": lock_shadow.producer_shadow.SESSION_ID,
}
SYNTHETIC_OUTCOME_BYTES = receipt_contract.canonical_json_bytes(SYNTHETIC_OUTCOME) + b"\n"


class OutcomeBoundaryShadowError(ValueError):
    """HOLD: no successful outcome-boundary execution manifest."""


def require(condition, reason):
    if not condition:
        raise OutcomeBoundaryShadowError(reason)


def utcnow():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256(data):
    return receipt_contract.sha256(data)


def strict_json(data):
    def object_pairs(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate_json_key")
            value[key] = item
        return value

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


def verify_lock_shadow(run_id, implementation_git_sha):
    producer_root, producer_manifest, producer_manifest_bytes, forecast_bytes = (
        lock_shadow.verify_producer_shadow(run_id, implementation_git_sha)
    )
    root = LOCK_RUNTIME_ROOT / run_id
    require(root.is_dir() and not root.is_symlink(), "lock_shadow_missing")
    manifest_bytes = read_file(root / "lock_execution_manifest.json", root)
    manifest = strict_json(manifest_bytes)
    require(manifest.get("status") == lock_shadow.STATUS, "lock_shadow_not_successful")
    require(manifest.get("execution_mode") == lock_shadow.MODE, "lock_shadow_mode_mismatch")
    require(manifest.get("run_id") == run_id, "lock_shadow_run_mismatch")
    require(
        manifest.get("implementation_git_sha") == implementation_git_sha,
        "lock_shadow_head_mismatch",
    )
    require(
        manifest.get("producer_shadow_manifest_sha256") == sha256(producer_manifest_bytes),
        "producer_manifest_binding_mismatch",
    )
    for field in lock_shadow.FALSE_FLAGS:
        require(manifest.get(field) is False, "unsupported_lock_trust_claim")
    require("verified_receipt_bindings" not in manifest, "manufactured_verified_binding")
    require("engine_execution" not in manifest, "unexpected_engine_execution")

    expected_files = {
        "forecast_payload.csv",
        "producer_execution_receipt.json",
        "forecast_lock_receipt.json",
        "lock_report.md",
    }
    declared = manifest.get("evidence_sha256")
    require(isinstance(declared, dict) and set(declared) == expected_files, "lock_evidence_set_mismatch")
    evidence = {}
    for name, digest in declared.items():
        require(
            isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
            "malformed_lock_evidence_identity",
        )
        data = read_file(root / name, root)
        require(sha256(data) == digest, "lock_evidence_hash_mismatch")
        evidence[name] = data
    require(evidence["forecast_payload.csv"] == forecast_bytes, "same_run_payload_mismatch")

    producer = strict_json(evidence["producer_execution_receipt.json"])
    lock = strict_json(evidence["forecast_lock_receipt.json"])
    payload_sha = sha256(forecast_bytes)
    forecast = lock_shadow.build_forecast_manifest(
        producer_manifest, manifest["internal_lock_utc"], payload_sha
    )
    forecast["producer"] = {
        key: producer["payload"][key] for key in receipt_contract.PRODUCER_KEYS
    }
    rebuilt = boundary_contract.build_forecast_lock(
        forecast,
        producer,
        forecast_bytes,
        lock_utc=manifest["internal_lock_utc"],
        receipt_created_utc=manifest["lock_receipt_created_utc"],
        storage_ref=manifest["storage_ref"],
    )
    require(rebuilt == lock, "noncanonical_same_run_lock")
    require(
        receipt_contract.receipt_sha256(producer) == manifest["producer_receipt_sha256"]
        and receipt_contract.receipt_sha256(lock) == manifest["lock_receipt_sha256"],
        "lock_receipt_digest_mismatch",
    )
    return forecast, producer, producer_manifest_bytes, manifest_bytes


def source_capture_receipt(forecast, payload_sha, observed, created, capture_ref):
    payload = {
        "source_id": SOURCE_ID,
        "source_uri": SOURCE_URI,
        "source_sha256": payload_sha,
        "event_time_utc": None,
        "publisher_time_utc": None,
        "first_observed_utc": observed,
        "ingested_utc": observed,
        "capture_ref": capture_ref,
        "implementation": IMPLEMENTATION,
    }
    identity = {
        "receipt_type": "source_capture",
        "scope": {
            "event_id": forecast["event_id"],
            "meeting_id": forecast["meeting_id"],
            "session_id": forecast["session_id"],
        },
        "parent_receipt_ids": [],
        "payload": payload,
    }
    receipt = {
        "schema_version": receipt_contract.VERSION,
        "receipt_id": "source_capture:"
        + sha256(receipt_contract.canonical_json_bytes(identity)),
        "receipt_created_utc": created,
        **identity,
    }
    receipt_contract.validate_receipt_envelope(receipt)
    receipt_contract.verify_temporal_bindings(receipt)
    return receipt


def run_outcome_boundary_shadow(
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
    require(isinstance(github_run_id, str) and github_run_id.isdigit(), "invalid_github_run_id")
    require(
        isinstance(github_run_attempt, str) and github_run_attempt.isdigit(),
        "invalid_github_run_attempt",
    )
    require(run_id == "gha-" + github_run_id + "-" + github_run_attempt, "run_identity_mismatch")
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
    require(workflow and git_ref == "refs/heads/main", "invalid_workflow_or_ref")
    require(
        workflow_ref == repository + "/" + WORKFLOW_PATH + "@" + git_ref,
        "workflow_ref_mismatch",
    )
    forecast, producer, producer_manifest_bytes, lock_manifest_bytes = verify_lock_shadow(
        run_id, implementation_git_sha
    )
    observed = clock()
    capture_created = clock()
    boundary_created = clock()
    require(
        receipt_contract._time(observed)
        <= receipt_contract._time(capture_created)
        <= receipt_contract._time(boundary_created),
        "invalid_outcome_timeline",
    )

    OUTCOME_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    require(not OUTCOME_RUNTIME_ROOT.is_symlink(), "ambiguous_outcome_runtime_root")
    output = OUTCOME_RUNTIME_ROOT / run_id
    output.mkdir()
    try:
        payload_name = "synthetic_outcome_payload.json"
        capture_ref = (
            "artifact-relative:_runtime/dr002_pre2b7i_outcome_boundary_shadow/"
            + run_id
            + "/"
            + payload_name
        )
        payload_sha = sha256(SYNTHETIC_OUTCOME_BYTES)
        capture = source_capture_receipt(
            forecast, payload_sha, observed, capture_created, capture_ref
        )
        forecast_source_ids = {item["source_id"] for item in forecast["evidence"]}
        require(SOURCE_ID not in forecast_source_ids, "outcome_source_reuses_forecast_input")
        boundary = boundary_contract.build_outcome_boundary(
            forecast,
            producer,
            capture,
            outcome_session_id=forecast["session_id"],
            boundary_policy_ref=POLICY_REF,
            receipt_created_utc=boundary_created,
        )
        require(boundary["parent_receipt_ids"] == [capture["receipt_id"]], "boundary_parent_mismatch")
        require(
            boundary["payload"]["outcome_availability_boundary_utc"] == observed,
            "boundary_not_first_observed",
        )
        require(boundary["payload"]["boundary_policy_ref"] == POLICY_REF, "boundary_policy_mismatch")

        pre_attestation = {
            payload_name: SYNTHETIC_OUTCOME_BYTES,
            "outcome_source_capture_receipt.json": json_file_bytes(capture),
            "outcome_boundary_receipt.json": json_file_bytes(boundary),
        }
        report = (
            "# Synthetic outcome-boundary shadow\n\n"
            + STATUS
            + "\n\nThe exact synthetic outcome bytes are represented by a separate unbound "
            + "source-capture receipt and the unchanged Gate 2B-4 outcome-boundary "
            + "constructor. This is not a real result or authenticated observation.\n\n"
            + "Internal outcome first_observed_utc: "
            + observed
            + "\n\nInternal outcome receipt creation time: "
            + capture_created
            + "\n\nInternal boundary receipt creation time: "
            + boundary_created
            + "\n\nA future GitHub/Sigstore transparency-log time is separate and does not "
            + "authenticate any of these internal clocks.\n"
        ).encode("utf-8")
        pre_attestation["outcome_boundary_report.md"] = report
        evidence_hashes = {
            name: persist_checked(output / name, data)
            for name, data in sorted(pre_attestation.items())
        }
        manifest = {
            "schema_version": SCHEMA,
            "status": STATUS,
            "execution_mode": MODE,
            "repository": repository,
            "workflow_path": WORKFLOW_PATH,
            "workflow_name": workflow,
            "workflow_ref": workflow_ref,
            "git_ref": git_ref,
            "implementation_git_sha": implementation_git_sha,
            "github_run_id": github_run_id,
            "github_run_attempt": github_run_attempt,
            "run_id": run_id,
            "producer_shadow_manifest_sha256": sha256(producer_manifest_bytes),
            "lock_execution_manifest_sha256": sha256(lock_manifest_bytes),
            "synthetic_outcome_payload_sha256": payload_sha,
            "outcome_capture_receipt_sha256": receipt_contract.receipt_sha256(capture),
            "outcome_boundary_receipt_sha256": receipt_contract.receipt_sha256(boundary),
            "synthetic_first_observed_utc": observed,
            "outcome_capture_receipt_created_utc": capture_created,
            "outcome_boundary_receipt_created_utc": boundary_created,
            "outcome_availability_boundary_utc": boundary["payload"]["outcome_availability_boundary_utc"],
            "boundary_policy_ref": POLICY_REF,
            "evidence_sha256": evidence_hashes,
            "synthetic_outcome": True,
            "separate_synthetic_outcome_capture_constructed": True,
            "gate2b4_outcome_boundary_constructor_used": True,
            "boundary_equals_outcome_first_observed": True,
            **{field: False for field in FALSE_FLAGS},
            "claim_limit": (
                "Synthetic shadow construction only. A future GitHub attestation may bind "
                "this manifest's bytes; it cannot authenticate the internal outcome clock, "
                "publisher, observation completeness, receipts, or production enforcement."
            ),
        }
        persist_checked(
            output / "outcome_boundary_execution_manifest.json",
            json_file_bytes(manifest),
        )
        return manifest
    except Exception as exc:
        final = output / "outcome_boundary_execution_manifest.json"
        if final.exists():
            final.unlink()
        (output / "hold_report.md").write_text(
            "HOLD\n\n" + type(exc).__name__ + ": " + str(exc) + "\n",
            encoding="utf-8",
        )
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Synthetic outcome-boundary shadow; no production publication."
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
    result = run_outcome_boundary_shadow(**vars(args))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
