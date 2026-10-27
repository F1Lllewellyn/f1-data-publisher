"""Adversarial offline tests for the guarded workflow-dispatch adapter."""

from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ops" / "f1_workflow_dispatch_guard_v1.py"
SPEC = importlib.util.spec_from_file_location("f1_workflow_dispatch_guard_v1", MODULE_PATH)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = guard
SPEC.loader.exec_module(guard)

NOW = dt.datetime(2026, 10, 30, 12, 0, tzinfo=dt.timezone.utc)
WORKFLOW_ID = 99112233
HEAD_SHA = "a" * 40
ACTOR = "future-operator"
RUN_ID = 7788990011


class FakeTransport:
    def __init__(self, steps=(), *, credential_available=True):
        self.steps = list(steps)
        self.records = []
        self._credential_available = credential_available

    @property
    def credential_available(self):
        return self._credential_available

    def request(self, method, url, *, json_body=None, timeout=20.0):
        self.records.append(
            {"method": method, "url": url, "json_body": copy.deepcopy(json_body), "timeout": timeout}
        )
        if not self.steps:
            raise AssertionError(f"unexpected request: {method} {url}")
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            return step(method, url, json_body)
        return step


class SequenceAuthorityReader:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if len(self.values) > 1:
            return self.values.pop(0)
        return self.values[0]


class SequenceClock:
    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        if len(self.values) > 1:
            value = self.values.pop(0)
        else:
            value = self.values[0]
        if isinstance(value, BaseException):
            raise value
        return value


class BrokenTimezone(dt.tzinfo):
    def utcoffset(self, value):
        raise RuntimeError("broken timezone")


class RaisingRunMapping(dict):
    def get(self, key, default=None):
        if key == "id":
            raise RuntimeError("run validation failed")
        return super().get(key, default)


def fixed_clock():
    return NOW


def valid_inputs():
    return {
        "season": "2027",
        "completed_only": "true",
        "provenance_shadow_session_key": "22001",
        "provenance_shadow_endpoint": "weather",
    }


def valid_authority(*, reviewed=None):
    return guard.DispatchAuthority(
        work_order_id="F1-WO-FUTURE-SINGLE-SOURCE-001",
        issue_number=999,
        approved=True,
        repository=guard.EXPECTED_REPOSITORY,
        workflow_path=guard.EXPECTED_WORKFLOW_PATH,
        workflow_id=WORKFLOW_ID,
        ref="main",
        expected_head_sha=HEAD_SHA,
        expected_actor=ACTOR,
        inputs=valid_inputs(),
        source_identity_authorized=True,
        authorized_session_key="22001",
        authorized_endpoint="weather",
        not_before_utc="2026-10-30T11:00:00Z",
        source_as_of_cutoff_utc="2026-10-30T13:00:00Z",
        history_review_complete=True,
        reviewed_run_input_hashes={} if reviewed is None else reviewed,
        prior_submission_state="none",
        cross_operator_exclusion_confirmed=True,
        cross_operator_lock_id="future-work-order-exclusive-operator-window",
    )


def response(status, body=None):
    return guard.HttpResponse(status=status, json_body=body)


def history_run(run_id, *, workflow_id=WORKFLOW_ID, path=None):
    return {
        "id": run_id,
        "workflow_id": workflow_id,
        "path": path or guard.EXPECTED_WORKFLOW_PATH,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": "b" * 40,
        "run_attempt": 1,
        "created_at": "2026-10-20T12:00:00Z",
        "actor": {"login": "historical-operator"},
        "repository": {"full_name": guard.EXPECTED_REPOSITORY},
    }


def history_response(runs=(), *, total=None):
    values = list(runs)
    return response(200, {"total_count": len(values) if total is None else total, "workflow_runs": values})


def dispatch_response(run_id=RUN_ID, **changes):
    body = {
        "workflow_run_id": run_id,
        "run_url": f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/actions/runs/{run_id}",
        "html_url": f"https://github.com/{guard.EXPECTED_REPOSITORY}/actions/runs/{run_id}",
    }
    body.update(changes)
    return response(200, body)


def exact_run(run_id=RUN_ID):
    return {
        "id": run_id,
        "workflow_id": WORKFLOW_ID,
        "path": guard.EXPECTED_WORKFLOW_PATH,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": HEAD_SHA,
        "run_attempt": 1,
        "run_number": 777,
        "status": "queued",
        "created_at": "2026-10-30T12:00:00Z",
        "url": f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/actions/runs/{run_id}",
        "html_url": f"https://github.com/{guard.EXPECTED_REPOSITORY}/actions/runs/{run_id}",
        "actor": {"login": ACTOR},
        "repository": {"full_name": guard.EXPECTED_REPOSITORY},
        "head_repository": {"full_name": guard.EXPECTED_REPOSITORY},
        "head_commit": {"id": HEAD_SHA},
    }


