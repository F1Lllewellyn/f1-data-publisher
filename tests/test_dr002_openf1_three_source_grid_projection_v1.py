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
SCRIPT = BUNDLE_DIR / "dr002_openf1_three_source_grid_projection_v1.py"
sys.path.insert(0, str(BUNDLE_DIR))
spec = importlib.util.spec_from_file_location("three_source_grid_projection", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import dr002_openf1_historical_rest_capture_v1 as capture
import verify_forecast_integrity_receipts_v1 as receipts


class ThreeSourceGridProjectionTests(unittest.TestCase):
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
        self.grid_rows = [self.grid(2, 16), self.grid(1, 44), self.grid(3, 81)]
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

    def driver(self, number, **changes):
        row = {
            "meeting_key": 1295,
            "session_key": 11371,
            "driver_number": number,
            "broadcast_name": f"DRIVER {number}",
            "full_name": f"Driver {number}",
            "team_name": f"Team {number}",
        }
        row.update(changes)
        return row

    def grid(self, position, number, **changes):
        row = {
            "position": position,
            "driver_number": number,
            "lap_duration": None,
            "meeting_key": 1295,
            "session_key": 11373,
        }
        row.update(changes)
        return row

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
            "source_to_race_link_evidence_type": m.compatibility.PROVIDER_LINK,
            "session_discovery_raw_sha256": sessions_sha,
            "discovery_response_sha256": sessions_sha,
            "starting_grid_raw_sha256": grid_sha,
            "raw_response_sha256": grid_sha,
            "source_receipt_id": grid_receipt["receipt_id"],
            "raw_source_id": grid_receipt["payload"]["source_id"],
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

    def project(self, **changes):
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
        return m.project_compatible_openf1_three_sources_for_p2_mechanics(**args)

    def result_for_sessions(self, rows):
        raw = self.json_bytes(rows)
        manifest = copy.deepcopy(self.manifest)
        digest = hashlib.sha256(raw).hexdigest()
        manifest["session_discovery_raw_sha256"] = digest
        manifest["discovery_response_sha256"] = digest
        return self.project(
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
            "schema_version", "status", "reason_codes", *m.FALSE_FLAGS
        })
        self.assertTrue(all(result[field] is False for field in m.FALSE_FLAGS))
        serialized = json.dumps(result)
        for forbidden in (
            "runtime_input_csv_bytes", "candidate_producer_manifest_bytes",
            json.loads(self.weather_receipt)["receipt_id"], "DRIVER 44",
        ):
            self.assertNotIn(forbidden, serialized)

    # 1
    def test_valid_projection_preserves_three_session_relationship(self):
        result = self.project()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["classification"], m.CLASSIFICATION)
        self.assertEqual(result["practice_session"]["session_id"], "11371")
        self.assertEqual(result["qualifying_source_session"]["session_id"],
                         "11373")
        self.assertEqual(result["target_race_session"]["session_id"], "11377")

    # 2
    def test_weather_and_drivers_csv_bytes_are_exact_adapter_outputs(self):
        result = self.project()
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
        self.assertEqual(result["runtime_input_csv_bytes"]["weather"],
                         weather["producer_input_csv_bytes"])
        self.assertEqual(result["runtime_input_csv_bytes"]["drivers"],
                         drivers["producer_input_csv_bytes"])

    # 3
    def test_projected_grid_is_exact_two_column_position_ordered_lf(self):
        projected = self.project()["runtime_input_csv_bytes"]["starting_grid"]
        self.assertEqual(
            projected,
            b"driver_number,position\n44,1\n16,2\n81,3\n",
        )
        self.assertNotIn(b"\r", projected)

    # 4
    def test_only_projected_grid_drops_scope_columns(self):
        inputs = self.project()["runtime_input_csv_bytes"]
        self.assertIn(b"session_key", inputs["weather"].splitlines()[0])
        self.assertIn(b"session_key", inputs["drivers"].splitlines()[0])
        self.assertEqual(inputs["starting_grid"].splitlines()[0],
                         b"driver_number,position")
        for field in (b"event_id", b"meeting_id", b"session_id", b"session_key"):
            self.assertNotIn(field, inputs["starting_grid"])

    # 5
    def test_original_qualifying_grid_hash_and_scope_remain_in_lineage(self):
        result = self.project()
        grid = m.grid_adapter.adapt_openf1_starting_grid_to_producer_input(
            source_capture_receipt_bytes=self.grid_receipt,
            raw_starting_grid_response_bytes=self.grid_raw,
            event_id=self.event_id, meeting_id=self.meeting_id,
            session_id=self.qualifying_id, source_session_kind="Qualifying",
            target_race_session_id=self.race_id,
        )
        lineage = result["original_source_lineage"]["starting_grid"]
        self.assertEqual(lineage["original_session_id"], self.qualifying_id)
        self.assertEqual(result["original_qualifying_grid_csv_sha256"],
                         grid["producer_input_sha256"])
        self.assertNotEqual(result["projected_grid_csv_sha256"],
                            grid["producer_input_sha256"])

    # 6
    def test_manifest_has_exact_schema_scope_sources_and_filenames(self):
        manifest = self.project()["candidate_producer_manifest"]
        self.assertEqual(set(manifest), {
            "schema_version", "event_id", "meeting_id", "session_id", "sources"
        })
        self.assertEqual(manifest["schema_version"], m.FROZEN_SCHEMA)
        self.assertEqual(manifest["session_id"], self.practice_id)
        self.assertEqual([row["source_name"] for row in manifest["sources"]],
                         list(m.SOURCE_NAMES))
        self.assertEqual([row["relative_path"] for row in manifest["sources"]],
                         [name + ".csv" for name in m.SOURCE_NAMES])

    # 7
    def test_manifest_hashes_match_all_three_runtime_bytes(self):
        result = self.project()
        inputs = result["runtime_input_csv_bytes"]
        for source in result["candidate_producer_manifest"]["sources"]:
            self.assertEqual(source["source_sha256"], hashlib.sha256(
                inputs[source["source_name"]]
            ).hexdigest())
        self.assertEqual(result["candidate_producer_manifest_sha256"],
                         hashlib.sha256(
                             result["candidate_producer_manifest_bytes"]
                         ).hexdigest())

    # 8
    def test_manifest_contains_only_derived_runtime_ids_not_source_identities(self):
        result = self.project()
        serialized = result["candidate_producer_manifest_bytes"].decode()
        identities = []
        for metadata in result["original_source_lineage"].values():
            identities.extend((metadata["source_receipt_id"],
                               metadata["raw_source_id"]))
        self.assertTrue(all(source["source_id"].startswith("derived:")
                            for source in result["candidate_producer_manifest"][
                                "sources"
                            ]))
        self.assertTrue(all(identity not in serialized for identity in identities))

    # 9
    def test_projection_identity_is_distinct_and_digest_bound(self):
        result = self.project()
        expected = (
            "derived:postevent-unscoped-qualifying-grid-projection:"
            + result["projected_grid_csv_sha256"]
        )
        self.assertEqual(result["projected_grid_runtime_identity"], expected)
        self.assertNotEqual(
            expected,
            result["original_source_lineage"]["starting_grid"][
                "original_derived_runtime_identity"
            ],
        )

    # 10
    def test_repeated_synthetic_projection_is_byte_deterministic(self):
        first = self.project()
        second = self.project()
        self.assertEqual(first["runtime_input_csv_bytes"],
                         second["runtime_input_csv_bytes"])
        self.assertEqual(first["candidate_producer_manifest_bytes"],
                         second["candidate_producer_manifest_bytes"])
        self.assertEqual(first["candidate_producer_manifest_sha256"],
                         second["candidate_producer_manifest_sha256"])

    # 11
    def test_all_scientific_operational_and_promotion_claims_are_false(self):
        result = self.project()
        self.assertTrue(all(result[field] is False for field in m.FALSE_FLAGS))
        self.assertTrue(result["candidate_manifest_is_sandbox_only"])
        self.assertTrue(result["producer_scope_is_p2_mechanics_only"])

    # 12
    def test_k4r21_runs_first_and_hold_prevents_adapter_materialization(self):
        hold = m.compatibility._hold("deliberate_test_hold")
        with mock.patch.object(
            m.compatibility, "assess_openf1_three_source_event_compatibility",
            return_value=hold,
        ), mock.patch.object(
            m.weather_adapter, "adapt_openf1_weather_to_producer_input"
        ) as weather_call:
            result = self.project()
        self.assert_hold_minimal(result)
        weather_call.assert_not_called()

    # 13
    def test_each_adapter_is_rederived_after_k4r21(self):
        with mock.patch.object(
            m.weather_adapter, "adapt_openf1_weather_to_producer_input",
            wraps=m.weather_adapter.adapt_openf1_weather_to_producer_input,
        ) as weather_call, mock.patch.object(
            m.drivers_adapter, "adapt_openf1_drivers_to_producer_input",
            wraps=m.drivers_adapter.adapt_openf1_drivers_to_producer_input,
        ) as drivers_call, mock.patch.object(
            m.grid_adapter, "adapt_openf1_starting_grid_to_producer_input",
            wraps=m.grid_adapter.adapt_openf1_starting_grid_to_producer_input,
        ) as grid_call:
            result = self.project()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(weather_call.call_count, 2)
        self.assertEqual(drivers_call.call_count, 2)
        self.assertEqual(grid_call.call_count, 2)

    # 14
    def test_arbitrary_adapter_metadata_cannot_replace_recomputed_output(self):
        valid_compatibility = (
            m.compatibility.assess_openf1_three_source_event_compatibility(
                weather_source_capture_receipt_bytes=self.weather_receipt,
                raw_weather_response_bytes=self.weather_raw,
                drivers_source_capture_receipt_bytes=self.drivers_receipt,
                raw_drivers_response_bytes=self.drivers_raw,
                starting_grid_source_capture_receipt_bytes=self.grid_receipt,
                raw_starting_grid_response_bytes=self.grid_raw,
                sessions_response_bytes=self.sessions_raw,
                grid_shadow_manifest_bytes=self.manifest_raw,
                event_id=self.event_id, meeting_id=self.meeting_id,
                practice_session_id=self.practice_id,
                qualifying_source_session_id=self.qualifying_id,
                target_race_session_id=self.race_id,
                implementation_git_sha="a" * 40,
            )
        )
        forged = m.weather_adapter.adapt_openf1_weather_to_producer_input(
            source_capture_receipt_bytes=self.weather_receipt,
            raw_weather_response_bytes=self.weather_raw,
            event_id=self.event_id, meeting_id=self.meeting_id,
            session_id=self.practice_id,
        )
        forged = dict(forged, producer_input_sha256="0" * 64)
        with mock.patch.object(
            m.compatibility, "assess_openf1_three_source_event_compatibility",
            return_value=valid_compatibility,
        ), mock.patch.object(
            m.weather_adapter, "adapt_openf1_weather_to_producer_input",
            return_value=forged,
        ):
            self.assert_hold_minimal(self.project())

    # 15
    def test_duplicate_same_meeting_practice_2_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows.append(self.session("11370", "Practice 2", "Practice",
                                 "2026-09-23T12:00:00Z",
                                 "2026-09-23T13:00:00Z"))
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 16
    def test_case_insensitive_sprint_classification_holds(self):
        rows = copy.deepcopy(self.sessions)
        rows.append(self.session("11372", "Practice", "sPrInT",
                                 "2026-09-25T08:00:00Z",
                                 "2026-09-25T09:00:00Z"))
        self.assert_hold_minimal(self.result_for_sessions(rows))

    # 17
    def test_raw_and_receipt_hash_mismatch_holds(self):
        changed_raw = self.weather_raw + b" "
        self.assert_hold_minimal(self.project(
            raw_weather_response_bytes=changed_raw
        ))

    # 18
    def test_wrong_receipt_identity_holds(self):
        receipt = self.changed_receipt(
            self.drivers_receipt,
            lambda row: row.__setitem__("receipt_id", "source_capture:" + "0" * 64),
            refresh_id=False,
        )
        self.assert_hold_minimal(self.project(
            drivers_source_capture_receipt_bytes=receipt
        ))

    # 19
    def test_nonunique_qualifying_or_race_holds(self):
        for session_id, name, kind, start, end in (
            ("11374", "Qualifying", "Qualifying",
             "2026-09-25T14:00:00Z", "2026-09-25T15:00:00Z"),
            ("11378", "Race", "Race",
             "2026-09-27T11:00:00Z", "2026-09-27T13:00:00Z"),
        ):
            with self.subTest(kind=kind):
                rows = copy.deepcopy(self.sessions)
                rows.append(self.session(session_id, name, kind, start, end))
                self.assert_hold_minimal(self.result_for_sessions(rows))

    # 20
    def test_first_observed_not_after_race_holds(self):
        receipt = self.receipt(
            "weather", self.practice_id, self.weather_raw,
            "2026-09-26T12:00:00Z",
        )
        self.assert_hold_minimal(self.project(
            weather_source_capture_receipt_bytes=receipt
        ))

    # 21
    def test_mismatched_driver_roster_holds_without_filler(self):
        rows = self.drivers_rows[:-1]
        raw = self.json_bytes(rows)
        receipt = self.receipt(
            "drivers", self.practice_id, raw, "2026-10-08T13:00:00Z"
        )
        self.assert_hold_minimal(self.project(
            raw_drivers_response_bytes=raw,
            drivers_source_capture_receipt_bytes=receipt,
        ))

    # 22
    def test_missing_or_holey_grid_holds_without_partial_projection(self):
        for rows in ([], [self.grid(1, 44), self.grid(3, 16), self.grid(4, 81)]):
            with self.subTest(row_count=len(rows)):
                raw = self.json_bytes(rows)
                receipt = self.receipt(
                    "starting_grid", self.qualifying_id, raw,
                    "2026-10-14T10:14:18Z",
                )
                self.assert_hold_minimal(self.project(
                    raw_starting_grid_response_bytes=raw,
                    starting_grid_source_capture_receipt_bytes=receipt,
                ))

    # 23
    def test_each_http_attempt_flag_must_be_literal_true(self):
        for field in ("session_discovery_request_attempted",
                      "starting_grid_request_attempted"):
            manifest = copy.deepcopy(self.manifest)
            manifest[field] = False
            self.assert_hold_minimal(self.project(
                grid_shadow_manifest_bytes=self.json_bytes(manifest)
            ))

    # 24
    def test_each_http_status_must_be_exact_integer_200(self):
        for field in ("session_discovery_http_status_code",
                      "starting_grid_http_status_code"):
            manifest = copy.deepcopy(self.manifest)
            manifest[field] = "200"
            self.assert_hold_minimal(self.project(
                grid_shadow_manifest_bytes=self.json_bytes(manifest)
            ))

    # 25
    def test_wrong_source_session_holds_without_relabelling(self):
        rows = copy.deepcopy(self.grid_rows)
        rows[0]["session_key"] = 11371
        raw = self.json_bytes(rows)
        receipt = self.changed_receipt(
            self.grid_receipt,
            lambda row: row["payload"].__setitem__(
                "source_sha256", hashlib.sha256(raw).hexdigest()
            ),
        )
        self.assert_hold_minimal(self.project(
            raw_starting_grid_response_bytes=raw,
            starting_grid_source_capture_receipt_bytes=receipt,
        ))

    # 26
    def test_invalid_json_holds_minimally(self):
        self.assert_hold_minimal(self.project(sessions_response_bytes=b"["))

    # 27
    def test_wrong_shadow_manifest_hashes_hold(self):
        for field in ("session_discovery_raw_sha256",
                      "starting_grid_raw_sha256"):
            manifest = copy.deepcopy(self.manifest)
            manifest[field] = "0" * 64
            self.assert_hold_minimal(self.project(
                grid_shadow_manifest_bytes=self.json_bytes(manifest)
            ))

    # 28
    def test_no_extra_rows_or_derived_identity_collisions(self):
        result = self.project()
        grid_rows = list(csv.DictReader(io.StringIO(
            result["runtime_input_csv_bytes"]["starting_grid"].decode()
        )))
        self.assertEqual(len(grid_rows), len(self.grid_rows))
        ids = [row["source_id"]
               for row in result["candidate_producer_manifest"]["sources"]]
        self.assertEqual(len(ids), len(set(ids)))

    # 29
    def test_implementation_sha_is_optional_non_scientific_metadata(self):
        result = self.project(implementation_git_sha=None)
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertNotIn("implementation_git_sha", result)
        self.assert_hold_minimal(self.project(implementation_git_sha="bad"))

    # 30
    def test_module_has_no_io_network_clock_subprocess_or_producer_surface(self):
        tree = ast.parse(SCRIPT.read_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imported.isdisjoint({
            "os", "pathlib", "requests", "urllib", "socket", "subprocess",
            "tempfile", "time", "datetime",
        }))
        text = SCRIPT.read_text()
        for forbidden in (
            "produce_actual_forecast_rows", "subprocess.", "requests.",
            "urlopen(", "Path(", "open(", "datetime.now", "datetime.utcnow",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
