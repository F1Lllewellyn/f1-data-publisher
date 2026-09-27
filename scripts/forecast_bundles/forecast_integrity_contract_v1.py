"""Offline DR-002 contract evaluator. No I/O, clock, production imports or activation.

Execution receipts are supplied separately by a trusted verifier, never accepted
from the forecast's self-asserted flags. This evaluator checks their bindings;
it does not authenticate external receipts or discover historical availability.
"""
from datetime import datetime, timezone
from enum import Enum
import re
import hashlib
import json


class State(str, Enum):
    VALID_LOCKED = "VALID_LOCKED"
    HOLD = "HOLD"
    MISSED_DEADLINE = "MISSED_DEADLINE"
    SUPERSEDED = "SUPERSEDED"
    POST_CUTOFF_REVISION = "POST_CUTOFF_REVISION"
    OUTCOME_AWARE_EVALUATION_ONLY = "OUTCOME_AWARE_EVALUATION_ONLY"
    TEMPORAL_ELIGIBILITY_UNPROVEN = "TEMPORAL_ELIGIBILITY_UNPROVEN"


VERSION = "dr002-integrity-v1"
PREDICTION_GATES = frozenset(("pre_weekend", "post_fp3", "post_qualifying"))
EVALUATION_GATES = frozenset(("race_result", "post_event"))


def input_manifest_sha256(record):
    """Canonical binding for the declared scope, cutoff, policy and consumed inputs."""
    keys = ("forecast_id", "product_id", "product_contract_id", "gate", "lane_name",
            "event_id", "meeting_id", "session_id", "allowed_session_ids",
            "evidence_cutoff_utc", "forecast_deadline_utc", "mandatory_source_ids",
            "revision_policy", "evidence")
    manifest = {k: record[k] for k in keys}
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value, length=64):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def _time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must use explicit UTC Z")
    result = datetime.fromisoformat(value[:-1] + "+00:00")
    if "T" not in value or result.utcoffset().total_seconds() != 0:
        raise ValueError("invalid UTC timestamp")
    return result.astimezone(timezone.utc)


def _result(state, *reasons, revisions=()):
    return {"contract_version": VERSION, "state": state.value,
            "blind_validation_eligible": state == State.VALID_LOCKED,
            "reason_codes": sorted(set(reasons)), "revision_events": list(revisions)}


def classify_forecast(record, *, verified_execution_records=None):
    """Assess a JSON-compatible record without mutation.

Legacy records are never upgraded by this version, even with added fields.
Unknown/new gates fail closed; this module adds no production gate. Optional
inputs in evidence are consumed inputs and therefore obey the same checks.
"""
    if not isinstance(record, dict):
        return _result(State.HOLD, "malformed_record")
    if isinstance(record.get("gate"), str) and record.get("gate") in EVALUATION_GATES:
        return _result(State.OUTCOME_AWARE_EVALUATION_ONLY, "evaluation_gate")
    if record.get("schema_version") != VERSION or record.get("legacy") is not False:
        return _result(State.TEMPORAL_ELIGIBILITY_UNPROVEN, "legacy_or_unknown_schema")
    if record.get("execution_mode") in ("replay", "manual_validation"):
        return _result(State.OUTCOME_AWARE_EVALUATION_ONLY, "non_prospective_execution")
    try:
        return _classify(record, verified_execution_records or {})
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return _result(State.HOLD, "missing_or_malformed_contract")


