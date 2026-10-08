import ast
import copy
import csv
import hashlib
import importlib.util
import inspect
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "scripts/forecast_bundles"
SCRIPT = (
    BUNDLE_DIR
    / "dr002_openf1_weather_drivers_frozen_producer_composition_v1.py"
)
sys.path.insert(0, str(BUNDLE_DIR))
spec = importlib.util.spec_from_file_location("weather_drivers_composition", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import dr002_openf1_historical_rest_capture_v1 as capture


def git_blob_sha(data):
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def csv_rows(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))


class OpenF1WeatherDriversFrozenProducerCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = {
            "event_id": "2026_1295_azerbaijan_baku_baku",
            "meeting_id": "1295",
            "session_id": "11371",
        }
        cls.weather_rows = [
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
        cls.driver_rows = [
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
                "first_name": "Max",
                "last_name": "Verstappen",
                "name_acronym": "VER",
                "team_colour": "3671C6",
                "headshot_url": None,
                "country_code": "NED",
            },
            {
                "meeting_key": 1295,
                "session_key": 11371,
                "driver_number": 16,
                "broadcast_name": "C LECLERC",
                "full_name": "Charles LECLERC",
                "team_name": "Scuderia Ferrari HP",
                "first_name": "Charles",
                "last_name": "Leclerc",
                "name_acronym": "LEC",
                "team_colour": "E80020",
                "headshot_url": None,
                "country_code": "MON",
            },
        ]
        cls.weather_raw = cls.json_bytes(cls.weather_rows)
        cls.drivers_raw = cls.json_bytes(cls.driver_rows)
        cls.weather_receipt = cls.receipt_for(
            "weather", cls.weather_raw, "_runtime/k4r9/weather.response.json"
        )
        cls.drivers_receipt = cls.receipt_for(
            "drivers", cls.drivers_raw, "_runtime/k4r9/drivers.response.json"
        )
        cls.implementation_sha = "a" * 40
        cls.weather_adapter_result = (
            m.weather_adapter.adapt_openf1_weather_to_producer_input(
                source_capture_receipt_bytes=cls.weather_receipt,
                raw_weather_response_bytes=cls.weather_raw,
                **cls.scope,
            )
        )
        cls.drivers_adapter_result = (
            m.drivers_adapter.adapt_openf1_drivers_to_producer_input(
                source_capture_receipt_bytes=cls.drivers_receipt,
                raw_drivers_response_bytes=cls.drivers_raw,
                **cls.scope,
            )
        )
        cls.result = cls.compose()
        if cls.result["status"] != m.VALIDATED:
            raise AssertionError(cls.result)

    @staticmethod
    def json_bytes(value):
        return json.dumps(
            value, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")

    @classmethod
    def receipt_for(cls, endpoint, raw, capture_ref):
        assessed = capture.assess_openf1_historical_rest_capture(
            **cls.scope,
            endpoint=endpoint,
            request_params={"session_key": cls.scope["session_id"]},
            raw_response_bytes=raw,
            http_status=200,
            session_end_utc="2026-09-24T13:00:00Z",
            first_observed_utc="2026-10-08T12:12:09.784033Z",
            ingested_utc="2026-10-08T12:12:09.784372Z",
            receipt_created_utc="2026-10-08T12:12:09.784388Z",
            capture_ref=capture_ref,
            implementation="dr002_openf1_historical_rest_capture_v1",
        )
        if assessed["status"] != capture.VALIDATED:
            raise AssertionError(assessed)
        return assessed["source_capture_receipt_bytes"]

    @classmethod
    def compose(cls, **changes):
        values = {
            "weather_source_capture_receipt_bytes": cls.weather_receipt,
            "raw_weather_response_bytes": cls.weather_raw,
            "drivers_source_capture_receipt_bytes": cls.drivers_receipt,
            "raw_drivers_response_bytes": cls.drivers_raw,
            **cls.scope,
            "implementation_git_sha": cls.implementation_sha,
        }
        values.update(changes)
        return m.compose_openf1_weather_drivers_into_frozen_producer(**values)

    def assert_hold_without_partial_output(self, result):
        self.assertEqual(result["status"], m.HOLD)
        self.assertNotIn("producer_input_bytes", result)
        self.assertNotIn("producer_evidence_bytes", result)
        self.assertNotIn("frozen_producer_input_manifest", result)
        self.assertFalse(result["new_scientific_receipt_created"])

    def verifier_arguments(self):
        result = self.result
        evidence = result["producer_evidence_bytes"]
        drivers_bytes = result["producer_input_bytes"]["drivers"]
        return {
            "audit": json.loads(evidence["producer_audit.json"]),
            "metadata": json.loads(evidence["forecast_metadata.json"]),
            "forecast_rows": csv_rows(evidence["forecast_rows.csv"]),
            "snapshot": csv_rows(evidence["source_snapshot_manifest.csv"]),
            "manifest": result["frozen_producer_input_manifest"],
            "manifest_bytes": result["frozen_producer_input_manifest_bytes"],
            "inputs": result["producer_input_bytes"],
            "weather_result": self.weather_adapter_result,
            "drivers_result": self.drivers_adapter_result,
            "driver_records": m._driver_records(drivers_bytes),
        }

    def test_valid_distinct_receipts_execute_real_producer_once(self):
        result = self.result
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["scope"], self.scope)
        self.assertTrue(result["weather_source_receipt_validated"])
        self.assertTrue(result["drivers_source_receipt_validated"])
        self.assertTrue(result["starting_grid_synthetic"])
        self.assertTrue(result["dual_source_mechanics_only"])
        self.assertTrue(result["producer_executed"])
        self.assertEqual(result["producer_subprocess_attempt_count"], 1)

    def test_both_accepted_adapters_are_called_before_subprocess(self):
        weather = m.weather_adapter.adapt_openf1_weather_to_producer_input
        drivers = m.drivers_adapter.adapt_openf1_drivers_to_producer_input
        with mock.patch.object(
            m.weather_adapter, "adapt_openf1_weather_to_producer_input",
            wraps=weather,
        ) as weather_call, mock.patch.object(
            m.drivers_adapter, "adapt_openf1_drivers_to_producer_input",
            wraps=drivers,
        ) as drivers_call, mock.patch.object(
            m, "_git_blob_sha", return_value="changed"
        ), mock.patch.object(m.subprocess, "run") as run:
            result = self.compose()
        self.assert_hold_without_partial_output(result)
        weather_call.assert_called_once()
        drivers_call.assert_called_once()
        run.assert_not_called()

    def test_raw_receipts_sources_hashes_and_unbound_manifests_stay_separate(self):
        result = self.result
        self.assertNotEqual(result["raw_weather_source_receipt_id"],
                            result["raw_drivers_source_receipt_id"])
        self.assertNotEqual(result["raw_weather_source_id"],
                            result["raw_drivers_source_id"])
        self.assertEqual(result["raw_weather_sha256"],
                         hashlib.sha256(self.weather_raw).hexdigest())
        self.assertEqual(result["raw_drivers_sha256"],
                         hashlib.sha256(self.drivers_raw).hexdigest())
        for prefix in ("weather", "drivers"):
            manifest = result[f"{prefix}_raw_frozen_evidence_manifest"]
            self.assertEqual(manifest["trust"],
                             m.weather_adapter.frozen_contract.TRUST)
            self.assertEqual(len(manifest["evidence"]), 1)
            self.assertEqual(
                hashlib.sha256(m._json_bytes(manifest)).hexdigest(),
                result[f"{prefix}_raw_frozen_evidence_manifest_sha256"],
            )

    def test_cross_scope_wrong_raw_and_swapped_receipts_hold_pre_subprocess(self):
        cases = (
            {"session_id": "99999"},
            {"raw_weather_response_bytes": self.weather_raw + b" "},
            {"raw_drivers_response_bytes": self.drivers_raw + b" "},
            {
                "weather_source_capture_receipt_bytes": self.drivers_receipt,
                "drivers_source_capture_receipt_bytes": self.weather_receipt,
            },
        )
        for change in cases:
            with self.subTest(change=tuple(change)), \
                    mock.patch.object(m.subprocess, "run") as run:
                result = self.compose(**change)
                self.assert_hold_without_partial_output(result)
                self.assertFalse(result["producer_execution_attempted"])
                run.assert_not_called()

    def test_either_adapter_hold_prevents_subprocess_and_partial_output(self):
        for held in ("weather", "drivers"):
            patches = {
                "weather": mock.patch.object(
                    m.weather_adapter,
                    "adapt_openf1_weather_to_producer_input",
                    return_value={"status": m.weather_adapter.HOLD},
                ),
                "drivers": mock.patch.object(
                    m.drivers_adapter,
                    "adapt_openf1_drivers_to_producer_input",
                    return_value={"status": m.drivers_adapter.HOLD},
                ),
            }
            with self.subTest(held=held), patches[held], \
                    mock.patch.object(m.subprocess, "run") as run:
                result = self.compose()
                self.assert_hold_without_partial_output(result)
                self.assertFalse(result["producer_execution_attempted"])
                run.assert_not_called()

    def test_synthetic_grid_is_exact_dynamic_universe_and_order_independent(self):
        drivers = self.result["producer_input_bytes"]["drivers"]
        rows = drivers.splitlines()
        reordered = b"\n".join([rows[0], *reversed(rows[1:])]) + b"\n"
        grid_a, records_a = m._synthetic_grid(drivers, **self.scope)
        grid_b, records_b = m._synthetic_grid(reordered, **self.scope)
        self.assertEqual(grid_a, grid_b)
        self.assertEqual(records_a, records_b)
        self.assertNotIn(b"observed", grid_a.lower())
        self.assertNotIn(b"fia", grid_a.lower())
        parsed = csv_rows(grid_a)
        self.assertEqual([row["driver_number"] for row in parsed],
                         ["1", "16", "44"])
        self.assertEqual([row["position"] for row in parsed], ["1", "2", "3"])
        self.assertEqual(len(parsed), len(self.driver_rows))
        for row in parsed:
            self.assertEqual(row["event_id"], self.scope["event_id"])
            self.assertEqual(row["meeting_id"], self.scope["meeting_id"])
            self.assertEqual(row["session_id"], self.scope["session_id"])

    def test_derived_and_synthetic_identities_recompute_and_differ_from_raw(self):
        result = self.result
        inputs = result["producer_input_bytes"]
        expected = {
            "drivers": "derived:openf1-drivers-csv:",
            "weather": "derived:openf1-weather-csv:",
            "starting_grid": "synthetic:starting-grid-csv:",
        }
        declared = {entry["source_name"]: entry
                    for entry in result["declared_sources"]}
        for name, prefix in expected.items():
            digest = hashlib.sha256(inputs[name]).hexdigest()
            self.assertEqual(declared[name]["source_id"], prefix + digest)
            self.assertEqual(declared[name]["source_sha256"], digest)
            self.assertNotIn(declared[name]["source_id"], {
                result["raw_weather_source_id"], result["raw_drivers_source_id"]
            })
        self.assertEqual(len({entry["source_id"]
                              for entry in declared.values()}), 3)

    def test_three_source_manifest_is_canonical_exact_and_deterministic(self):
        result = self.result
        manifest = result["frozen_producer_input_manifest"]
        self.assertEqual(set(manifest), {
            "schema_version", "event_id", "meeting_id", "session_id", "sources"
        })
        self.assertEqual(manifest["schema_version"], m.FROZEN_SCHEMA)
        self.assertEqual([entry["source_name"] for entry in manifest["sources"]],
                         ["drivers", "starting_grid", "weather"])
        self.assertEqual([entry["relative_path"] for entry in manifest["sources"]],
                         ["drivers.csv", "starting_grid.csv", "weather.csv"])
        data = result["frozen_producer_input_manifest_bytes"]
        self.assertEqual(data, m._json_bytes(manifest))
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         result["frozen_producer_input_manifest_sha256"])

    def test_real_producer_outputs_dynamic_driver_identity_grid_and_readiness(self):
        result = self.result
        rows = csv_rows(result["producer_evidence_bytes"]["forecast_rows.csv"])
        expected = {
            str(row["driver_number"]): (row["broadcast_name"], row["team_name"])
            for row in self.driver_rows
        }
        self.assertEqual(result["driver_universe_count"], 3)
        self.assertEqual(result["generated_row_count"], 3)
        self.assertEqual(set(row["driver_number"] for row in rows), set(expected))
        for row in rows:
            self.assertEqual((row["driver_name"], row["team_name"]),
                             expected[row["driver_number"]])
            self.assertEqual(row["grid_position"],
                             str([1, 16, 44].index(int(row["driver_number"])) + 1))
        self.assertEqual({float(row["source_readiness_score"]) for row in rows},
                         {0.48})
        self.assertEqual(result["source_readiness"], 0.48)

    def test_frozen_mode_bindings_propagate_through_audit_metadata_snapshot(self):
        evidence = self.result["producer_evidence_bytes"]
        audit = json.loads(evidence["producer_audit.json"])
        metadata = json.loads(evidence["forecast_metadata.json"])
        snapshot = csv_rows(evidence["source_snapshot_manifest.csv"])
        for record in (audit, metadata):
            self.assertEqual(record["input_mode"], "frozen_manifest")
            self.assertFalse(record["broad_discovery_used"])
            self.assertEqual(record["sources"], self.result["declared_sources"])
            self.assertEqual(record["source_counts"], self.result["source_counts"])
        declared = {entry["source_name"]: entry
                    for entry in self.result["declared_sources"]}
        for row in snapshot:
            if row["source_name"] in declared:
                self.assertEqual(row["source_id"],
                                 declared[row["source_name"]]["source_id"])
                self.assertEqual(row["source_sha256"],
                                 declared[row["source_name"]]["source_sha256"])

    def test_real_producer_command_is_bounded_and_environment_is_minimal(self):
        command = self.result["producer_command"]
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(Path(command[1]), m.PRODUCER_PATH)
        for flag, value in (
            ("--event-id", self.scope["event_id"]),
            ("--meeting-id", self.scope["meeting_id"]),
            ("--session-id", self.scope["session_id"]),
            ("--gate", "post_event"),
            ("--lane", "experimental_challenger"),
            ("--race-name", m.RACE_NAME),
        ):
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn("--frozen-input-manifest", command)
        self.assertIn("--repo-root", command)
        self.assertIn("--strict-source", command)
        self.assertTrue(m.RACE_NAME.endswith("NOT A PREDICTION"))

    def test_current_real_producer_blob_is_verified_before_and_after(self):
        data = m.PRODUCER_PATH.read_bytes()
        self.assertEqual(git_blob_sha(data), m.PRODUCER_BLOB_SHA)
        self.assertEqual(self.result["producer_git_blob_sha"],
                         m.PRODUCER_BLOB_SHA)
        self.assertEqual(self.result["producer_code_sha256"],
                         hashlib.sha256(data).hexdigest())

    def test_verifier_rejects_audit_snapshot_manifest_and_driver_tampering(self):
        cases = []
        audit = self.verifier_arguments()
        audit["audit"] = copy.deepcopy(audit["audit"])
        audit["audit"]["broad_discovery_used"] = True
        cases.append(audit)
        snapshot = self.verifier_arguments()
        snapshot["snapshot"] = copy.deepcopy(snapshot["snapshot"])
        snapshot["snapshot"][0]["source_sha256"] = "0" * 64
        cases.append(snapshot)
        manifest = self.verifier_arguments()
        manifest["manifest_bytes"] += b" "
        cases.append(manifest)
        driver = self.verifier_arguments()
        driver["forecast_rows"] = copy.deepcopy(driver["forecast_rows"])
        driver["forecast_rows"][0]["team_name"] = "Tampered"
        cases.append(driver)
        for arguments in cases:
            with self.subTest(case=len(arguments)):
                with self.assertRaises(m.CompositionError):
                    m._verify_producer_evidence(**arguments)

    def test_input_or_manifest_readback_tamper_holds_without_retry(self):
        original = m._write_checked
        for target in ("drivers.csv", "frozen_input_manifest.json"):
            with self.subTest(target=target):
                def tamper(path, data, target=target):
                    original(path, data)
                    if path.name == target:
                        path.write_bytes(path.read_bytes() + b" ")

                with mock.patch.object(m, "_write_checked", side_effect=tamper), \
                        mock.patch.object(m.subprocess, "run",
                                          wraps=subprocess.run) as run:
                    result = self.compose()
                self.assert_hold_without_partial_output(result)
                self.assertTrue(result["producer_execution_attempted"])
                run.assert_called_once()

    def test_producer_failure_holds_after_exactly_one_attempt(self):
        failed = subprocess.CompletedProcess(
            args=["producer"], returncode=2, stdout="", stderr="failed"
        )
        with mock.patch.object(m.subprocess, "run", return_value=failed) as run:
            result = self.compose()
        self.assert_hold_without_partial_output(result)
        self.assertTrue(result["producer_execution_attempted"])
        run.assert_called_once()

    def test_sandbox_exact_outputs_mirrors_hashes_and_disposal(self):
        result = self.result
        paths = result["producer_output_paths"]
        self.assertEqual(len(paths), 16)
        self.assertTrue(all(path.startswith(("inputs/", "_runtime/", "latest/",
                                             "history/")) for path in paths))
        self.assertTrue(result["producer_output_sandbox_disposed"])
        self.assertTrue(result["checkout_latest_history_unchanged"])
        command = result["producer_command"]
        sandbox = Path(command[command.index("--repo-root") + 1])
        self.assertFalse(sandbox.exists())
        for name, data in result["producer_evidence_bytes"].items():
            self.assertEqual(hashlib.sha256(data).hexdigest(),
                             result["producer_evidence_sha256"][name])

    def test_no_network_credentials_clock_source_substitution_or_discovery(self):
        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports.isdisjoint({
            "requests", "urllib", "http", "socket", "aiohttp", "github"
        }))
        for forbidden in ("os.environ", "getenv", "api.openf1.org",
                          "GITHUB_TOKEN", "workflow_dispatch"):
            self.assertNotIn(forbidden, source)
        signature = inspect.signature(
            m.compose_openf1_weather_drivers_into_frozen_producer
        )
        self.assertEqual(set(signature.parameters), {
            "weather_source_capture_receipt_bytes", "raw_weather_response_bytes",
            "drivers_source_capture_receipt_bytes", "raw_drivers_response_bytes",
            "event_id", "meeting_id", "session_id", "implementation_git_sha",
        })
        self.assertNotIn("forecast_generation_utc", signature.parameters)

    def test_no_receipts_bindings_stable_engine_forecast_or_promotion_claims(self):
        result = self.result
        for field in (
            "derived_weather_is_source_evidence",
            "derived_drivers_is_source_evidence",
            "synthetic_grid_is_observed_or_fia_official",
            "new_scientific_receipt_created",
            "normalization_receipt_created",
            "producer_execution_receipt_created",
            "verified_receipt_bindings_created",
            "stable_engine_executed",
            "production_forecast_generated",
            "blind_validation_eligible",
            "production_authenticated",
            "historical_availability_proven",
            "dr002_activated",
            "promotion_allowed",
        ):
            self.assertIs(result[field], False, field)
        self.assertIn("MECHANICS_ONLY_NOT_A_PREDICTION", result["status"])

    def test_all_nine_named_dependency_blobs_are_unchanged(self):
        self.assertEqual(len(m.DEPENDENCY_BLOBS), 9)
        for relative, expected in m.DEPENDENCY_BLOBS.items():
            self.assertEqual(git_blob_sha((ROOT / relative).read_bytes()),
                             expected, relative)

    def test_invalid_scope_or_git_context_holds_before_adapters(self):
        cases = (
            {"event_id": ""},
            {"meeting_id": " 1295"},
            {"session_id": "11371\n"},
            {"implementation_git_sha": "not-a-sha"},
        )
        for change in cases:
            with self.subTest(change=change), mock.patch.object(
                m.weather_adapter, "adapt_openf1_weather_to_producer_input"
            ) as weather, mock.patch.object(
                m.drivers_adapter, "adapt_openf1_drivers_to_producer_input"
            ) as drivers, mock.patch.object(m.subprocess, "run") as run:
                result = self.compose(**change)
                self.assert_hold_without_partial_output(result)
                weather.assert_not_called()
                drivers.assert_not_called()
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