def expected_candidate(run_id=RUN_ID):
    return {
        "verification_state": "UNVERIFIED_CANDIDATE",
        "id": run_id,
        "run_url": (
            f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/actions/runs/{run_id}"
        ),
        "html_url": f"https://github.com/{guard.EXPECTED_REPOSITORY}/actions/runs/{run_id}",
        "post_started_utc": "2026-10-30T12:00:00Z",
    }


def main_ref_response(**changes):
    body = {
        "ref": "refs/heads/main",
        "object": {
            "type": "commit",
            "sha": HEAD_SHA,
            "url": (
                f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/git/commits/"
                f"{HEAD_SHA}"
            ),
        },
    }
    body.update(changes)
    return response(200, body)


def workflow_blob_response(**changes):
    body = {
        "type": "file",
        "path": guard.EXPECTED_WORKFLOW_PATH,
        "sha": guard.EXPECTED_WORKFLOW_BLOB_SHA,
        "size": 1234,
        "html_url": (
            f"https://github.com/{guard.EXPECTED_REPOSITORY}/blob/{HEAD_SHA}/"
            f"{guard.EXPECTED_WORKFLOW_PATH}"
        ),
        "git_url": (
            f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/git/blobs/"
            f"{guard.EXPECTED_WORKFLOW_BLOB_SHA}"
        ),
    }
    body.update(changes)
    return response(200, body)


def workflow_metadata_response(**changes):
    body = {
        "id": WORKFLOW_ID,
        "path": guard.EXPECTED_WORKFLOW_PATH,
        "state": "active",
        "url": (
            f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/actions/workflows/"
            f"{WORKFLOW_ID}"
        ),
        "html_url": (
            f"https://github.com/{guard.EXPECTED_REPOSITORY}/blob/main/"
            f"{guard.EXPECTED_WORKFLOW_PATH}"
        ),
    }
    body.update(changes)
    return response(200, body)


def protected_preflight_steps():
    return [main_ref_response(), workflow_blob_response(), workflow_metadata_response()]


def successful_steps():
    return [
        history_response(),
        history_response(),
        *protected_preflight_steps(),
        dispatch_response(),
        response(200, exact_run()),
    ]


def execute(
    authority=None,
    steps=None,
    *,
    reader=None,
    credential_available=True,
    clock=fixed_clock,
):
    authority = authority or valid_authority()
    transport = FakeTransport(successful_steps() if steps is None else steps, credential_available=credential_available)
    reader = reader or SequenceAuthorityReader(authority)
    result = guard.run_guard(
        authority_reader=reader,
        transport=transport,
        clock=clock,
        execute=True,
        arm_digest=guard.authority_digest(authority),
    )
    return result, transport, reader


def post_records(transport):
    return [record for record in transport.records if record["method"] == "POST"]


