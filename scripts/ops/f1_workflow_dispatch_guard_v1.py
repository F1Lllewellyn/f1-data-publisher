#!/usr/bin/env python3
"""Fail-closed GitHub workflow-dispatch guard.

This module is deliberately inert by default.  It does not contact GitHub or
dispatch a workflow unless a future, explicit authority document is supplied,
``--execute`` is selected, and the caller supplies the exact arm digest for
that authority.  Credentials are accepted only from the runtime environment.

The guard proves only dispatch acceptance and immutable run identity.  It does
not prove that a source job succeeded, that source content is valid, that
same-run custody exists, or that scientific ex-ante eligibility is satisfied.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import socket
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple
import urllib.error
import urllib.request


SCHEMA_VERSION = "f1-workflow-dispatch-guard-v1"
EXPECTED_REPOSITORY = "F1Lllewellyn/f1-data-publisher"
EXPECTED_WORKFLOW_PATH = ".github/workflows/f1-openf1-lightweight-source-closure.yml"
EXPECTED_WORKFLOW_BLOB_SHA = "6768b09449905cd61281386d6fc147f0fa18d01c"
EXPECTED_REF = "main"
ALLOWED_ENDPOINTS = {"weather", "drivers", "starting_grid"}
INPUT_KEYS = {
    "season",
    "completed_only",
    "provenance_shadow_session_key",
    "provenance_shadow_endpoint",
}
API_ROOT = "https://api.github.com"
WEB_ROOT = "https://github.com"
API_VERSION = "2026-03-10"
MAX_HISTORY_PAGES = 1000
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
RUN_CLOCK_SKEW = dt.timedelta(minutes=5)


class HttpTransport(Protocol):
    """One-shot HTTP interface.  Implementations must not retry."""

    @property
    def credential_available(self) -> bool:
        ...

    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[Mapping[str, Any]] = None,
        timeout: float = 20.0,
    ) -> "HttpResponse":
        ...


@dataclass(frozen=True)
class HttpResponse:
    status: int
    json_body: Any = None
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchAuthority:
    """Future work-order-specific authority; never contains a credential."""

    work_order_id: str
    issue_number: int
    approved: bool
    repository: str
    workflow_path: str
    workflow_id: int
    ref: str
    expected_head_sha: str
    expected_actor: str
    inputs: Mapping[str, str]
    source_identity_authorized: bool
    authorized_session_key: str
    authorized_endpoint: str
    not_before_utc: str
    source_as_of_cutoff_utc: str
    history_review_complete: bool
    reviewed_run_input_hashes: Mapping[int, str]
    prior_submission_state: str
    cross_operator_exclusion_confirmed: bool
    cross_operator_lock_id: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DispatchAuthority":
        if not isinstance(value, Mapping):
            raise ValueError("authority_not_object")
        reviewed_raw = value.get("reviewed_run_input_hashes", {})
        if not isinstance(reviewed_raw, Mapping):
            raise ValueError("reviewed_history_not_object")
        reviewed: Dict[int, str] = {}
        for key, item in reviewed_raw.items():
            if isinstance(key, bool):
                raise ValueError("reviewed_run_id_invalid")
            try:
                run_id = int(key)
            except (TypeError, ValueError) as exc:
                raise ValueError("reviewed_run_id_invalid") from exc
            reviewed[run_id] = item
        inputs = value.get("inputs", {})
        if not isinstance(inputs, Mapping):
            raise ValueError("inputs_not_object")
        return cls(
            work_order_id=value.get("work_order_id"),
            issue_number=value.get("issue_number"),
            approved=value.get("approved"),
            repository=value.get("repository"),
            workflow_path=value.get("workflow_path"),
            workflow_id=value.get("workflow_id"),
            ref=value.get("ref"),
            expected_head_sha=value.get("expected_head_sha"),
            expected_actor=value.get("expected_actor"),
            inputs=dict(inputs),
            source_identity_authorized=value.get("source_identity_authorized"),
            authorized_session_key=value.get("authorized_session_key"),
            authorized_endpoint=value.get("authorized_endpoint"),
            not_before_utc=value.get("not_before_utc"),
            source_as_of_cutoff_utc=value.get("source_as_of_cutoff_utc"),
            history_review_complete=value.get("history_review_complete"),
            reviewed_run_input_hashes=reviewed,
            prior_submission_state=value.get("prior_submission_state"),
            cross_operator_exclusion_confirmed=value.get("cross_operator_exclusion_confirmed"),
            cross_operator_lock_id=value.get("cross_operator_lock_id"),
        )


@dataclass(frozen=True)
class HistorySnapshot:
    runs: Tuple[Mapping[str, Any], ...]
    total_count: int
    fingerprint: str


@dataclass(frozen=True)
class GuardResult:
    disposition: str
    reasons: Tuple[str, ...]
    audit: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "disposition": self.disposition,
            "reasons": list(self.reasons),
            "audit": dict(self.audit),
        }


@dataclass(frozen=True)
class FollowOnEvidence:
    source_job_succeeded: Optional[bool] = None
    source_artifact_valid: Optional[bool] = None
    same_run_custody_attested: Optional[bool] = None
    within_source_deadline: Optional[bool] = None


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def format_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: Any) -> Optional[dt.datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = dt.datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        return None
    return parsed.astimezone(dt.timezone.utc)


def _positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value):
        return int(value)
    return None


def _safe_text(value: Any, *, maximum: int = 200) -> bool:
    return (
        isinstance(value, str)
        and value.strip() == value
        and 0 < len(value) <= maximum
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def input_digest(inputs: Mapping[str, str]) -> str:
    """Hash exact workflow inputs; no credential is accepted by this function."""
    return hashlib.sha256(canonical_json(dict(inputs))).hexdigest()


def authority_digest(authority: DispatchAuthority) -> str:
    value = asdict(authority)
    value["reviewed_run_input_hashes"] = {
        str(key): item for key, item in sorted(authority.reviewed_run_input_hashes.items())
    }
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _base_audit(now: dt.datetime) -> Dict[str, Any]:
    return {
        "observed_utc": format_utc(now),
        "work_order_id": None,
        "issue_number": None,
        "repository": None,
        "workflow_path": None,
        "workflow_id": None,
        "ref": None,
        "head_sha": None,
        "input_sha256": None,
        "authority_sha256": None,
        "protected_workflow_blob_sha": EXPECTED_WORKFLOW_BLOB_SHA,
        "history_get_calls": 0,
        "protected_preflight_get_calls": 0,
        "post_calls": 0,
        "run_get_calls": 0,
        "http_response_classification": "not_attempted",
        "dispatch_response_accepted": False,
        "dispatch_identity_verified": False,
        "unverified_candidate_run": None,
        "source_job_succeeded": None,
        "source_content_valid": None,
        "same_run_custody_attested": None,
        "scientific_ex_ante_eligible": False,
        "original_run": None,
        "history_input_limitation": (
            "Workflow-run listings do not prove original form inputs. Every listed manual run must be "
            "bound to independently reviewed input evidence before dispatch."
        ),
        "toctou_residual": (
            "A list-then-POST guard cannot provide a global exactly-once guarantee; a different operator "
            "can submit after the final history read and before the POST."
        ),
        "credential_permissions_required": (
            "GitHub Actions write for dispatch and Actions read for history/run verification."
        ),
        "activation_requirement": (
            "A separate future work order must approve one exact source identity, time window, authority "
            "document, credential context, arm digest, and live execution."
        ),
        "authority_control_limitation": (
            "Approval, history review, and cross-operator exclusion are self-declared local JSON "
            "assertions. The arm digest is not cryptographic independent authorization, and the "
            "cross-operator lock identifier is not a shared distributed lock."
        ),
    }


def _result(disposition: str, reasons: Sequence[str], audit: Mapping[str, Any]) -> GuardResult:
    unique: List[str] = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    return GuardResult(disposition=disposition, reasons=tuple(unique), audit=dict(audit))


def validate_authority(authority: DispatchAuthority, now: dt.datetime) -> List[str]:
    reasons: List[str] = []
    if authority.approved is not True:
        reasons.append("missing_future_execution_approval")
    if not _safe_text(authority.work_order_id):
        reasons.append("invalid_work_order_id")
    if _positive_int(authority.issue_number) is None:
        reasons.append("invalid_issue_number")
    if authority.repository != EXPECTED_REPOSITORY:
        reasons.append("repository_scope_mismatch")
    if authority.workflow_path != EXPECTED_WORKFLOW_PATH:
        reasons.append("workflow_scope_mismatch")
    if _positive_int(authority.workflow_id) is None:
        reasons.append("workflow_id_missing_or_invalid")
    if authority.ref != EXPECTED_REF:
        reasons.append("ref_must_be_main")
    if not isinstance(authority.expected_head_sha, str) or not re.fullmatch(
        r"[0-9a-f]{40}", authority.expected_head_sha
    ):
        reasons.append("head_sha_missing_or_invalid")
    if not _safe_text(authority.expected_actor, maximum=100):
        reasons.append("expected_actor_missing_or_invalid")

    inputs = authority.inputs
    if not isinstance(inputs, Mapping) or set(inputs) != INPUT_KEYS:
        reasons.append("workflow_input_schema_mismatch")
    elif not all(_safe_text(value, maximum=200) for value in inputs.values()):
        reasons.append("workflow_input_value_invalid")
    else:
        season = inputs.get("season")
        session_key = inputs.get("provenance_shadow_session_key")
        endpoint = inputs.get("provenance_shadow_endpoint")
        if not isinstance(season, str) or re.fullmatch(r"20[0-9]{2}", season) is None:
            reasons.append("season_invalid")
        if inputs.get("completed_only") != "true":
            reasons.append("completed_only_must_be_true")
        if _positive_int(session_key) is None:
            reasons.append("session_key_missing_or_invalid")
        if endpoint not in ALLOWED_ENDPOINTS:
            reasons.append("endpoint_not_allowed")
        if authority.source_identity_authorized is not True:
            reasons.append("source_identity_not_user_authorized")
        if session_key != authority.authorized_session_key:
            reasons.append("session_key_authority_mismatch")
        if endpoint != authority.authorized_endpoint:
            reasons.append("endpoint_authority_mismatch")

    not_before = parse_utc(authority.not_before_utc)
    cutoff = parse_utc(authority.source_as_of_cutoff_utc)
    if not_before is None:
        reasons.append("not_before_missing_or_invalid")
    if cutoff is None:
        reasons.append("source_cutoff_missing_or_invalid")
    if not_before is not None and cutoff is not None:
        if not_before >= cutoff:
            reasons.append("invalid_authorized_time_window")
        if now < not_before:
            reasons.append("not_before_gate_closed")
        if now >= cutoff:
            reasons.append("source_cutoff_reached")

    if authority.history_review_complete is not True:
        reasons.append("manual_history_review_incomplete")
    if not isinstance(authority.reviewed_run_input_hashes, Mapping):
        reasons.append("reviewed_history_invalid")
    else:
        for run_id, digest in authority.reviewed_run_input_hashes.items():
            if _positive_int(run_id) is None or not isinstance(digest, str) or re.fullmatch(
                r"[0-9a-f]{64}", digest
            ) is None:
                reasons.append("reviewed_history_invalid")
                break
    if authority.prior_submission_state != "none":
        reasons.append("prior_submission_state_not_clear")
    if authority.cross_operator_exclusion_confirmed is not True:
        reasons.append("cross_operator_duplicate_risk_unresolved")
    if not _safe_text(authority.cross_operator_lock_id, maximum=200):
        reasons.append("cross_operator_lock_missing")
    if isinstance(inputs, Mapping) and set(inputs) == INPUT_KEYS:
        try:
            digest = input_digest(inputs)
        except (TypeError, ValueError):
            digest = None
        if digest and digest in authority.reviewed_run_input_hashes.values():
            reasons.append("existing_matching_original_run")
    return reasons


def _history_url(authority: DispatchAuthority, page: int) -> str:
    return (
        f"{API_ROOT}/repos/{authority.repository}/actions/workflows/{authority.workflow_id}/runs"
        f"?event=workflow_dispatch&per_page=100&page={page}"
    )


def _run_url(authority: DispatchAuthority, run_id: int) -> str:
    return f"{API_ROOT}/repos/{authority.repository}/actions/runs/{run_id}"


def _dispatch_url(authority: DispatchAuthority) -> str:
    return f"{API_ROOT}/repos/{authority.repository}/actions/workflows/{authority.workflow_id}/dispatches"


def _main_ref_url(authority: DispatchAuthority) -> str:
    return f"{API_ROOT}/repos/{authority.repository}/git/ref/heads/{authority.ref}"


def _workflow_contents_url(authority: DispatchAuthority) -> str:
    return (
        f"{API_ROOT}/repos/{authority.repository}/contents/{authority.workflow_path}"
        f"?ref={authority.expected_head_sha}"
    )


def _workflow_metadata_url(authority: DispatchAuthority) -> str:
    return (
        f"{API_ROOT}/repos/{authority.repository}/actions/workflows/"
        f"{authority.workflow_id}"
    )


def verify_protected_workflow(
    authority: DispatchAuthority,
    transport: HttpTransport,
) -> Tuple[List[str], int]:
    """Bind current main and the protected workflow blob immediately before POST."""
    calls = 0
    try:
        calls += 1
        ref_response = transport.request("GET", _main_ref_url(authority))
    except Exception as exc:
        return [f"main_ref_request_exception_{type(exc).__name__}"], calls
    if ref_response.status != 200:
        return [f"main_ref_http_{ref_response.status}"], calls
    ref_body = ref_response.json_body
    expected_ref = f"refs/heads/{authority.ref}"
    expected_commit_url = (
        f"{API_ROOT}/repos/{authority.repository}/git/commits/{authority.expected_head_sha}"
    )
    if not (
        isinstance(ref_body, Mapping)
        and ref_body.get("ref") == expected_ref
        and isinstance(ref_body.get("object"), Mapping)
        and ref_body["object"].get("type") == "commit"
        and ref_body["object"].get("sha") == authority.expected_head_sha
        and ref_body["object"].get("url") == expected_commit_url
    ):
        return ["main_ref_identity_mismatch"], calls
    try:
        calls += 1
        file_response = transport.request("GET", _workflow_contents_url(authority))
    except Exception as exc:
        return [f"protected_workflow_request_exception_{type(exc).__name__}"], calls
    if file_response.status != 200:
        return [f"protected_workflow_http_{file_response.status}"], calls
    body = file_response.json_body
    expected_html = (
        f"{WEB_ROOT}/{authority.repository}/blob/{authority.expected_head_sha}/"
        f"{authority.workflow_path}"
    )
    expected_git = (
        f"{API_ROOT}/repos/{authority.repository}/git/blobs/{EXPECTED_WORKFLOW_BLOB_SHA}"
    )
    if not (
        isinstance(body, Mapping)
        and body.get("type") == "file"
        and body.get("path") == authority.workflow_path
        and body.get("sha") == EXPECTED_WORKFLOW_BLOB_SHA
        and _positive_int(body.get("size")) is not None
        and body.get("html_url") == expected_html
        and body.get("git_url") == expected_git
    ):
        return ["protected_workflow_identity_mismatch"], calls

    try:
        calls += 1
        workflow_response = transport.request("GET", _workflow_metadata_url(authority))
    except Exception as exc:
        return [f"workflow_metadata_request_exception_{type(exc).__name__}"], calls
    if workflow_response.status != 200:
        return [f"workflow_metadata_http_{workflow_response.status}"], calls
    workflow = workflow_response.json_body
    expected_api = _workflow_metadata_url(authority)
    expected_html = (
        f"{WEB_ROOT}/{authority.repository}/blob/{authority.ref}/{authority.workflow_path}"
    )
    if not (
        isinstance(workflow, Mapping)
        and workflow.get("id") == authority.workflow_id
        and workflow.get("path") == authority.workflow_path
        and workflow.get("state") == "active"
        and workflow.get("url") == expected_api
        and workflow.get("html_url") == expected_html
    ):
        return ["workflow_metadata_identity_mismatch"], calls
    return [], calls


def _history_run_safe(run: Any, authority: DispatchAuthority) -> bool:
    return (
        isinstance(run, Mapping)
        and _positive_int(run.get("id")) is not None
        and run.get("workflow_id") == authority.workflow_id
        and run.get("path") == authority.workflow_path
        and run.get("event") == "workflow_dispatch"
        and run.get("head_branch") == authority.ref
        and isinstance(run.get("head_sha"), str)
        and re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]) is not None
        and _positive_int(run.get("run_attempt")) is not None
        and isinstance(run.get("repository"), Mapping)
        and run["repository"].get("full_name") == authority.repository
        and isinstance(run.get("actor"), Mapping)
        and _safe_text(run["actor"].get("login"), maximum=100)
        and parse_utc(run.get("created_at")) is not None
    )


def load_complete_history(
    authority: DispatchAuthority,
    transport: HttpTransport,
) -> Tuple[Optional[HistorySnapshot], List[str], int]:
    """Read every page; partial, changing, or malformed pagination is a HOLD."""
    reasons: List[str] = []
    runs: List[Mapping[str, Any]] = []
    total_expected: Optional[int] = None
    calls = 0
    for page in range(1, MAX_HISTORY_PAGES + 1):
        try:
            calls += 1
            response = transport.request("GET", _history_url(authority, page))
        except Exception as exc:  # transport errors are terminal and never retried
            reasons.append(f"history_request_exception_{type(exc).__name__}")
            return None, reasons, calls
        if response.status != 200:
            reasons.append(f"history_http_{response.status}")
            return None, reasons, calls
        body = response.json_body
        if not isinstance(body, Mapping):
            reasons.append("history_response_not_object")
            return None, reasons, calls
        total = body.get("total_count")
        page_runs = body.get("workflow_runs")
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            reasons.append("history_total_count_invalid")
            return None, reasons, calls
        if not isinstance(page_runs, list) or len(page_runs) > 100:
            reasons.append("history_page_invalid")
            return None, reasons, calls
        if total_expected is None:
            total_expected = total
        elif total != total_expected:
            reasons.append("history_total_changed_during_pagination")
            return None, reasons, calls
        if not all(_history_run_safe(run, authority) for run in page_runs):
            reasons.append("history_run_identity_ambiguous")
            return None, reasons, calls
        runs.extend(page_runs)
        ids = [run["id"] for run in runs]
        if len(set(ids)) != len(ids):
            reasons.append("history_duplicate_run_id")
            return None, reasons, calls
        if len(runs) > total_expected:
            reasons.append("history_count_exceeds_total")
            return None, reasons, calls
        if len(runs) == total_expected:
            normalized = [
                {
                    "id": run["id"],
                    "created_at": run["created_at"],
                    "head_sha": run.get("head_sha"),
                    "actor": run["actor"]["login"],
                }
                for run in sorted(runs, key=lambda item: item["id"])
            ]
            fingerprint = hashlib.sha256(canonical_json(normalized)).hexdigest()
            return HistorySnapshot(tuple(runs), total_expected, fingerprint), reasons, calls
        if not page_runs or len(page_runs) < 100:
            reasons.append("history_pagination_gap")
            return None, reasons, calls
    reasons.append("history_page_limit_exceeded")
    return None, reasons, calls


def validate_reviewed_history(snapshot: HistorySnapshot, authority: DispatchAuthority) -> List[str]:
    reasons: List[str] = []
    observed_ids = {run["id"] for run in snapshot.runs}
    reviewed_ids = set(authority.reviewed_run_input_hashes)
    if observed_ids != reviewed_ids:
        reasons.append("unknown_or_missing_reviewed_manual_run")
    target = input_digest(authority.inputs)
    for run_id in observed_ids & reviewed_ids:
        if authority.reviewed_run_input_hashes[run_id] == target:
            reasons.append("existing_matching_original_run")
    return reasons


def _valid_dispatch_response(body: Any, authority: DispatchAuthority) -> Tuple[Optional[int], List[str]]:
    reasons: List[str] = []
    if not isinstance(body, Mapping) or set(body) != {"workflow_run_id", "run_url", "html_url"}:
        return None, ["dispatch_200_schema_invalid"]
    run_id = _positive_int(body.get("workflow_run_id"))
    if run_id is None:
        reasons.append("dispatch_run_id_invalid")
        return None, reasons
    expected_api = _run_url(authority, run_id)
    expected_html = f"{WEB_ROOT}/{authority.repository}/actions/runs/{run_id}"
    if body.get("run_url") != expected_api:
        reasons.append("dispatch_run_url_unsafe_or_mismatched")
    if body.get("html_url") != expected_html:
        reasons.append("dispatch_html_url_unsafe_or_mismatched")
    return (run_id if not reasons else None), reasons


def validate_exact_run(
    body: Any,
    authority: DispatchAuthority,
    run_id: int,
    post_started: dt.datetime,
    observed_after: dt.datetime,
) -> List[str]:
    if not isinstance(body, Mapping):
        return ["run_response_not_object"]
    reasons: List[str] = []
    checks = {
        "id": body.get("id") == run_id,
        "workflow_id": body.get("workflow_id") == authority.workflow_id,
        "workflow_path": body.get("path") == authority.workflow_path,
        "event": body.get("event") == "workflow_dispatch",
        "head_branch": body.get("head_branch") == authority.ref,
        "head_sha": body.get("head_sha") == authority.expected_head_sha,
        "attempt": body.get("run_attempt") == 1,
        "api_url": body.get("url") == _run_url(authority, run_id),
        "html_url": body.get("html_url") == f"{WEB_ROOT}/{authority.repository}/actions/runs/{run_id}",
        "actor": isinstance(body.get("actor"), Mapping)
        and body["actor"].get("login") == authority.expected_actor,
        "repository": isinstance(body.get("repository"), Mapping)
        and body["repository"].get("full_name") == authority.repository,
        "head_repository": isinstance(body.get("head_repository"), Mapping)
        and body["head_repository"].get("full_name") == authority.repository,
        "head_commit": isinstance(body.get("head_commit"), Mapping)
        and body["head_commit"].get("id") == authority.expected_head_sha,
        "run_number": _positive_int(body.get("run_number")) is not None,
    }
    for label, passed in checks.items():
        if not passed:
            reasons.append(f"run_identity_mismatch_{label}")
    created = parse_utc(body.get("created_at"))
    not_before = parse_utc(authority.not_before_utc)
    cutoff = parse_utc(authority.source_as_of_cutoff_utc)
    if created is None:
        reasons.append("run_created_at_invalid")
    else:
        if not_before is None or cutoff is None or created < not_before or created >= cutoff:
            reasons.append("run_created_outside_authorized_window")
        if created < post_started - RUN_CLOCK_SKEW or created > observed_after + RUN_CLOCK_SKEW:
            reasons.append("run_created_clock_mismatch")
    return reasons


def run_guard(
    *,
    authority_reader: Optional[Callable[[], DispatchAuthority]] = None,
    transport: Optional[HttpTransport] = None,
    clock: Callable[[], dt.datetime] = utc_now,
    execute: bool = False,
    arm_digest: Optional[str] = None,
) -> GuardResult:
    """Run the guard.  Default invocation performs zero network calls."""
    try:
        now = clock()
    except Exception as exc:
        audit = _base_audit(utc_now())
        return _result("HOLD", [f"initial_clock_error_{type(exc).__name__}"], audit)
    if not isinstance(now, dt.datetime) or now.tzinfo is None:
        audit = _base_audit(utc_now())
        return _result("HOLD", ["initial_clock_not_timezone_aware"], audit)
    now = now.astimezone(dt.timezone.utc)
    audit = _base_audit(now)
    if authority_reader is None:
        return _result("HOLD", ["missing_future_work_order_authority"], audit)
    try:
        authority = authority_reader()
    except Exception as exc:
        return _result("HOLD", [f"authority_read_error_{type(exc).__name__}"], audit)
    if not isinstance(authority, DispatchAuthority):
        return _result("HOLD", ["authority_type_invalid"], audit)
    try:
        digest = authority_digest(authority)
        inputs_digest = (
            input_digest(authority.inputs) if isinstance(authority.inputs, Mapping) else None
        )
    except (TypeError, ValueError):
        return _result("HOLD", ["authority_serialization_invalid"], audit)
    audit.update(
        {
            "work_order_id": authority.work_order_id,
            "issue_number": authority.issue_number,
            "repository": authority.repository,
            "workflow_path": authority.workflow_path,
            "workflow_id": authority.workflow_id,
            "ref": authority.ref,
            "head_sha": authority.expected_head_sha,
            "input_sha256": inputs_digest,
            "authority_sha256": digest,
        }
    )
    reasons = validate_authority(authority, now)
    if reasons:
        return _result("HOLD", reasons, audit)
    if not execute:
        return _result("DRY_RUN_NO_SIDE_EFFECTS", ["execution_not_armed"], audit)
    if not isinstance(arm_digest, str) or arm_digest != digest:
        return _result("HOLD", ["arm_digest_missing_or_mismatched"], audit)
    if transport is None:
        return _result("HOLD", ["authenticated_transport_missing"], audit)
    try:
        credential_available = transport.credential_available
    except Exception as exc:
        return _result("HOLD", [f"credential_check_error_{type(exc).__name__}"], audit)
    if credential_available is not True:
        return _result("HOLD", ["runtime_credential_missing"], audit)

    first_history, history_reasons, calls = load_complete_history(authority, transport)
    audit["history_get_calls"] += calls
    if history_reasons or first_history is None:
        return _result("HOLD", history_reasons or ["history_unavailable"], audit)
    reasons = validate_reviewed_history(first_history, authority)
    if reasons:
        return _result("HOLD", reasons, audit)

    try:
        current_authority = authority_reader()
    except Exception as exc:
        return _result("HOLD", [f"authority_reread_error_{type(exc).__name__}"], audit)
    if not isinstance(current_authority, DispatchAuthority):
        return _result("HOLD", ["concurrent_authority_type_invalid"], audit)
    try:
        current_digest = authority_digest(current_authority)
    except (TypeError, ValueError):
        return _result("HOLD", ["concurrent_authority_serialization_invalid"], audit)
    if current_digest != digest:
        return _result("HOLD", ["concurrent_authority_drift"], audit)

    second_history, history_reasons, calls = load_complete_history(authority, transport)
    audit["history_get_calls"] += calls
    if history_reasons or second_history is None:
        return _result("HOLD", history_reasons or ["history_unavailable_before_post"], audit)
    if second_history.fingerprint != first_history.fingerprint:
        return _result("HOLD", ["delayed_or_concurrent_manual_run_detected"], audit)
    reasons = validate_reviewed_history(second_history, authority)
    if reasons:
        return _result("HOLD", reasons, audit)

    protected_reasons, calls = verify_protected_workflow(authority, transport)
    audit["protected_preflight_get_calls"] += calls
    if protected_reasons:
        return _result("HOLD", protected_reasons, audit)

    try:
        final_authority = authority_reader()
    except Exception as exc:
        return _result("HOLD", [f"final_authority_read_error_{type(exc).__name__}"], audit)
    if not isinstance(final_authority, DispatchAuthority):
        return _result("HOLD", ["final_authority_type_invalid"], audit)
    try:
        final_digest = authority_digest(final_authority)
    except (TypeError, ValueError):
        return _result("HOLD", ["final_authority_serialization_invalid"], audit)
    if final_digest != digest:
        return _result("HOLD", ["final_authority_drift"], audit)

    try:
        post_started = clock()
    except Exception as exc:
        return _result("HOLD", [f"final_clock_error_{type(exc).__name__}"], audit)
    if not isinstance(post_started, dt.datetime) or post_started.tzinfo is None:
        return _result("HOLD", ["final_clock_not_timezone_aware"], audit)
    post_started = post_started.astimezone(dt.timezone.utc)
    not_before = parse_utc(authority.not_before_utc)
    cutoff = parse_utc(authority.source_as_of_cutoff_utc)
    if (
        not_before is None
        or cutoff is None
        or post_started < not_before
        or post_started >= cutoff
    ):
        return _result("HOLD", ["dispatch_time_window_closed_before_post"], audit)

    post_body = {
        "ref": authority.ref,
        "inputs": dict(authority.inputs),
        "return_run_details": True,
    }
    audit["post_calls"] = 1
    try:
        response = transport.request("POST", _dispatch_url(authority), json_body=post_body)
    except Exception as exc:  # an ambiguous request is terminal; never retry
        audit["http_response_classification"] = "ambiguous_request_exception"
        return _result("HOLD", [f"dispatch_request_exception_{type(exc).__name__}"], audit)
    if not isinstance(response, HttpResponse):
        audit["http_response_classification"] = "invalid_transport_response"
        return _result("HOLD", ["dispatch_response_invalid"], audit)
    audit["http_response_classification"] = f"http_{response.status}"
    if response.status != 200:
        reason = "dispatch_204_no_run_identity" if response.status == 204 else f"dispatch_http_{response.status}"
        return _result("HOLD", [reason], audit)
    try:
        run_id, response_reasons = _valid_dispatch_response(response.json_body, authority)
    except Exception as exc:
        return _result(
            "HOLD", [f"dispatch_response_validation_exception_{type(exc).__name__}"], audit
        )
    if response_reasons or run_id is None:
        return _result("HOLD", response_reasons or ["dispatch_identity_missing"], audit)
    audit["dispatch_response_accepted"] = True
    audit["unverified_candidate_run"] = {
        "verification_state": "UNVERIFIED_CANDIDATE",
        "id": run_id,
        "run_url": response.json_body["run_url"],
        "html_url": response.json_body["html_url"],
        "post_started_utc": format_utc(post_started),
    }

    audit["run_get_calls"] = 1
    try:
        run_response = transport.request("GET", _run_url(authority, run_id))
    except Exception as exc:
        return _result("HOLD", [f"run_verification_exception_{type(exc).__name__}"], audit)
    if not isinstance(run_response, HttpResponse):
        return _result("HOLD", ["run_verification_response_invalid"], audit)
    if run_response.status != 200:
        return _result("HOLD", [f"run_verification_http_{run_response.status}"], audit)
    try:
        observed_after_raw = clock()
    except Exception as exc:
        return _result("HOLD", [f"post_dispatch_clock_error_{type(exc).__name__}"], audit)
    if not isinstance(observed_after_raw, dt.datetime):
        return _result("HOLD", ["post_dispatch_clock_not_datetime"], audit)
    if observed_after_raw.tzinfo is None:
        return _result("HOLD", ["post_dispatch_clock_not_timezone_aware"], audit)
    try:
        if observed_after_raw.utcoffset() is None:
            return _result("HOLD", ["post_dispatch_clock_timezone_invalid"], audit)
        observed_after = observed_after_raw.astimezone(dt.timezone.utc)
    except Exception as exc:
        return _result(
            "HOLD", [f"post_dispatch_clock_timezone_error_{type(exc).__name__}"], audit
        )
    try:
        run_reasons = validate_exact_run(
            run_response.json_body, authority, run_id, post_started, observed_after
        )
    except Exception as exc:
        return _result("HOLD", [f"run_validation_exception_{type(exc).__name__}"], audit)
    if run_reasons:
        return _result("HOLD", run_reasons, audit)
    run = run_response.json_body
    audit["dispatch_identity_verified"] = True
    audit["original_run"] = {
        "verification_state": "VERIFIED_ORIGINAL_RUN",
        "id": run_id,
        "url": run["html_url"],
        "attempt": run["run_attempt"],
        "event": run["event"],
        "created_at": run["created_at"],
        "actor": run["actor"]["login"],
        "ref": run["head_branch"],
        "head_sha": run["head_sha"],
        "workflow_id": run["workflow_id"],
        "workflow_path": run["path"],
    }
    return _result("DISPATCH_IDENTITY_VERIFIED", [], audit)


def assess_follow_on_evidence(
    dispatch_result: GuardResult,
    evidence: FollowOnEvidence,
) -> Dict[str, Any]:
    """Keep later job/artifact facts separate; never pronounce scientific eligibility."""
    reasons: List[str] = []
    if dispatch_result.audit.get("dispatch_identity_verified") is not True:
        reasons.append("dispatch_identity_not_verified")
    if evidence.source_job_succeeded is not True:
        reasons.append("source_job_not_successful")
    if evidence.source_artifact_valid is not True:
        reasons.append("source_artifact_missing_or_invalid")
    if evidence.same_run_custody_attested is not True:
        reasons.append("same_run_custody_missing_or_unverified")
    if evidence.within_source_deadline is not True:
        reasons.append("source_deadline_missing_or_breached")
    reasons.append("independent_scientific_verification_required")
    return {
        "dispatch_identity_verified": dispatch_result.audit.get("dispatch_identity_verified") is True,
        "source_job_succeeded": evidence.source_job_succeeded is True,
        "source_artifact_valid": evidence.source_artifact_valid is True,
        "same_run_custody_attested": evidence.same_run_custody_attested is True,
        "within_source_deadline": evidence.within_source_deadline is True,
        "weather_source_eligible": False,
        "scientific_ex_ante_eligible": False,
        "forecast_ready": False,
        "reasons": reasons,
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class GitHubApiTransport:
    """Stdlib authenticated transport with redirects and retries disabled."""

    def __init__(self, token_env: str = "GITHUB_TOKEN") -> None:
        self._token = os.environ.get(token_env, "")
        self._opener = urllib.request.build_opener(_NoRedirect())

    @property
    def credential_available(self) -> bool:
        return bool(self._token)

    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[Mapping[str, Any]] = None,
        timeout: float = 20.0,
    ) -> HttpResponse:
        if not url.startswith(f"{API_ROOT}/"):
            raise ValueError("non_github_api_url_rejected")
        data = canonical_json(dict(json_body)) if json_body is not None else None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": SCHEMA_VERSION,
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            response = self._opener.open(request, timeout=timeout)
            status = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            response_headers = dict(exc.headers.items()) if exc.headers else {}
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
            raise ConnectionError("github_transport_failed") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("github_response_too_large")
        if not raw:
            parsed: Any = None
        else:
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("github_response_invalid_json") from exc
        return HttpResponse(status=status, json_body=parsed, headers=response_headers)


def _authority_reader(path: Path) -> Callable[[], DispatchAuthority]:
    def read() -> DispatchAuthority:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return DispatchAuthority.from_dict(raw)

    return read


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-json", type=Path, help="Future work-order authority JSON")
    parser.add_argument("--execute", action="store_true", help="Arm live execution; no effect without exact digest")
    parser.add_argument("--arm-digest", help="Exact SHA-256 of the future authority document")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    reader = _authority_reader(args.authority_json) if args.authority_json else None
    # Constructing the transport does not perform I/O.  run_guard invokes it only
    # after authority, arm, time, history-evidence, and credential gates pass.
    transport: Optional[HttpTransport] = GitHubApiTransport() if args.execute else None
    result = run_guard(
        authority_reader=reader,
        transport=transport,
        execute=args.execute,
        arm_digest=args.arm_digest,
    )
    print(json.dumps(result.to_dict(), sort_keys=True, indent=2))
    return 0 if result.disposition in {"DRY_RUN_NO_SIDE_EFFECTS", "DISPATCH_IDENTITY_VERIFIED"} else 20


if __name__ == "__main__":
    raise SystemExit(main())
