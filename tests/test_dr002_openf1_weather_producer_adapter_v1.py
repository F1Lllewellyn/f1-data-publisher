import ast
import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "scripts/forecast_bundles"
SCRIPT = BUNDLE_DIR / "dr002_openf1_weather_producer_adapter_v1.py"
sys.path.insert(0, str(BUNDLE_DIR))
spec = importlib.util.spec_from_file_location("openf1_weather_adapter", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import dr002_openf1_historical_rest_capture_v1 as capture
import verify_forecast_integrity_receipts_v1 as receipts


def git_blob_sha(data):
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


class OpenF1WeatherProducerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.scope = {
            "event_id": "2026_1295_azerbaijan_baku_baku",
            "meeting_id": "1295",
            "session_id": "11371",
        }
        self.rows = [
            {
                "date": "2026-09-24T11:45:49.748000+00:00",
                "session_key": 11371,
                "meeting_key": 1295,
                "air_temperature": 23.4,
                "track_temperature": 31.0,
                "humidity": 56,
                "pressure": 1012.5,
                "rainfall": 0,
                "wind_direction": 270,
                "wind_speed": 3.25,
            },
            {
                "date": "2026-09-24T12:00:01Z",
                "session_key": "11371",
                "meeting_key": "1295",
                "air_temperature": 22,
                "track_temperature": 30.5,
                "humidity": 57.0,
                "pressure": 1012,
                "rainfall": 1,
                "wind_direction": 271.5,
                "wind_speed": 4,
            },
        ]
        self.raw = self.raw_bytes(self.rows)
        self.receipt_bytes = self.receipt_for(self.raw)

    @staticmethod
    def raw_bytes(value):
        return json.dumps(value, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")

    def receipt_for(self, raw):
        result = capture.assess_openf1_historical_rest_capture(
            **self.scope,
            endpoint="weather",
            request_params={"session_key": self.scope["session_id"]},
            raw_response_bytes=raw,
            http_status=200,
            session_end_utc="2026-09-24T13:00:00Z",
            first_observed_utc="2026-10-08T12:12:09.784033Z",
            ingested_utc="2026-10-08T12:12:09.784372Z",
            receipt_created_utc="2026-10-08T12:12:09.784388Z",
            capture_ref="_runtime/k4r3/weather.response.json",
            implementation="dr002_openf1_historical_rest_capture_v1",
        )
        self.assertEqual(result["status"], capture.VALIDATED)
        return result["source_capture_receipt_bytes"]

    def adapt(self, receipt_bytes=None, raw=None, **scope_changes):
        return m.adapt_openf1_weather_to_producer_input(
            source_capture_receipt_bytes=(self.receipt_bytes
                                          if receipt_bytes is None else receipt_bytes),
            raw_weather_response_bytes=self.raw if raw is None else raw,
            **{**self.scope, **scope_changes},
        )

    def changed_receipt(self, change, *, refresh_identity=True):
        receipt = json.loads(self.receipt_bytes)
        change(receipt)
        if refresh_identity:
            identity = {key: receipt[key] for key in
                        ("receipt_type", "scope", "parent_receipt_ids", "payload")}
            receipt["receipt_id"] = "source_capture:" + receipts.sha256(
                receipts.canonical_json_bytes(identity)
            )
        return receipts.canonical_json_bytes(receipt)

    def receipt_for_unvalidated_raw(self, raw):
        return self.changed_receipt(
            lambda receipt: receipt["payload"].__setitem__(
                "source_sha256", receipts.sha256(raw)
            )
        )

    def assert_hold_without_partial_output(self, result):
        self.assertEqual(result["status"], m.HOLD)
        self.assertNotIn("producer_input_csv_bytes", result)
        self.assertNotIn("frozen_evidence_manifest", result)
        self.assertFalse(result["new_scientific_receipt_created"])

    def test_valid_weather_receipt_and_raw_json_validate(self):
        result = self.adapt()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["scope"], self.scope)
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["producer_input_source_name"], "weather")
        self.assertEqual(result["producer_input_filename"], "weather.csv")

    def test_frozen_manifest_binds_raw_receipt_and_content_not_csv(self):
        result = self.adapt()
        evidence = result["frozen_evidence_manifest"]["evidence"][0]
        self.assertEqual(evidence["source_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(evidence["receipt_id"], result["source_receipt_id"])
        self.assertNotEqual(evidence["source_sha256"], result["producer_input_sha256"])

    def test_exact_header_and_lf_line_endings(self):
        data = self.adapt()["producer_input_csv_bytes"]
        header = b"date,session_key,meeting_key,air_temperature,track_temperature,humidity,pressure,rainfall,wind_direction,wind_speed\n"
        self.assertTrue(data.startswith(header))
        self.assertNotIn(b"\r", data)

    def test_source_row_order_is_preserved(self):
        data = self.adapt()["producer_input_csv_bytes"].decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(data, newline="")))
        self.assertEqual([row["date"] for row in rows],
                         [row["date"] for row in self.rows])

    def test_actual_k4r3_plus_zero_source_timestamp_is_preserved_exactly(self):
        actual = "2026-09-24T11:45:49.748000+00:00"
        result = self.adapt()
        rows = list(csv.DictReader(io.StringIO(
            result["producer_input_csv_bytes"].decode("utf-8"), newline=""
        )))
        self.assertEqual(rows[0]["date"], actual)
        self.assertEqual(self.rows[0]["date"], actual)

    def test_repeated_call_is_deterministic(self):
        self.assertEqual(self.adapt(), self.adapt())

    def test_raw_hash_mismatch_holds_without_partial_output(self):
        self.assert_hold_without_partial_output(self.adapt(raw=self.raw + b" "))

    def test_noncanonical_malformed_parented_and_wrong_type_receipts_hold(self):
        cases = [
            self.receipt_bytes + b" ",
            b"{",
            self.changed_receipt(
                lambda receipt: receipt["parent_receipt_ids"].append("other")
            ),
            self.changed_receipt(
                lambda receipt: receipt.__setitem__("receipt_type", "revision")
            ),
        ]
        for receipt_bytes in cases:
            with self.subTest(receipt_bytes=receipt_bytes[:20]):
                self.assert_hold_without_partial_output(
                    self.adapt(receipt_bytes=receipt_bytes)
                )

    def test_wrong_receipt_id_holds(self):
        bad = self.changed_receipt(
            lambda receipt: receipt.__setitem__("receipt_id", "source_capture:wrong"),
            refresh_identity=False,
        )
        self.assert_hold_without_partial_output(self.adapt(receipt_bytes=bad))

    def test_wrong_source_uri_source_id_and_scope_hold(self):
        bad_uri = self.changed_receipt(
            lambda receipt: receipt["payload"].update(
                source_uri="https://api.openf1.org/v1/weather?session_key=99999",
                source_id="openf1:weather:" + "0" * 64,
            )
        )
        bad_id = self.changed_receipt(
            lambda receipt: receipt["payload"].__setitem__(
                "source_id", "openf1:weather:" + "0" * 64
            )
        )
        bad_scope = self.changed_receipt(
            lambda receipt: receipt["scope"].__setitem__("session_id", "99999")
        )
        for receipt_bytes in (bad_uri, bad_id, bad_scope):
            with self.subTest(receipt_bytes=receipt_bytes):
                self.assert_hold_without_partial_output(
                    self.adapt(receipt_bytes=receipt_bytes)
                )

    def test_duplicate_key_malformed_and_nonfinite_json_hold(self):
        cases = (
            b"[",
            b'[{"date":"2026-09-24T12:00:00Z","date":"2026-09-24T12:00:01Z"}]',
            b'[{"value":NaN}]',
        )
        for raw in cases:
            with self.subTest(raw=raw):
                receipt_bytes = self.receipt_for_unvalidated_raw(raw)
                self.assert_hold_without_partial_output(
                    self.adapt(receipt_bytes=receipt_bytes, raw=raw)
                )

    def test_object_and_empty_list_hold(self):
        for value in ({}, []):
            raw = self.raw_bytes(value)
            self.assert_hold_without_partial_output(self.adapt(
                receipt_bytes=self.receipt_for_unvalidated_raw(raw), raw=raw
            ))

    def test_missing_and_extra_weather_fields_hold(self):
        missing = copy.deepcopy(self.rows)
        missing[0].pop("humidity")
        extra = copy.deepcopy(self.rows)
        extra[0]["unexpected"] = 1
        for rows in (missing, extra):
            raw = self.raw_bytes(rows)
            self.assert_hold_without_partial_output(self.adapt(
                receipt_bytes=self.receipt_for_unvalidated_raw(raw), raw=raw
            ))

    def test_foreign_session_and_meeting_hold(self):
        session = copy.deepcopy(self.rows)
        session[0]["session_key"] = 99999
        meeting = copy.deepcopy(self.rows)
        meeting[0]["meeting_key"] = 9999
        for rows in (session, meeting):
            raw = self.raw_bytes(rows)
            self.assert_hold_without_partial_output(self.adapt(
                receipt_bytes=self.receipt_for_unvalidated_raw(raw), raw=raw
            ))

    def test_malformed_and_non_utc_date_hold(self):
        for date in ("not-a-time", "2026-09-24T12:00:00+01:00", 1):
            rows = copy.deepcopy(self.rows)
            rows[0]["date"] = date
            raw = self.raw_bytes(rows)
            self.assert_hold_without_partial_output(self.adapt(
                receipt_bytes=self.receipt_for_unvalidated_raw(raw), raw=raw
            ))

    def test_bool_and_nonfinite_numeric_evidence_hold(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["rainfall"] = True
        raw = self.raw_bytes(rows)
        self.assert_hold_without_partial_output(self.adapt(
            receipt_bytes=self.receipt_for_unvalidated_raw(raw), raw=raw
        ))
        nonfinite = self.raw.replace(b'"air_temperature":23.4',
                                     b'"air_temperature":1e400', 1)
        self.assert_hold_without_partial_output(self.adapt(
            receipt_bytes=self.receipt_for_unvalidated_raw(nonfinite), raw=nonfinite
        ))

    def test_derived_hash_recomputes_and_differs_from_transforming_input(self):
        result = self.adapt()
        self.assertEqual(result["producer_input_sha256"], hashlib.sha256(
            result["producer_input_csv_bytes"]).hexdigest())
        self.assertNotEqual(result["producer_input_sha256"],
                            result["raw_source_sha256"])

    def test_no_invented_observation_or_provenance_columns(self):
        header = self.adapt()["producer_input_csv_bytes"].splitlines()[0]
        self.assertEqual(header.decode("ascii"), ",".join(m.WEATHER_FIELDS))
        self.assertNotIn(b"source_closure_retrieved_utc", header)
        self.assertNotIn(b"first_observed_utc", header)
        self.assertNotIn(b"receipt", header)

    def test_no_receipt_or_verified_binding_is_created(self):
        result = self.adapt()
        self.assertFalse(result["derived_csv_is_source_evidence"])
        self.assertFalse(result["new_scientific_receipt_created"])
        self.assertFalse(result["normalization_receipt_created"])
        self.assertFalse(result["verified_receipt_bindings_created"])
        self.assertNotIn("verified_receipt_bindings", result)
        self.assertNotIn("verified_receipt_bindings",
                         result["frozen_evidence_manifest"])
        encoded = receipts.canonical_json_bytes(
            {key: value for key, value in result.items()
             if key != "producer_input_csv_bytes"}
        )
        self.assertNotIn(b'"receipt_type":"normalization"', encoded)

    def test_frozen_manifest_trust_remains_unbound_and_false(self):
        trust = self.adapt()["frozen_evidence_manifest"]["trust"]
        self.assertEqual(trust, m.frozen_contract.TRUST)
        self.assertEqual(trust["binding_status"], "UNBOUND")
        self.assertIs(trust["production_authenticated"], False)
        self.assertIs(trust["historical_availability_proven"], False)

    def test_all_result_claim_ceilings_remain_false(self):
        result = self.adapt()
        for field in (
            "stable_engine_execution_proven", "blind_validation_eligible",
            "production_forecast_generated", "dr002_activated",
            "promotion_allowed",
        ):
            self.assertIs(result[field], False)

    def test_adapter_has_no_filesystem_network_clock_environment_or_subprocess_access(self):
        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(imported & {
            "pathlib", "os", "subprocess", "socket", "requests", "urllib",
            "time", "glob", "tempfile",
        })
        for forbidden in (
            "Path(", "open(", ".read_", ".write_", "datetime.now", "utcnow",
            "getenv", "environ", "subprocess", "requests", "urllib.request",
        ):
            self.assertNotIn(forbidden, source)

    def test_producer_dependency_still_recognizes_weather_csv(self):
        producer = (ROOT / "scripts/forecasts/produce_actual_forecast_rows_v1.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(producer)
        assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SOURCE_FILES"
                    for target in node.targets)
        )
        source_files = ast.literal_eval(assignment.value)
        self.assertIn("weather.csv", source_files["weather"])

    def test_all_named_dependency_blobs_are_unchanged(self):
        for relative_path, expected in m.DEPENDENCY_BLOBS.items():
            with self.subTest(relative_path=relative_path):
                self.assertEqual(git_blob_sha((ROOT / relative_path).read_bytes()), expected)


if __name__ == "__main__":
    unittest.main()
