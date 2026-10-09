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
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "scripts/forecast_bundles"
SCRIPT = BUNDLE_DIR / "dr002_openf1_starting_grid_producer_adapter_v1.py"
sys.path.insert(0, str(BUNDLE_DIR))
spec = importlib.util.spec_from_file_location("openf1_starting_grid_adapter", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import dr002_openf1_historical_rest_capture_v1 as capture
import verify_forecast_integrity_receipts_v1 as receipts


def git_blob_sha(data):
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


class OpenF1StartingGridProducerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.scope = {
            "event_id": "2026_1279_australia_melbourne_race",
            "meeting_id": "1279",
            "session_id": "11442",
        }
        self.rows = [
            {
                "position": 3,
                "driver_number": 81,
                "lap_duration": None,
                "meeting_key": 1279,
                "session_key": 11442,
            },
            {
                "position": 1,
                "driver_number": 44,
                "lap_duration": 75.123,
                "meeting_key": "1279",
                "session_key": "11442",
            },
            {
                "position": 2,
                "driver_number": 16,
                "lap_duration": 0,
                "meeting_key": 1279,
                "session_key": "11442",
            },
        ]
        self.raw = self.raw_bytes(self.rows)
        self.receipt_bytes = self.receipt_for(self.raw)

    @staticmethod
    def raw_bytes(value):
        return json.dumps(
            value, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")

    def receipt_for(self, raw):
        result = capture.assess_openf1_historical_rest_capture(
            **self.scope,
            endpoint="starting_grid",
            request_params={"session_key": self.scope["session_id"]},
            raw_response_bytes=raw,
            http_status=200,
            session_end_utc="2026-03-08T06:00:00Z",
            first_observed_utc="2026-10-09T13:00:00Z",
            ingested_utc="2026-10-09T13:00:01Z",
            receipt_created_utc="2026-10-09T13:00:02Z",
            capture_ref="_runtime/mock/starting_grid.response.json",
            implementation="dr002_openf1_historical_rest_capture_v1",
        )
        self.assertEqual(result["status"], capture.VALIDATED)
        return result["source_capture_receipt_bytes"]

    def adapt(self, receipt_bytes=None, raw=None, **changes):
        args = {
            "source_capture_receipt_bytes": (
                self.receipt_bytes if receipt_bytes is None else receipt_bytes
            ),
            "raw_starting_grid_response_bytes": self.raw if raw is None else raw,
            **self.scope,
        }
        args.update(changes)
        return m.adapt_openf1_starting_grid_to_producer_input(**args)

    def changed_receipt(self, change, *, refresh_identity=True):
        receipt = json.loads(self.receipt_bytes)
        change(receipt)
        if refresh_identity:
            identity = {
                key: receipt[key]
                for key in (
                    "receipt_type",
                    "scope",
                    "parent_receipt_ids",
                    "payload",
                )
            }
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
        for key in (
            "producer_input_csv_bytes",
            "frozen_evidence_manifest",
            "source_receipt_id",
            "raw_source_id",
            "raw_source_sha256",
            "derived_runtime_identity",
        ):
            self.assertNotIn(key, result)
        self.assertFalse(result["new_scientific_receipt_created"])
        self.assertFalse(result["verified_receipt_bindings_created"])

    # 1
    def test_valid_documented_three_driver_response_validates(self):
        result = self.adapt()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["scope"], self.scope)
        self.assertEqual(result["session_kind"], "Race")
        self.assertTrue(result["session_kind_asserted"])
        self.assertFalse(result["session_kind_assertion_authenticated"])
        self.assertEqual(result["row_count"], 3)
        self.assertEqual(result["unique_driver_count"], 3)
        self.assertEqual(result["slot_count"], 3)

    # 2
    def test_csv_has_exact_header_lf_and_numeric_position_order(self):
        data = self.adapt()["producer_input_csv_bytes"]
        self.assertNotIn(b"\r", data)
        self.assertEqual(
            data,
            (
                "driver_number,position,event_id,meeting_id,session_id\n"
                "44,1,2026_1279_australia_melbourne_race,1279,11442\n"
                "16,2,2026_1279_australia_melbourne_race,1279,11442\n"
                "81,3,2026_1279_australia_melbourne_race,1279,11442\n"
            ).encode("utf-8"),
        )

    # 3
    def test_derived_hash_and_identity_are_exact_and_distinct_from_raw(self):
        result = self.adapt()
        expected = hashlib.sha256(result["producer_input_csv_bytes"]).hexdigest()
        self.assertEqual(result["producer_input_sha256"], expected)
        self.assertEqual(
            result["derived_runtime_identity"],
            "derived:openf1-starting-grid-csv:" + expected,
        )
        self.assertNotEqual(expected, result["raw_source_sha256"])
        self.assertNotEqual(
            result["derived_runtime_identity"], result["raw_source_id"]
        )

    # 4
    def test_raw_row_order_changes_raw_identity_but_not_derived_csv(self):
        reversed_raw = self.raw_bytes(list(reversed(self.rows)))
        first = self.adapt()
        second = self.adapt(
            receipt_bytes=self.receipt_for(reversed_raw), raw=reversed_raw
        )
        self.assertEqual(first["producer_input_csv_bytes"],
                         second["producer_input_csv_bytes"])
        self.assertEqual(first["producer_input_sha256"],
                         second["producer_input_sha256"])
        self.assertNotEqual(first["raw_source_sha256"],
                            second["raw_source_sha256"])
        self.assertNotEqual(first["source_receipt_id"],
                            second["source_receipt_id"])

    # 5
    def test_frozen_manifest_binds_raw_receipt_and_bytes_not_csv(self):
        result = self.adapt()
        manifest = result["frozen_evidence_manifest"]
        evidence = manifest["evidence"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["receipt_id"], result["source_receipt_id"])
        self.assertEqual(evidence[0]["source_sha256"],
                         result["raw_source_sha256"])
        self.assertNotEqual(evidence[0]["source_sha256"],
                            result["producer_input_sha256"])
        self.assertEqual(manifest["trust"], m.frozen_contract.TRUST)
        self.assertEqual(manifest["trust"]["binding_status"], "UNBOUND")

    # 6
    def test_null_lap_duration_is_valid_and_never_inferred_into_csv(self):
        result = self.adapt()
        self.assertEqual(result["status"], m.VALIDATED)
        header = result["producer_input_csv_bytes"].splitlines()[0]
        self.assertNotIn(b"lap_duration", header)
        self.assertNotIn(b"qualifying", result["producer_input_csv_bytes"])

    # 7
    def test_repeated_call_is_deterministic(self):
        self.assertEqual(self.adapt(), self.adapt())

    # 8
    def test_only_exact_explicit_race_session_kind_is_accepted(self):
        for value in ("Practice 2", "Sprint", "Qualifying", "race", "Race ", None):
            with self.subTest(value=value):
                self.assert_hold_without_partial_output(
                    self.adapt(session_kind=value)
                )
        self.assertEqual(self.adapt(session_kind="Race")["status"], m.VALIDATED)

    # 9
    def test_required_keyword_arguments_remain_required(self):
        with self.assertRaises(TypeError):
            m.adapt_openf1_starting_grid_to_producer_input(
                source_capture_receipt_bytes=self.receipt_bytes,
                raw_starting_grid_response_bytes=self.raw,
                event_id=self.scope["event_id"],
                meeting_id=self.scope["meeting_id"],
            )

    # 10
    def test_raw_hash_mismatch_and_foreign_raw_types_hold(self):
        for raw in (self.raw + b" ", bytearray(self.raw), "not bytes", b""):
            with self.subTest(raw_type=type(raw).__name__):
                self.assert_hold_without_partial_output(self.adapt(raw=raw))

    # 11
    def test_noncanonical_malformed_duplicate_nonfinite_parented_receipts_hold(self):
        duplicate = self.receipt_bytes.replace(
            b'"schema_version":',
            b'"schema_version":"dr002-receipt-v1","schema_version":',
            1,
        )
        nonfinite = self.receipt_bytes.replace(
            b'"event_time_utc":null', b'"event_time_utc":NaN', 1
        )
        cases = (
            self.receipt_bytes + b" ",
            b"{",
            duplicate,
            nonfinite,
            self.changed_receipt(
                lambda receipt: receipt["parent_receipt_ids"].append("other")
            ),
            bytearray(self.receipt_bytes),
            b"",
        )
        for value in cases:
            with self.subTest(value_type=type(value).__name__):
                self.assert_hold_without_partial_output(
                    self.adapt(receipt_bytes=value)
                )

    # 12
    def test_wrong_receipt_type_and_receipt_id_hold(self):
        wrong_type = self.changed_receipt(
            lambda receipt: receipt.__setitem__("receipt_type", "revision")
        )
        wrong_id = self.changed_receipt(
            lambda receipt: receipt.__setitem__(
                "receipt_id", "source_capture:wrong"
            ),
            refresh_identity=False,
        )
        for value in (wrong_type, wrong_id):
            self.assert_hold_without_partial_output(
                self.adapt(receipt_bytes=value)
            )

    # 13
    def test_wrong_uri_query_alias_provider_and_source_id_hold(self):
        cases = (
            self.changed_receipt(
                lambda receipt: receipt["payload"].update(
                    source_uri=(
                        "https://api.openf1.org/v1/starting_grid?session_key=011442"
                    ),
                    source_id="openf1:starting_grid:" + "0" * 64,
                )
            ),
            self.changed_receipt(
                lambda receipt: receipt["payload"].update(
                    source_uri="https://example.invalid/v1/starting_grid?session_key=11442",
                    source_id="openf1:starting_grid:" + "0" * 64,
                )
            ),
            self.changed_receipt(
                lambda receipt: receipt["payload"].__setitem__(
                    "source_id", "openf1:starting_grid:" + "0" * 64
                )
            ),
        )
        for value in cases:
            self.assert_hold_without_partial_output(
                self.adapt(receipt_bytes=value)
            )

    # 14
    def test_receipt_scope_mismatch_and_noncanonical_scope_ids_hold(self):
        for changes in (
            {"event_id": "different"},
            {"meeting_id": "9999"},
            {"session_id": "99999"},
            {"meeting_id": "01279"},
            {"session_id": "011442"},
        ):
            with self.subTest(changes=changes):
                self.assert_hold_without_partial_output(self.adapt(**changes))

    # 15
    def test_malformed_duplicate_nonfinite_wrong_top_level_and_empty_json_hold(self):
        cases = (
            b"[",
            b'[{"position":1,"position":2}]',
            b'[{"position":NaN}]',
            b'[{"position":Infinity}]',
            b"{}",
            b"[]",
        )
        for raw in cases:
            with self.subTest(raw=raw):
                self.assert_hold_without_partial_output(
                    self.adapt(
                        receipt_bytes=self.receipt_for_unvalidated_raw(raw),
                        raw=raw,
                    )
                )

    # 16
    def test_missing_and_extra_documented_columns_hold(self):
        for field in m.DOCUMENTED_FIELDS:
            rows = copy.deepcopy(self.rows)
            rows[0].pop(field)
            with self.subTest(missing=field):
                self.assert_hold_without_partial_output(self.result_for_rows(rows))
        rows = copy.deepcopy(self.rows)
        rows[0]["unexpected"] = "schema drift"
        self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 17
    def test_position_must_be_positive_integer_not_bool(self):
        for value in (True, False, None, 0, -1, 1.0, "1"):
            rows = copy.deepcopy(self.rows)
            rows[0]["position"] = value
            with self.subTest(value=value):
                self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 18
    def test_driver_number_must_be_positive_integer_not_bool(self):
        for value in (True, False, None, 0, -1, 44.0, "44"):
            rows = copy.deepcopy(self.rows)
            rows[0]["driver_number"] = value
            with self.subTest(value=value):
                self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 19
    def test_duplicate_position_and_driver_number_hold(self):
        rows = copy.deepcopy(self.rows)
        rows[1]["position"] = rows[0]["position"]
        self.assert_hold_without_partial_output(self.result_for_rows(rows))
        rows = copy.deepcopy(self.rows)
        rows[1]["driver_number"] = rows[0]["driver_number"]
        self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 20
    def test_foreign_and_noncanonical_meeting_or_session_values_hold(self):
        cases = (
            ("meeting_key", 9999),
            ("meeting_key", "01279"),
            ("meeting_key", True),
            ("session_key", 99999),
            ("session_key", "011442"),
            ("session_key", True),
        )
        for field, value in cases:
            rows = copy.deepcopy(self.rows)
            rows[0][field] = value
            with self.subTest(field=field, value=value):
                self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 21
    def test_empty_and_more_than_26_rows_hold(self):
        self.assert_hold_without_partial_output(self.result_for_rows([]))
        rows = [
            {
                "position": index,
                "driver_number": 100 + index,
                "lap_duration": None,
                "meeting_key": 1279,
                "session_key": 11442,
            }
            for index in range(1, 28)
        ]
        self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 22
    def test_holes_null_slots_withdrawals_and_non_one_based_positions_hold(self):
        cases = (
            [1, 3, 4],
            [2, 3, 4],
            [1, 2, None],
        )
        for positions in cases:
            rows = copy.deepcopy(self.rows)
            for row, position in zip(rows, positions):
                row["position"] = position
            with self.subTest(positions=positions):
                self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 23
    def test_lap_duration_allows_finite_nonnegative_number_or_null_only(self):
        for value in (None, 0, 0.0, 75, 75.123):
            rows = copy.deepcopy(self.rows)
            rows[0]["lap_duration"] = value
            with self.subTest(valid=value):
                self.assertEqual(self.result_for_rows(rows)["status"], m.VALIDATED)
        for value in (True, False, -0.1, "75.123", [], {}):
            rows = copy.deepcopy(self.rows)
            rows[0]["lap_duration"] = value
            with self.subTest(invalid=value):
                self.assert_hold_without_partial_output(self.result_for_rows(rows))

    # 24
    def test_dynamic_driver_universe_is_not_hardcoded_to_22(self):
        rows = copy.deepcopy(self.rows[:2])
        rows[0]["position"] = 2
        rows[1]["position"] = 1
        result = self.result_for_rows(rows)
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["unique_driver_count"], 2)
        self.assertEqual(result["slot_count"], 2)

    # 25
    def test_existing_receipt_and_frozen_contracts_are_called(self):
        with mock.patch.object(
            m.receipt_contract,
            "validate_receipt_envelope",
            wraps=m.receipt_contract.validate_receipt_envelope,
        ) as validate_receipt, mock.patch.object(
            m.receipt_contract,
            "verify_temporal_bindings",
            wraps=m.receipt_contract.verify_temporal_bindings,
        ) as verify_time, mock.patch.object(
            m.frozen_contract,
            "build_frozen_evidence_manifest",
            wraps=m.frozen_contract.build_frozen_evidence_manifest,
        ) as build_frozen, mock.patch.object(
            m.frozen_contract,
            "validate_frozen_evidence_manifest",
            wraps=m.frozen_contract.validate_frozen_evidence_manifest,
        ) as validate_frozen:
            result = self.adapt()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertTrue(validate_receipt.called)
        self.assertTrue(verify_time.called)
        build_frozen.assert_called_once()
        self.assertTrue(validate_frozen.called)

    # 26
    def test_every_scientific_and_activation_ceiling_remains_false(self):
        result = self.adapt()
        for field in m.CLAIM_CEILINGS:
            self.assertIs(result[field], False, field)
        self.assertEqual(
            result["provider_category"], "UNOFFICIAL_OPENF1_DOCUMENTED_REST"
        )
        self.assertFalse(result["commercial_or_redistribution_permission_claimed"])

    # 27
    def test_adapter_has_no_network_filesystem_clock_subprocess_or_dispatch_access(self):
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
            "time", "datetime", "glob", "tempfile", "http", "selenium",
        })
        for forbidden in (
            "Path(", "open(", ".read_", ".write_", "datetime.now", "utcnow",
            "getenv", "environ", "subprocess", "requests", "urllib.request",
            "workflow_dispatch", "api.openf1.org", ".pdf", "formula1.com",
        ):
            self.assertNotIn(forbidden, source)

    # 28
    def test_all_named_dependency_blobs_are_unchanged(self):
        for relative_path, expected in m.DEPENDENCY_BLOBS.items():
            with self.subTest(relative_path=relative_path):
                self.assertEqual(
                    git_blob_sha((ROOT / relative_path).read_bytes()), expected
                )

    # 29
    def test_csv_is_parseable_with_exact_scope_and_position_values(self):
        data = self.adapt()["producer_input_csv_bytes"].decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(data, newline="")))
        self.assertEqual(tuple(rows[0]), m.CSV_FIELDS)
        self.assertEqual([row["position"] for row in rows], ["1", "2", "3"])
        self.assertEqual({row["event_id"] for row in rows},
                         {self.scope["event_id"]})
        self.assertEqual({row["meeting_id"] for row in rows}, {"1279"})
        self.assertEqual({row["session_id"] for row in rows}, {"11442"})


if __name__ == "__main__":
    unittest.main()
