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
SCRIPT = BUNDLE_DIR / "dr002_openf1_three_source_precutoff_candidate_v1.py"
sys.path.insert(0, str(BUNDLE_DIR))
spec = importlib.util.spec_from_file_location("precutoff_candidate", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import dr002_openf1_historical_rest_capture_v1 as capture
import dr002_openf1_three_source_event_compatibility_v1 as compatibility
import verify_forecast_integrity_receipts_v1 as receipts


class ThreeSourcePrecutoffCandidateTests(unittest.TestCase):
    def setUp(self):
        self.event_id = "2026_7001_testland_test_city_test_ring"
        self.meeting_id = "7001"
        self.practice_id = "7101"
        self.qualifying_id = "7102"
        self.race_id = "7103"
        self.cutoff = "2026-01-03T14:00:00Z"
        self.weather_rows = [{
            "date": "2026-01-02T12:15:00Z",
            "session_key": 7101,
            "meeting_key": 7001,
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
                         "2026-01-02T12:00:00Z", "2026-01-02T13:00:00Z"),
            self.session(self.qualifying_id, "Qualifying", "Qualifying",
                         "2026-01-03T12:00:00Z", "2026-01-03T13:00:00Z"),
            self.session(self.race_id, "Race", "Race",
                         "2026-01-04T11:00:00Z", "2026-01-04T13:00:00Z"),
        ]
        self.weather_raw = self.json_bytes(self.weather_rows)
        self.drivers_raw = self.json_bytes(self.drivers_rows)
        self.grid_raw = self.json_bytes(self.grid_rows)
        self.sessions_raw = self.json_bytes(self.sessions)
        self.weather_receipt = self.receipt(
            "weather", self.practice_id, self.weather_raw,
            "2026-01-02T13:30:00Z", "2026-01-02T13:31:00Z",
            "2026-01-02T13:32:00Z",
        )
        self.drivers_receipt = self.receipt(
            "drivers", self.practice_id, self.drivers_raw,
            "2026-01-02T13:33:00Z", "2026-01-02T13:34:00Z",
            "2026-01-02T13:35:00Z",
        )
        self.grid_receipt = self.receipt(
            "starting_grid", self.qualifying_id, self.grid_raw,
            "2026-01-03T13:30:00Z", "2026-01-03T13:31:00Z",
            "2026-01-03T13:32:00Z",
        )
        self.manifest_raw = self.json_bytes(self.valid_manifest())

    @staticmethod
    def json_bytes(value):
        return json.dumps(
            value, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")

    def driver(self, number):
        return {
            "meeting_key": 7001,
            "session_key": 7101,
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
            "meeting_key": 7001,
            "session_key": 7102,
        }

    def session(self, session_id, name, kind, start, end, **changes):
        row = {
            "session_key": int(session_id),
            "meeting_key": 7001,
            "year": 2026,
            "country_name": "Testland",
            "location": "Test City",
            "circuit_short_name": "Test Ring",
            "session_name": name,
            "session_type": kind,
            "date_start": start,
            "date_end": end,
        }
        row.update(changes)
        return row

    def session_end(self, session_id):
        return (
            "2026-01-02T13:00:00Z"
            if session_id == self.practice_id
            else "2026-01-03T13:00:00Z"
        )

    def receipt(self, endpoint, session_id, raw, first, ingested, created,
                *, event_time=None, publisher_time=None):
        result = capture.assess_openf1_historical_rest_capture(
            event_id=self.event_id,
            meeting_id=self.meeting_id,
            session_id=session_id,
            endpoint=endpoint,
            request_params={"session_key": session_id},
            raw_response_bytes=raw,
            http_status=200,
            session_end_utc=self.session_end(session_id),
            first_observed_utc=first,
            ingested_utc=ingested,
            receipt_created_utc=created,
            capture_ref=f"memory:{endpoint}.response.json",
            implementation="synthetic-test-fixture",
            event_time_utc=event_time,
            publisher_time_utc=publisher_time,
        )
        self.assertEqual(result["status"], capture.VALIDATED)
        return result["source_capture_receipt_bytes"]

    def valid_manifest(self, *, grid_receipt=None, grid_raw=None,
                       sessions_raw=None):
        grid_receipt_bytes = grid_receipt or self.grid_receipt
        grid_bytes = grid_raw or self.grid_raw
        discovery_bytes = sessions_raw or self.sessions_raw
        receipt = json.loads(grid_receipt_bytes)
        grid_sha = hashlib.sha256(grid_bytes).hexdigest()
        sessions_sha = hashlib.sha256(discovery_bytes).hexdigest()
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
            "source_to_race_link_evidence_type": m.compatibility.PROVIDER_LINK,
            "session_discovery_raw_sha256": sessions_sha,
            "discovery_response_sha256": sessions_sha,
            "starting_grid_raw_sha256": grid_sha,
            "raw_response_sha256": grid_sha,
            "source_receipt_id": receipt["receipt_id"],
            "raw_source_id": receipt["payload"]["source_id"],
            "frozen_evidence_binding_status": "UNBOUND",
            "session_discovery_request_attempted": True,
            "starting_grid_request_attempted": True,
            "session_discovery_http_status_code": 200,
            "starting_grid_http_status_code": 200,
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
            "forecast_cutoff_utc": self.cutoff,
            "implementation_git_sha": "a" * 40,
        }
        args.update(changes)
        return m.assess_openf1_three_source_precutoff_candidate(**args)

    def result_for_sessions(self, rows):
        raw = self.json_bytes(rows)
        manifest = self.valid_manifest(sessions_raw=raw)
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

    def assess_grid_receipt(self, receipt_bytes, *, raw=None):
        grid_raw = self.grid_raw if raw is None else raw
        manifest = self.valid_manifest(grid_receipt=receipt_bytes, grid_raw=grid_raw)
        return self.assess(
            starting_grid_source_capture_receipt_bytes=receipt_bytes,
            raw_starting_grid_response_bytes=grid_raw,
            grid_shadow_manifest_bytes=self.json_bytes(manifest),
        )

    def assert_hold_minimal(self, result):
        self.assertEqual(result["status"], m.HOLD)
        self.assertEqual(set(result), {
            "schema_version", "status", "reason_codes", *m.FALSE_FLAGS
        })
        self.assertTrue(all(result[field] is False for field in m.FALSE_FLAGS))
        serialized = json.dumps(result)
        self.assertNotIn("source_capture:", serialized)
        self.assertNotIn("DRIVER 44", serialized)

    # 1
    def test_valid_synthetic_event_is_only_unauthenticated_candidate(self):
        result = self.assess()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["classification"], m.CLASSIFICATION)
        self.assertTrue(result["candidate_manifest_is_sandbox_only"])
        self.assertTrue(result["internal_temporal_checks_satisfied"])

    # 2
    def test_all_claim_ceiling_flags_are_explicitly_false(self):
        result = self.assess()
        self.assertTrue(all(result[field] is False for field in m.FALSE_FLAGS))
        self.assertFalse(result["candidate_is_approved_producer_authorization"])

    # 3
    def test_same_inputs_are_byte_deterministic(self):
        first = self.assess()
        second = self.assess()
        self.assertEqual(first, second)
        self.assertEqual(first["candidate_manifest_bytes"],
                         second["candidate_manifest_bytes"])

    # 4
    def test_cutoff_equal_to_qualifying_end_holds(self):
        self.assert_hold_minimal(self.assess(
            forecast_cutoff_utc="2026-01-03T13:00:00Z"
        ))

    # 5
    def test_cutoff_before_qualifying_end_holds(self):
        self.assert_hold_minimal(self.assess(
            forecast_cutoff_utc="2026-01-03T12:59:59Z"
        ))

    # 6
    def test_cutoff_at_or_after_race_start_holds(self):
        for value in ("2026-01-04T11:00:00Z", "2026-01-04T11:00:01Z"):
            with self.subTest(value=value):
                self.assert_hold_minimal(self.assess(forecast_cutoff_utc=value))

    # 7
    def test_cutoff_missing_or_non_utc_timezone_holds(self):
        for value in (None, "2026-01-03T14:00:00", "2026-01-03T15:00:00+01:00"):
            with self.subTest(value=value):
                self.assert_hold_minimal(self.assess(forecast_cutoff_utc=value))

    # 8
    def test_duplicate_same_meeting_practice_2_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows.append(self.session(
            "7100", "Practice 2", "Practice",
            "2026-01-01T12:00:00Z", "2026-01-01T13:00:00Z",
        ))
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 9
    def test_ambiguous_same_meeting_qualifying_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows.append(self.session(
            "7104", "Qualifying", "Qualifying",
            "2026-01-03T14:30:00Z", "2026-01-03T15:30:00Z",
        ))
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 10
    def test_ambiguous_same_meeting_race_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows.append(self.session(
            "7105", "Race", "Race",
            "2026-01-05T11:00:00Z", "2026-01-05T13:00:00Z",
        ))
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 11
    def test_mixed_case_sprint_classification_holds(self):
        for name, kind in (("sPrInT", "Race"), ("Practice", "SpRiNt")):
            rows = copy.deepcopy(self.sessions)
            rows.append(self.session(
                "7104", name, kind,
                "2026-01-03T08:00:00Z", "2026-01-03T09:00:00Z",
            ))
            self.assert_hold_minimal(self.result_for_sessions(rows))

    # 12
    def test_cross_meeting_session_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows[1]["meeting_key"] = 9999
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 13
    def test_cross_year_session_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows[1]["year"] = 2025
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 14
    def test_cross_circuit_session_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows[2]["circuit_short_name"] = "Other Ring"
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 15
    def test_explicit_session_ids_must_be_typed_canonical_and_distinct(self):
        for field, value in (
            ("practice_session_id", 7101),
            ("qualifying_source_session_id", "07102"),
            ("target_race_session_id", "7102"),
        ):
            with self.subTest(field=field, value=value):
                self.assert_hold_minimal(self.assess(**{field: value}))

    # 16
    def test_weather_first_observed_after_cutoff_holds(self):
        changed = self.changed_receipt(
            self.weather_receipt,
            lambda row: (
                row["payload"].__setitem__("first_observed_utc", "2026-01-03T14:01:00Z"),
                row["payload"].__setitem__("ingested_utc", "2026-01-03T14:02:00Z"),
                row.__setitem__("receipt_created_utc", "2026-01-03T14:03:00Z"),
            ),
        )
        self.assert_hold_minimal(self.assess(
            weather_source_capture_receipt_bytes=changed
        ))

    # 17
    def test_drivers_ingested_after_cutoff_holds(self):
        changed = self.changed_receipt(
            self.drivers_receipt,
            lambda row: (
                row["payload"].__setitem__("ingested_utc", "2026-01-03T14:01:00Z"),
                row.__setitem__("receipt_created_utc", "2026-01-03T14:02:00Z"),
            ),
        )
        self.assert_hold_minimal(self.assess(
            drivers_source_capture_receipt_bytes=changed
        ))

    # 18
    def test_grid_receipt_created_after_cutoff_holds(self):
        changed = self.changed_receipt(
            self.grid_receipt,
            lambda row: row.__setitem__(
                "receipt_created_utc", "2026-01-03T14:01:00Z"
            ),
        )
        self.assert_hold_minimal(self.assess_grid_receipt(changed))

    # 19
    def test_source_first_observed_after_race_holds(self):
        changed = self.changed_receipt(
            self.weather_receipt,
            lambda row: (
                row["payload"].__setitem__("first_observed_utc", "2026-01-04T13:01:00Z"),
                row["payload"].__setitem__("ingested_utc", "2026-01-04T13:02:00Z"),
                row.__setitem__("receipt_created_utc", "2026-01-04T13:03:00Z"),
            ),
        )
        self.assert_hold_minimal(self.assess(
            weather_source_capture_receipt_bytes=changed
        ))

    # 20
    def test_early_publisher_and_event_times_cannot_rescue_late_observation(self):
        changed = self.changed_receipt(
            self.grid_receipt,
            lambda row: (
                row["payload"].__setitem__("event_time_utc", "2026-01-03T12:00:00Z"),
                row["payload"].__setitem__("publisher_time_utc", "2026-01-03T12:30:00Z"),
                row["payload"].__setitem__("first_observed_utc", "2026-01-03T14:01:00Z"),
                row["payload"].__setitem__("ingested_utc", "2026-01-03T14:02:00Z"),
                row.__setitem__("receipt_created_utc", "2026-01-03T14:03:00Z"),
            ),
        )
        self.assert_hold_minimal(self.assess_grid_receipt(changed))

    # 21
    def test_noncanonical_receipt_bytes_hold(self):
        noncanonical = json.dumps(
            json.loads(self.weather_receipt), indent=2
        ).encode("utf-8")
        self.assert_hold_minimal(self.assess(
            weather_source_capture_receipt_bytes=noncanonical
        ))

    # 22
    def test_wrong_canonical_source_uri_holds(self):
        changed = self.changed_receipt(
            self.drivers_receipt,
            lambda row: row["payload"].__setitem__(
                "source_uri", "https://api.openf1.org/v1/drivers?session_key=9999"
            ),
        )
        self.assert_hold_minimal(self.assess(
            drivers_source_capture_receipt_bytes=changed
        ))

    # 23
    def test_raw_content_hash_mismatch_holds(self):
        self.assert_hold_minimal(self.assess(
            raw_weather_response_bytes=self.weather_raw + b" "
        ))

    # 24
    def test_manifest_requires_both_requests_attempted(self):
        for field in (
            "session_discovery_request_attempted",
            "starting_grid_request_attempted",
        ):
            manifest = self.valid_manifest()
            manifest[field] = False
            self.assert_hold_minimal(self.assess(
                grid_shadow_manifest_bytes=self.json_bytes(manifest)
            ))

    # 25
    def test_manifest_requires_both_exact_integer_http_200_statuses(self):
        for field in (
            "session_discovery_http_status_code",
            "starting_grid_http_status_code",
        ):
            for value in (403, True, "200"):
                manifest = self.valid_manifest()
                manifest[field] = value
                self.assert_hold_minimal(self.assess(
                    grid_shadow_manifest_bytes=self.json_bytes(manifest)
                ))

    # 26
    def test_mismatched_driver_and_grid_rosters_hold_without_filler(self):
        raw = self.json_bytes(self.drivers_rows[:-1])
        receipt = self.receipt(
            "drivers", self.practice_id, raw,
            "2026-01-02T13:33:00Z", "2026-01-02T13:34:00Z",
            "2026-01-02T13:35:00Z",
        )
        self.assert_hold_minimal(self.assess(
            raw_drivers_response_bytes=raw,
            drivers_source_capture_receipt_bytes=receipt,
        ))

    # 27
    def test_duplicate_grid_slot_holds(self):
        rows = [self.grid(1, 44), self.grid(1, 16), self.grid(3, 81)]
        raw = self.json_bytes(rows)
        receipt = self.receipt(
            "starting_grid", self.qualifying_id, raw,
            "2026-01-03T13:30:00Z", "2026-01-03T13:31:00Z",
            "2026-01-03T13:32:00Z",
        )
        self.assert_hold_minimal(self.assess_grid_receipt(receipt, raw=raw))

    # 28
    def test_holey_grid_slots_hold(self):
        rows = [self.grid(1, 44), self.grid(3, 16), self.grid(4, 81)]
        raw = self.json_bytes(rows)
        receipt = self.receipt(
            "starting_grid", self.qualifying_id, raw,
            "2026-01-03T13:30:00Z", "2026-01-03T13:31:00Z",
            "2026-01-03T13:32:00Z",
        )
        self.assert_hold_minimal(self.assess_grid_receipt(receipt, raw=raw))

    # 29
    def test_negative_grid_slot_holds(self):
        rows = [self.grid(-1, 44), self.grid(2, 16), self.grid(3, 81)]
        raw = self.json_bytes(rows)
        receipt = self.receipt(
            "starting_grid", self.qualifying_id, raw,
            "2026-01-03T13:30:00Z", "2026-01-03T13:31:00Z",
            "2026-01-03T13:32:00Z",
        )
        self.assert_hold_minimal(self.assess_grid_receipt(receipt, raw=raw))

    # 30
    def test_source_scope_mismatch_holds(self):
        changed = self.changed_receipt(
            self.weather_receipt,
            lambda row: row["scope"].__setitem__("session_id", "9999"),
        )
        self.assert_hold_minimal(self.assess(
            weather_source_capture_receipt_bytes=changed
        ))

    # 31
    def test_original_grid_stays_five_column_and_projection_is_two_column(self):
        result = self.assess()
        original = result["original_source_lineage"]["starting_grid"]
        adapter = m.grid_adapter.adapt_openf1_starting_grid_to_producer_input(
            source_capture_receipt_bytes=self.grid_receipt,
            raw_starting_grid_response_bytes=self.grid_raw,
            event_id=self.event_id,
            meeting_id=self.meeting_id,
            session_id=self.qualifying_id,
            source_session_kind="Qualifying",
            target_race_session_id=self.race_id,
        )
        self.assertEqual(original["original_five_column_csv_sha256"],
                         adapter["producer_input_sha256"])
        projected = result["runtime_input_csv_bytes"]["starting_grid"]
        self.assertEqual(projected, b"driver_number,position\n44,1\n16,2\n81,3\n")
        self.assertNotIn(b"session", projected)

    # 32
    def test_candidate_manifest_exactly_binds_three_canonical_runtime_files(self):
        result = self.assess()
        manifest = result["candidate_manifest"]
        self.assertTrue(manifest["sandbox_only"])
        self.assertFalse(manifest["approved_producer_authorization"])
        self.assertEqual(manifest["session_id"], self.practice_id)
        self.assertEqual(manifest["qualifying_source_session_id"],
                         self.qualifying_id)
        self.assertEqual(manifest["target_race_session_id"], self.race_id)
        self.assertEqual(
            [row["relative_path"] for row in manifest["sources"]],
            ["drivers.csv", "starting_grid.csv", "weather.csv"],
        )
        for row in manifest["sources"]:
            name = row["source_name"]
            self.assertEqual(row["source_sha256"], hashlib.sha256(
                result["runtime_input_csv_bytes"][name]
            ).hexdigest())
        self.assertEqual(result["candidate_manifest_sha256"], hashlib.sha256(
            result["candidate_manifest_bytes"]
        ).hexdigest())

    # 33
    def test_runtime_identity_collision_holds(self):
        weather = m.weather_adapter.adapt_openf1_weather_to_producer_input(
            source_capture_receipt_bytes=self.weather_receipt,
            raw_weather_response_bytes=self.weather_raw,
            event_id=self.event_id,
            meeting_id=self.meeting_id,
            session_id=self.practice_id,
        )
        collision = "derived:openf1-weather-csv:" + weather["producer_input_sha256"]
        original = m.drivers_adapter.adapt_openf1_drivers_to_producer_input

        def collide(**kwargs):
            result = original(**kwargs)
            result["derived_runtime_identity"] = collision
            return result

        with mock.patch.object(
            m.drivers_adapter,
            "adapt_openf1_drivers_to_producer_input",
            side_effect=collide,
        ):
            self.assert_hold_minimal(self.assess())

    # 34
    def test_no_filesystem_network_clock_workflow_producer_or_model_surface(self):
        tree = ast.parse(SCRIPT.read_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imported.isdisjoint({
            "os", "pathlib", "requests", "urllib", "socket", "subprocess",
            "tempfile", "time",
        }))
        text = SCRIPT.read_text()
        for forbidden in (
            "assess_openf1_three_source_event_compatibility(",
            "project_compatible_openf1_three_sources_for_p2_mechanics(",
            "produce_actual_forecast_rows_v1", "evaluate_as_of(",
            "urlopen(", "requests.", "subprocess.", "Path(", "open(",
            "datetime.now", "datetime.utcnow",
        ):
            self.assertNotIn(forbidden, text)

    # 35
    def test_k4r21_post_event_rule_is_unchanged_and_not_prospective(self):
        post_weather = self.receipt(
            "weather", self.practice_id, self.weather_raw,
            "2026-01-05T10:00:00Z", "2026-01-05T10:01:00Z",
            "2026-01-05T10:02:00Z",
        )
        post_drivers = self.receipt(
            "drivers", self.practice_id, self.drivers_raw,
            "2026-01-05T10:03:00Z", "2026-01-05T10:04:00Z",
            "2026-01-05T10:05:00Z",
        )
        post_grid = self.receipt(
            "starting_grid", self.qualifying_id, self.grid_raw,
            "2026-01-05T10:06:00Z", "2026-01-05T10:07:00Z",
            "2026-01-05T10:08:00Z",
        )
        manifest = self.json_bytes(self.valid_manifest(grid_receipt=post_grid))
        k4r21 = compatibility.assess_openf1_three_source_event_compatibility(
            weather_source_capture_receipt_bytes=post_weather,
            raw_weather_response_bytes=self.weather_raw,
            drivers_source_capture_receipt_bytes=post_drivers,
            raw_drivers_response_bytes=self.drivers_raw,
            starting_grid_source_capture_receipt_bytes=post_grid,
            raw_starting_grid_response_bytes=self.grid_raw,
            sessions_response_bytes=self.sessions_raw,
            grid_shadow_manifest_bytes=manifest,
            event_id=self.event_id,
            meeting_id=self.meeting_id,
            practice_session_id=self.practice_id,
            qualifying_source_session_id=self.qualifying_id,
            target_race_session_id=self.race_id,
        )
        self.assertEqual(k4r21["status"], compatibility.VALIDATED)
        prospective = self.assess(
            weather_source_capture_receipt_bytes=post_weather,
            drivers_source_capture_receipt_bytes=post_drivers,
            starting_grid_source_capture_receipt_bytes=post_grid,
            grid_shadow_manifest_bytes=manifest,
        )
        self.assert_hold_minimal(prospective)

    # 36
    def test_optional_implementation_sha_is_information_only(self):
        without = self.assess(implementation_git_sha=None)
        self.assertEqual(without["status"], m.VALIDATED)
        self.assertNotIn("implementation_git_sha", without)
        self.assert_hold_minimal(self.assess(implementation_git_sha="bad"))

    # 37: nine independent source/timestamp cutoff cases
    def test_every_source_timestamp_after_cutoff_independently_holds(self):
        sources = (
            ("weather", self.weather_receipt),
            ("drivers", self.drivers_receipt),
            ("starting_grid", self.grid_receipt),
        )
        for source_name, original_receipt in sources:
            for timestamp_field in (
                "first_observed_utc", "ingested_utc", "receipt_created_utc"
            ):
                with self.subTest(source=source_name, field=timestamp_field):
                    def change(row):
                        row["payload"]["first_observed_utc"] = (
                            "2026-01-03T13:58:00Z"
                        )
                        row["payload"]["ingested_utc"] = (
                            "2026-01-03T13:59:00Z"
                        )
                        row["receipt_created_utc"] = "2026-01-03T14:00:00Z"
                        if timestamp_field == "first_observed_utc":
                            row["payload"]["first_observed_utc"] = (
                                "2026-01-03T14:01:00Z"
                            )
                            row["payload"]["ingested_utc"] = (
                                "2026-01-03T14:02:00Z"
                            )
                            row["receipt_created_utc"] = (
                                "2026-01-03T14:03:00Z"
                            )
                        elif timestamp_field == "ingested_utc":
                            row["payload"]["ingested_utc"] = (
                                "2026-01-03T14:01:00Z"
                            )
                            row["receipt_created_utc"] = (
                                "2026-01-03T14:02:00Z"
                            )
                        else:
                            row["receipt_created_utc"] = (
                                "2026-01-03T14:01:00Z"
                            )

                    changed = self.changed_receipt(original_receipt, change)
                    if source_name == "starting_grid":
                        result = self.assess_grid_receipt(changed)
                    else:
                        result = self.assess(**{
                            source_name + "_source_capture_receipt_bytes": changed
                        })
                    self.assert_hold_minimal(result)

    # 38
    def test_missing_or_non_utc_receipt_timestamp_holds(self):
        for value in (None, "2026-01-02T13:30:00", "2026-01-02T14:30:00+01:00"):
            with self.subTest(value=value):
                changed = self.changed_receipt(
                    self.weather_receipt,
                    lambda row: row["payload"].__setitem__(
                        "first_observed_utc", value
                    ),
                )
                self.assert_hold_minimal(self.assess(
                    weather_source_capture_receipt_bytes=changed
                ))

    # 39
    def test_equal_size_twenty_two_driver_roster_mismatch_holds(self):
        driver_rows = [self.driver(number) for number in range(1, 23)]
        grid_rows = [
            self.grid(position, number)
            for position, number in enumerate(range(2, 24), start=1)
        ]
        drivers_raw = self.json_bytes(driver_rows)
        grid_raw = self.json_bytes(grid_rows)
        drivers_receipt = self.receipt(
            "drivers", self.practice_id, drivers_raw,
            "2026-01-02T13:33:00Z", "2026-01-02T13:34:00Z",
            "2026-01-02T13:35:00Z",
        )
        grid_receipt = self.receipt(
            "starting_grid", self.qualifying_id, grid_raw,
            "2026-01-03T13:30:00Z", "2026-01-03T13:31:00Z",
            "2026-01-03T13:32:00Z",
        )
        manifest = self.valid_manifest(
            grid_receipt=grid_receipt, grid_raw=grid_raw
        )
        self.assert_hold_minimal(self.assess(
            raw_drivers_response_bytes=drivers_raw,
            drivers_source_capture_receipt_bytes=drivers_receipt,
            raw_starting_grid_response_bytes=grid_raw,
            starting_grid_source_capture_receipt_bytes=grid_receipt,
            grid_shadow_manifest_bytes=self.json_bytes(manifest),
        ))


if __name__ == "__main__":
    unittest.main()
