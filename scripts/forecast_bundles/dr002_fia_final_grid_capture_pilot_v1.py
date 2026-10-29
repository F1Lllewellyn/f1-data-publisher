"""Fail-closed FIA final-grid exact-byte capture/intake boundary.

The CLI is intentionally fixed to the historical 2026 Australian Grand Prix
Final Starting Grid, Doc 55.  It performs one request with no retry and emits
only an UNBOUND source-capture candidate.  A programmatic boundary additionally
accepts an exact, caller-pinned capture profile for other events while preserving
the same one-request transport and trust ceiling.  Neither path parses grid
positions, authenticates FIA authorship, proves historical availability,
establishes forecast-cutoff eligibility, or runs a producer.
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
    _canonical_fia_uri,
    _scope_valid,
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
CAPTURE_PROFILE_SCHEMA_VERSION = "dr002-fia-final-grid-capture-profile-v1"
CAPTURE_INTAKE_SCHEMA_VERSION = "dr002-fia-final-grid-capture-intake-v1"
MAX_CAPTURE_PROFILE_BYTES = 64 * 1024
MAX_PRIOR_RECEIPTS = 64

_CAPTURE_PROFILE_FIELDS = {
    "schema_version", "profile_id", "document_type", "document_number",
    "document_title", "document_uri", "official_index_uri", "event_id",
    "meeting_id", "session_id", "claimed_published_utc",
    "publication_evidence", "expected_document_sha256",
}
_PUBLICATION_EVIDENCE_FIELDS = {
    "official_index_uri", "claimed_published_utc", "index_publication_text",
    "document_header_date", "document_header_time",
}

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

INTAKE_PREDECESSOR_PINS = {
    "scripts/forecast_bundles/dr002_fia_final_grid_capture_pilot_v1.py":
        "b8e017e247954e0955285e8910a145fe4ee89d52",
    "tests/test_dr002_fia_final_grid_capture_pilot_v1.py":
        "941d335cb76c0ebf4c5d9255bbe005bc858e4375",
}

INTAKE_DEPENDENCY_PINS = {
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
    "scripts/forecast_bundles/dr002_fia_grid_document_candidate_v1.py":
        "15867e3d1af56a5c00b2bd35c1220541e7e4f619",
    "scripts/forecast_bundles/dr002_verified_source_consumer_v1.py":
        "e402939202ed579c368499f3baefb3641de27de7",
    "scripts/forecast_bundles/dr002_github_attestation_binding_v1.py":
        "215f012b79aa9e6f33aff6ad62ca7efba53a9627",
    "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
        "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
    "scripts/forecast_bundles/dr002_fia_final_grid_provenance_verifier_v1.py":
        "2f9f2266a87f8a2a743bc64a55fd0bd7f8fba204",
    "scripts/session_data_processor/session_data_processor_loop_v1.py":
        "6a9af69e13a937230788cfb08f889bdc36e95018",
    "docs/F1_PROJECT_ROADMAP_AND_CONTINUITY.md":
        "23f7ee1f673a02fa676ca29f4ba1ab9f049e7189",
    ".github/workflows/dr002-fia-final-grid-capture-shadow.yml":
        "036e8091dded164557dbebf9d1fb7d3efd46ba05",
    "docs/DR002_PRE2B7K4R12_FIA_FINAL_GRID_CAPTURE_ATTESTATION_SHADOW_2026-10-09.md":
        "bed7af034a5fa39b8e6b0014cfdb23b111c362ab",
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

INTAKE_FALSE_CLAIMS = {
    **FALSE_CLAIMS,
    "fia_publisher_authenticated": False,
    "publisher_time_authenticated": False,
    "github_execution_custody_verified": False,
    "first_observed_clock_authenticated": False,
    "prospective_forecast_cutoff_eligible": False,
    "race_predictions_unlocked": False,
    "fantasy_predictions_unlocked": False,
    "session_processor_modified": False,
    "readiness_gate_modified": False,
    "stable_engine_modified": False,
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


def _is_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _strict_json_bytes(raw, code):
    require(type(raw) is bytes, code)

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(CaptureError("nonfinite_json")),
        )
    except CaptureError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CaptureError(code)


def _capture_profile(raw, expected_sha256):
    require(type(raw) is bytes, "capture_profile_exact_bytes_required")
    require(0 < len(raw) <= MAX_CAPTURE_PROFILE_BYTES, "capture_profile_size_out_of_bounds")
    require(_is_hash(expected_sha256), "invalid_capture_profile_identity")
    require(sha256(raw) == expected_sha256, "unrecognized_capture_profile")
    profile = _strict_json_bytes(raw, "malformed_capture_profile")
    require(raw == canonical_json_bytes(profile), "noncanonical_capture_profile")
    require(isinstance(profile, dict) and set(profile) == _CAPTURE_PROFILE_FIELDS,
            "malformed_capture_profile")
    require(profile["schema_version"] == CAPTURE_PROFILE_SCHEMA_VERSION,
            "unsupported_capture_profile")
    require(_scope_valid(profile["profile_id"]), "invalid_profile_id")
    require(profile["document_type"] == DOCUMENT_TYPE
            and profile["document_title"] == DOCUMENT_TITLE,
            "unsupported_document_identity")
    require(isinstance(profile["document_number"], int)
            and not isinstance(profile["document_number"], bool)
            and profile["document_number"] > 0,
            "invalid_document_number")
    for field in ("event_id", "meeting_id", "session_id"):
        require(_scope_valid(profile[field]), "invalid_" + field)
    require(profile["meeting_id"].startswith(profile["event_id"] + ":"),
            "meeting_event_identity_mismatch")
    require(profile["session_id"].startswith(profile["event_id"] + ":"),
            "session_event_identity_mismatch")
    require(profile["profile_id"].startswith(profile["event_id"] + ":"),
            "profile_event_identity_mismatch")

    document_uri, error = _canonical_fia_uri(profile["document_uri"], purpose="document")
    require(error is None and document_uri == profile["document_uri"],
            error or "invalid_document_uri")
    index_uri, error = _canonical_fia_uri(
        profile["official_index_uri"], purpose="official_index"
    )
    require(error is None and index_uri == profile["official_index_uri"],
            error or "invalid_official_index_uri")
    require(document_uri != index_uri, "document_and_index_uri_must_be_distinct")

    publication = profile["publication_evidence"]
    require(isinstance(publication, dict)
            and set(publication) == _PUBLICATION_EVIDENCE_FIELDS,
            "malformed_publication_evidence")
    require(publication["official_index_uri"] == index_uri,
            "publication_evidence_index_uri_mismatch")
    require(publication["claimed_published_utc"] == profile["claimed_published_utc"],
            "publication_evidence_time_mismatch")
    for field in ("index_publication_text", "document_header_date", "document_header_time"):
        value = publication[field]
        require(isinstance(value, str) and value == value.strip() and bool(value),
                "malformed_publication_evidence")
    parse_utc(profile["claimed_published_utc"])
    expected_document = profile["expected_document_sha256"]
    require(expected_document is None or _is_hash(expected_document),
            "invalid_expected_document_sha256")
    return profile, expected_sha256


def _intake_preflight_hold(code):
    return {
        "schema_version": CAPTURE_INTAKE_SCHEMA_VERSION,
        "validation_status": "HOLD",
        "reason_codes": [code],
        "http_get_count": 0,
        "binding_status": "UNBOUND",
        "source_capture_receipt_id": None,
        "source_capture_receipt_sha256": None,
        **INTAKE_FALSE_CLAIMS,
    }


def _prior_receipts(prior_receipt_bytes, profile):
    require(isinstance(prior_receipt_bytes, (tuple, list)), "malformed_prior_evidence_set")
    require(len(prior_receipt_bytes) <= MAX_PRIOR_RECEIPTS, "prior_evidence_set_too_large")
    expected_scope = {
        "event_id": profile["event_id"],
        "meeting_id": profile["meeting_id"],
        "session_id": profile["session_id"],
    }
    parsed = []
    seen = set()
    for raw in prior_receipt_bytes:
        require(type(raw) is bytes and 0 < len(raw) <= MAX_CAPTURE_PROFILE_BYTES,
                "malformed_prior_receipt_bytes")
        receipt = _strict_json_bytes(raw, "malformed_prior_receipt")
        validate_receipt_envelope(receipt)
        verify_temporal_bindings(receipt)
        require(raw == canonical_json_bytes(receipt), "noncanonical_prior_receipt")
        require(receipt["receipt_type"] == "source_capture"
                and receipt["parent_receipt_ids"] == [],
                "prior_evidence_not_parentless_source_capture")
        require(receipt["scope"] == expected_scope, "prior_evidence_scope_mismatch")
        require(receipt["payload"]["source_uri"] == profile["document_uri"],
                "prior_evidence_document_uri_mismatch")
        receipt_id = receipt["receipt_id"]
        require(receipt_id not in seen, "duplicate_prior_receipt_id")
        seen.add(receipt_id)
        parsed.append(receipt)
    return tuple(parsed)


def _check_prior_evidence(priors, profile, candidate, current_sha256, current_observed):
    current_published = parse_utc(profile["claimed_published_utc"])
    current_observed_time = parse_utc(current_observed)
    for prior in priors:
        payload = prior["payload"]
        require(payload["source_id"] == candidate["claimed_source_id"],
                "prior_evidence_source_identity_mismatch")
        require(payload["publisher_time_utc"] is not None,
                "prior_evidence_publisher_time_missing")
        prior_published = parse_utc(payload["publisher_time_utc"])
        prior_observed = parse_utc(payload["first_observed_utc"])
        require(payload["source_sha256"] != current_sha256,
                "duplicate_document_evidence")
        require(current_published >= prior_published,
                "regressing_claimed_publication_time")
        require(current_published != prior_published,
                "stale_publication_evidence")
        require(current_observed_time > prior_observed,
                "non_increasing_observation_evidence")


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


def _transport_document(document_uri):
    """Perform one controlled GET.  No redirect, retry, range, cookie or auth."""
    request = Request(
        document_uri,
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
            "redirected": 300 <= exc.code < 400 or exc.geturl() != document_uri,
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
            "redirected": final_url != document_uri,
        }


def transport():
    """Preserved fixed Australian one-GET transport used by the existing CLI."""
    return _transport_document(PDF_URI)


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


def _response_body(response, expected_uri=PDF_URI):
    required = {
        "status", "body", "content_type", "content_length", "final_url", "complete", "redirected"
    }
    require(isinstance(response, dict) and set(response) == required, "malformed_transport_result")
    require(response["redirected"] is False and response["final_url"] == expected_uri,
            "redirect_or_url_change")
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


def _legacy_profile():
    return {
        "profile_id": "fia:2026-australian-grand-prix:document-55",
        "document_type": DOCUMENT_TYPE,
        "document_number": DOCUMENT_NUMBER,
        "document_title": DOCUMENT_TITLE,
        "document_uri": PDF_URI,
        "official_index_uri": INDEX_URI,
        "claimed_published_utc": CLAIMED_PUBLISHED_UTC,
        "expected_document_sha256": None,
        **SCOPE,
    }


def _base_manifest(
    run_id, github_run_id, github_run_attempt, repository, git_commit, workflow_ref,
    root, profile, capture_profile_sha256=None,
):
    raw_path = root / (
        "raw/fia_final_starting_grid_doc_" + str(profile["document_number"]) + ".pdf"
    )
    receipt_path = root / "source_capture_receipt.json"
    manifest = {
        "schema_version": (
            CAPTURE_INTAKE_SCHEMA_VERSION if capture_profile_sha256 is not None
            else "dr002-fia-final-grid-capture-shadow-v1"
        ),
        "validation_status": "HOLD",
        "reason_codes": [],
        "run_id": run_id,
        "github_run_id": github_run_id,
        "github_run_attempt": github_run_attempt,
        "repository": repository,
        "implementation_git_sha": git_commit,
        "workflow_ref": workflow_ref,
        "implementation": IMPLEMENTATION,
        "request_uri": profile["document_uri"],
        "official_index_uri": profile["official_index_uri"],
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
        "document_type": profile["document_type"],
        "document_number": profile["document_number"],
        "document_title": profile["document_title"],
        "claimed_published_utc": profile["claimed_published_utc"],
        "event_id": profile["event_id"],
        "meeting_id": profile["meeting_id"],
        "session_id": profile["session_id"],
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
        **(INTAKE_FALSE_CLAIMS if capture_profile_sha256 is not None else FALSE_CLAIMS),
    }
    if capture_profile_sha256 is not None:
        publication = profile["publication_evidence"]
        manifest.update(
            profile_id=profile["profile_id"],
            capture_profile_schema_version=profile["schema_version"],
            capture_profile_sha256=capture_profile_sha256,
            capture_profile_path=(root / "capture_profile.json").as_posix(),
            expected_document_sha256=profile["expected_document_sha256"],
            publication_evidence=dict(publication),
            publication_evidence_sha256=sha256(canonical_json_bytes(publication)),
            publisher_time_claim_status="CALLER_CLAIM_UNAUTHENTICATED",
            internal_first_observation_status="RUNNER_CLOCK_UNAUTHENTICATED",
            attested_receipt_existed_by_utc=None,
            prior_evidence_receipt_ids=[],
        )
    return manifest


def _receipt(candidate, source_sha256, first_observed, ingested, created, capture_ref, profile):
    source_id = candidate["claimed_source_id"]
    scope = {
        "event_id": profile["event_id"],
        "meeting_id": profile["meeting_id"],
        "session_id": profile["session_id"],
    }
    identity = {
        "source_id": source_id,
        **scope,
        "source_sha256": source_sha256,
        "first_observed_utc": first_observed,
    }
    return {
        "schema_version": RECEIPT_VERSION,
        "receipt_id": "source_capture:" + sha256(canonical_json_bytes(identity)),
        "receipt_type": "source_capture",
        "receipt_created_utc": created,
        "scope": scope,
        "parent_receipt_ids": [],
        "payload": {
            "source_id": source_id,
            "source_uri": profile["document_uri"],
            "source_sha256": source_sha256,
            "event_time_utc": None,
            "publisher_time_utc": profile["claimed_published_utc"],
            "first_observed_utc": first_observed,
            "ingested_utc": ingested,
            "capture_ref": capture_ref,
            "implementation": IMPLEMENTATION,
        },
    }


def _report(manifest):
    reasons = ", ".join(manifest["reason_codes"]) if manifest["reason_codes"] else "none"
    if manifest["schema_version"] == CAPTURE_INTAKE_SCHEMA_VERSION:
        return (
            "# DR-002 FIA final-grid capture intake\n\n"
            "Status: " + manifest["validation_status"] + "\n\n"
            "Profile: " + manifest["profile_id"] + ".\n\n"
            "Document: " + manifest["document_title"] + ", Doc "
            + str(manifest["document_number"]) + ".\n\n"
            "This is UNBOUND and unauthenticated. GitHub execution custody, FIA publisher "
            "authenticity, publisher time, independently evidenced first observation, and "
            "prospective forecast-cutoff eligibility remain separate and unestablished.\n\n"
            "Reason codes: " + reasons + "\n"
        ).encode("utf-8")
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


def _capture_with_profile(
    *,
    profile,
    capture_profile_bytes,
    capture_profile_sha256,
    prior_receipts,
    github_run_id,
    github_run_attempt,
    repository,
    git_commit,
    workflow_ref,
    request,
    clock=utc_now,
    writer=write_bytes,
    reader=lambda path: path.read_bytes(),
    renamer=rename_path,
    runtime_root=ROOT,
):
    """Run a prevalidated profile through the shared atomic capture boundary."""
    _validate_runtime_identity(github_run_id, github_run_attempt, repository, git_commit, workflow_ref)
    run_id = "gha-" + github_run_id + "-" + github_run_attempt
    runtime_root = Path(runtime_root)
    final_root = runtime_root / run_id
    staging_root = runtime_root / ("pending-" + run_id)
    if final_root.exists() or staging_root.exists():
        raise FileExistsError("exclusive_run_directory_exists")
    staging_root.mkdir(parents=True, exist_ok=False)
    manifest = _base_manifest(
        run_id, github_run_id, github_run_attempt, repository, git_commit, workflow_ref,
        final_root, profile, capture_profile_sha256,
    )
    profile_path = staging_root / "capture_profile.json"
    receipt_candidate = staging_root / "receipt_candidate.diagnostic.json"
    staged_receipt = staging_root / "source_capture_receipt.json"
    candidate_manifest_path = staging_root / "source_candidate_manifest.json"
    manifest_path = staging_root / "capture_manifest.json"
    report_path = staging_root / "capture_report.md"
    try:
        if capture_profile_sha256 is not None:
            writer(profile_path, capture_profile_bytes)
            require(reader(profile_path) == capture_profile_bytes,
                    "capture_profile_readback_mismatch")
        manifest["request_started_utc"] = clock()
        manifest["http_get_count"] = 1
        response = request(profile["document_uri"])
        manifest["response_completed_utc"] = clock()
        if isinstance(response, dict):
            manifest["http_status"] = response.get("status")
            manifest["http_content_type"] = response.get("content_type")
            manifest["http_declared_content_length"] = response.get("content_length")
        body = _response_body(response, profile["document_uri"])
        manifest["first_observed_utc"] = manifest["response_completed_utc"]
        source_digest = sha256(body)
        expected_document = profile["expected_document_sha256"]
        require(expected_document is None or source_digest == expected_document,
                "document_identity_mismatch")
        raw_staged = staging_root / (
            "raw/fia_final_starting_grid_doc_" + str(profile["document_number"]) + ".pdf"
        )
        writer(raw_staged, body)
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
        require(parse_utc(profile["claimed_published_utc"]) <= ordered[1],
                "claimed_publication_after_first_observation")

        assessment = assess_fia_grid_document_candidate(
            raw_document_bytes=body,
            document_type=profile["document_type"],
            document_number=profile["document_number"],
            document_title=profile["document_title"],
            document_uri=profile["document_uri"],
            official_index_uri=profile["official_index_uri"],
            event_id=profile["event_id"],
            meeting_id=profile["meeting_id"],
            session_id=profile["session_id"],
            published_utc=profile["claimed_published_utc"],
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
        _check_prior_evidence(
            prior_receipts, profile, candidate, source_digest, manifest["first_observed_utc"]
        )
        if capture_profile_sha256 is not None:
            manifest["prior_evidence_receipt_ids"] = [
                receipt["receipt_id"] for receipt in prior_receipts
            ]
        receipt = _receipt(
            candidate,
            source_digest,
            manifest["first_observed_utc"],
            manifest["ingested_utc"],
            manifest["receipt_created_utc"],
            manifest["raw_artifact_path"],
            profile,
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
        if capture_profile_sha256 is not None:
            candidate_manifest.update(
                capture_profile_id=profile["profile_id"],
                capture_profile_sha256=capture_profile_sha256,
                publication_evidence=dict(profile["publication_evidence"]),
                publication_evidence_sha256=manifest["publication_evidence_sha256"],
                prior_evidence_receipt_ids=list(manifest["prior_evidence_receipt_ids"]),
                trust_claims=dict(INTAKE_FALSE_CLAIMS),
            )
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


def capture_fia_final_grid_intake(
    *,
    capture_profile_bytes,
    expected_capture_profile_sha256,
    prior_receipt_bytes=(),
    github_run_id,
    github_run_attempt,
    repository,
    git_commit,
    workflow_ref,
    request=_transport_document,
    clock=utc_now,
    writer=write_bytes,
    reader=lambda path: path.read_bytes(),
    renamer=rename_path,
    runtime_root=ROOT,
):
    """Capture one caller-pinned FIA final-grid candidate without raising its trust."""
    try:
        profile, profile_sha256 = _capture_profile(
            capture_profile_bytes, expected_capture_profile_sha256
        )
        priors = _prior_receipts(prior_receipt_bytes, profile)
    except (CaptureError, ReceiptError, KeyError, TypeError, ValueError) as exc:
        return _intake_preflight_hold(getattr(exc, "code", str(exc) or "intake_preflight_failed"))
    return _capture_with_profile(
        profile=profile,
        capture_profile_bytes=capture_profile_bytes,
        capture_profile_sha256=profile_sha256,
        prior_receipts=priors,
        github_run_id=github_run_id,
        github_run_attempt=github_run_attempt,
        repository=repository,
        git_commit=git_commit,
        workflow_ref=workflow_ref,
        request=request,
        clock=clock,
        writer=writer,
        reader=reader,
        renamer=renamer,
        runtime_root=runtime_root,
    )


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
    """Preserve the fixed Australian capture API and its zero-argument request seam."""
    return _capture_with_profile(
        profile=_legacy_profile(),
        capture_profile_bytes=None,
        capture_profile_sha256=None,
        prior_receipts=(),
        github_run_id=github_run_id,
        github_run_attempt=github_run_attempt,
        repository=repository,
        git_commit=git_commit,
        workflow_ref=workflow_ref,
        request=lambda _uri: request(),
        clock=clock,
        writer=writer,
        reader=reader,
        renamer=renamer,
        runtime_root=runtime_root,
    )


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
