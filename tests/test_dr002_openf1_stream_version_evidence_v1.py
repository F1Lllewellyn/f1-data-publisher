import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/forecast_bundles/dr002_openf1_stream_version_evidence_v1.py"
spec = importlib.util.spec_from_file_location("openf1_stream_evidence", MODULE_PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class OpenF1StreamVersionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.topics = ["v1/meetings/42/drivers", "v1/meetings/42/weather"]
        self.window = {
            "connection_id": "synthetic-connection-1",
            "window_start_utc": "2026-10-07T12:00:00Z",
            "window_end_utc": "2026-10-07T12:10:00Z",
        }
        self.messages = [
            self.record(self.topics[0], 100, "driver-1", 0, name="A"),
            self.record(self.topics[1], 104, "weather-1", 1, rain=0),
            self.record(self.topics[0], 109, "driver-1", 2, name="B"),
        ]

    def record(self, topic, message_id, key, index, **payload):
        return {
            "topic": topic,
            "raw_json_bytes": raw({"_id": message_id, "_key": key, **payload}),
            "received_order_index": index,
        }

    def assess(self, **changes):
        values = {
            "provider": "openf1",
            "subscription_topics": self.topics,
            "connection_window": self.window,
            "messages": self.messages,
        }
        values.update(changes)
        return m.assess_openf1_stream_version_evidence(**values)

    def assert_hold(self, **changes):
        self.assertEqual(self.assess(**changes)["status"], m.HOLD)

    def k1(self, status=m.K1_PROVEN):
        result = {
            "schema_version": m.K1_SCHEMA_VERSION,
            "assessment_type": "DECLARED_OBSERVER_WINDOW_COVERAGE",
            "status": status,
            "declared_window_schedule_coverage_proven": status == m.K1_PROVEN,
            "all_successful_observations_receipt_bound": True,
        }
        result.update({field: False for field in m.K1_TRUST_CEILINGS})
        return result

    def test_valid_synthetic_messages_validate(self):
        result = self.assess()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["total_observed_message_count"], 3)
        self.assertEqual(result["unique_id_count"], 3)
        self.assertEqual((result["min_observed_id"], result["max_observed_id"]), (100, 109))

    def test_exact_raw_byte_hashes_are_preserved(self):
        result = self.assess()
        expected = [hashlib.sha256(item["raw_json_bytes"]).hexdigest() for item in self.messages]
        self.assertEqual([item["raw_json_sha256"] for item in result["observed_messages"]], expected)

    def test_same_topic_and_key_groups_as_one_object(self):
        result = self.assess()
        driver = next(item for item in result["per_object_version_evidence"]
                      if item["topic"] == self.topics[0] and item["_key"] == "driver-1")
        self.assertEqual(driver["observed_message_count"], 2)
        self.assertEqual(result["objects_with_multiple_observed_messages"],
                         [{"topic": self.topics[0], "_key": "driver-1"}])

    def test_same_key_on_different_topics_is_distinct(self):
        messages = [
            self.record(self.topics[0], 1, "shared", 0),
            self.record(self.topics[1], 2, "shared", 1),
        ]
        result = self.assess(messages=messages)
        self.assertEqual(len(result["observed_object_identities"]), 2)

    def test_per_object_sequence_is_ordered_by_id(self):
        messages = [
            self.record(self.topics[0], 9, "driver-1", 0),
            self.record(self.topics[0], 3, "driver-1", 1),
        ]
        result = self.assess(messages=messages)
        sequence = result["per_object_version_evidence"][0]["observed_message_sequence"]
        self.assertEqual([item["_id"] for item in sequence], [3, 9])

    def test_non_contiguous_ids_validate_without_loss_inference(self):
        result = self.assess()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertTrue(result["numeric_id_gaps_observed"])
        self.assertFalse(result["openf1_id_contiguity_assumed"])
        self.assertFalse(result["message_loss_proven_from_id_gaps"])

    def test_duplicate_id_holds(self):
        messages = self.messages + [self.record(self.topics[1], 100, "other", 3)]
        self.assert_hold(messages=messages)

    def test_malformed_json_holds(self):
        messages = copy.deepcopy(self.messages)
        messages[0]["raw_json_bytes"] = b"{"
        self.assert_hold(messages=messages)

    def test_duplicate_json_key_holds(self):
        messages = copy.deepcopy(self.messages)
        messages[0]["raw_json_bytes"] = b'{"_id":1,"_id":2,"_key":"x"}'
        self.assert_hold(messages=messages)

    def test_missing_or_invalid_id_holds(self):
        cases = [
            {"_key": "x"},
            {"_id": -1, "_key": "x"},
            {"_id": True, "_key": "x"},
            {"_id": "1", "_key": "x"},
        ]
        for value in cases:
            message = {"topic": self.topics[0], "raw_json_bytes": raw(value), "received_order_index": 0}
            with self.subTest(value=value):
                self.assert_hold(messages=[message])

    def test_missing_or_invalid_key_holds(self):
        for key in (None, "", "   ", 7):
            value = {"_id": 1}
            if key is not None:
                value["_key"] = key
            message = {"topic": self.topics[0], "raw_json_bytes": raw(value), "received_order_index": 0}
            with self.subTest(key=key):
                self.assert_hold(messages=[message])

    def test_undeclared_topic_holds(self):
        self.assert_hold(messages=[self.record("v1/undeclared", 1, "x", 0)])

    def test_malformed_or_non_unique_received_order_index_holds(self):
        malformed = copy.deepcopy(self.messages)
        malformed[0]["received_order_index"] = True
        duplicate = copy.deepcopy(self.messages)
        duplicate[1]["received_order_index"] = 0
        self.assert_hold(messages=malformed)
        self.assert_hold(messages=duplicate)

    def test_non_monotonic_receive_order_is_recorded_without_false_claim(self):
        messages = [
            self.record(self.topics[0], 20, "x", 0),
            self.record(self.topics[0], 10, "x", 1),
        ]
        result = self.assess(messages=messages)
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertFalse(result["received_order_id_strictly_increasing"])
        self.assertFalse(result["message_loss_proven_from_id_gaps"])
        self.assertFalse(result["publisher_revision_completeness_proven"])

    def test_one_or_many_updates_never_prove_completeness(self):
        result = self.assess()
        self.assertTrue(result["objects_with_multiple_observed_messages"])
        self.assertFalse(result["publisher_revision_completeness_proven"])
        self.assertFalse(result["global_observation_completeness_proven"])

    def test_k1_proven_composes_without_completeness_upgrade(self):
        result = self.assess(k1_assessment=self.k1())
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertTrue(result["declared_window_schedule_coverage_proven"])
        self.assertFalse(result["publisher_revision_completeness_proven"])

    def test_k1_incomplete_composes_without_upgrade(self):
        result = self.assess(k1_assessment=self.k1(m.K1_INCOMPLETE))
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["k1_observer_coverage_status"], m.K1_INCOMPLETE)
        self.assertFalse(result["declared_window_schedule_coverage_proven"])

    def test_malformed_or_incompatible_k1_holds(self):
        malformed = self.k1()
        malformed["publisher_revision_completeness_proven"] = True
        incompatible = self.k1()
        incompatible["schema_version"] = "other"
        self.assert_hold(k1_assessment=malformed)
        self.assert_hold(k1_assessment=incompatible)

    def test_caller_completeness_or_authentication_assertion_holds(self):
        for field in m.TRUST_CEILINGS:
            with self.subTest(field=field):
                self.assert_hold(**{field: True})

    def test_repeated_calls_are_deterministic(self):
        self.assertEqual(self.assess(), self.assess())

    def test_no_new_receipt_type_or_receipt_output(self):
        source = MODULE_PATH.read_text()
        self.assertNotIn("receipt_type", source)
        self.assertNotIn("receipt_type", self.assess())
        self.assertEqual(self.assess()["assessment_type"], "OPENF1_STREAM_VERSION_EVIDENCE")

    def test_implementation_is_pure_offline(self):
        tree = ast.parse(MODULE_PATH.read_text())
        imports = {alias.name for node in ast.walk(tree)
                   if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        prohibited_imports = {
            "os", "pathlib", "glob", "urllib", "requests", "socket", "subprocess",
            "secrets", "time", "datetime", "paho", "websocket", "websockets",
        }
        self.assertFalse(imports & prohibited_imports)
        self.assertFalse(attrs & {"now", "utcnow", "open", "glob", "rglob", "iterdir",
                                  "walk", "listdir", "scandir", "connect", "publish", "subscribe"})
        self.assertNotIn("environ", names)

    def test_named_dependency_blobs_unchanged(self):
        expected = {
            "scripts/forecast_bundles/dr002_observer_coverage_contract_v1.py": "e0794e3c901b70a636b5d552ffd673576aeea412",
            "tests/test_dr002_observer_coverage_contract_v1.py": "d8ea5592057f6c2f8e083636de65ea5e477f99ba",
            "docs/DR002_PRE2B7K1_OBSERVER_COVERAGE_COMPLETENESS_CONTRACT_2026-10-07.md": "63d5e579ed7c95a74e0fdf878bb37c366b90c9e3",
            "docs/DR002_PRE2B7J2_LIVE_GITHUB_ATTESTED_REVISION_SHADOW_2026-10-06.md": "8803e8f7d6373ea7f4319a7737f9430feb90893b",
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py": "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob_sha((ROOT / path).read_bytes()), digest)


if __name__ == "__main__":
    unittest.main()
