"""Pure/offline assessment of observed OpenF1 stream version evidence.

This module validates caller-supplied message bytes and observed chronology. It
does not connect to OpenF1 and cannot establish complete publisher history.
"""
import hashlib
import json


SCHEMA_VERSION = "dr002-openf1-stream-version-evidence-assessment-v1"
VALIDATED = "OPENF1_STREAM_VERSION_EVIDENCE_VALIDATED"
HOLD = "HOLD"

TRUST_CEILINGS = (
    "openf1_id_contiguity_assumed",
    "message_loss_proven_from_id_gaps",
    "publisher_revision_completeness_proven",
    "global_observation_completeness_proven",
    "publisher_source_authenticated",
    "observation_clock_authenticated",
    "historical_availability_proven",
    "production_revision_tracking_proven",
    "full_gate2b1_chain_verified",
    "stable_engine_execution_proven",
    "blind_validation_eligible",
    "dr002_activated",
    "promotion_allowed",
)

K1_SCHEMA_VERSION = "dr002-observer-coverage-assessment-v1"
K1_PROVEN = "DECLARED_WINDOW_SCHEDULE_COVERAGE_PROVEN"
K1_INCOMPLETE = "DECLARED_WINDOW_SCHEDULE_COVERAGE_INCOMPLETE"
K1_TRUST_CEILINGS = (
    "publisher_revision_completeness_proven",
    "global_observation_completeness_proven",
    "publisher_source_authenticated",
    "observation_clock_authenticated",
    "historical_availability_proven",
    "production_revision_tracking_proven",
    "full_gate2b1_chain_verified",
    "stable_engine_execution_proven",
    "blind_validation_eligible",
    "dr002_activated",
    "promotion_allowed",
)


class StreamEvidenceInputError(ValueError):
    """Malformed, ambiguous, or unsupported caller-supplied evidence."""


def _require(condition, reason):
    if not condition:
        raise StreamEvidenceInputError(reason)


def _strict_message_object(raw_bytes):
    _require(isinstance(raw_bytes, bytes), "raw_json_not_bytes")

    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value, "duplicate_json_key")
            value[key] = item
        return value

    try:
        value = json.loads(raw_bytes, object_pairs_hook=pairs)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise StreamEvidenceInputError("malformed_json")
    _require(isinstance(value, dict), "message_json_not_object")
    return value


def _validate_k1_assessment(assessment):
    _require(isinstance(assessment, dict), "malformed_k1_assessment")
    _require(assessment.get("schema_version") == K1_SCHEMA_VERSION,
             "incompatible_k1_schema")
    _require(assessment.get("assessment_type") == "DECLARED_OBSERVER_WINDOW_COVERAGE",
             "incompatible_k1_assessment_type")
    status = assessment.get("status")
    _require(status in (K1_PROVEN, K1_INCOMPLETE), "incompatible_k1_status")
    coverage = assessment.get("declared_window_schedule_coverage_proven")
    _require(isinstance(coverage, bool) and coverage == (status == K1_PROVEN),
             "incompatible_k1_coverage_fact")
    _require(assessment.get("all_successful_observations_receipt_bound") is True,
             "incompatible_k1_receipt_binding_fact")
    for field in K1_TRUST_CEILINGS:
        _require(field in assessment and assessment[field] is False,
                 "incompatible_k1_trust_ceiling:" + field)
    return status, coverage