def _classify(r, receipts):
    if r["gate"] not in PREDICTION_GATES or r["execution_mode"] != "prospective":
        return _result(State.HOLD, "unsupported_gate_or_mode")
    if r["contract_approved"] is not True or not _text(r["product_contract_id"]):
        return _result(State.HOLD, "unapproved_contract")
    for key in ("forecast_id", "product_id", "lane_name", "event_id", "meeting_id", "session_id"):
        if not _text(r[key]):
            raise ValueError(key)
    allowed = r["allowed_session_ids"]
    if allowed is None:
        allowed = [r["session_id"]]
    if (not isinstance(allowed, list) or not allowed or
            not all(_text(x) for x in allowed) or len(set(allowed)) != len(allowed)):
        return _result(State.HOLD, "ambiguous_allowed_sessions")
    cutoff, generated, deadline, locked, outcome = (
        _time(r[k]) for k in ("evidence_cutoff_utc", "forecast_generation_utc",
                             "forecast_deadline_utc", "forecast_lock_utc",
                             "outcome_availability_boundary_utc"))
    if not _text(r["outcome_boundary_evidence_ref"]) or not _text(r["lock_receipt_ref"]):
        return _result(State.HOLD, "missing_boundary_or_lock_proof")
    if cutoff >= outcome or generated >= outcome or locked >= outcome:
        return _result(State.OUTCOME_AWARE_EVALUATION_ONLY, "not_before_outcome")
    if not cutoff <= generated <= locked or cutoff > deadline or deadline >= outcome:
        return _result(State.HOLD, "inconsistent_timeline")
    p = r["producer"]
    if p["input_manifest_sha256"] != input_manifest_sha256(r):
        return _result(State.HOLD, "input_manifest_hash_mismatch")
    binding = ("implementation", "git_commit", "code_sha256", "execution_id",
               "input_manifest_sha256", "forecast_payload_sha256", "engine_implementation")
    if (not _text(p["implementation"]) or not _text(p["execution_id"]) or
            not _hash(p["git_commit"], 40) or
            not all(_hash(p[k]) for k in ("code_sha256", "input_manifest_sha256", "forecast_payload_sha256")) or
            not (p["engine_implementation"] is None or _text(p["engine_implementation"]))):
        return _result(State.HOLD, "invalid_producer_lineage")
    receipt = receipts.get(p["execution_id"])
    if (not isinstance(receipt, dict) or not _text(receipt.get("verification_ref")) or
            any(k not in receipt or receipt[k] != p[k] for k in binding)):
        return _result(State.HOLD, "execution_lineage_unproven")
    required, evidence = r["mandatory_source_ids"], r["evidence"]
    if (not isinstance(required, list) or not required or not all(_text(x) for x in required)
            or len(set(required)) != len(required) or not isinstance(evidence, list)):
        return _result(State.HOLD, "ambiguous_mandatory_sources")
    ids = [e["source_id"] for e in evidence]
    if not all(_text(x) for x in ids) or len(set(ids)) != len(ids):
        return _result(State.HOLD, "ambiguous_source_identity")
    if not set(required).issubset(ids):
        return _result(State.HOLD, "missing_mandatory_evidence")
    for e in evidence:
        if (e["event_id"] != r["event_id"] or e["meeting_id"] != r["meeting_id"] or
                e["session_id"] not in allowed):
            return _result(State.HOLD, "source_scope_mismatch")
        if not _text(e["source_uri"]) or not _hash(e["source_sha256"]) or not _text(e["capture_evidence_ref"]):
            return _result(State.HOLD, "source_provenance_missing")
        observed, ingested = _time(e["first_observed_utc"]), _time(e["ingested_utc"])
        if observed > cutoff:
            return _result(State.HOLD, "first_observed_after_cutoff")
        if not isinstance(e["ingestion_required_at_cutoff"], bool):
            raise ValueError("ingestion policy")
        if observed > ingested or ingested > generated:
            return _result(State.HOLD, "inconsistent_ingestion_time")
        if e["ingestion_required_at_cutoff"] and ingested > cutoff:
            return _result(State.HOLD, "ingested_after_cutoff")
        # These describe source semantics, not operational availability. A future
        # event timestamp can legitimately describe a pre-published schedule.
        for k in ("event_time_utc", "publisher_time_utc"):
            if e[k] is not None:
                _time(e[k])
    revisions = r["revisions"]
    if not isinstance(revisions, list) or r["revision_policy"] not in ("none", "supersede_before_deadline"):
        raise ValueError("revision contract")
    revision_events = []
    seen = set()
    superseded = False
    for rev in revisions:
        if (not _text(rev["revision_id"]) or rev["revision_id"] in seen or
                rev["forecast_id"] != r["forecast_id"] or rev["product_id"] != r["product_id"] or
                rev["event_id"] != r["event_id"] or rev["meeting_id"] != r["meeting_id"] or
                rev["session_id"] != r["session_id"] or
                rev["source_id"] not in ids or
                not _hash(rev["source_sha256"]) or not _text(rev["capture_evidence_ref"])):
            return _result(State.HOLD, "ambiguous_revision_provenance")
        seen.add(rev["revision_id"])
        observed = _time(rev["first_observed_utc"])
        incorporated = any(e["source_id"] == rev["source_id"] and
                           e["source_sha256"] == rev["source_sha256"] for e in evidence)
        if incorporated:
            if observed > cutoff:
                return _result(State.HOLD, "revision_incorporated_after_cutoff")
            continue
        if r["revision_policy"] == "none":
            return _result(State.HOLD, "revision_policy_unresolved")
        if observed == deadline:
            return _result(State.HOLD, "revision_at_deadline_policy_unresolved")
        if observed < deadline:
            superseded = True
        else:
            revision_events.append({"revision_id": rev["revision_id"],
                                    "state": State.POST_CUTOFF_REVISION.value})
    if superseded:
        return _result(State.SUPERSEDED, "pre_deadline_revision_not_incorporated", revisions=revision_events)
    if locked > deadline:
        return _result(State.MISSED_DEADLINE, "lock_after_deadline", revisions=revision_events)
    return _result(State.VALID_LOCKED, "contract_checks_satisfied", revisions=revision_events)
