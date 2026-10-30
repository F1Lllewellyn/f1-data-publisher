"""Bind one verified GitHub attestation execution to one FIA capture manifest.

This pure offline boundary composes the existing GitHub custody bridge with the
execution identity recorded by the reusable FIA final-grid capture.  It does
not perform cryptographic verification, authenticate FIA, authenticate the
runner clock, or establish historical/prospective availability.
"""
import json
import re

from . import dr002_github_attestation_binding_v1 as bridge
from . import verify_forecast_integrity_receipts_v1 as receipts


VERSION = "dr002-fia-capture-attestation-execution-binding-v1"
CAPTURE_SCHEMA_VERSION = "dr002-fia-final-grid-capture-intake-v1"
CAPTURE_STATUS = "CAPTURED_UNBOUND_CANDIDATE"


class ExecutionBindingError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise ExecutionBindingError(code)


def _hold(code):
    return {
        "status": "HOLD",
        "reason_codes": [code],
        "verified_receipt_bindings": {},
        "trust_scope": bridge.TRUST_SCOPE,
        **bridge.HOLD_TRUST,
    }


def _strict_manifest(raw):
    _require(type(raw) is bytes, "capture_manifest_exact_bytes_required")

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    try:
        manifest = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ExecutionBindingError("nonfinite_json")
            ),
        )
        _require(isinstance(manifest, dict), "malformed_capture_manifest")
        canonical = receipts.canonical_json_bytes(manifest)
    except ExecutionBindingError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ExecutionBindingError("malformed_capture_manifest")
    _require(
        raw == canonical,
        "noncanonical_capture_manifest_bytes",
    )
    return manifest


def _manifest_execution(raw):
    manifest = _strict_manifest(raw)
    required = {
        "schema_version",
        "validation_status",
        "reason_codes",
        "run_id",
        "github_run_id",
        "github_run_attempt",
        "repository",
        "implementation_git_sha",
        "workflow_ref",
        "source_capture_receipt_sha256",
        "binding_status",
        "verified_receipt_bindings_created",
    }
    _require(
        required.issubset(manifest),
        "missing_capture_manifest_identity_field",
    )
    _require(
        manifest["schema_version"] == CAPTURE_SCHEMA_VERSION,
        "unsupported_capture_manifest_schema",
    )
    _require(
        manifest["validation_status"] == CAPTURE_STATUS
        and manifest["reason_codes"] == []
        and manifest["binding_status"] == "UNBOUND"
        and manifest["verified_receipt_bindings_created"] is False,
        "capture_manifest_not_successful_unbound_candidate",
    )

    repository = manifest["repository"]
    commit = manifest["implementation_git_sha"]
    workflow_ref = manifest["workflow_ref"]
    run_id = manifest["github_run_id"]
    attempt = manifest["github_run_attempt"]
    receipt_digest = manifest["source_capture_receipt_sha256"]
    _require(
        isinstance(repository, str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None
        and isinstance(commit, str)
        and re.fullmatch(r"[0-9a-f]{40}", commit) is not None
        and isinstance(workflow_ref, str)
        and isinstance(receipt_digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", receipt_digest) is not None,
        "malformed_capture_manifest_identity",
    )
    _require(
        isinstance(run_id, str)
        and re.fullmatch(r"[1-9][0-9]*", run_id) is not None
        and isinstance(attempt, str)
        and re.fullmatch(r"[1-9][0-9]*", attempt) is not None,
        "malformed_capture_manifest_run_identity",
    )

    signer_workflow, separator, source_ref = workflow_ref.rpartition("@")
    workflow_prefix = repository + "/.github/workflows/"
    _require(
        separator == "@"
        and source_ref == "refs/heads/main"
        and signer_workflow.startswith(workflow_prefix)
        and signer_workflow.endswith((".yml", ".yaml")),
        "malformed_capture_manifest_workflow_identity",
    )
    _require(
        manifest["run_id"] == "gha-" + run_id + "-" + attempt,
        "capture_manifest_run_identity_mismatch",
    )
    return {
        "repository": repository,
        "commit": commit,
        "signer_workflow": signer_workflow,
        "source_ref": source_ref,
        "run_id": run_id,
        "run_attempt": attempt,
        "receipt_digest": receipt_digest,
    }


def _attested_run(identity):
    prefix = (
        "https://github.com/"
        + identity["repository"]
        + "/actions/runs/"
    )
    value = identity["run_invocation_uri"]
    if not isinstance(value, str) or not value.startswith(prefix):
        return None, None
    match = re.fullmatch(r"([0-9]+)/attempts/([0-9]+)", value[len(prefix):])
    return match.groups() if match else (None, None)


def build_capture_bound_verified_github_receipt_binding(
    *,
    capture_manifest_bytes,
    receipt_bytes,
    attestation_bundle_bytes,
    verified_attestation_result,
    attested_identity,
    verification_ref,
):
    """Return the existing bridge envelope only for the manifest's execution.

    The caller-supplied verified result remains a trust interface.  The
    unchanged bridge first proves that the supplied attested identity is
    coherent with that result, its saved bundle, certificate and exact receipt
    subject.  This boundary then compares the bridge-validated identity to the
    capture manifest.  Any failure returns no receipt binding.
    """
    try:
        expected = _manifest_execution(capture_manifest_bytes)
    except (ExecutionBindingError, KeyError, TypeError, ValueError) as exc:
        return _hold(getattr(exc, "code", None) or "malformed_capture_manifest")

    result = bridge.build_verified_github_receipt_binding(
        receipt_bytes,
        attestation_bundle_bytes,
        verified_attestation_result,
        attested_identity,
        verification_ref,
    )
    if result.get("status") != "VERIFIED_GITHUB_PROVENANCE_BINDING":
        return result

    if result["exact_receipt_sha256"] != expected["receipt_digest"]:
        return _hold("capture_manifest_receipt_digest_mismatch")
    if attested_identity["repository"] != expected["repository"]:
        return _hold("capture_attestation_repository_mismatch")
    if (
        attested_identity["source_digest"] != expected["commit"]
        or attested_identity["signer_digest"] != expected["commit"]
    ):
        return _hold("capture_attestation_commit_mismatch")
    if (
        attested_identity["signer_workflow"] != expected["signer_workflow"]
        or attested_identity["source_ref"] != expected["source_ref"]
    ):
        return _hold("capture_attestation_workflow_mismatch")

    run_id, attempt = _attested_run(attested_identity)
    if run_id != expected["run_id"]:
        return _hold("capture_attestation_run_id_mismatch")
    if attempt != expected["run_attempt"]:
        return _hold("capture_attestation_run_attempt_mismatch")
    return result
