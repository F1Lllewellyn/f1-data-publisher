import ast
import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "scripts/forecast_bundles"
SCRIPT = BUNDLE_DIR / "dr002_openf1_drivers_producer_adapter_v1.py"
PRODUCER_SCRIPT = ROOT / "scripts/forecasts/produce_actual_forecast_rows_v1.py"
sys.path.insert(0, str(BUNDLE_DIR))
spec = importlib.util.spec_from_file_location("openf1_drivers_adapter", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import dr002_openf1_historical_rest_capture_v1 as capture
import verify_forecast_integrity_receipts_v1 as receipts


def git_blob_sha(data):
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


class OpenF1DriversProducerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.scope = {
            "event_id": "2026_1295_azerbaijan_baku_baku",
            "meeting_id": "1295",
            "session_id": "11371",
        }
        self.rows = [
            {
                "meeting_key": 1295,
                "session_key": 11371,
                "driver_number": 44,
                "broadcast_name": "L HAMILTON",
                "full_name": "Lewis HAMILTON",
                "team_name": "Scuderia Ferrari HP",
                "first_name": "Lewis",
                "last_name": "Hamilton",
                "name_acronym": "HAM",
                "team_colour": "E80020",
                "headshot_url": None,
                "country_code": "GBR",
            },
            {
                "meeting_key": "1295",
                "session_key": "11371",
                "driver_number": 1,
                "broadcast_name": "M VERSTAPPEN",
                "full_name": "Max VERSTAPPEN",
                "team_name": "Red Bull Racing",
                "first_name": None,
                "last_name": "Verstappen",
                "name_acronym": "VER",
                "team_colour": None,
                "headshot_url": "https://example.invalid/ver.png",
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
            endpoint="drivers",
            request_params={"session_key": self.scope["session_id"]},
            raw_response_bytes=raw,
            http_status=200,
            session_end_utc="2026-09-24T13:00:00Z",
            first_observed_utc="2026-10-08T12:12:09.784033Z",
            ingested_utc="2026-10-08T12:12:09.784372Z",
            receipt_created_utc="2026-10-08T12:12:09.784388Z",
            capture_ref="_runtime/k4r6/drivers.response.json",
            implementation="dr002_openf1_historical_rest_capture_v1",
        )
        self.assertEqual(result["status"], capture.VALIDATED)
        return result["source_capture_receipt_bytes"]

    def adapt(self, receipt_bytes=None, raw=None, **scope_changes):
        return m.adapt_openf1_drivers_to_producer_input(
            source_capture_receipt_bytes=(self.receipt_bytes
                                          if receipt_bytes is None else receipt_bytes),
            raw_drivers_response_bytes=self.raw if raw is None else raw,
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

    def result_for_rows(self, rows):
        raw = self.raw_bytes(rows)
        return self.adapt(
            receipt_bytes=self.receipt_for_unvalidated_raw(raw), raw=raw
        )

    def assert_hold_without_partial_output(self, result):
        self.assertEqual(result["status"], m.HOLD)
        self.assertNotIn("producer_input_csv_bytes", result)
        self.assertNotIn("frozen_evidence_manifest", result)
        self.assertFalse(result["new_scientific_receipt_created"])

    # 1
    def test_valid_documented_drivers_response_validates(self):
        result = self.adapt()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["scope"], self.scope)
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["unique_driver_count"], 2)
        self.assertEqual(result["producer_input_source_name"], "drivers")
        self.assertEqual(result["producer_input_filename"], "drivers.csv")
        self.assertEqual(result["raw_source_id"],
                         json.loads(self.receipt_bytes)["payload"]["source_id"])

    # 2
    def test_frozen_manifest_binds_raw_receipt_and_content_not_csv(self):
        result = self.adapt()
        evidence = result["frozen_evidence_manifest"]["evidence"][0]
        self.assertEqual(evidence["source_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(evidence["receipt_id"], result["source_receipt_id"])
        self.assertNotEqual(evidence["source_sha256"], result["producer_input_sha256"])

    # 3
    def test_exact_fixed_header_and_lf_line_endings(self):
        data = self.adapt()["producer_input_csv_bytes"]
        self.assertTrue(data.startswith(
            b"driver_number,broadcast_name,full_name,team_name,meeting_key,session_key\n"
        ))
        self.assertNotIn(b"\r", data)

    # 4
    def test_source_row_order_and_strings_are_preserved(self):
        data = self.adapt()["producer_input_csv_bytes"].decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(data, newline="")))
        self.assertEqual([row["driver_number"] for row in rows], ["44", "1"])
        self.assertEqual([row["broadcast_name"] for row in rows],
                         [row["broadcast_name"] for row in self.rows])
        self.assertEqual([row["full_name"] for row in rows],
                         [row["full_name"] for row in self.rows])
        self.assertEqual([row["team_name"] for row in rows],
                         [row["team_name"] for row in self.rows])

    # 5
    def test_repeated_call_is_deterministic(self):
        self.assertEqual(self.adapt(), self.adapt())

    # 6
    def test_raw_hash_mismatch_holds_without_partial_output(self):
        self.assert_hold_without_partial_output(self.adapt(raw=self.raw + b" "))

    # 7
    def test_noncanonical_malformed_duplicate_nonfinite_parented_and_wrong_type_receipts_hold(self):
        duplicate = self.receipt_bytes.replace(
            b'"schema_version":',
            b'"schema_version":"dr002-receipt-v1","schema_version":', 1,
        )
        nonfinite = self.receipt_bytes.replace(b'"event_time_utc":null',
                                               b'"event_time_utc":NaN', 1)
        cases = [
            self.receipt_bytes + b" ",
            b"{",
            duplicate,
            nonfinite,
            self.changed_receipt(
                lambda receipt: receipt["parent_receipt_ids"].append("other")
            ),
            self.changed_receipt(
                lambda receipt: receipt.__setitem__("receipt_type", "revision")
            ),
        ]
        for receipt_bytes in cases:
            with self.subTest(receipt_bytes=receipt_bytes[:32]):
                self.assert_hold_without_partial_output(
                    self.adapt(receipt_bytes=receipt_bytes)
                )

    # 8
    def test_wrong_source_uri_source_id_receipt_id_and_session_identity_hold(self):
        bad_uri = self.changed_receipt(
            lambda receipt: receipt["payload"].update(
                source_uri="https://api.openf1.org/v1/drivers?session_key=99999",
                source_id="openf1:drivers:" + "0" * 64,
            )
        )
        bad_source_id = self.changed_receipt(
            lambda receipt: receipt["payload"].__setitem__(
                "source_id", "openf1:drivers:" + "0" * 64
            )
        )
        bad_receipt_id = self.changed_receipt(
            lambda receipt: receipt.__setitem__(
                "receipt_id", "source_capture:wrong"
            ),
            refresh_identity=False,
        )
        for result in (
            self.adapt(receipt_bytes=bad_uri),
            self.adapt(receipt_bytes=bad_source_id),
            self.adapt(receipt_bytes=bad_receipt_id),
            self.adapt(session_id="99999"),
        ):
            self.assert_hold_without_partial_output(result)

    # 9
    def test_malformed_duplicate_key_and_nonfinite_drivers_json_hold(self):
        cases = (
            b"[",
            b'[{"driver_number":44,"driver_number":1}]',
            b'[{"driver_number":NaN}]',
        )
        for raw in cases:
            with self.subTest(raw=raw):
                self.assert_hold_without_partial_output(self.adapt(
                    receipt_bytes=self.receipt_for_unvalidated_raw(raw), raw=raw
                ))

    # 10
    def test_top_level_object_and_empty_list_hold(self):
        for value in ({}, []):
            self.assert_hold_without_partial_output(self.result_for_rows(value))

    # 11
    def test_missing_each_required_driver_field_holds(self):
        for field in m.REQUIRED_FIELDS:
            rows = copy.deepcopy(self.rows)
            rows[0].pop(field)
            with self.subTest(field=field):
                self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 12
    def test_unknown_source_field_holds(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["unexpected"] = "schema drift"
        self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 13
    def test_country_code_may_be_present_or_absent(self):
        present = copy.deepcopy(self.rows)
        absent = copy.deepcopy(self.rows)
        present[1]["country_code"] = None
        absent[0].pop("country_code")
        self.assertEqual(self.result_for_rows(present)["status"], m.VALIDATED)
        self.assertEqual(self.result_for_rows(absent)["status"], m.VALIDATED)

    # 14
    def test_foreign_session_and_meeting_hold(self):
        for field, value in (("session_key", 99999), ("meeting_key", 9999)):
            rows = copy.deepcopy(self.rows)
            rows[0][field] = value
            with self.subTest(field=field):
                self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 15
    def test_duplicate_driver_number_holds(self):
        rows = copy.deepcopy(self.rows)
        rows[1]["driver_number"] = rows[0]["driver_number"]
        self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 16
    def test_bool_zero_negative_float_and_string_driver_number_hold(self):
        for value in (True, 0, -1, 44.0, "44"):
            rows = copy.deepcopy(self.rows)
            rows[0]["driver_number"] = value
            with self.subTest(value=value):
                self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 17
    def test_blank_and_untrimmed_required_names_hold(self):
        for field in ("broadcast_name", "full_name", "team_name"):
            for value in ("", "   ", " leading", "trailing "):
                rows = copy.deepcopy(self.rows)
                rows[0][field] = value
                with self.subTest(field=field, value=value):
                    self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 18
    def test_optional_metadata_accepts_only_string_or_null(self):
        valid = copy.deepcopy(self.rows)
        for field in m.OPTIONAL_FIELDS:
            valid[0][field] = ""
            valid[1][field] = None
        self.assertEqual(self.result_for_rows(valid)["status"], m.VALIDATED)
        for field in m.OPTIONAL_FIELDS:
            invalid = copy.deepcopy(self.rows)
            invalid[0][field] = 1
            with self.subTest(field=field):
                self.assert_hold_without_partial_output(self.result_for_rows(invalid))

    # 19
    def test_no_retrieval_timestamp_or_provenance_columns(self):
        header = self.adapt()["producer_input_csv_bytes"].splitlines()[0]
        self.assertEqual(header.decode("ascii"), ",".join(m.CSV_FIELDS))
        self.assertNotIn(b"source_closure_retrieved_utc", header)
        self.assertNotIn(b"first_observed_utc", header)
        self.assertNotIn(b"receipt", header)

    # 20
    def test_derived_hash_and_runtime_identity_recompute_exactly(self):
        result = self.adapt()
        expected = hashlib.sha256(result["producer_input_csv_bytes"]).hexdigest()
        self.assertEqual(result["producer_input_sha256"], expected)
        self.assertEqual(result["derived_runtime_identity"],
                         "derived:openf1-drivers-csv:" + expected)
        self.assertNotEqual(expected, result["raw_source_sha256"])

    # 21
    def test_no_new_receipt_normalization_receipt_or_verified_binding(self):
        result = self.adapt()
        self.assertFalse(result["derived_csv_is_source_evidence"])
        self.assertFalse(result["new_scientific_receipt_created"])
        self.assertFalse(result["normalization_receipt_created"])
        self.assertFalse(result["verified_receipt_bindings_created"])
        self.assertNotIn("verified_receipt_bindings", result)
        self.assertNotIn("verified_receipt_bindings",
                         result["frozen_evidence_manifest"])

    # 22
    def test_frozen_manifest_trust_remains_unbound_and_false(self):
        trust = self.adapt()["frozen_evidence_manifest"]["trust"]
        self.assertEqual(trust, m.frozen_contract.TRUST)
        self.assertEqual(trust["binding_status"], "UNBOUND")
        self.assertIs(trust["production_authenticated"], False)
        self.assertIs(trust["historical_availability_proven"], False)

    # 23
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
            "time", "datetime", "glob", "tempfile",
        })
        for forbidden in (
            "Path(", "open(", ".read_", ".write_", "datetime.now", "utcnow",
            "getenv", "environ", "subprocess", "requests", "urllib.request",
        ):
            self.assertNotIn(forbidden, source)

    # 24
    def test_unchanged_producer_recognizes_and_consumes_drivers_csv_columns(self):
        producer_spec = importlib.util.spec_from_file_location(
            "actual_forecast_producer_for_k4r6_test", PRODUCER_SCRIPT
        )
        producer = importlib.util.module_from_spec(producer_spec)
        producer_spec.loader.exec_module(producer)
        self.assertIn("drivers.csv", producer.SOURCE_FILES["drivers"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drivers.csv"
            path.write_bytes(self.adapt()["producer_input_csv_bytes"])
            universe = producer.build_driver_universe({"drivers": path})
        by_number = {row["driver_number"]: row for row in universe}
        self.assertEqual(by_number[44]["driver_name"], "L HAMILTON")
        self.assertEqual(by_number[44]["team_name"], "Scuderia Ferrari HP")
        self.assertEqual(by_number[1]["driver_name"], "M VERSTAPPEN")
        self.assertEqual(by_number[1]["team_name"], "Red Bull Racing")

    # 25
    def test_all_named_dependency_blobs_are_unchanged(self):
        for relative_path, expected in m.DEPENDENCY_BLOBS.items():
            with self.subTest(relative_path=relative_path):
                self.assertEqual(git_blob_sha((ROOT / relative_path).read_bytes()), expected)

    def test_all_result_claim_ceilings_remain_false(self):
        result = self.adapt()
        for field in (
            "stable_engine_execution_proven", "blind_validation_eligible",
            "production_forecast_generated", "dr002_activated",
            "promotion_allowed",
        ):
            self.assertIs(result[field], False)


if __name__ == "__main__":
    unittest.main()
