import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("openf1_historical_rest_capture", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import verify_forecast_integrity_receipts_v1 as receipts


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class OpenF1HistoricalRestCaptureTests(unittest.TestCase):
    def setUp(self):
        self.options = {
            "event_id": "2026-australia",
            "meeting_id": "1295",
            "session_id": "11371",
            "endpoint": "weather",
            "request_params": {"session_key": 11371, "driver_number": 44},
            "raw_response_bytes": b'[{"air_temperature":23.4,"session_key":11371}]',
            "http_status": 200,
            "session_end_utc": "2026-10-07T14:00:00Z",
            "first_observed_utc": "2026-10-07T14:30:00Z",
            "ingested_utc": "2026-10-07T14:30:01Z",
            "receipt_created_utc": "2026-10-07T14:30:02Z",
            "capture_ref": "github:run/207/artifact/openf1-weather.json",
            "implementation": "dr002_openf1_historical_rest_capture_v1",
        }

    def assess(self, **changes):
        options = {**self.options, **changes}
        return m.assess_openf1_historical_rest_capture(**options)

    def test_valid_post_window_list_response_validates(self):
        result = self.assess()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["row_count"], 1)
        self.assertTrue(result["openf1_documented_historical_window_satisfied"])

    def test_valid_json_object_has_null_row_count(self):
        result = self.assess(raw_response_bytes=b'{"session_key":11371}')
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertIsNone(result["row_count"])

    def test_exact_raw_bytes_and_hash_survive_noncanonical_whitespace(self):
        raw = b'[  {"session_key" : 11371, "air_temperature" : 23.4}  ]\n'
        result = self.assess(raw_response_bytes=raw)
        self.assertEqual(result["raw_response_bytes"], raw)
        self.assertEqual(result["raw_response_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(raw, json.dumps(json.loads(raw), separators=(",", ":")).encode())

    def test_canonical_uri_is_deterministic_across_parameter_order(self):
        left = self.assess(request_params={"session_key": 11371, "driver_number": 44})
        right = self.assess(request_params={"driver_number": 44, "session_key": 11371})
        expected = "https://api.openf1.org/v1/weather?driver_number=44&session_key=11371"
        self.assertEqual(left["canonical_request_uri"], expected)
        self.assertEqual(left["canonical_request_uri"], right["canonical_request_uri"])
        self.assertEqual(left["source_id"], right["source_id"])
        self.assertEqual(left["source_capture_receipt_bytes"], right["source_capture_receipt_bytes"])

    def test_source_id_binds_exact_canonical_request_filters(self):
        first = self.assess(request_params={"session_key": 11371, "driver_number": 44})
        different = self.assess(request_params={"session_key": 11371, "driver_number": 1})
        reordered = self.assess(request_params={"driver_number": 44, "session_key": 11371})
        self.assertNotEqual(first["source_id"], different["source_id"])
        self.assertEqual(first["source_id"], reordered["source_id"])

    def test_supplied_request_scope_keys_must_match_dr002_scope(self):
        valid = self.assess(request_params={"meeting_key": 1295, "session_key": "11371"})
        self.assertEqual(valid["status"], m.VALIDATED)
        cases = (
            ({"session_key": 99999}, "request_session_scope_mismatch"),
            ({"meeting_key": "9999"}, "request_meeting_scope_mismatch"),
        )
        for request_params, reason in cases:
            with self.subTest(request_params=request_params):
                result = self.assess(request_params=request_params)
                self.assertEqual(result["status"], m.HOLD)
                self.assertIn(reason, result["reason_codes"])

    def test_response_records_with_foreign_scope_hold(self):
        cases = (
            (b'[{"session_key":99999}]', "response_session_scope_mismatch"),
            (b'{"meeting_key":9999}', "response_meeting_scope_mismatch"),
            (b'{"data":[{"session_key":"foreign"}]}', "response_session_scope_mismatch"),
        )
        for raw, reason in cases:
            with self.subTest(raw=raw):
                result = self.assess(raw_response_bytes=raw)
                self.assertEqual(result["status"], m.HOLD)
                self.assertIn(reason, result["reason_codes"])

    def test_response_scope_accepts_matching_numeric_or_string_keys(self):
        result = self.assess(
            raw_response_bytes=b'[{"session_key":11371,"meeting_key":"1295"}]'
        )
        self.assertEqual(result["status"], m.VALIDATED)

    def test_observation_exactly_at_1800_seconds_validates(self):
        result = self.assess(first_observed_utc="2026-10-07T14:30:00Z")
        self.assertEqual(result["historical_window_eligible_utc"], "2026-10-07T14:30:00Z")
        self.assertEqual(result["status"], m.VALIDATED)

    def test_observation_one_microsecond_before_window_holds(self):
        result = self.assess(first_observed_utc="2026-10-07T14:29:59.999999Z")
        self.assertEqual(result["status"], m.HOLD)
        self.assertIn("observation_before_historical_window", result["reason_codes"])
        self.assertFalse(result["openf1_documented_historical_window_satisfied"])

    def test_first_observed_after_ingested_holds(self):
        result = self.assess(
            first_observed_utc="2026-10-07T14:30:02Z",
            ingested_utc="2026-10-07T14:30:01Z",
        )
        self.assertEqual(result["status"], m.HOLD)
        self.assertIn("inconsistent_capture_times", result["reason_codes"])

    def test_ingested_after_receipt_created_holds(self):
        result = self.assess(
            ingested_utc="2026-10-07T14:30:03Z",
            receipt_created_utc="2026-10-07T14:30:02Z",
        )
        self.assertEqual(result["status"], m.HOLD)
        self.assertIn("inconsistent_capture_times", result["reason_codes"])

    def test_non_200_status_holds(self):
        result = self.assess(http_status=404)
        self.assertEqual(result["status"], m.HOLD)
        self.assertIn("http_status_not_200", result["reason_codes"])

    def test_malformed_json_holds(self):
        result = self.assess(raw_response_bytes=b"[")
        self.assertEqual(result["status"], m.HOLD)
        self.assertIn("malformed_json", result["reason_codes"])

    def test_duplicate_json_key_holds_at_any_depth(self):
        for raw in (b'{"a":1,"a":2}', b'[{"outer":{"a":1,"a":2}}]'):
            with self.subTest(raw=raw):
                result = self.assess(raw_response_bytes=raw)
                self.assertEqual(result["status"], m.HOLD)
                self.assertIn("duplicate_json_key", result["reason_codes"])

    def test_malformed_endpoint_or_params_hold(self):
        cases = (
            {"endpoint": "weather/live"},
            {"endpoint": "Weather"},
            {"request_params": {}},
            {"request_params": {"bad key": 1}},
            {"request_params": {"session_key": [11371]}},
            {"request_params": {"session_key": float("nan")}},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.assess(**changes)["status"], m.HOLD)

    def test_parentless_existing_source_capture_receipt_validates(self):
        result = self.assess()
        receipt = json.loads(result["source_capture_receipt_bytes"])
        self.assertEqual(receipt["receipt_type"], "source_capture")
        self.assertEqual(receipt["parent_receipt_ids"], [])
        self.assertTrue(receipts.validate_receipt_envelope(receipt))
        self.assertTrue(receipts.verify_temporal_bindings(receipt))

    def test_receipt_source_hash_is_exact_response_hash(self):
        result = self.assess()
        receipt = json.loads(result["source_capture_receipt_bytes"])
        self.assertEqual(receipt["payload"]["source_sha256"],
                         hashlib.sha256(self.options["raw_response_bytes"]).hexdigest())
        self.assertEqual(result["receipt_sha256"],
                         hashlib.sha256(result["source_capture_receipt_bytes"]).hexdigest())

    def test_no_verified_binding_is_fabricated(self):
        result = self.assess()
        self.assertNotIn("verified_receipt_bindings", result)
        receipt = json.loads(result["source_capture_receipt_bytes"])
        self.assertNotIn("verified_receipt_bindings", receipt)

    def test_all_trust_ceilings_remain_false(self):
        result = self.assess()
        for field in m.TRUST_CEILINGS:
            with self.subTest(field=field):
                self.assertIs(result[field], False)

    def test_unsupported_true_trust_assertion_holds(self):
        for field in m.TRUST_CEILINGS:
            with self.subTest(field=field):
                result = self.assess(unsupported_claims={field: True})
                self.assertEqual(result["status"], m.HOLD)
                self.assertTrue(all(result[name] is False for name in m.TRUST_CEILINGS))

    def test_repeated_call_is_byte_for_byte_deterministic(self):
        self.assertEqual(self.assess(), self.assess())

    def test_contract_is_pure_offline_and_has_no_implicit_facts(self):
        source = SCRIPT.read_text()
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertEqual(imports, {"json", "math", "re", "urllib.parse",
                                   "verify_forecast_integrity_receipts_v1"})
        for forbidden in (
            "requests", "urllib.request", "socket", "subprocess", "os.environ",
            "Path(", "open(", ".read_", ".write_", "datetime.now", "utcnow",
            "getenv", "secret", "password", "token",
        ):
            self.assertNotIn(forbidden, source)

    def test_no_new_receipt_type_is_created(self):
        result = self.assess()
        receipt = json.loads(result["source_capture_receipt_bytes"])
        self.assertEqual(receipt["schema_version"], receipts.VERSION)
        self.assertEqual(receipt["receipt_type"], "source_capture")
        self.assertEqual(set(receipts.PAYLOADS), {
            "source_capture", "engine_execution", "producer_execution", "normalization",
            "forecast_lock", "outcome_boundary", "revision",
        })

    def test_named_dependency_blob_pins_are_exact_and_local_validators_unchanged(self):
        expected = {
            "scripts/openf1/publish_openf1_lightweight_source_closure.py": "ebdba37477b7efdc584c2550295cb7c61cf53481",
            ".github/workflows/f1-openf1-lightweight-source-closure.yml": "7521e0e91e201b0610d8771a8524393c59ba1ecb",
            "configs/openf1/openf1_lightweight_source_closure_policy.json": "d21765b33e66dfa499b92c9f44a4543608f2c6a4",
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py": "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
            "scripts/forecast_bundles/dr002_verified_source_consumer_v1.py": "e402939202ed579c368499f3baefb3641de27de7",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
        }
        self.assertEqual(m.DEPENDENCY_BLOBS, expected)
        for path in (
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(git_blob_sha((ROOT / path).read_bytes()), expected[path])

    def test_optional_event_and_publisher_times_are_null_or_valid_utc(self):
        result = self.assess(
            event_time_utc="2026-10-07T13:00:00Z",
            publisher_time_utc="2026-10-07T13:00:01Z",
        )
        receipt = json.loads(result["source_capture_receipt_bytes"])
        self.assertEqual(receipt["payload"]["event_time_utc"], "2026-10-07T13:00:00Z")
        self.assertEqual(receipt["payload"]["publisher_time_utc"], "2026-10-07T13:00:01Z")
        self.assertEqual(self.assess(event_time_utc="not-utc")["status"], m.HOLD)


if __name__ == "__main__":
    unittest.main()