def _base_assessment(*, status, reason_codes, provider, subscription_topics,
                     connection_window, k1_supplied, k1_status, k1_coverage):
    result = {
        "schema_version": SCHEMA_VERSION,
        "assessment_type": "OPENF1_STREAM_VERSION_EVIDENCE",
        "status": status,
        "reason_codes": list(reason_codes),
        "provider": provider,
        "subscription_topics": list(subscription_topics),
        "connection_window": connection_window,
        "total_observed_message_count": 0,
        "unique_id_count": 0,
        "duplicate_id_detected": False,
        "min_observed_id": None,
        "max_observed_id": None,
        "received_order_id_strictly_increasing": False,
        "numeric_id_gaps_observed": False,
        "observed_topic_set": [],
        "observed_object_identities": [],
        "observed_messages": [],
        "per_object_version_evidence": [],
        "objects_with_multiple_observed_messages": [],
        "k1_observer_coverage_supplied": k1_supplied,
        "k1_observer_coverage_status": k1_status,
        "declared_window_schedule_coverage_proven": k1_coverage,
    }
    result.update({field: False for field in TRUST_CEILINGS})
    return result


def assess_openf1_stream_version_evidence(
    *,
    provider,
    subscription_topics,
    connection_window,
    messages,
    k1_assessment=None,
    openf1_id_contiguity_assumed=False,
    message_loss_proven_from_id_gaps=False,
    publisher_revision_completeness_proven=False,
    global_observation_completeness_proven=False,
    publisher_source_authenticated=False,
    observation_clock_authenticated=False,
    historical_availability_proven=False,
    production_revision_tracking_proven=False,
    full_gate2b1_chain_verified=False,
    stable_engine_execution_proven=False,
    blind_validation_eligible=False,
    dr002_activated=False,
    promotion_allowed=False,
):
    """Validate explicit captured OpenF1 messages without completeness claims."""
    topics_fact = []
    window_fact = None
    k1_supplied = k1_assessment is not None
    k1_status = None
    k1_coverage = False
    try:
        assertions = {
            "openf1_id_contiguity_assumed": openf1_id_contiguity_assumed,
            "message_loss_proven_from_id_gaps": message_loss_proven_from_id_gaps,
            "publisher_revision_completeness_proven": publisher_revision_completeness_proven,
            "global_observation_completeness_proven": global_observation_completeness_proven,
            "publisher_source_authenticated": publisher_source_authenticated,
            "observation_clock_authenticated": observation_clock_authenticated,
            "historical_availability_proven": historical_availability_proven,
            "production_revision_tracking_proven": production_revision_tracking_proven,
            "full_gate2b1_chain_verified": full_gate2b1_chain_verified,
            "stable_engine_execution_proven": stable_engine_execution_proven,
            "blind_validation_eligible": blind_validation_eligible,
            "dr002_activated": dr002_activated,
            "promotion_allowed": promotion_allowed,
        }
        _require(all(isinstance(value, bool) for value in assertions.values()),
                 "malformed_unsupported_assertion")
        asserted = sorted(field for field, value in assertions.items() if value)
        _require(not asserted, "unsupported_assertion:" + ",".join(asserted))

        _require(provider == "openf1", "unsupported_provider")
        _require(isinstance(subscription_topics, list) and subscription_topics,
                 "missing_subscription_topics")
        _require(all(isinstance(topic, str) and topic.strip() for topic in subscription_topics),
                 "malformed_subscription_topic")
        _require(len(subscription_topics) == len(set(subscription_topics)),
                 "duplicate_subscription_topic")
        topics_fact = sorted(subscription_topics)
        declared_topics = set(subscription_topics)

        _require(
            isinstance(connection_window, dict)
            and set(connection_window) == {"connection_id", "window_start_utc", "window_end_utc"}
            and all(isinstance(connection_window[key], str) and connection_window[key].strip()
                    for key in connection_window),
            "malformed_connection_window",
        )
        window_fact = {key: connection_window[key] for key in
                       ("connection_id", "window_start_utc", "window_end_utc")}

        if k1_supplied:
            k1_status, k1_coverage = _validate_k1_assessment(k1_assessment)

        _require(isinstance(messages, list), "malformed_message_records")
        parsed = []
        received_indexes = set()
        observed_ids = set()
        for record in messages:
            _require(
                isinstance(record, dict)
                and set(record) == {"topic", "raw_json_bytes", "received_order_index"},
                "malformed_message_record",
            )
            topic = record["topic"]
            index = record["received_order_index"]
            _require(isinstance(topic, str) and topic.strip(), "malformed_message_topic")
            _require(topic in declared_topics, "undeclared_topic")
            _require(isinstance(index, int) and not isinstance(index, bool) and index >= 0,
                     "malformed_received_order_index")
            _require(index not in received_indexes, "duplicate_received_order_index")
            received_indexes.add(index)

            value = _strict_message_object(record["raw_json_bytes"])
            message_id = value.get("_id")
            object_key = value.get("_key")
            _require(isinstance(message_id, int) and not isinstance(message_id, bool)
                     and message_id >= 0, "missing_or_invalid_id")
            _require(isinstance(object_key, str) and object_key.strip(),
                     "missing_or_invalid_key")
            _require(message_id not in observed_ids, "duplicate_id")
            observed_ids.add(message_id)
            parsed.append({
                "topic": topic,
                "_key": object_key,
                "_id": message_id,
                "received_order_index": index,
                "raw_json_sha256": hashlib.sha256(record["raw_json_bytes"]).hexdigest(),
            })

        received = sorted(parsed, key=lambda item: item["received_order_index"])
        received_ids = [item["_id"] for item in received]
        strictly_increasing = all(left < right for left, right in
                                  zip(received_ids, received_ids[1:]))
        sorted_ids = sorted(observed_ids)
        gaps = any(right - left > 1 for left, right in zip(sorted_ids, sorted_ids[1:]))

        grouped = {}
        for item in parsed:
            grouped.setdefault((item["topic"], item["_key"]), []).append(item)
        identities = [
            {"topic": topic, "_key": key}
            for topic, key in sorted(grouped)
        ]
        per_object = []
        multiple = []
        for identity in sorted(grouped):
            topic, key = identity
            sequence = sorted(grouped[identity], key=lambda item: item["_id"])
            raw_hashes = sorted({item["raw_json_sha256"] for item in sequence})
            evidence = {
                "topic": topic,
                "_key": key,
                "observed_message_count": len(sequence),
                "distinct_raw_payload_hash_count": len(raw_hashes),
                "distinct_raw_payload_sha256": raw_hashes,
                "observed_message_sequence": [
                    {
                        "_id": item["_id"],
                        "received_order_index": item["received_order_index"],
                        "raw_json_sha256": item["raw_json_sha256"],
                    }
                    for item in sequence
                ],
            }
            per_object.append(evidence)
            if len(sequence) > 1:
                multiple.append({"topic": topic, "_key": key})

        result = _base_assessment(
            status=VALIDATED,
            reason_codes=[],
            provider=provider,
            subscription_topics=topics_fact,
            connection_window=window_fact,
            k1_supplied=k1_supplied,
            k1_status=k1_status,
            k1_coverage=k1_coverage,
        )
        result.update({
            "total_observed_message_count": len(parsed),
            "unique_id_count": len(observed_ids),
            "duplicate_id_detected": False,
            "min_observed_id": min(observed_ids) if observed_ids else None,
            "max_observed_id": max(observed_ids) if observed_ids else None,
            "received_order_id_strictly_increasing": strictly_increasing,
            "numeric_id_gaps_observed": gaps,
            "observed_topic_set": sorted({item["topic"] for item in parsed}),
            "observed_object_identities": identities,
            "observed_messages": received,
            "per_object_version_evidence": per_object,
            "objects_with_multiple_observed_messages": multiple,
        })
        return result
    except (StreamEvidenceInputError, KeyError, TypeError, ValueError) as exc:
        return _base_assessment(
            status=HOLD,
            reason_codes=[str(exc) or "malformed_stream_evidence"],
            provider=provider if isinstance(provider, str) else None,
            subscription_topics=topics_fact,
            connection_window=window_fact,
            k1_supplied=k1_supplied,
            k1_status=k1_status,
            k1_coverage=False,
        )
