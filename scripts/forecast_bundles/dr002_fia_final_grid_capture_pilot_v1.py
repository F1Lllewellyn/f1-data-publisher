"""Manual-only fixed FIA final-grid exact-byte capture shadow.

The CLI is intentionally fixed to the historical 2026 Australian Grand Prix
Final Starting Grid, Doc 55.  It performs one request with no retry and emits
only an UNBOUND source-capture candidate.  It does not parse grid positions,
authenticate FIA authorship, prove historical availability, or run a producer.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import sys
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dr002_fia_grid_document_candidate_v1 import (  # noqa: E402
    VALIDATED_STATUS as CANDIDATE_VALIDATED_STATUS,
    assess_fia_grid_document_candidate,
)
from verify_forecast_integrity_receipts_v1 import (  # noqa: E402
    VERSION as RECEIPT_VERSION,
    ReceiptError,
    canonical_json_bytes,
    receipt_sha256,
    sha256,
    validate_receipt_envelope,
    verify_temporal_bindings,
)


PDF_URI = (
    "https://www.fia.com/system/files/decision-document/"
    "2026_australian_grand_prix_-_final_starting_grid.pdf"
)
INDEX_URI = (
    "https://www.fia.com/documents/championships/"
    "fia-formula-one-world-championship-14/event/Australian%20Grand%20Prix"
)
DOCUMENT_TYPE = "final_starting_grid"
DOCUMENT_NUMBER = 55
DOCUMENT_TITLE = "Final Starting Grid"
CLAIMED_PUBLISHED_UTC = "2026-03-08T03:00:00Z"
SCOPE = {
    "event_id": "fia:2026:australian-grand-prix",
    "meeting_id": "fia:2026:australian-grand-prix:meeting",
    "session_id": "fia:2026:australian-grand-prix:race",
}
IMPLEMENTATION = "scripts/forecast_bundles/dr002_fia_final_grid_capture_pilot_v1.py"
WORKFLOW_PATH = ".github/workflows/dr002-fia-final-grid-capture-shadow.yml"
REPOSITORY = "F1Lllewellyn/f1-data-publisher"
ROOT = Path("_runtime/dr002_fia_final_grid_capture_shadow")
MAX_BODY_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 30

DEPENDENCY_PINS = {
    "scripts/forecast_bundles/dr002_fia_grid_document_candidate_v1.py":
        "15867e3d1af56a5c00b2bd35c1220541e7e4f619",
    "docs/DR002_PRE2B7K4R11_FIA_GRID_DOCUMENT_CANDIDATE_CONTRACT_2026-10-09.md":
        "54efa78ccf72efee9d58f34d330076b562d9b803",
    "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
        "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
    ".github/workflows/dr002-capture-provenance-pilot.yml":
        "883fcbc1a00ec9ae1dd6dd40423a03af05ae1fe3",
    "scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py":
        "b9b1f9acc1be30d5b7cdf42424853e3d652b9466",
    "scripts/forecast_bundles/dr002_github_attestation_binding_v1.py":
        "215f012b79aa9e6f33aff6ad62ca7efba53a9627",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
}

AUTHORIZED_PATHS = frozenset({
    "scripts/forecast_bundles/dr002_fia_final_grid_capture_pilot_v1.py",
    "tests/test_dr002_fia_final_grid_capture_pilot_v1.py",
    ".github/workflows/dr002-fia-final-grid-capture-shadow.yml",
    "docs/DR002_PRE2B7K4R12_FIA_FINAL_GRID_CAPTURE_ATTESTATION_SHADOW_2026-10-09.md",
})

FALSE_CLAIMS = {
    "production_authenticated": False,
    "official_source_authenticated": False,
    "official_starting_grid_verified": False,
    "grid_positions_extracted": False,
    "historical_availability_verified": False,
    "dr002_activated": False,
    "promotion_allowed": False,
}


class CaptureError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def require(condition, code):
    if not condition:
        raise CaptureError(code)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc(value):
    require(
        isinstance(value, str)
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value) is not None,
        "invalid_utc",
    )
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise CaptureError("invalid_utc")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _content_length(headers):
    value = headers.get("Content-Length")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def transport():
    """Perform the one fixed GET.  No redirect, retry, range, cookie or auth."""
    request = Request(
        PDF_URI,
        method="GET",
        headers={
            "Accept": "application/pdf",
            "Accept-Encoding": "identity",
            "User-Agent": "f1-data-publisher-dr002-fia-grid-shadow/1",
        },
    )
    opener = build_opener(_NoRedirect)
    try:
        response = opener.open(request, timeout=TIMEOUT_SECONDS)
    except HTTPError as exc:
        return {
            "status": exc.code,
            "body": b"",
            "content_type": exc.headers.get("Content-Type", ""),
            "content_length": _content_length(exc.headers),
            "final_url": exc.geturl(),
            "complete": False,
            "redirected": 300 <= exc.code < 400 or exc.geturl() != PDF_URI,
        }
    with response:
        chunks = []
        total = 0
        complete = False
        while total <= MAX_BODY_BYTES:
            chunk = response.read(min(64 * 1024, MAX_BODY_BYTES + 1 - total))
            if not chunk:
                complete = True
                break
            chunks.append(chunk)
            total += len(chunk)
        body = b"".join(chunks)
        final_url = response.geturl()
        return {
            "status": response.status,
            "body": body,
            "content_type": response.headers.get("Content-Type", ""),
            "content_length": _content_length(response.headers),
            "final_url": final_url,
            "complete": complete,
            "redirected": final_url != PDF_URI,
        }


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def rename_path(source, target):
    source.rename(target)


def _validate_runtime_identity(github_run_id, github_run_attempt, repository, git_commit, workflow_ref):
    require(isinstance(github_run_id, str) and re.fullmatch(r"[1-9]\d*", github_run_id), "invalid_run_id")
    require(
        isinstance(github_run_attempt, str) and re.fullmatch(r"[1-9]\d*", github_run_attempt),
        "invalid_run_attempt",
    )
    require(repository == REPOSITORY, "unexpected_repository")
    require(isinstance(git_commit, str) and re.fullmatch(r"[0-9a-f]{40}", git_commit), "invalid_git_commit")
    expected_workflow_ref = REPOSITORY + "/" + WORKFLOW_PATH + "@refs/heads/main"
    require(workflow_ref == expected_workflow_ref, "unexpected_workflow_ref")


def _response_body(response):
    required = {
        "status", "body", "content_type", "content_length", "final_url", "complete", "redirected"
    }
    require(isinstance(response, dict) and set(response) == required, "malformed_transport_result")
    require(response["redirected"] is False and response["final_url"] == PDF_URI, "redirect_or_url_change")
    require(response["status"] == 200, "http_status_not_200")
    require(response["complete"] is True, "incomplete_response_body")
    body = response["body"]
    require(isinstance(body, bytes) and bool(body), "empty_or_invalid_response_bytes")
    require(len(body) <= MAX_BODY_BYTES, "response_body_too_large")
    length = response["content_length"]
    if length is not None:
        require(isinstance(length, int) and not isinstance(length, bool) and length >= 0,
                "invalid_content_length")
        require(length == len(body), "content_length_mismatch_or_truncation")
    content_type = response["content_type"]
    require(isinstance(content_type, str), "invalid_content_type")
    media_type = content_type.split(";", 1)[0].strip().casefold()
    require(media_type == "application/pdf", "invalid_content_type")
    return body


def _base_manifest(run_id, github_run_id, github_run_attempt, repository, git_commit, workflow_ref, root):
    raw_path = root / "raw/fia_final_starting_grid_doc_55.pdf"
    receipt_path = root / "source_capture_receipt.json"
    return {
        "schema_version": "dr002-fia-final-grid-capture-shadow-v1",
        "validation_status": "HOLD",
        "reason_codes": [],
        "run_id": run_id,
        "github_run_id": github_run_id,
        "github_run_attempt": github_run_attempt,
        "repository": repository,
        "implementation_git_sha": git_commit,
        "workflow_ref": workflow_ref,
        "implementation": IMPLEMENTATION,
        "request_uri": PDF_URI,
        "official_index_uri": INDEX_URI,
        "http_method": "GET",
        "http_get_count": 0,
        "http_status": None,
        "http_content_type": None,
        "http_declared_content_length": None,
        "request_started_utc": None,
        "response_completed_utc": None,
        "first_observed_utc": None,
        "ingested_utc": None,
        "receipt_created_utc": None,
        "shadow_review_cutoff_utc": None,
        "document_type": DOCUMENT_TYPE,
        "document_number": DOCUMENT_NUMBER,
        "document_title": DOCUMENT_TITLE,
        "claimed_published_utc": CLAIMED_PUBLISHED_UTC,
        **SCOPE,
        "raw_artifact_path": raw_path.as_posix(),
        "raw_document_sha256": None,
        "raw_document_size_bytes": 0,
        "readback_sha256": None,
        "readback_verified": False,
        "candidate_status": None,
        "candidate_id": None,
        "candidate_content_version_id": None,
        "claimed_source_id": None,
        "receipt_path": None,
        "source_capture_receipt_id": None,
        "source_capture_receipt_sha256": None,
        "binding_status": "UNBOUND",
        "verified_receipt_bindings_created": False,
        **FALSE_CLAIMS,
    }


def _receipt(candidate, source_sha256, first_observed, ingested, created, capture_ref):
    source_id = candidate["claimed_source_id"]
    identity = {
        "source_id": source_id,
        **SCOPE,
        "source_sha256": source_sha256,
        "first_observed_utc": first_observed,
    }
    return {
        "schema_version": RECEIPT_VERSION,
        "receipt_id": "source_capture:" + sha256(canonical_json_bytes(identity)),
        "receipt_type": "source_capture",
        "receipt_created_utc": created,
        "scope": dict(SCOPE),
        "parent_receipt_ids": [],
        "payload": {
            "source_id": source_id,
            "source_uri": PDF_URI,
            "source_sha256": source_sha256,
            "event_time_utc": None,
            "publisher_time_utc": CLAIMED_PUBLISHED_UTC,
            "first_observed_utc": first_observed,
            "ingested_utc": ingested,
            "capture_ref": capture_ref,
            "implementation": IMPLEMENTATION,
        },
    }


def _report(manifest):
    reasons = ", ".join(manifest["reason_codes"]) if manifest["reason_codes"] else "none"
    return (
        "# DR-002 manual FIA final-grid capture shadow\n\n"
        "Status: " + manifest["validation_status"] + "\n\n"
        "Fixed target: 2026 Australian Grand Prix Final Starting Grid, Doc 55.\n\n"
        "This is post-event, UNBOUND and unauthenticated. It proves neither FIA authorship nor "
        "historical pre-race availability, and it extracts no grid positions.\n\n"
        "Reason codes: " + reasons + "\n"
    ).encode("utf-8")


def _persist_manifest(staging_root, manifest, writer, reader):
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_path = staging_root / "capture_manifest.json"
    writer(manifest_path, manifest_bytes)
    require(reader(manifest_path) == manifest_bytes, "capture_manifest_readback_mismatch")
    report_bytes = _report(manifest)
    report_path = staging_root / "capture_report.md"
    writer(report_path, report_bytes)
    require(reader(report_path) == report_bytes, "capture_report_readback_mismatch")


def capture(
    *,
    github_run_id,
    github_run_attempt,
    repository,
    git_commit,
    workflow_ref,
    request=transport,
    clock=utc_now,
    writer=write_bytes,
    reader=lambda path: path.read_bytes(),
    renamer=rename_path,
    runtime_root=ROOT,
):
    """Run one injected-or-fixed capture and atomically publish one runtime directory."""
    _validate_runtime_identity(github_run_id, github_run_attempt, repository, git_commit, workflow_ref)
    run_id = "gha-" + github_run_id + "-" + github_run_attempt
    runtime_root = Path(runtime_root)
    final_root = runtime_root / run_id
    staging_root = runtime_root / ("pending-" + run_id)
    if final_root.exists() or staging_root.exists():
        raise FileExistsError("exclusive_run_directory_exists")
    staging_root.mkdir(parents=True, exist_ok=False)
    manifest = _base_manifest(
        run_id, github_run_id, github_run_attempt, repository, git_commit, workflow_ref, final_root
    )
    receipt_candidate = staging_root / "receipt_candidate.diagnostic.json"
    staged_receipt = staging_root / "source_capture_receipt.json"
    candidate_manifest_path = staging_root / "source_candidate_manifest.json"
    manifest_path = staging_root / "capture_manifest.json"
    report_path = staging_root / "capture_report.md"
    try:
        manifest["request_started_utc"] = clock()
        manifest["http_get_count"] = 1
        response = request()
        manifest["response_completed_utc"] = clock()
        if isinstance(response, dict):
            manifest["http_status"] = response.get("status")
            manifest["http_content_type"] = response.get("content_type")
            manifest["http_declared_content_length"] = response.get("content_length")
        body = _response_body(response)
        manifest["first_observed_utc"] = manifest["response_completed_utc"]
        raw_staged = staging_root / "raw/fia_final_starting_grid_doc_55.pdf"
        writer(raw_staged, body)
        source_digest = sha256(body)
        readback_digest = sha256(reader(raw_staged))
        manifest.update(
            raw_document_sha256=source_digest,
            raw_document_size_bytes=len(body),
            readback_sha256=readback_digest,
        )
        require(readback_digest == source_digest, "raw_document_readback_hash_mismatch")
        manifest["readback_verified"] = True
        manifest["ingested_utc"] = clock()
        manifest["receipt_created_utc"] = clock()
        manifest["shadow_review_cutoff_utc"] = manifest["receipt_created_utc"]
        ordered = [
            parse_utc(manifest[name])
            for name in (
                "request_started_utc", "first_observed_utc", "ingested_utc", "receipt_created_utc"
            )
        ]
        require(ordered == sorted(ordered), "invalid_capture_time_order")

        assessment = assess_fia_grid_document_candidate(
            raw_document_bytes=body,
            document_type=DOCUMENT_TYPE,
            document_number=DOCUMENT_NUMBER,
            document_title=DOCUMENT_TITLE,
            document_uri=PDF_URI,
            official_index_uri=INDEX_URI,
            event_id=SCOPE["event_id"],
            meeting_id=SCOPE["meeting_id"],
            session_id=SCOPE["session_id"],
            published_utc=CLAIMED_PUBLISHED_UTC,
            first_observed_utc=manifest["first_observed_utc"],
            ingested_utc=manifest["ingested_utc"],
            receipt_created_utc=manifest["receipt_created_utc"],
            forecast_cutoff_utc=manifest["shadow_review_cutoff_utc"],
        )
        manifest["candidate_status"] = assessment["status"]
        require(assessment["status"] == CANDIDATE_VALIDATED_STATUS, "fia_candidate_hold")
        require(all(value is False for value in assessment["claim_flags"].values()),
                "candidate_claim_ceiling_violated")
        candidate = assessment["document_candidate"]
        manifest.update(
            candidate_id=candidate["candidate_id"],
            candidate_content_version_id=candidate["content_version_id"],
            claimed_source_id=candidate["claimed_source_id"],
        )
        receipt = _receipt(
            candidate,
            source_digest,
            manifest["first_observed_utc"],
            manifest["ingested_utc"],
            manifest["receipt_created_utc"],
            manifest["raw_artifact_path"],
        )
        validate_receipt_envelope(receipt)
        verify_temporal_bindings(receipt)
        receipt_bytes = canonical_json_bytes(receipt)
        require(receipt_sha256(receipt) == sha256(receipt_bytes), "receipt_digest_mismatch")
        writer(receipt_candidate, receipt_bytes)
        require(reader(receipt_candidate) == receipt_bytes, "receipt_readback_mismatch")

        candidate_manifest = {
            "schema_version": "dr002-fia-final-grid-source-candidate-manifest-v1",
            "candidate_status": assessment["status"],
            "candidate": candidate,
            "claim_flags": assessment["claim_flags"],
            "evidence_chain_status": assessment["evidence_chain_status"],
            "source_capture_receipt_id": receipt["receipt_id"],
            "source_capture_receipt_sha256": sha256(receipt_bytes),
            "binding_status": "UNBOUND",
            "shadow_review_cutoff_label": "POST_EVENT_SHADOW_ASSESSMENT_ONLY",
        }
        candidate_manifest_bytes = canonical_json_bytes(candidate_manifest)
        writer(candidate_manifest_path, candidate_manifest_bytes)
        require(reader(candidate_manifest_path) == candidate_manifest_bytes,
                "source_candidate_manifest_readback_mismatch")
        renamer(receipt_candidate, staged_receipt)
        require(reader(staged_receipt) == receipt_bytes, "published_receipt_readback_mismatch")
        manifest.update(
            validation_status="CAPTURED_UNBOUND_CANDIDATE",
            receipt_path=(final_root / "source_capture_receipt.json").as_posix(),
            source_capture_receipt_id=receipt["receipt_id"],
            source_capture_receipt_sha256=sha256(receipt_bytes),
        )
        _persist_manifest(staging_root, manifest, writer, reader)
    except (CaptureError, ReceiptError, OSError, KeyError, TypeError, ValueError) as exc:
        manifest["validation_status"] = "HOLD"
        manifest["reason_codes"] = [getattr(exc, "code", str(exc) or "capture_failed")]
        manifest["candidate_id"] = None
        manifest["candidate_content_version_id"] = None
        manifest["claimed_source_id"] = None
        manifest["receipt_path"] = None
        manifest["source_capture_receipt_id"] = None
        manifest["source_capture_receipt_sha256"] = None
        for path in (
            receipt_candidate,
            staged_receipt,
            candidate_manifest_path,
            manifest_path,
            report_path,
        ):
            path.unlink(missing_ok=True)
        try:
            _persist_manifest(staging_root, manifest, writer, reader)
        except (CaptureError, OSError, TypeError, ValueError) as diagnostic_exc:
            manifest["reason_codes"].append(
                "diagnostic_persistence_failed:" + (str(diagnostic_exc) or type(diagnostic_exc).__name__)
            )
    renamer(staging_root, final_root)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--github-run-attempt", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--implementation-git-sha", required=True)
    parser.add_argument("--workflow-ref", required=True)
    args = parser.parse_args()
    result = capture(
        github_run_id=args.github_run_id,
        github_run_attempt=args.github_run_attempt,
        repository=args.repository,
        git_commit=args.implementation_git_sha,
        workflow_ref=args.workflow_ref,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["validation_status"] == "CAPTURED_UNBOUND_CANDIDATE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
