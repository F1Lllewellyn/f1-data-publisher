"""Pure offline assessment of caller-supplied FIA grid-document candidates.

This module validates syntax and caller-claimed metadata only.  It performs no
network, filesystem, PDF parsing, receipt creation, grid extraction, producer
execution, or trust upgrade.
"""
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_forecast_integrity_receipts_v1 import (  # noqa: E402
    ReceiptError,
    _time,
    canonical_json_bytes,
    sha256,
)


SCHEMA_VERSION = "dr002-fia-grid-document-candidate-v1"
VALIDATED_STATUS = "FIA_GRID_DOCUMENT_CANDIDATE_METADATA_VALIDATED_UNAUTHENTICATED"
MAX_PDF_BYTES = 32 * 1024 * 1024
ALLOWED_FIA_HOSTS = frozenset({"fia.com", "www.fia.com", "api.fia.com", "admin.fia.com"})
DOCUMENT_TYPE_TITLES = {
    "provisional_starting_grid": "provisional starting grid",
    "final_starting_grid": "final starting grid",
}

SOURCE_ID_DOMAIN = b"dr002-fia-grid-document-claimed-source-v1\0"
CONTENT_VERSION_DOMAIN = b"dr002-fia-grid-document-content-version-v1\0"
CANDIDATE_ID_DOMAIN = b"dr002-fia-grid-document-candidate-v1\0"

DEPENDENCY_PINS = {
    "docs/DR002_PRE2B7K4R10_EXACT_HISTORICAL_ARTIFACTS_DUAL_SOURCE_REPLAY_2026-10-08.md":
        "b9d57a68ac7eef39e71a6a19ca9de407a68fb09d",
    "scripts/forecast_bundles/dr002_openf1_weather_drivers_frozen_producer_composition_v1.py":
        "f69a5ac49b6e3055cd13472037f8b49e8ea41265",
    "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
        "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
    "scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py":
        "064d93ee5ae30354590a3fb95be598c5fe8b3b9a",
    "scripts/forecasts/produce_actual_forecast_rows_v1.py":
        "af27586668c767de126af829c1131c6bae4634ad",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
}

FALSE_CLAIMS = {
    "official_source_authenticated": False,
    "official_starting_grid_verified": False,
    "grid_positions_extracted": False,
    "source_captured_by_attested_observer": False,
    "historical_availability_verified": False,
    "verified_receipt_bindings_created": False,
    "production_authenticated": False,
    "blind_validation_eligible": False,
    "dr002_activated": False,
    "promotion_allowed": False,
}

_BAD_URI_CHARACTER = re.compile(r"[\x00-\x20\x7f\\]")
_BAD_DECODED_PATH_CHARACTER = re.compile(r"[\x00-\x1f\x7f\\]")
_BAD_SCOPE_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")
_BAD_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-F]{2})")


def _unique(values):
    return list(dict.fromkeys(values))


def _hold(reason_codes):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "HOLD",
        "reason_codes": _unique(reason_codes),
        "evidence_chain_status": "NOT_ESTABLISHED",
        "claim_flags": dict(FALSE_CLAIMS),
    }
def _normalized_title(value):
    return " ".join(value.split()).casefold() if isinstance(value, str) else None


def _scope_valid(value):
    return (
        isinstance(value, str)
        and value == value.strip()
        and 0 < len(value) <= 256
        and _BAD_SCOPE_CHARACTER.search(value) is None
    )


