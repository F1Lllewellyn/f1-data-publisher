"""Construct one unbound synthetic post-cutoff revision shadow package.

This wrapper verifies the accepted same-run producer, lock, and outcome packages,
then uses the unchanged Gate 2B-4 constructors exactly once. It does not observe
a publisher, authenticate a clock, verify GitHub attestations, or invoke production.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dr002_outcome_boundary_shadow_pilot_v1 as outcome_shadow
import dr002_lock_boundary_revision_v1 as boundary_contract
import verify_forecast_integrity_receipts_v1 as receipt_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_RUNTIME_ROOT = REPO_ROOT / "_runtime/dr002_pre2b7h_forecast_lock_shadow"
OUTCOME_RUNTIME_ROOT = REPO_ROOT / "_runtime/dr002_pre2b7i_outcome_boundary_shadow"
REVISION_RUNTIME_ROOT = REPO_ROOT / "_runtime/dr002_pre2b7j_revision_shadow"
SCHEMA = "dr002-revision-shadow-pilot-v1"
STATUS = "SHADOW_POST_CUTOFF_REVISION_ONLY_NOT_PRODUCTION"
MODE = "manual_github_synthetic_post_cutoff_revision_shadow"
IMPLEMENTATION = "scripts/forecast_bundles/dr002_revision_shadow_pilot_v1.py"
SYNTHETIC_REVISED_SOURCE = {
    "classification": "SYNTHETIC_POST_CUTOFF_REVISION_NOT_REAL_PUBLISHER_REVISION",
    "event_id": outcome_shadow.lock_shadow.producer_shadow.EVENT_ID,
    "meeting_id": outcome_shadow.lock_shadow.producer_shadow.MEETING_ID,
    "session_id": outcome_shadow.lock_shadow.producer_shadow.SESSION_ID,
    "source_id": "synthetic:dr002:drivers",
    "source_uri": "runtime-artifact:evidence/drivers.csv",
    "synthetic_change": "Synthetic driver-source bytes changed after forecast cutoff.",
}
SYNTHETIC_REVISED_SOURCE_BYTES = (
    receipt_contract.canonical_json_bytes(SYNTHETIC_REVISED_SOURCE) + b"\n"
)
FALSE_FLAGS = (
    "revision_capture_externally_bound",
    "revision_receipt_externally_bound",
    "revision_clock_authenticated",
    "revision_source_publisher_authenticated",
    "observation_completeness_proven",
    "revision_completeness_proven",
    "revision_proof_completed",
    "durable_storage_proven",
    "full_gate2b1_chain_verified",
    "production_authenticated",
    "historical_availability_proven",
    "stable_engine_execution_proven",
    "blind_validation_eligible",
    "production_forecast_locked",
    "production_outcome_boundary_proven",
    "production_revision_tracking_proven",
    "dr002_activated",
    "promotion_allowed",
)


class RevisionShadowError(ValueError):
    """HOLD: no successful revision execution manifest."""


def require(condition, reason):
    if not condition:
        raise RevisionShadowError(reason)


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


def source_capture_receipt(forecast, source, payload_sha, observed, created, capture_ref):
    payload = {
        "source_id": source["source_id"],
        "source_uri": source["source_uri"],
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
            "event_id": source["event_id"],
            "meeting_id": source["meeting_id"],
            "session_id": source["session_id"],
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


def verify_same_run_chain(
    run_id,
    implementation_git_sha,
    repository,
    workflow,
    workflow_ref,
    git_ref,
    github_run_id,
    github_run_attempt,
):
    caller_path = outcome_shadow.lock_shadow.validate_workflow_ref(
        workflow_ref, repository, git_ref
    )
    forecast, producer, producer_manifest_bytes, lock_manifest_bytes = (
        outcome_shadow.verify_lock_shadow(
            run_id,
            implementation_git_sha,
            repository,
            workflow,
            workflow_ref,
            git_ref,
            github_run_id,
            github_run_attempt,
        )
    )
    lock_root = LOCK_RUNTIME_ROOT / run_id
    lock_bytes = read_file(lock_root / "forecast_lock_receipt.json", lock_root)
    lock = strict_json(lock_bytes)

    root = OUTCOME_RUNTIME_ROOT / run_id
    require(root.is_dir() and not root.is_symlink(), "outcome_shadow_missing")
    manifest_bytes = read_file(root / "outcome_boundary_execution_manifest.json", root)
    manifest = strict_json(manifest_bytes)
    require(manifest.get("status") == outcome_shadow.STATUS, "outcome_shadow_not_successful")
    require(manifest.get("execution_mode") == outcome_shadow.MODE, "outcome_shadow_mode_mismatch")
    expected_identity = {
        "repository": repository,
        "workflow_path": caller_path,
        "workflow_name": workflow,
        "workflow_ref": workflow_ref,
        "git_ref": git_ref,
        "implementation_git_sha": implementation_git_sha,
        "github_run_id": github_run_id,
        "github_run_attempt": github_run_attempt,
        "run_id": run_id,
    }
    require(
        all(manifest.get(key) == value for key, value in expected_identity.items()),
        "outcome_shadow_identity_mismatch",
    )
    require(
        manifest.get("producer_shadow_manifest_sha256") == sha256(producer_manifest_bytes)
        and manifest.get("lock_execution_manifest_sha256") == sha256(lock_manifest_bytes),
        "outcome_predecessor_binding_mismatch",
    )
    for field in outcome_shadow.FALSE_FLAGS:
        require(manifest.get(field) is False, "unsupported_outcome_trust_claim")
    require("verified_receipt_bindings" not in manifest, "manufactured_verified_binding")
    require("engine_execution" not in manifest, "unexpected_engine_execution")

    expected_files = {
        "synthetic_outcome_payload.json",
        "outcome_source_capture_receipt.json",
        "outcome_boundary_receipt.json",
        "outcome_boundary_report.md",
    }
    declared = manifest.get("evidence_sha256")
    require(isinstance(declared, dict) and set(declared) == expected_files, "outcome_evidence_set_mismatch")
    evidence = {}
    for name, digest in declared.items():
        require(
            isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
            "malformed_outcome_evidence_identity",
        )
        data = read_file(root / name, root)
        require(sha256(data) == digest, "outcome_evidence_hash_mismatch")
        evidence[name] = data
    require(
        evidence["synthetic_outcome_payload.json"] == outcome_shadow.SYNTHETIC_OUTCOME_BYTES,
        "synthetic_outcome_bytes_mismatch",
    )
    capture = strict_json(evidence["outcome_source_capture_receipt.json"])
    boundary = strict_json(evidence["outcome_boundary_receipt.json"])
    require(
        capture["payload"]["source_sha256"]
        == sha256(evidence["synthetic_outcome_payload.json"])
        == manifest.get("synthetic_outcome_payload_sha256"),
        "outcome_payload_binding_mismatch",
    )
    rebuilt = boundary_contract.build_outcome_boundary(
        forecast,
        producer,
        capture,
        outcome_session_id=forecast["session_id"],
        boundary_policy_ref=manifest["boundary_policy_ref"],
        receipt_created_utc=manifest["outcome_boundary_receipt_created_utc"],
    )
    require(rebuilt == boundary, "noncanonical_same_run_outcome_boundary")
    require(
        receipt_contract.receipt_sha256(capture) == manifest["outcome_capture_receipt_sha256"]
        and receipt_contract.receipt_sha256(boundary)
        == manifest["outcome_boundary_receipt_sha256"],
        "outcome_receipt_digest_mismatch",
    )
    return (
        caller_path,
        forecast,
        producer,
        lock,
        boundary,
        producer_manifest_bytes,
        lock_manifest_bytes,
        manifest_bytes,
    )


def run_revision_shadow(
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
    (
        caller_path,
        forecast,
        producer,
        lock,
        boundary,
        producer_manifest_bytes,
        lock_manifest_bytes,
        outcome_manifest_bytes,
    ) = verify_same_run_chain(
        run_id,
        implementation_git_sha,
        repository,
        workflow,
        workflow_ref,
        git_ref,
        github_run_id,
        github_run_attempt,
    )
    selected = min(forecast["evidence"], key=lambda item: item["source_id"])
    require(
        selected["source_id"] == SYNTHETIC_REVISED_SOURCE["source_id"]
        and selected["source_uri"] == SYNTHETIC_REVISED_SOURCE["source_uri"],
        "fixed_revision_source_mismatch",
    )
    require(
        selected["event_id"] == SYNTHETIC_REVISED_SOURCE["event_id"]
        and selected["meeting_id"] == SYNTHETIC_REVISED_SOURCE["meeting_id"]
        and selected["session_id"] == SYNTHETIC_REVISED_SOURCE["session_id"],
        "fixed_revision_scope_mismatch",
    )
    payload_sha = sha256(SYNTHETIC_REVISED_SOURCE_BYTES)
    require(payload_sha != selected["source_sha256"], "synthetic_revision_matches_original")
    observed = clock()
    capture_created = clock()
    revision_created = clock()
    require(
        receipt_contract._time(observed) > receipt_contract._time(forecast["evidence_cutoff_utc"]),
        "revision_not_after_forecast_cutoff",
    )
    require(
        receipt_contract._time(observed)
        <= receipt_contract._time(capture_created)
        <= receipt_contract._time(revision_created),
        "invalid_revision_timeline",
    )

    REVISION_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    require(not REVISION_RUNTIME_ROOT.is_symlink(), "ambiguous_revision_runtime_root")
    output = REVISION_RUNTIME_ROOT / run_id
    output.mkdir()
    try:
        payload_name = "synthetic_revised_source_payload.json"
        capture_ref = (
            "artifact-relative:_runtime/dr002_pre2b7j_revision_shadow/"
            + run_id
            + "/"
            + payload_name
        )
        capture = source_capture_receipt(
            forecast, selected, payload_sha, observed, capture_created, capture_ref
        )
        revision, declaration = boundary_contract.build_revision(
            forecast, capture, receipt_created_utc=revision_created
        )
        require(revision["parent_receipt_ids"] == [capture["receipt_id"]], "revision_parent_mismatch")
        require(
            revision["payload"]["source_id"] == capture["payload"]["source_id"]
            and revision["payload"]["source_sha256"] == capture["payload"]["source_sha256"]
            and revision["payload"]["first_observed_utc"]
            == capture["payload"]["first_observed_utc"],
            "revision_capture_binding_mismatch",
        )
        require(
            receipt_contract._time(revision["receipt_created_utc"])
            >= receipt_contract._time(capture["receipt_created_utc"]),
            "revision_before_parent_capture",
        )
        completed = boundary_contract.complete_forecast_record(
            forecast, producer, lock, boundary, [declaration]
        )
        require(all(completed[key] == value for key, value in forecast.items()), "original_forecast_changed")
        require(completed.get("revisions") == [declaration], "single_revision_declaration_mismatch")
        require(
            boundary_contract.input_manifest_sha256(completed)
            == producer["payload"]["input_manifest_sha256"],
            "producer_input_manifest_identity_changed",
        )

        evidence = {
            payload_name: SYNTHETIC_REVISED_SOURCE_BYTES,
            "revised_source_capture_receipt.json": json_file_bytes(capture),
            "revision_receipt.json": json_file_bytes(revision),
            "completed_forecast_record.json": json_file_bytes(completed),
        }
        report = (
            "# Synthetic post-cutoff revision shadow\n\n"
            + STATUS
            + "\n\nExactly one fixed synthetic revised-source payload was bound to the "
            + "deterministically selected forecast input source, constructed with the "
            + "unchanged Gate 2B-4 revision constructor, and added to a completed "
            + "forecast record. This is not a real publisher revision or completeness proof.\n\n"
            + "Selected source: "
            + selected["source_id"]
            + "\n\nForecast evidence cutoff: "
            + forecast["evidence_cutoff_utc"]
            + "\n\nSynthetic first observed: "
            + observed
            + "\n"
        ).encode("utf-8")
        evidence["revision_report.md"] = report
        evidence_hashes = {
            name: persist_checked(output / name, data)
            for name, data in sorted(evidence.items())
        }
        manifest = {
            "schema_version": SCHEMA,
            "status": STATUS,
            "execution_mode": MODE,
            "repository": repository,
            "workflow_path": caller_path,
            "workflow_name": workflow,
            "workflow_ref": workflow_ref,
            "git_ref": git_ref,
            "implementation_git_sha": implementation_git_sha,
            "github_run_id": github_run_id,
            "github_run_attempt": github_run_attempt,
            "run_id": run_id,
            "producer_shadow_manifest_sha256": sha256(producer_manifest_bytes),
            "lock_execution_manifest_sha256": sha256(lock_manifest_bytes),
            "outcome_execution_manifest_sha256": sha256(outcome_manifest_bytes),
            "selected_original_source_id": selected["source_id"],
            "selected_original_source_uri": selected["source_uri"],
            "selected_original_source_sha256": selected["source_sha256"],
            "synthetic_revised_source_payload_sha256": evidence_hashes[payload_name],
            "revised_source_capture_receipt_sha256": evidence_hashes["revised_source_capture_receipt.json"],
            "revision_receipt_sha256": evidence_hashes["revision_receipt.json"],
            "completed_forecast_record_sha256": evidence_hashes["completed_forecast_record.json"],
            "revised_first_observed_utc": observed,
            "forecast_evidence_cutoff_utc": forecast["evidence_cutoff_utc"],
            "evidence_sha256": evidence_hashes,
            "revision_after_forecast_cutoff": True,
            "single_synthetic_revision_constructed": True,
            "gate2b4_revision_constructor_used": True,
            "completed_forecast_record_bound": True,
            **{field: False for field in FALSE_FLAGS},
            "claim_limit": (
                "One unbound synthetic post-cutoff revision only. A future GitHub "
                "attestation may bind this manifest's bytes; it cannot authenticate the "
                "internal clock, publisher, completeness, receipts, or production tracking."
            ),
        }
        persist_checked(output / "revision_execution_manifest.json", json_file_bytes(manifest))
        return manifest
    except Exception as exc:
        final = output / "revision_execution_manifest.json"
        if final.exists():
            final.unlink()
        (output / "hold_report.md").write_text(
            "HOLD\n\n" + type(exc).__name__ + ": " + str(exc) + "\n",
            encoding="utf-8",
        )
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Synthetic post-cutoff revision shadow; no production publication."
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
    result = run_revision_shadow(**vars(args))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