class DefaultAndAuthorityGateTests(unittest.TestCase):
    def test_default_mode_has_zero_transport_calls(self):
        transport = FakeTransport()
        result = guard.run_guard(transport=transport, clock=fixed_clock)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("missing_future_work_order_authority", result.reasons)
        self.assertEqual(transport.records, [])
        self.assertEqual(result.audit["post_calls"], 0)

    def test_valid_dry_run_is_nonexecuting(self):
        authority = valid_authority()
        transport = FakeTransport()
        result = guard.run_guard(
            authority_reader=SequenceAuthorityReader(authority),
            transport=transport,
            clock=fixed_clock,
        )
        self.assertEqual(result.disposition, "DRY_RUN_NO_SIDE_EFFECTS")
        self.assertEqual(result.reasons, ("execution_not_armed",))
        self.assertEqual(transport.records, [])
        self.assertFalse(result.audit["dispatch_identity_verified"])

    def test_missing_future_approval_holds_before_network(self):
        authority = dataclasses.replace(valid_authority(), approved=False)
        transport = FakeTransport()
        result = guard.run_guard(
            authority_reader=SequenceAuthorityReader(authority),
            transport=transport,
            clock=fixed_clock,
            execute=True,
            arm_digest=guard.authority_digest(authority),
        )
        self.assertIn("missing_future_execution_approval", result.reasons)
        self.assertEqual(transport.records, [])

    def test_missing_or_wrong_arm_holds_before_network(self):
        authority = valid_authority()
        for arm in (None, "0" * 64):
            with self.subTest(arm=arm):
                transport = FakeTransport()
                result = guard.run_guard(
                    authority_reader=SequenceAuthorityReader(authority),
                    transport=transport,
                    clock=fixed_clock,
                    execute=True,
                    arm_digest=arm,
                )
                self.assertIn("arm_digest_missing_or_mismatched", result.reasons)
                self.assertEqual(transport.records, [])

    def test_missing_runtime_credential_holds_before_network(self):
        result, transport, _ = execute(credential_available=False)
        self.assertIn("runtime_credential_missing", result.reasons)
        self.assertEqual(transport.records, [])

    def test_branch_workflow_repository_and_head_scope_fail_closed(self):
        cases = [
            ("branch", dataclasses.replace(valid_authority(), ref="feature"), "ref_must_be_main"),
            (
                "workflow",
                dataclasses.replace(valid_authority(), workflow_path=".github/workflows/other.yml"),
                "workflow_scope_mismatch",
            ),
            (
                "repository",
                dataclasses.replace(valid_authority(), repository="attacker/example"),
                "repository_scope_mismatch",
            ),
            ("head", dataclasses.replace(valid_authority(), expected_head_sha="main"), "head_sha_missing_or_invalid"),
        ]
        for label, authority, reason in cases:
            with self.subTest(label=label):
                transport = FakeTransport()
                result = guard.run_guard(
                    authority_reader=SequenceAuthorityReader(authority),
                    transport=transport,
                    clock=fixed_clock,
                    execute=True,
                    arm_digest=guard.authority_digest(authority),
                )
                self.assertIn(reason, result.reasons)
                self.assertEqual(transport.records, [])

    def test_source_scope_requires_explicit_identity_not_api_values_alone(self):
        cases = [
            (dataclasses.replace(valid_authority(), source_identity_authorized=False), "source_identity_not_user_authorized"),
            (dataclasses.replace(valid_authority(), authorized_session_key="22002"), "session_key_authority_mismatch"),
            (dataclasses.replace(valid_authority(), authorized_endpoint="drivers"), "endpoint_authority_mismatch"),
            (
                dataclasses.replace(
                    valid_authority(),
                    inputs={**valid_inputs(), "provenance_shadow_endpoint": "telemetry"},
                ),
                "endpoint_not_allowed",
            ),
        ]
        for authority, reason in cases:
            with self.subTest(reason=reason):
                transport = FakeTransport()
                result = guard.run_guard(
                    authority_reader=SequenceAuthorityReader(authority),
                    transport=transport,
                    clock=fixed_clock,
                    execute=True,
                    arm_digest=guard.authority_digest(authority),
                )
                self.assertIn(reason, result.reasons)
                self.assertEqual(transport.records, [])

    def test_time_window_and_cutoff_fail_closed(self):
        cases = [
            (
                dataclasses.replace(valid_authority(), not_before_utc="2026-10-30T12:01:00Z"),
                "not_before_gate_closed",
            ),
            (
                dataclasses.replace(valid_authority(), source_as_of_cutoff_utc="2026-10-30T12:00:00Z"),
                "source_cutoff_reached",
            ),
            (
                dataclasses.replace(valid_authority(), source_as_of_cutoff_utc="not-a-time"),
                "source_cutoff_missing_or_invalid",
            ),
        ]
        for authority, reason in cases:
            with self.subTest(reason=reason):
                transport = FakeTransport()
                result = guard.run_guard(
                    authority_reader=SequenceAuthorityReader(authority),
                    transport=transport,
                    clock=fixed_clock,
                    execute=True,
                    arm_digest=guard.authority_digest(authority),
                )
                self.assertIn(reason, result.reasons)
                self.assertEqual(transport.records, [])

    def test_ambiguous_prior_submission_and_operator_risk_hold(self):
        cases = [
            (dataclasses.replace(valid_authority(), history_review_complete=False), "manual_history_review_incomplete"),
            (dataclasses.replace(valid_authority(), prior_submission_state="unknown"), "prior_submission_state_not_clear"),
            (
                dataclasses.replace(valid_authority(), cross_operator_exclusion_confirmed=False),
                "cross_operator_duplicate_risk_unresolved",
            ),
            (dataclasses.replace(valid_authority(), cross_operator_lock_id=""), "cross_operator_lock_missing"),
        ]
        for authority, reason in cases:
            with self.subTest(reason=reason):
                transport = FakeTransport()
                result = guard.run_guard(
                    authority_reader=SequenceAuthorityReader(authority),
                    transport=transport,
                    clock=fixed_clock,
                    execute=True,
                    arm_digest=guard.authority_digest(authority),
                )
                self.assertIn(reason, result.reasons)
                self.assertEqual(transport.records, [])

    def test_default_cli_writes_no_files_and_does_no_network(self):
        with tempfile.TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            proc = subprocess.run(
                [sys.executable, str(MODULE_PATH)],
                cwd=directory,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 20)
            self.assertEqual(set(Path(directory).iterdir()), before)
            parsed = json.loads(proc.stdout)
            self.assertEqual(parsed["disposition"], "HOLD")
            self.assertEqual(parsed["audit"]["post_calls"], 0)


