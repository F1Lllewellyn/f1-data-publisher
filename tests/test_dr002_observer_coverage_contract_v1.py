import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts/forecast_bundles"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "observer_coverage", SCRIPTS / "dr002_observer_coverage_contract_v1.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import verify_forecast_integrity_receipts_v1 as receipts


def utc(minute, second=0):
    return "2026-10-07T12:" + str(minute).zfill(2) + ":" + str(second).zfill(2) + "Z"


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class ObserverCoverageTests(unittest.TestCase):
    def setUp(self):
        self.scope = {
            "source_id": "synthetic:publisher:drivers",
            "source_uri": "https://publisher.example/drivers",
            "event_id": "event",
            "meeting_id": "meeting",
            "session_id": "session",
        }
        self.window = {"start_utc": utc(0), "end_utc": utc(30)}
        self.slots = [
            {"slot_id": "slot-1", "due_utc": utc(5)},
            {"slot_id": "slot-2", "due_utc": utc(10)},
            {"slot_id": "slot-3", "due_utc": utc(15)},
        ]
        self.attempts = [
            {"slot_id": slot["slot_id"], "status": "SUCCESS", "observed_utc": slot["due_utc"]}
            for slot in self.slots
        ]
        self.source_bytes = {
            slot["slot_id"]: ("content-" + slot["slot_id"]).encode()
            for slot in self.slots
        }
        self.receipt_bytes = {
            slot["slot_id"]: self.capture_bytes(slot["slot_id"], slot["due_utc"])
            for slot in self.slots
        }

    def capture_bytes(self, slot_id, observed, **overrides):
        data = self.source_bytes[slot_id]
        receipt = {
            "schema_version": receipts.VERSION,
            "receipt_id": "source_capture:" + slot_id,
            "receipt_type": "source_capture",
            "receipt_created_utc": observed[:-1] + ".500000Z",
            "scope": {key: self.scope[key] for key in receipts.SCOPE},
            "parent_receipt_ids": [],
            "payload": {
                "source_id": self.scope["source_id"],
                "source_uri": self.scope["source_uri"],
                "source_sha256": receipts.sha256(data),
                "event_time_utc": None,
                "publisher_time_utc": None,
                "first_observed_utc": observed,
                "ingested_utc": observed,
                "capture_ref": "synthetic:" + slot_id,
                "implementation": "synthetic-observer",
            },
        }
        for path, value in overrides.items():
            target = receipt
            parts = path.split("__")
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
        return receipts.canonical_json_bytes(receipt)

    def assess(self, **changes):
        values = {
            "scope": self.scope,
            "window": self.window,
            "planned_slots": self.slots,
            "attempts": self.attempts,
            "receipt_bytes_by_slot": self.receipt_bytes,
            "source_bytes_by_slot": self.source_bytes,
        }
        values.update(changes)
        return m.assess_observer_coverage(**values)

    def assert_hold(self, **changes):
        self.assertEqual(self.assess(**changes)["status"], m.HOLD)

    def test_complete_schedule_is_proven(self):
        result = self.assess()
        self.assertEqual(result["status"], m.PROVEN)
        self.assertTrue(result["declared_window_schedule_coverage_proven"])
        self.assertTrue(result["all_successful_observations_receipt_bound"])
        self.assertEqual(result["missed_or_failed_slots"], [])

    def test_missing_slot_is_incomplete(self):
        attempts = self.attempts[:-1]
        receipt_bytes = {k: v for k, v in self.receipt_bytes.items() if k != "slot-3"}
        source_bytes = {k: v for k, v in self.source_bytes.items() if k != "slot-3"}
        result = self.assess(attempts=attempts, receipt_bytes_by_slot=receipt_bytes, source_bytes_by_slot=source_bytes)
        self.assertEqual(result["status"], m.INCOMPLETE)
        self.assertEqual(result["missed_or_failed_slots"], ["slot-3"])

    def test_failed_slot_is_incomplete(self):
        attempts = copy.deepcopy(self.attempts)
        attempts[1]["status"] = "FAILED"
        receipt_bytes = dict(self.receipt_bytes); receipt_bytes.pop("slot-2")
        source_bytes = dict(self.source_bytes); source_bytes.pop("slot-2")
        result = self.assess(attempts=attempts, receipt_bytes_by_slot=receipt_bytes, source_bytes_by_slot=source_bytes)
        self.assertEqual(result["status"], m.INCOMPLETE)
        self.assertEqual(result["missed_or_failed_slots"], ["slot-2"])

    def test_cancelled_slot_is_incomplete(self):
        attempts = copy.deepcopy(self.attempts)
        attempts[0]["status"] = "CANCELLED"
        receipt_bytes = dict(self.receipt_bytes); receipt_bytes.pop("slot-1")
        source_bytes = dict(self.source_bytes); source_bytes.pop("slot-1")
        self.assertEqual(self.assess(attempts=attempts, receipt_bytes_by_slot=receipt_bytes, source_bytes_by_slot=source_bytes)["status"], m.INCOMPLETE)

    def test_duplicate_planned_or_attempt_slot_holds(self):
        duplicate_plan = self.slots + [{"slot_id": "slot-3", "due_utc": utc(20)}]
        duplicate_attempt = self.attempts + [copy.deepcopy(self.attempts[0])]
        self.assert_hold(planned_slots=duplicate_plan)
        self.assert_hold(attempts=duplicate_attempt)

    def test_undeclared_attempt_slot_holds(self):
        attempts = self.attempts + [{"slot_id": "other", "status": "FAILED", "observed_utc": utc(20)}]
        self.assert_hold(attempts=attempts)

    def test_duplicate_or_unordered_due_time_holds(self):
        duplicate = copy.deepcopy(self.slots); duplicate[1]["due_utc"] = duplicate[0]["due_utc"]
        unordered = copy.deepcopy(self.slots); unordered[1]["due_utc"] = utc(4)
        self.assert_hold(planned_slots=duplicate)
        self.assert_hold(planned_slots=unordered)

    def test_attempt_outside_window_holds(self):
        attempts = copy.deepcopy(self.attempts); attempts[2]["observed_utc"] = utc(31)
        self.assert_hold(attempts=attempts)

    def test_noncanonical_malformed_parented_or_wrong_type_receipt_holds(self):
        cases = []
        noncanonical = dict(self.receipt_bytes); noncanonical["slot-1"] += b"\n"; cases.append(noncanonical)
        malformed = dict(self.receipt_bytes); malformed["slot-1"] = b"{"; cases.append(malformed)
        parented = dict(self.receipt_bytes); parented["slot-1"] = self.capture_bytes("slot-1", utc(5), parent_receipt_ids=["parent"]); cases.append(parented)
        wrong_type = dict(self.receipt_bytes); wrong_type["slot-1"] = self.capture_bytes("slot-1", utc(5), receipt_type="revision"); cases.append(wrong_type)
        for value in cases:
            with self.subTest(value=value["slot-1"][:30]):
                self.assert_hold(receipt_bytes_by_slot=value)

    def test_source_content_hash_mismatch_holds(self):
        source_bytes = dict(self.source_bytes); source_bytes["slot-2"] = b"tampered"
        self.assert_hold(source_bytes_by_slot=source_bytes)

    def test_source_identity_and_scope_mismatches_hold(self):
        paths = (
            ("payload__source_uri", "other"),
            ("payload__source_id", "other"),
            ("scope__event_id", "other"),
            ("scope__meeting_id", "other"),
            ("scope__session_id", "other"),
        )
        for path, value in paths:
            changed = dict(self.receipt_bytes)
            changed["slot-1"] = self.capture_bytes("slot-1", utc(5), **{path: value})
            with self.subTest(path=path):
                self.assert_hold(receipt_bytes_by_slot=changed)

    def test_attempt_observed_time_mismatch_holds(self):
        attempts = copy.deepcopy(self.attempts); attempts[0]["observed_utc"] = utc(6)
        self.assert_hold(attempts=attempts)

    def test_ingestion_before_observation_holds(self):
        changed = dict(self.receipt_bytes)
        changed["slot-2"] = self.capture_bytes("slot-2", utc(10), payload__ingested_utc=utc(9))
        self.assert_hold(receipt_bytes_by_slot=changed)

    def test_complete_schedule_never_proves_publisher_or_global_completeness(self):
        result = self.assess()
        for field in m.TRUST_CEILINGS:
            self.assertIs(result[field], False)

    def test_one_or_many_changed_hashes_do_not_prove_completeness(self):
        self.assertGreater(len({receipts.sha256(v) for v in self.source_bytes.values()}), 1)
        result = self.assess()
        self.assertFalse(result["publisher_revision_completeness_proven"])
        self.assertFalse(result["global_observation_completeness_proven"])
        one_slot = self.slots[:1]
        result = self.assess(
            planned_slots=one_slot,
            attempts=self.attempts[:1],
            receipt_bytes_by_slot={"slot-1": self.receipt_bytes["slot-1"]},
            source_bytes_by_slot={"slot-1": self.source_bytes["slot-1"]},
        )
        self.assertFalse(result["publisher_revision_completeness_proven"])

    def test_caller_completeness_assertions_hold(self):
        self.assert_hold(publisher_revision_completeness_proven=True)
        self.assert_hold(global_observation_completeness_proven=True)

    def test_repeated_calls_are_deterministic(self):
        self.assertEqual(self.assess(), self.assess())

    def test_no_new_receipt_type_or_receipt_output(self):
        self.assertEqual(set(receipts.PAYLOADS), {"source_capture", "engine_execution", "producer_execution", "normalization", "forecast_lock", "outcome_boundary", "revision"})
        self.assertNotIn("receipt_type", self.assess())

    def test_pure_offline_source_has_no_discovery_clock_network_subprocess_or_secrets(self):
        tree = ast.parse(Path(m.__file__).read_text())
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertFalse(imports & {"os", "pathlib", "glob", "urllib", "requests", "socket", "subprocess", "secrets", "time", "datetime"})
        self.assertFalse(attrs & {"now", "utcnow", "glob", "rglob", "iterdir", "walk", "listdir", "scandir", "open", "write_bytes", "write_text"})
        self.assertNotIn("environ", names)

    def test_named_dependency_blobs_unchanged(self):
        expected = {
            "docs/DR002_PRE2B7J2_LIVE_GITHUB_ATTESTED_REVISION_SHADOW_2026-10-06.md": "8803e8f7d6373ea7f4319a7737f9430feb90893b",
            "scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py": "064d93ee5ae30354590a3fb95be598c5fe8b3b9a",
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py": "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
            "scripts/forecast_bundles/dr002_full_shadow_assessment_v1.py": "b86c69ee7574ad4941b574962a91bcaf8bfb1501",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob_sha((ROOT / path).read_bytes()), digest)


if __name__ == "__main__":
    unittest.main()
