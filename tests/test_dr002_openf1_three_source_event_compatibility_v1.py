import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "scripts/forecast_bundles"
SCRIPT = BUNDLE_DIR / "dr002_openf1_three_source_event_compatibility_v1.py"
sys.path.insert(0, str(BUNDLE_DIR))
spec = importlib.util.spec_from_file_location("three_source_compatibility", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import dr002_openf1_historical_rest_capture_v1 as capture
import verify_forecast_integrity_receipts_v1 as receipts


class ThreeSourceEventCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.event_id = "2026_1295_azerbaijan_baku_baku"
        self.meeting_id = "1295"
        self.practice_id = "11371"
        self.qualifying_id = "11373"
        self.race_id = "11377"
        self.weather_rows = [{
            "date": "2026-09-24T12:15:00Z",
            "session_key": 11371,
            "meeting_key": 1295,
            "air_temperature": 24.0,
            "track_temperature": 31.0,
            "humidity": 48,
            "pressure": 1012,
            "rainfall": 0,
            "wind_direction": 180,
            "wind_speed": 3.5,
        }]
        self.drivers_rows = [self.driver(44), self.driver(16), self.driver(81)]
        self.grid_rows = [
            self.grid(2, 16), self.grid(1, 44), self.grid(3, 81)
        ]
        self.sessions = [
            self.session(self.practice_id, "Practice 2", "Practice",
                         "2026-09-24T12:00:00Z", "2026-09-24T13:00:00Z"),
            self.session(self.qualifying_id, "Qualifying", "Qualifying",
                         "2026-09-25T12:00:00Z", "2026-09-25T13:00:00Z"),
            self.session(self.race_id, "Race", "Race",
                         "2026-09-26T11:00:00Z", "2026-09-26T13:00:00Z"),
        ]
        self.refresh_sources()

    @staticmethod
    def json_bytes(value):
        return json.dumps(
            value, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")

    def driver(self, number):
        return {
            "meeting_key": 1295,
            "session_key": 11371,
            "driver_number": number,
            "broadcast_name": f"DRIVER {number}",
            "full_name": f"Driver {number}",
            "team_name": f"Team {number}",
        }

    def grid(self, position, number):
        return {
            "position": position,
            "driver_number": number,
            "lap_duration": None,
            "meeting_key": 1295,
            "session_key": 11373,
        }

    def session(self, session_id, name, kind, start, end, **changes):
        row = {
            "session_key": int(session_id),
            "meeting_key": 1295,
            "year": 2026,
            "country_name": "Azerbaijan",
            "location": "Baku",
            "circuit_short_name": "Baku",
            "session_name": name,
            "session_type": kind,
            "date_start": start,
            "date_end": end,
        }
        row.update(changes)
        return row

    def receipt(self, endpoint, session_id, raw, first_observed):
        result = capture.assess_openf1_historical_rest_capture(
            event_id=self.event_id,
            meeting_id=self.meeting_id,
            session_id=session_id,
            endpoint=endpoint,
            request_params={"session_key": session_id},
            raw_response_bytes=raw,
            http_status=200,
            session_end_utc=("2026-09-24T13:00:00Z"
                             if session_id == self.practice_id
                             else "2026-09-25T13:00:00Z"),
            first_observed_utc=first_observed,
            ingested_utc="2026-10-14T10:14:20Z",
            receipt_created_utc="2026-10-14T10:14:21Z",
            capture_ref=f"memory:{endpoint}.response.json",
            implementation="synthetic-test-fixture",
        )
        self.assertEqual(result["status"], capture.VALIDATED)
        return result["source_capture_receipt_bytes"]

    def refresh_sources(self):
        self.weather_raw = self.json_bytes(self.weather_rows)
        self.drivers_raw = self.json_bytes(self.drivers_rows)
        self.grid_raw = self.json_bytes(self.grid_rows)
        self.sessions_raw = self.json_bytes(self.sessions)
        self.weather_receipt = self.receipt(
            "weather", self.practice_id, self.weather_raw,
            "2026-10-08T12:12:09Z",
        )
        self.drivers_receipt = self.receipt(
            "drivers", self.practice_id, self.drivers_raw,
            "2026-10-08T13:00:00Z",
        )
        self.grid_receipt = self.receipt(
            "starting_grid", self.qualifying_id, self.grid_raw,
            "2026-10-14T10:14:18Z",
        )
        self.manifest = self.valid_manifest()
        self.manifest_raw = self.json_bytes(self.manifest)

    def valid_manifest(self):
        grid_receipt = json.loads(self.grid_receipt)
        source_id = grid_receipt["payload"]["source_id"]
        grid_sha = hashlib.sha256(self.grid_raw).hexdigest()
        sessions_sha = hashlib.sha256(self.sessions_raw).hexdigest()
        return {
            "status": capture.VALIDATED,
            "k4r1_status": capture.VALIDATED,
            "k4r14_status": m.grid_adapter.VALIDATED,
            "selected_endpoint": "starting_grid",
            "event_id": self.event_id,
            "meeting_id": self.meeting_id,
            "session_id": self.qualifying_id,
            "grid_source_session_id": self.qualifying_id,
            "grid_source_session_kind": "Qualifying",
            "grid_target_race_session_id": self.race_id,
            "grid_target_race_session_kind": "Race",
            "source_to_race_link_evidence_type": m.PROVIDER_LINK,
            "session_discovery_raw_sha256": sessions_sha,
            "discovery_response_sha256": sessions_sha,
            "starting_grid_raw_sha256": grid_sha,
            "raw_response_sha256": grid_sha,
            "source_receipt_id": grid_receipt["receipt_id"],
            "raw_source_id": source_id,
            "frozen_evidence_binding_status": "UNBOUND",
            "source_session_classification_authenticated": False,
            "target_race_session_classification_authenticated": False,
            "producer_input_csv_is_target_race_scoped": False,
            "cross_session_join_authorized": False,
            "official_fia_grid_authenticated": False,
            "historical_pre_race_availability_proven": False,
            "blind_validation_eligible": False,
            "stable_engine_execution_proven": False,
            "production_forecast_generated": False,
            "dr002_activated": False,
            "promotion_allowed": False,
        }

    def assess(self, **changes):
        args = {
            "weather_source_capture_receipt_bytes": self.weather_receipt,
            "raw_weather_response_bytes": self.weather_raw,
            "drivers_source_capture_receipt_bytes": self.drivers_receipt,
            "raw_drivers_response_bytes": self.drivers_raw,
            "starting_grid_source_capture_receipt_bytes": self.grid_receipt,
            "raw_starting_grid_response_bytes": self.grid_raw,
            "sessions_response_bytes": self.sessions_raw,
            "grid_shadow_manifest_bytes": self.manifest_raw,
            "event_id": self.event_id,
            "meeting_id": self.meeting_id,
            "practice_session_id": self.practice_id,
            "qualifying_source_session_id": self.qualifying_id,
            "target_race_session_id": self.race_id,
            "implementation_git_sha": "a" * 40,
        }
        args.update(changes)
        return m.assess_openf1_three_source_event_compatibility(**args)

    def result_for_sessions(self, rows):
        raw = self.json_bytes(rows)
        manifest = copy.deepcopy(self.manifest)
        digest = hashlib.sha256(raw).hexdigest()
        manifest["session_discovery_raw_sha256"] = digest
        manifest["discovery_response_sha256"] = digest
        return self.assess(
            sessions_response_bytes=raw,
            grid_shadow_manifest_bytes=self.json_bytes(manifest),
        )

    def changed_receipt(self, receipt_bytes, change, *, refresh_id=True):
        receipt = json.loads(receipt_bytes)
        change(receipt)
        if refresh_id:
            identity = {key: receipt[key] for key in (
                "receipt_type", "scope", "parent_receipt_ids", "payload"
            )}
            receipt["receipt_id"] = "source_capture:" + receipts.sha256(
                receipts.canonical_json_bytes(identity)
            )
        return receipts.canonical_json_bytes(receipt)

    def assert_hold_minimal(self, result):
        self.assertEqual(result["status"], m.HOLD)
        self.assertEqual(set(result), {
            "schema_version", "status", "reason_codes", *m.COMMON_FALSE_FLAGS
        })
        self.assertTrue(all(result[field] is False for field in m.COMMON_FALSE_FLAGS))
        serialized = json.dumps(result)
        for forbidden_value in (
            json.loads(self.weather_receipt)["receipt_id"],
            json.loads(self.drivers_receipt)["payload"]["source_id"],
            "DRIVER 44",
        ):
            self.assertNotIn(forbidden_value, serialized)

    # 1
    def test_valid_synthetic_baku_event_is_post_event_mechanics_only(self):
        result = self.assess()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertIn("POST_EVENT_MECHANICS_ONLY_NOT_A_PREDICTION",
                      result["status"])
        self.assertEqual(result["event_id"], self.event_id)
        self.assertEqual(result["drivers"]["unique_driver_count"], 3)
        self.assertEqual(result["starting_grid"]["slot_count"], 3)

    # 2
    def test_result_is_deterministic_json_serializable_and_contains_no_bytes(self):
        first = self.assess()
        second = self.assess()
        self.assertEqual(first, second)
        json.dumps(first, sort_keys=True, allow_nan=False)

        def visit(value):
            if isinstance(value, dict):
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
            else:
                self.assertNotIsInstance(value, bytes)
        visit(first)

    # 3
    def test_valid_result_preserves_three_distinct_sessions_and_false_claims(self):
        result = self.assess()
        self.assertEqual(result["practice_session"]["session_id"], "11371")
        self.assertEqual(result["qualifying_source_session"]["session_id"], "11373")
        self.assertEqual(result["target_race_session"]["session_id"], "11377")
        self.assertTrue(all(result[field] is False for field in m.COMMON_FALSE_FLAGS))
        self.assertFalse(result["combined_frozen_producer_manifest_created"])

    # 4
    def test_valid_result_preserves_separate_source_and_derived_identities(self):
        result = self.assess()
        sources = [result[name] for name in ("weather", "drivers", "starting_grid")]
        self.assertEqual(len({row["source_receipt_id"] for row in sources}), 3)
        self.assertEqual(len({row["raw_source_id"] for row in sources}), 3)
        self.assertEqual(len({row["derived_runtime_identity"] for row in sources}), 3)
        self.assertTrue(all(row["raw_frozen_evidence_binding_status"] == "UNBOUND"
                            for row in sources))

    # 5
    def test_explicit_ids_must_be_canonical_positive_and_distinct(self):
        for field, value in (
            ("meeting_id", "01295"), ("practice_session_id", 11371),
            ("qualifying_source_session_id", "0"),
            ("target_race_session_id", "11373"),
        ):
            with self.subTest(field=field, value=value):
                self.assert_hold_minimal(self.assess(**{field: value}))

    # 6
    def test_empty_malformed_object_duplicate_and_nonfinite_discovery_hold(self):
        for raw in (b"", b"[", b"{}", b'[{"x":1,"x":2}]', b"[NaN]"):
            with self.subTest(raw=raw):
                self.assert_hold_minimal(self.assess(sessions_response_bytes=raw))

    # 7
    def test_missing_practice_session_holds(self):
        self.assert_hold_minimal(self.result_for_sessions(self.sessions[1:]))

    # 8
    def test_duplicate_session_id_holds(self):
        rows = self.sessions + [copy.deepcopy(self.sessions[0])]
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 9
    def test_wrong_practice_type_or_name_holds(self):
        for field, value in (("session_name", "Practice 1"),
                             ("session_type", "Qualifying")):
            rows = copy.deepcopy(self.sessions)
            rows[0][field] = value
            self.assert_hold_minimal(self.result_for_sessions(rows))

    # 10
    def test_wrong_qualifying_type_or_name_holds(self):
        for field, value in (("session_name", "Sprint Qualifying"),
                             ("session_type", "Sprint")):
            rows = copy.deepcopy(self.sessions)
            rows[1][field] = value
            self.assert_hold_minimal(self.result_for_sessions(rows))

    # 11
    def test_wrong_race_type_or_name_holds(self):
        for field, value in (("session_name", "Sprint"),
                             ("session_type", "Practice")):
            rows = copy.deepcopy(self.sessions)
            rows[2][field] = value
            self.assert_hold_minimal(self.result_for_sessions(rows))

    # 12
    def test_cancelled_session_holds(self):
        for index in range(3):
            rows = copy.deepcopy(self.sessions)
            rows[index]["cancelled"] = True
            self.assert_hold_minimal(self.result_for_sessions(rows))

    # 13
    def test_cross_meeting_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows[1]["meeting_key"] = 9999
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 14
    def test_cross_year_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows[1]["year"] = 2025
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 15
    def test_cross_circuit_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows[2]["circuit_short_name"] = "Other"
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 16
    def test_cross_country_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows[1]["country_name"] = "Other"
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 17
    def test_cross_location_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows[1]["location"] = "Other"
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 18
    def test_event_id_must_match_discovery_identity(self):
        self.assert_hold_minimal(self.assess(event_id="2026_1295_fake"))

    # 19
    def test_chronology_inversion_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows[1]["date_start"] = "2026-09-24T12:30:00Z"
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 20
    def test_missing_end_and_non_utc_timezone_hold(self):
        for value in (None, "2026-09-25T13:00:00+01:00"):
            rows = copy.deepcopy(self.sessions)
            rows[1]["date_end"] = value
            self.assert_hold_minimal(self.result_for_sessions(rows))

    # 21
    def test_sprint_weekend_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows.append(self.session("11372", "Sprint", "Sprint",
                                 "2026-09-25T08:00:00Z",
                                 "2026-09-25T09:00:00Z"))
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 22
    def test_extra_qualifying_or_race_is_ambiguous_and_holds(self):
        for session_id, name, kind in (
            ("11374", "Qualifying", "Qualifying"),
            ("11378", "Race", "Race"),
        ):
            rows = copy.deepcopy(self.sessions)
            rows.append(self.session(session_id, name, kind,
                                     "2026-09-25T14:00:00Z",
                                     "2026-09-25T15:00:00Z"))
            self.assert_hold_minimal(self.result_for_sessions(rows))

    # 23
    def test_manifest_discovery_hash_mismatch_holds(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["discovery_response_sha256"] = "0" * 64
        self.assert_hold_minimal(self.assess(
            grid_shadow_manifest_bytes=self.json_bytes(manifest)
        ))

    # 24
    def test_manifest_grid_hash_or_source_id_mismatch_holds(self):
        for field, value in (("starting_grid_raw_sha256", "0" * 64),
                             ("raw_source_id", "openf1:starting_grid:" + "0" * 64)):
            manifest = copy.deepcopy(self.manifest)
            manifest[field] = value
            self.assert_hold_minimal(self.assess(
                grid_shadow_manifest_bytes=self.json_bytes(manifest)
            ))

    # 25
    def test_manifest_receipt_id_or_target_mismatch_holds(self):
        for field, value in (("source_receipt_id", "source_capture:" + "0" * 64),
                             ("grid_target_race_session_id", "99999")):
            manifest = copy.deepcopy(self.manifest)
            manifest[field] = value
            self.assert_hold_minimal(self.assess(
                grid_shadow_manifest_bytes=self.json_bytes(manifest)
            ))

    # 26
    def test_manifest_forbidden_claim_holds(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["cross_session_join_authorized"] = True
        self.assert_hold_minimal(self.assess(
            grid_shadow_manifest_bytes=self.json_bytes(manifest)
        ))

    # 27
    def test_weather_wrong_scope_hash_or_receipt_id_holds(self):
        cases = [
            self.changed_receipt(
                self.weather_receipt,
                lambda row: row["scope"].__setitem__("session_id", "99999"),
            ),
            self.changed_receipt(
                self.weather_receipt,
                lambda row: row["payload"].__setitem__("source_sha256", "0" * 64),
            ),
            self.changed_receipt(
                self.weather_receipt,
                lambda row: row.__setitem__("receipt_id", "source_capture:" + "0" * 64),
                refresh_id=False,
            ),
        ]
        for receipt_bytes in cases:
            self.assert_hold_minimal(self.assess(
                weather_source_capture_receipt_bytes=receipt_bytes
            ))

    # 28
    def test_driver_roster_mismatch_holds_without_padding(self):
        rows = self.drivers_rows[:-1]
        raw = self.json_bytes(rows)
        receipt_bytes = self.receipt(
            "drivers", self.practice_id, raw, "2026-10-08T13:00:00Z"
        )
        self.assert_hold_minimal(self.assess(
            raw_drivers_response_bytes=raw,
            drivers_source_capture_receipt_bytes=receipt_bytes,
        ))

    # 29
    def test_duplicate_grid_driver_and_grid_hole_hold_in_adapter(self):
        for rows in (
            [self.grid(1, 44), self.grid(2, 44), self.grid(3, 81)],
            [self.grid(1, 44), self.grid(3, 16), self.grid(4, 81)],
        ):
            raw = self.json_bytes(rows)
            receipt_bytes = self.receipt(
                "starting_grid", self.qualifying_id, raw,
                "2026-10-14T10:14:18Z",
            )
            self.assert_hold_minimal(self.assess(
                raw_starting_grid_response_bytes=raw,
                starting_grid_source_capture_receipt_bytes=receipt_bytes,
            ))

    # 30
    def test_source_first_observed_before_race_holds(self):
        receipt_bytes = self.receipt(
            "drivers", self.practice_id, self.drivers_raw,
            "2026-09-26T12:00:00Z",
        )
        self.assert_hold_minimal(self.assess(
            drivers_source_capture_receipt_bytes=receipt_bytes
        ))

    # 31
    def test_missing_or_unknown_first_observed_holds(self):
        for value in (None, "unknown"):
            receipt_bytes = self.changed_receipt(
                self.drivers_receipt,
                lambda row: row["payload"].__setitem__("first_observed_utc", value),
            )
            self.assert_hold_minimal(self.assess(
                drivers_source_capture_receipt_bytes=receipt_bytes
            ))

    # 32
    def test_nonmonotonic_receipt_time_holds(self):
        receipt_bytes = self.changed_receipt(
            self.grid_receipt,
            lambda row: row["payload"].__setitem__(
                "ingested_utc", "2026-10-14T10:14:17Z"
            ),
        )
        self.assert_hold_minimal(self.assess(
            starting_grid_source_capture_receipt_bytes=receipt_bytes
        ))

    # 33
    def test_duplicate_receipt_identity_holds(self):
        duplicate_id = json.loads(self.weather_receipt)["receipt_id"]
        original = m._receipt_metadata

        def duplicate(receipt_bytes, *, result, raw_bytes, source_name):
            value = original(
                receipt_bytes,
                result=result,
                raw_bytes=raw_bytes,
                source_name=source_name,
            )
            if source_name == "drivers":
                value["receipt_id"] = duplicate_id
            return value

        with mock.patch.object(m, "_receipt_metadata", side_effect=duplicate):
            self.assert_hold_minimal(self.assess())

    # 34
    def test_duplicate_key_and_nonfinite_raw_source_hold(self):
        for raw in (b'[{"driver_number":44,"driver_number":16}]', b"[NaN]"):
            receipt_bytes = self.changed_receipt(
                self.drivers_receipt,
                lambda row: row["payload"].__setitem__(
                    "source_sha256", hashlib.sha256(raw).hexdigest()
                ),
            )
            self.assert_hold_minimal(self.assess(
                raw_drivers_response_bytes=raw,
                drivers_source_capture_receipt_bytes=receipt_bytes,
            ))

    # 35
    def test_no_filesystem_network_subprocess_producer_or_clock_surface(self):
        tree = ast.parse(SCRIPT.read_text())
        imported = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        }
        self.assertTrue(imported.isdisjoint({
            "os", "pathlib", "requests", "urllib", "socket", "subprocess",
            "tempfile", "time",
        }))
        text = SCRIPT.read_text()
        for forbidden in (
            "produce_actual_forecast_rows", "weather_drivers_frozen_producer",
            "urlopen(", "requests.", "subprocess.", "Path(", "open(",
            "datetime.now", "datetime.utcnow",
        ):
            self.assertNotIn(forbidden, text)

    # 36
    def test_valid_hashes_are_exact_adapter_outputs_without_row_substitution(self):
        result = self.assess()
        weather = m.weather_adapter.adapt_openf1_weather_to_producer_input(
            source_capture_receipt_bytes=self.weather_receipt,
            raw_weather_response_bytes=self.weather_raw,
            event_id=self.event_id, meeting_id=self.meeting_id,
            session_id=self.practice_id,
        )
        drivers = m.drivers_adapter.adapt_openf1_drivers_to_producer_input(
            source_capture_receipt_bytes=self.drivers_receipt,
            raw_drivers_response_bytes=self.drivers_raw,
            event_id=self.event_id, meeting_id=self.meeting_id,
            session_id=self.practice_id,
        )
        grid = m.grid_adapter.adapt_openf1_starting_grid_to_producer_input(
            source_capture_receipt_bytes=self.grid_receipt,
            raw_starting_grid_response_bytes=self.grid_raw,
            event_id=self.event_id, meeting_id=self.meeting_id,
            session_id=self.qualifying_id, source_session_kind="Qualifying",
            target_race_session_id=self.race_id,
        )
        self.assertEqual(result["weather"]["derived_csv_sha256"],
                         weather["producer_input_sha256"])
        self.assertEqual(result["drivers"]["derived_csv_sha256"],
                         drivers["producer_input_sha256"])
        self.assertEqual(result["starting_grid"]["derived_csv_sha256"],
                         grid["producer_input_sha256"])

    # 37
    def test_implementation_sha_is_optional_information_only(self):
        without = self.assess(implementation_git_sha=None)
        self.assertEqual(without["status"], m.VALIDATED)
        self.assertNotIn("implementation_git_sha", without)
        self.assert_hold_minimal(self.assess(implementation_git_sha="not-a-sha"))


if __name__ == "__main__":
    unittest.main()