class HistoryAndConcurrencyTests(unittest.TestCase):
    def test_existing_matching_reviewed_run_holds_with_zero_post(self):
        authority = valid_authority(reviewed={123: guard.input_digest(valid_inputs())})
        transport = FakeTransport()
        result = guard.run_guard(
            authority_reader=SequenceAuthorityReader(authority),
            transport=transport,
            clock=fixed_clock,
            execute=True,
            arm_digest=guard.authority_digest(authority),
        )
        self.assertIn("existing_matching_original_run", result.reasons)
        self.assertEqual(post_records(transport), [])

    def test_unreviewed_history_run_is_ambiguous_and_never_posts(self):
        authority = valid_authority()
        result, transport, _ = execute(authority, [history_response([history_run(123)])])
        self.assertIn("unknown_or_missing_reviewed_manual_run", result.reasons)
        self.assertEqual(post_records(transport), [])

    def test_fully_paginated_history_is_read_twice_before_one_post(self):
        runs = [history_run(index) for index in range(1, 102)]
        reviewed = {run["id"]: "b" * 64 for run in runs}
        authority = valid_authority(reviewed=reviewed)
        pages = [
            history_response(runs[:100], total=101),
            history_response(runs[100:], total=101),
            history_response(runs[:100], total=101),
            history_response(runs[100:], total=101),
            *protected_preflight_steps(),
            dispatch_response(),
            response(200, exact_run()),
        ]
        result, transport, _ = execute(authority, pages)
        self.assertEqual(result.disposition, "DISPATCH_IDENTITY_VERIFIED")
        self.assertEqual(result.audit["history_get_calls"], 4)
        self.assertEqual(len(post_records(transport)), 1)
        self.assertFalse(transport.steps)

    def test_pagination_gap_and_total_change_hold_before_post(self):
        authority = valid_authority()
        cases = [
            [history_response([history_run(i) for i in range(1, 51)], total=101)],
            [
                history_response([history_run(i) for i in range(1, 101)], total=101),
                history_response([history_run(101)], total=102),
            ],
        ]
        expected = ["history_pagination_gap", "history_total_changed_during_pagination"]
        for steps, reason in zip(cases, expected):
            with self.subTest(reason=reason):
                result, transport, _ = execute(authority, steps)
                self.assertIn(reason, result.reasons)
                self.assertEqual(post_records(transport), [])

    def test_malformed_history_identity_holds_before_post(self):
        authority = valid_authority(reviewed={123: "b" * 64})
        mutations = {
            "path": None,
            "head_sha": None,
            "run_attempt": 0,
            "event": "schedule",
            "actor": {"login": "bad\nactor"},
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                bad = history_run(123)
                bad[field] = value
                result, transport, _ = execute(authority, [history_response([bad])])
                self.assertIn("history_run_identity_ambiguous", result.reasons)
                self.assertEqual(post_records(transport), [])

    def test_delayed_original_run_between_reads_holds_before_post(self):
        authority = valid_authority()
        steps = [history_response(), history_response([history_run(123)])]
        result, transport, _ = execute(authority, steps)
        self.assertIn("delayed_or_concurrent_manual_run_detected", result.reasons)
        self.assertEqual(post_records(transport), [])

    def test_concurrent_authority_drift_holds_before_second_history_and_post(self):
        authority = valid_authority()
        drifted = dataclasses.replace(authority, cross_operator_lock_id="changed-authority")
        reader = SequenceAuthorityReader(authority, drifted)
        result, transport, _ = execute(authority, [history_response()], reader=reader)
        self.assertIn("concurrent_authority_drift", result.reasons)
        self.assertEqual(len(transport.records), 1)
        self.assertEqual(post_records(transport), [])

    def test_final_authority_drift_after_network_preflight_holds_before_post(self):
        authority = valid_authority()
        drifted = dataclasses.replace(authority, cross_operator_lock_id="changed-at-final-gate")
        reader = SequenceAuthorityReader(authority, authority, drifted)
        result, transport, _ = execute(
            authority,
            [history_response(), history_response(), *protected_preflight_steps()],
            reader=reader,
        )
        self.assertIn("final_authority_drift", result.reasons)
        self.assertEqual(post_records(transport), [])

    def test_elapsed_source_cutoff_after_preflight_holds_before_post(self):
        cutoff = dt.datetime(2026, 10, 30, 13, 0, tzinfo=dt.timezone.utc)
        clock = SequenceClock(NOW, cutoff)
        result, transport, _ = execute(
            steps=[history_response(), history_response(), *protected_preflight_steps()],
            clock=clock,
        )
        self.assertIn("dispatch_time_window_closed_before_post", result.reasons)
        self.assertEqual(post_records(transport), [])

    def test_history_http_and_connection_failures_hold_without_post(self):
        for step, reason in [
            (response(403, {"message": "forbidden"}), "history_http_403"),
            (TimeoutError(), "history_request_exception_TimeoutError"),
            (ConnectionResetError(), "history_request_exception_ConnectionResetError"),
        ]:
            with self.subTest(reason=reason):
                result, transport, _ = execute(steps=[step])
                self.assertIn(reason, result.reasons)
                self.assertEqual(post_records(transport), [])


class ProtectedWorkflowPreflightTests(unittest.TestCase):
    def test_success_reads_exact_main_ref_and_pinned_workflow_before_post(self):
        result, transport, _ = execute()
        self.assertEqual(result.disposition, "DISPATCH_IDENTITY_VERIFIED")
        self.assertEqual(result.audit["protected_preflight_get_calls"], 3)
        self.assertEqual(
            transport.records[2]["url"],
            (
                f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/git/ref/heads/"
                "main"
            ),
        )
        self.assertEqual(
            transport.records[3]["url"],
            (
                f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/contents/"
                f"{guard.EXPECTED_WORKFLOW_PATH}?ref={HEAD_SHA}"
            ),
        )
        self.assertEqual(
            transport.records[4]["url"],
            (
                f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/actions/workflows/"
                f"{WORKFLOW_ID}"
            ),
        )
        self.assertEqual(transport.records[5]["method"], "POST")

    def test_main_ref_drift_or_hostile_metadata_holds_before_post(self):
        wrong_sha = "c" * 40
        cases = [
            main_ref_response(ref="refs/heads/feature"),
            response(
                200,
                {
                    "ref": "refs/heads/main",
                    "object": {
                        "type": "commit",
                        "sha": wrong_sha,
                        "url": (
                            f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/git/"
                            f"commits/{wrong_sha}"
                        ),
                    },
                },
            ),
            response(
                200,
                {
                    "ref": "refs/heads/main",
                    "object": {
                        "type": "commit",
                        "sha": HEAD_SHA,
                        "url": f"https://evil.example/git/commits/{HEAD_SHA}",
                    },
                },
            ),
        ]
        for bad_ref in cases:
            with self.subTest(body=bad_ref.json_body):
                result, transport, _ = execute(
                    steps=[history_response(), history_response(), bad_ref]
                )
                self.assertIn("main_ref_identity_mismatch", result.reasons)
                self.assertEqual(post_records(transport), [])

    def test_workflow_blob_drift_or_hostile_metadata_holds_before_post(self):
        cases = [
            workflow_blob_response(sha="c" * 40),
            workflow_blob_response(path=".github/workflows/other.yml"),
            workflow_blob_response(type="dir"),
            workflow_blob_response(size=0),
            workflow_blob_response(html_url="https://evil.example/workflow.yml"),
            workflow_blob_response(git_url="https://api.github.com@evil.example/blob"),
        ]
        for bad_blob in cases:
            with self.subTest(body=bad_blob.json_body):
                result, transport, _ = execute(
                    steps=[history_response(), history_response(), main_ref_response(), bad_blob]
                )
                self.assertIn("protected_workflow_identity_mismatch", result.reasons)
                self.assertEqual(post_records(transport), [])

    def test_workflow_id_path_state_or_links_hold_before_post(self):
        cases = [
            workflow_metadata_response(id=WORKFLOW_ID + 1),
            workflow_metadata_response(path=".github/workflows/other.yml"),
            workflow_metadata_response(state="disabled_manually"),
            workflow_metadata_response(url="https://evil.example/workflows/1"),
            workflow_metadata_response(html_url="https://github.com/other/repo/blob/main/x.yml"),
        ]
        for metadata in cases:
            with self.subTest(body=metadata.json_body):
                result, transport, _ = execute(
                    steps=[
                        history_response(),
                        history_response(),
                        main_ref_response(),
                        workflow_blob_response(),
                        metadata,
                    ]
                )
                self.assertIn("workflow_metadata_identity_mismatch", result.reasons)
                self.assertEqual(post_records(transport), [])

    def test_preflight_http_timeout_and_reset_fail_closed_without_post(self):
        cases = [
            (
                [history_response(), history_response(), response(404)],
                "main_ref_http_404",
            ),
            (
                [history_response(), history_response(), TimeoutError()],
                "main_ref_request_exception_TimeoutError",
            ),
            (
                [history_response(), history_response(), main_ref_response(), response(403)],
                "protected_workflow_http_403",
            ),
            (
                [history_response(), history_response(), main_ref_response(), ConnectionResetError()],
                "protected_workflow_request_exception_ConnectionResetError",
            ),
            (
                [
                    history_response(),
                    history_response(),
                    main_ref_response(),
                    workflow_blob_response(),
                    response(404),
                ],
                "workflow_metadata_http_404",
            ),
            (
                [
                    history_response(),
                    history_response(),
                    main_ref_response(),
                    workflow_blob_response(),
                    TimeoutError(),
                ],
                "workflow_metadata_request_exception_TimeoutError",
            ),
        ]
        for steps, reason in cases:
            with self.subTest(reason=reason):
                result, transport, _ = execute(steps=steps)
                self.assertIn(reason, result.reasons)
                self.assertEqual(post_records(transport), [])


class DispatchResponseTests(unittest.TestCase):
    def test_mocked_200_returns_dispatch_identity_only_and_exact_post_body(self):
        authority = valid_authority()
        result, transport, _ = execute(authority)
        self.assertEqual(result.disposition, "DISPATCH_IDENTITY_VERIFIED")
        self.assertTrue(result.audit["dispatch_response_accepted"])
        self.assertTrue(result.audit["dispatch_identity_verified"])
        self.assertEqual(result.audit["unverified_candidate_run"], expected_candidate())
        self.assertEqual(
            result.audit["original_run"]["verification_state"], "VERIFIED_ORIGINAL_RUN"
        )
        self.assertEqual(result.audit["original_run"]["id"], RUN_ID)
        self.assertIsNone(result.audit["source_job_succeeded"])
        self.assertIsNone(result.audit["source_content_valid"])
        self.assertIsNone(result.audit["same_run_custody_attested"])
        self.assertFalse(result.audit["scientific_ex_ante_eligible"])
        posts = post_records(transport)
        self.assertEqual(len(posts), 1)
        self.assertEqual(
            posts[0]["json_body"],
            {"ref": "main", "inputs": valid_inputs(), "return_run_details": True},
        )
        self.assertEqual(result.audit["post_calls"], 1)
        self.assertEqual(result.audit["run_get_calls"], 1)
        self.assertEqual(result.audit["protected_preflight_get_calls"], 3)

    def test_204_is_terminal_ambiguous_hold_and_never_retries(self):
        result, transport, _ = execute(
            steps=[
                history_response(),
                history_response(),
                *protected_preflight_steps(),
                response(204),
            ]
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("dispatch_204_no_run_identity", result.reasons)
        self.assertIsNone(result.audit["unverified_candidate_run"])
        self.assertEqual(len(post_records(transport)), 1)
        self.assertEqual(len(transport.records), 6)

    def test_malformed_200_responses_hold_after_exactly_one_post(self):
        malformed = [
            None,
            {},
            {"workflow_run_id": 1, "run_url": "x"},
            {
                "workflow_run_id": True,
                "run_url": "https://api.github.com/repos/x/y/actions/runs/1",
                "html_url": "https://github.com/x/y/actions/runs/1",
            },
            {
                "workflow_run_id": RUN_ID,
                "run_url": f"https://api.github.com/repos/{guard.EXPECTED_REPOSITORY}/actions/runs/{RUN_ID}",
                "html_url": f"https://github.com/{guard.EXPECTED_REPOSITORY}/actions/runs/{RUN_ID}",
                "unexpected": "field",
            },
        ]
        for body in malformed:
            with self.subTest(body=body):
                result, transport, _ = execute(
                    steps=[
                        history_response(),
                        history_response(),
                        *protected_preflight_steps(),
                        response(200, body),
                    ]
                )
                self.assertEqual(result.disposition, "HOLD")
                self.assertEqual(len(post_records(transport)), 1)
                self.assertEqual(result.audit["run_get_calls"], 0)
                self.assertIsNone(result.audit["unverified_candidate_run"])

    def test_invalid_transport_response_after_post_is_structured_hold(self):
        result, transport, _ = execute(
            steps=[
                history_response(),
                history_response(),
                *protected_preflight_steps(),
                object(),
            ]
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("dispatch_response_invalid", result.reasons)
        self.assertEqual(result.audit["post_calls"], 1)
        self.assertEqual(len(post_records(transport)), 1)
        self.assertFalse(result.audit["dispatch_response_accepted"])
        self.assertIsNone(result.audit["unverified_candidate_run"])

    def test_hostile_or_mismatched_links_are_rejected(self):
        cases = [
            dispatch_response(run_url=f"https://evil.example/actions/runs/{RUN_ID}"),
            dispatch_response(html_url=f"https://github.com/other/repo/actions/runs/{RUN_ID}"),
            dispatch_response(
                html_url=f"https://github.com/{guard.EXPECTED_REPOSITORY}/actions/runs/{RUN_ID}?token=secret"
            ),
            dispatch_response(run_url=f"https://api.github.com@evil.example/actions/runs/{RUN_ID}"),
        ]
        for bad_response in cases:
            with self.subTest(body=bad_response.json_body):
                result, transport, _ = execute(
                    steps=[
                        history_response(),
                        history_response(),
                        *protected_preflight_steps(),
                        bad_response,
                    ]
                )
                self.assertEqual(result.disposition, "HOLD")
                self.assertEqual(len(post_records(transport)), 1)
                self.assertFalse(result.audit["dispatch_response_accepted"])
                self.assertIsNone(result.audit["unverified_candidate_run"])

    def test_redirect_4xx_rate_limit_and_5xx_never_retry(self):
        for status in (301, 302, 401, 403, 422, 429, 500, 502, 503):
            with self.subTest(status=status):
                result, transport, _ = execute(
                    steps=[
                        history_response(),
                        history_response(),
                        *protected_preflight_steps(),
                        response(status),
                    ]
                )
                self.assertEqual(result.disposition, "HOLD")
                self.assertIn(f"dispatch_http_{status}", result.reasons)
                self.assertEqual(len(post_records(transport)), 1)
                self.assertEqual(result.audit["post_calls"], 1)

    def test_timeout_and_connection_reset_are_terminal_after_one_post(self):
        for exc in (TimeoutError(), ConnectionResetError()):
            with self.subTest(exc=type(exc).__name__):
                result, transport, _ = execute(
                    steps=[
                        history_response(),
                        history_response(),
                        *protected_preflight_steps(),
                        exc,
                    ]
                )
                self.assertEqual(result.disposition, "HOLD")
                self.assertIn(f"dispatch_request_exception_{type(exc).__name__}", result.reasons)
                self.assertEqual(len(post_records(transport)), 1)
                self.assertEqual(len(transport.records), 6)


class ExactRunIdentityTests(unittest.TestCase):
    def test_unexpected_run_metadata_is_rejected_field_by_field(self):
        mutations = {
            "id": 42,
            "workflow_id": 1,
            "path": ".github/workflows/other.yml",
            "event": "schedule",
            "head_branch": "feature",
            "head_sha": "c" * 40,
            "run_attempt": 2,
            "url": "https://api.github.com/repos/attacker/repo/actions/runs/7788990011",
            "html_url": "https://github.com/attacker/repo/actions/runs/7788990011",
            "actor": {"login": "other-actor"},
            "repository": {"full_name": "attacker/repo"},
            "head_repository": {"full_name": "attacker/repo"},
            "head_commit": {"id": "c" * 40},
            "run_number": 0,
            "created_at": "2026-10-30T14:00:00Z",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                run = exact_run()
                run[field] = value
                result, transport, _ = execute(
                    steps=[
                        history_response(),
                        history_response(),
                        *protected_preflight_steps(),
                        dispatch_response(),
                        response(200, run),
                    ]
                )
                self.assertEqual(result.disposition, "HOLD")
                self.assertEqual(len(post_records(transport)), 1)
                self.assertFalse(result.audit["dispatch_identity_verified"])
                self.assertEqual(result.audit["unverified_candidate_run"], expected_candidate())
                self.assertIsNone(result.audit["original_run"])
                assessment = guard.assess_follow_on_evidence(
                    result, guard.FollowOnEvidence(True, True, True, True)
                )
                self.assertFalse(assessment["weather_source_eligible"])
                self.assertFalse(assessment["scientific_ex_ante_eligible"])
                self.assertFalse(assessment["forecast_ready"])

    def test_unexpected_run_validation_exception_preserves_candidate_and_holds(self):
        result, transport, _ = execute(
            steps=[
                history_response(),
                history_response(),
                *protected_preflight_steps(),
                dispatch_response(),
                response(200, RaisingRunMapping(exact_run())),
            ]
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("run_validation_exception_RuntimeError", result.reasons)
        self.assertEqual(result.audit["post_calls"], 1)
        self.assertEqual(len(post_records(transport)), 1)
        self.assertTrue(result.audit["dispatch_response_accepted"])
        self.assertEqual(result.audit["unverified_candidate_run"], expected_candidate())
        self.assertFalse(result.audit["dispatch_identity_verified"])
        self.assertIsNone(result.audit["original_run"])

    def test_run_get_failure_is_hold_without_second_post(self):
        for step, reason in [
            (response(404), "run_verification_http_404"),
            (TimeoutError(), "run_verification_exception_TimeoutError"),
            (ConnectionResetError(), "run_verification_exception_ConnectionResetError"),
            (object(), "run_verification_response_invalid"),
        ]:
            with self.subTest(reason=reason):
                result, transport, _ = execute(
                    steps=[
                        history_response(),
                        history_response(),
                        *protected_preflight_steps(),
                        dispatch_response(),
                        step,
                    ]
                )
                self.assertIn(reason, result.reasons)
                self.assertTrue(result.audit["dispatch_response_accepted"])
                self.assertFalse(result.audit["dispatch_identity_verified"])
                self.assertEqual(len(post_records(transport)), 1)
                self.assertEqual(result.audit["post_calls"], 1)
                self.assertEqual(result.audit["unverified_candidate_run"], expected_candidate())
                self.assertIsNone(result.audit["original_run"])
                assessment = guard.assess_follow_on_evidence(
                    result, guard.FollowOnEvidence(True, True, True, True)
                )
                self.assertFalse(assessment["weather_source_eligible"])
                self.assertFalse(assessment["scientific_ex_ante_eligible"])
                self.assertFalse(assessment["forecast_ready"])

    def test_post_dispatch_clock_failures_preserve_candidate_and_hold(self):
        naive = dt.datetime(2026, 10, 30, 12, 0)
        broken_timezone = dt.datetime(2026, 10, 30, 12, 0, tzinfo=BrokenTimezone())
        cases = [
            (RuntimeError("clock failed"), "post_dispatch_clock_error_RuntimeError"),
            (naive, "post_dispatch_clock_not_timezone_aware"),
            ("not-a-datetime", "post_dispatch_clock_not_datetime"),
            (broken_timezone, "post_dispatch_clock_timezone_error_RuntimeError"),
        ]
        for clock_value, reason in cases:
            with self.subTest(reason=reason):
                clock = SequenceClock(NOW, NOW, clock_value)
                result, transport, _ = execute(clock=clock)
                self.assertEqual(result.disposition, "HOLD")
                self.assertIn(reason, result.reasons)
                self.assertEqual(result.audit["post_calls"], 1)
                self.assertEqual(len(post_records(transport)), 1)
                self.assertTrue(result.audit["dispatch_response_accepted"])
                self.assertEqual(result.audit["unverified_candidate_run"], expected_candidate())
                self.assertFalse(result.audit["dispatch_identity_verified"])
                self.assertIsNone(result.audit["original_run"])
                assessment = guard.assess_follow_on_evidence(
                    result, guard.FollowOnEvidence(True, True, True, True)
                )
                self.assertFalse(assessment["weather_source_eligible"])
                self.assertFalse(assessment["scientific_ex_ante_eligible"])
                self.assertFalse(assessment["forecast_ready"])


class ScientificBoundaryAndAuditTests(unittest.TestCase):
    def test_later_failures_never_become_weather_receipt_or_forecast_ready(self):
        dispatch, _, _ = execute()
        cases = [
            guard.FollowOnEvidence(False, True, True, True),
            guard.FollowOnEvidence(True, False, True, True),
            guard.FollowOnEvidence(True, True, False, True),
            guard.FollowOnEvidence(True, True, True, False),
            guard.FollowOnEvidence(None, None, None, None),
            guard.FollowOnEvidence(True, True, True, True),
        ]
        for evidence in cases:
            with self.subTest(evidence=evidence):
                assessment = guard.assess_follow_on_evidence(dispatch, evidence)
                self.assertFalse(assessment["weather_source_eligible"])
                self.assertFalse(assessment["scientific_ex_ante_eligible"])
                self.assertFalse(assessment["forecast_ready"])
                self.assertIn("independent_scientific_verification_required", assessment["reasons"])

    def test_audit_is_safe_and_contains_required_limitations(self):
        result, _, _ = execute()
        rendered = json.dumps(result.to_dict(), sort_keys=True)
        self.assertNotIn("Authorization", rendered)
        self.assertNotIn("Bearer", rendered)
        self.assertNotIn("GITHUB_TOKEN", rendered)
        self.assertEqual(result.audit["input_sha256"], guard.input_digest(valid_inputs()))
        self.assertEqual(result.audit["post_calls"], 1)
        self.assertIn("do not prove original form inputs", result.audit["history_input_limitation"])
        self.assertIn("cannot provide a global exactly-once guarantee", result.audit["toctou_residual"])
        self.assertIn("Actions write", result.audit["credential_permissions_required"])
        self.assertIn("separate future work order", result.audit["activation_requirement"])
        self.assertIn("self-declared local JSON", result.audit["authority_control_limitation"])
        self.assertIn(
            "not cryptographic independent authorization",
            result.audit["authority_control_limitation"],
        )
        self.assertIn("not a shared distributed lock", result.audit["authority_control_limitation"])

    def test_authority_digest_is_stable_and_changes_with_scope(self):
        authority = valid_authority()
        first = guard.authority_digest(authority)
        second = guard.authority_digest(valid_authority())
        changed = guard.authority_digest(dataclasses.replace(authority, authorized_session_key="22002"))
        self.assertEqual(first, second)
        self.assertRegex(first, r"^[0-9a-f]{64}$")
        self.assertNotEqual(first, changed)


if __name__ == "__main__":
    unittest.main()