def _canonical_fia_uri(value, *, purpose):
    """Return a strict canonical FIA URI or a deterministic reason code."""
    code = "invalid_" + purpose + "_uri"
    if not isinstance(value, str) or not value or value != value.strip():
        return None, code
    if not value.isascii() or _BAD_URI_CHARACTER.search(value) is not None:
        return None, code
    if _BAD_PERCENT_ESCAPE.search(value) is not None:
        return None, code
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None, code
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        return None, code
    if parsed.username is not None or parsed.password is not None or port is not None:
        return None, code
    host = parsed.hostname
    if host not in ALLOWED_FIA_HOSTS or parsed.netloc != host:
        return None, code
    if not parsed.path.startswith("/") or "//" in parsed.path:
        return None, code
    try:
        decoded_path = unquote(parsed.path, errors="strict")
    except (UnicodeDecodeError, ValueError):
        return None, code
    if _BAD_DECODED_PATH_CHARACTER.search(decoded_path) is not None:
        return None, code
    canonical_path = quote(decoded_path, safe="/-._~!$&'()*+,;=:@")
    if canonical_path != parsed.path:
        return None, code
    if any(segment in (".", "..") for segment in decoded_path.split("/")):
        return None, code
    if purpose == "document":
        if not decoded_path.endswith(".pdf"):
            return None, "document_uri_not_pdf"
    elif purpose == "official_index":
        if decoded_path != "/documents" and not decoded_path.startswith("/documents/"):
            return None, "official_index_uri_not_documents_route"
    else:  # Internal programming error: callers must use a known purpose.
        raise ValueError("unknown_uri_purpose")
    return value, None


def _explicit_event_route(uri):
    parts = [p for p in unquote(urlsplit(uri).path).split("/") if p]
    for index, part in enumerate(parts[:-1]):
        if part.casefold() == "event":
            return " ".join(parts[index + 1].split()).casefold()
    return None


def _valid_pdf(raw_document_bytes):
    reasons = []
    if not isinstance(raw_document_bytes, bytes):
        return ["raw_document_not_exact_bytes"]
    if not raw_document_bytes:
        reasons.append("raw_document_empty")
    if len(raw_document_bytes) > MAX_PDF_BYTES:
        reasons.append("raw_document_size_exceeds_limit")
    if not raw_document_bytes.startswith(b"%PDF-"):
        reasons.append("raw_document_missing_pdf_magic")
    tail = raw_document_bytes[-2048:]
    if re.search(br"%%EOF[\x00\x09\x0a\x0c\x0d\x20]*\Z", tail) is None:
        reasons.append("raw_document_missing_plausible_eof")
    return reasons


def _parsed_utc(value, field_name, reasons):
    try:
        return _time(value)
    except (ReceiptError, ValueError, TypeError):
        reasons.append("invalid_" + field_name)
        return None


