"""Offline original Actions completion + real source/consumer custody integration."""
import copy
import contextlib
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

import test_f1_1b_integrated_recovery_peak_handoff as fixtures

peak = fixtures.peak_mod


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PeakHandoffTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.now = self.fixture.now
        self.fixture.observe()
        self.env = dict(GITHUB_EVENT_NAME="schedule", UPSTREAM_RUN_ID="", UPSTREAM_RUN_ATTEMPT="",
                        UPSTREAM_HEAD_SHA="", GITHUB_REPOSITORY="F1Lllewellyn/f1-data-publisher")
        self.enterContext(patch.dict(os.environ, self.env))
        self.original = dict(id=1234, run_attempt=1, head_sha="a" * 40, head_branch="main",
            path=".github/workflows/f1-peak-elite-control-room-one-click-v1.yml",
            repository=dict(full_name="F1Lllewellyn/f1-data-publisher"),
            head_repository=dict(full_name="F1Lllewellyn/f1-data-publisher"),
            event="schedule", status="completed", conclusion="success",
            run_started_at="2026-11-07T16:59:00Z", updated_at="2026-11-07T17:02:00Z")

    def reconcile(self, original=None, now=None):
        with patch.object(peak, "fetch_original_run", return_value=self.original if original is None else original):
            return peak.reconcile_bridge_input(self.root, reference_time=now or self.now)

    def outputs(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for folder in ("latest", "history")
                for p in (self.root / folder).rglob("*") if p.is_file()}

    def consume(self):
        for label, filename, clock in (
            ("contract", "f1_1b_output_contract_v16.py", "utc_now"),
            ("downstream", "f1_1b_downstream_consumer_handoff_v24.py", "utc_now_iso"),
            ("context", "f1_1b_consumer_context_publisher_v25.py", "utc_now_iso"),
        ):
            module = fixtures.fixtures.load_module(label, "scripts/session_data_processor/" + filename)
            with patch.object(module, clock, return_value=self.now if clock == "utc_now" else self.now.isoformat()), contextlib.redirect_stdout(io.StringIO()):
                module.run(self.root)
        receipt = peak.verify_bridge_output(self.root, reference_time=self.now)
        self.assertEqual(receipt["status"], "VERIFIED_CONTEXT_ONLY", receipt)
        fixtures.write(self.root / "latest/1b_output_contract/verified_context_custody.json", receipt)

    def test_natural_scheduled_peak_native_handoff_and_duplicate_are_authenticated(self):
        with patch.dict(os.environ, self.fixture.env):
            result = self.reconcile()
            self.assertEqual(result["action"], "PROCESS", result)
            self.consume()
            before = self.outputs()
            self.assertEqual(self.reconcile()["action"], "NOOP_ALREADY_VERIFIED")
            self.assertEqual(before, self.outputs())

    def test_token_dispatched_peak_without_native_event_recovers_same_original_run(self):
        self.original["event"] = "workflow_dispatch"
        result = self.reconcile()
        self.assertEqual((result["action"], result["upstream_run_id"], result["upstream_run_attempt"]), ("PROCESS", "1234", "1"))
        self.consume()
        before = self.outputs()
        self.assertEqual(self.reconcile()["action"], "NOOP_ALREADY_VERIFIED")
        self.assertEqual(self.outputs(), before)

    def test_delayed_native_trigger_does_not_substitute_another_current_run(self):
        for name in ("UPSTREAM_RUN_ID", "UPSTREAM_RUN_ATTEMPT", "UPSTREAM_HEAD_SHA"):
            with self.subTest(name=name), patch.dict(os.environ, dict(self.fixture.env, **{name: "different"})):
                self.assertEqual(self.reconcile()["action"], "HOLD")

    def test_direct_and_reconciled_pins_are_enforced_outside_workflow_run(self):
        with patch.dict(os.environ, {"UPSTREAM_RUN_ID": "999"}):
            self.assertEqual(peak.verify_bridge_input(self.root, self.now)["status"], "HOLD")

    def test_failed_canceled_skipped_running_and_rerun_attempt_are_not_completion(self):
        for status, conclusion, attempt in (("completed", "failure", 1), ("completed", "cancelled", 1),
                ("completed", "skipped", 1), ("in_progress", None, 1), ("queued", None, 1),
                ("completed", "success", 2)):
            with self.subTest(status=status, conclusion=conclusion, attempt=attempt):
                run = dict(self.original, status=status, conclusion=conclusion, run_attempt=attempt)
                self.assertEqual(self.reconcile(run)["action"], "HOLD")

    def test_wrong_repository_workflow_event_branch_or_head_cannot_authenticate(self):
        for key, value in (("id", 999), ("path", ".github/workflows/other.yml"),
                           ("head_branch", "repair/fake"), ("head_sha", "b" * 40),
                           ("event", "pull_request"), ("repository", {"full_name": "untrusted/fork"}),
                           ("head_repository", {"full_name": "untrusted/fork"})):
            with self.subTest(key=key):
                self.assertEqual(self.reconcile(dict(self.original, **{key: value}))["action"], "HOLD")

    def test_source_alteration_or_stale_session_blocks_before_api_or_writes(self):
        path = self.root / "latest/combined_source_manifest.json"
        before = path.read_bytes()
        path.write_bytes(before + b" ")
        with patch.object(peak, "fetch_original_run") as api:
            self.assertEqual(peak.reconcile_bridge_input(self.root, self.now)["action"], "HOLD")
            api.assert_not_called()
        path.write_bytes(before)
        self.assertEqual(self.reconcile(now=self.now.replace(hour=21))["action"], "HOLD")

    def test_prior_receipt_or_output_tampering_never_becomes_duplicate_success(self):
        self.assertEqual(self.reconcile()["action"], "PROCESS")
        self.consume()
        receipt = self.root / "latest/1b_output_contract/verified_context_custody.json"
        original = receipt.read_bytes()
        for mutation in (lambda r: r.update(prediction_locked=True), lambda r: r.update(status="HOLD"),
                         lambda r: r["output_fingerprints"].clear()):
            data = json.loads(original); mutation(data); fixtures.write(receipt, data)
            self.assertEqual(self.reconcile()["action"], "HOLD")
        receipt.write_bytes(original)
        output = self.root / "latest/downstream_consumers/race_predictions/consumer_input.json"
        output.write_bytes(output.read_bytes() + b" ")
        self.assertEqual(self.reconcile()["action"], "HOLD")

    def test_original_api_outages_fail_closed_without_retry_or_token_leak(self):
        for code in (401, 403, 429, 503):
            with self.subTest(code=code), patch.object(peak, "fetch_original_run", side_effect=
                    urllib.error.HTTPError("fixture", code, "secret must not be echoed", {}, None)) as api:
                result = peak.reconcile_bridge_input(self.root, self.now)
                self.assertEqual(api.call_count, 1)
                self.assertEqual(result["action"], "HOLD")
                self.assertNotIn("secret", json.dumps(result))

    def test_recheck_after_consumption_detects_restarted_original_attempt(self):
        self.assertEqual(self.reconcile()["action"], "PROCESS")
        self.consume()
        with patch.object(peak, "fetch_original_run", return_value=dict(self.original, run_attempt=2)):
            self.assertEqual(peak.verify_bridge_origin(self.root, self.now)["status"], "HOLD")

    def test_original_completion_clock_cannot_be_future_missing_or_before_report(self):
        for value in ("2026-11-07T18:01:00Z", "2026-11-07T16:59:00Z", "not-a-clock", "2026-11-07T17:02:00"):
            self.assertEqual(self.reconcile(dict(self.original, updated_at=value))["action"], "HOLD")

    def test_workflow_reconciles_without_dispatch_and_skips_all_duplicate_writers(self):
        import yaml
        workflow = yaml.safe_load((fixtures.ROOT / ".github/workflows/f1-1b-output-contract-after-control-room-v22.yml").read_text())
        triggers = workflow.get("on", workflow.get(True))
        self.assertTrue(triggers["schedule"])
        self.assertIn("workflow_run", triggers)
        steps = workflow["jobs"]["output-contract-after-control-room"]["steps"]
        for step in steps:
            if any(token in step.get("run", "") for token in
                    ("f1_1b_output_contract_v16.py", "f1_1b_downstream_consumer_handoff_v24.py",
                     "f1_1b_consumer_context_publisher_v25.py", "git commit", "verify_bridge_output")):
                self.assertIn("steps.reconcile.outputs.action == 'PROCESS'", step["if"])
        self.assertEqual(workflow["concurrency"]["group"], "f1-main-write-serialization")
        self.assertNotIn("actions: write", json.dumps(workflow))


if __name__ == "__main__":
    unittest.main()