def assess_fia_grid_document_candidate(
    *,
    raw_document_bytes,
    document_type,
    document_number,
    document_title,
    document_uri,
    official_index_uri,
    event_id,
    meeting_id,
    session_id,
    published_utc,
    first_observed_utc,
    ingested_utc,
    receipt_created_utc,
    forecast_cutoff_utc,
):
    """Validate an unauthenticated offline document candidate, fail closed."""
    reasons = []

    if document_type not in DOCUMENT_TYPE_TITLES:
        reasons.append("unsupported_document_type")
    elif _normalized_title(document_title) != DOCUMENT_TYPE_TITLES[document_type]:
        reasons.append("document_title_type_mismatch")

    if isinstance(document_number, bool) or not isinstance(document_number, int) or document_number <= 0:
        reasons.append("invalid_document_number")

    for name, value in (
        ("event_id", event_id),
        ("meeting_id", meeting_id),
        ("session_id", session_id),
    ):
        if not _scope_valid(value):
            reasons.append("invalid_" + name)

    reasons.extend(_valid_pdf(raw_document_bytes))

    canonical_document_uri, error = _canonical_fia_uri(document_uri, purpose="document")
    if error:
        reasons.append(error)
    canonical_index_uri, error = _canonical_fia_uri(official_index_uri, purpose="official_index")
    if error:
        reasons.append(error)
    if canonical_document_uri is not None and canonical_index_uri is not None:
        if canonical_document_uri == canonical_index_uri:
            reasons.append("document_and_index_uri_must_be_distinct")
        document_event = _explicit_event_route(canonical_document_uri)
        index_event = _explicit_event_route(canonical_index_uri)
        if document_event is not None and index_event is not None and document_event != index_event:
            reasons.append("explicit_event_route_mismatch")

    time_values = {}
    for name, value in (
        ("published_utc", published_utc),
        ("first_observed_utc", first_observed_utc),
        ("ingested_utc", ingested_utc),
        ("receipt_created_utc", receipt_created_utc),
        ("forecast_cutoff_utc", forecast_cutoff_utc),
    ):
        time_values[name] = _parsed_utc(value, name, reasons)

    chronology_names = (
        "published_utc",
        "first_observed_utc",
        "ingested_utc",
        "receipt_created_utc",
    )
    if all(time_values[name] is not None for name in chronology_names):
        if not all(
            time_values[left] <= time_values[right]
            for left, right in zip(chronology_names, chronology_names[1:])
        ):
            reasons.append("invalid_document_observation_chronology")
    if time_values["published_utc"] is not None and time_values["forecast_cutoff_utc"] is not None:
        if time_values["published_utc"] > time_values["forecast_cutoff_utc"]:
            reasons.append("published_after_forecast_cutoff")
    if time_values["first_observed_utc"] is not None and time_values["forecast_cutoff_utc"] is not None:
        if time_values["first_observed_utc"] > time_values["forecast_cutoff_utc"]:
            reasons.append("first_observed_after_forecast_cutoff")

    if reasons:
        return _hold(reasons)

    raw_document_sha256 = sha256(raw_document_bytes)
    claimed_source_id = "claimed_fia_pdf_uri:" + sha256(
        SOURCE_ID_DOMAIN + canonical_document_uri.encode("utf-8")
    )
    content_version_payload = {
        "document_uri": canonical_document_uri,
        "raw_document_sha256": raw_document_sha256,
    }
    content_version_id = "fia_grid_document_content_version:" + sha256(
        CONTENT_VERSION_DOMAIN + canonical_json_bytes(content_version_payload)
    )
    candidate_identity = {
        "document_type": document_type,
        "document_number": document_number,
        "document_title": document_title,
        "document_uri": canonical_document_uri,
        "official_index_uri": canonical_index_uri,
        "event_id": event_id,
        "meeting_id": meeting_id,
        "session_id": session_id,
        "published_utc": published_utc,
        "first_observed_utc": first_observed_utc,
        "ingested_utc": ingested_utc,
        "receipt_created_utc": receipt_created_utc,
        "forecast_cutoff_utc": forecast_cutoff_utc,
        "claimed_source_id": claimed_source_id,
        "content_version_id": content_version_id,
    }
    candidate_id = "fia_grid_document_candidate:" + sha256(
        CANDIDATE_ID_DOMAIN + canonical_json_bytes(candidate_identity)
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": VALIDATED_STATUS,
        "reason_codes": [],
        "document_candidate": {
            **candidate_identity,
            "candidate_id": candidate_id,
            "raw_document_sha256": raw_document_sha256,
            "raw_document_size_bytes": len(raw_document_bytes),
            "source_claim_status": "CALLER_SUPPLIED_FIA_URI_CLAIM_UNAUTHENTICATED",
            "scope_binding_status": "CLAIMED_UNVERIFIED_NO_OPENF1_JOIN",
            "pdf_check_status": "SYNTACTIC_PDF_ENVELOPE_ONLY_NO_CONTENT_EXTRACTION",
            "temporal_check_status": "CLAIMED_METADATA_ORDERED_AND_AT_OR_BEFORE_CUTOFF",
        },
        "outputs": {
            "raw_document_included": False,
            "parsed_grid_emitted": False,
            "starting_grid_csv_emitted": False,
            "source_capture_receipt_created": False,
            "verified_binding_created": False,
        },
        "evidence_chain_status": "NOT_ESTABLISHED",
        "claim_flags": dict(FALSE_CLAIMS),
    }
