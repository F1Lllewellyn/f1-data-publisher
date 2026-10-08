import ast
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
SCRIPT = BUNDLE_DIR / "dr002_openf1_weather_frozen_producer_composition_v1.py"
sys.path.insert(0, str(BUNDLE_DIR))
spec = importlib.util.spec_from_file_location("weather_frozen_composition", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import dr002_openf1_historical_rest_capture_v1 as capture


def git_blob_sha(data):
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def csv_rows(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))


class OpenF1WeatherFrozenProducerCompositionTests(unittest.TestCase):
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
        cls.raw = json.dumps(
            cls.weather_rows, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        assessed = capture.assess_openf1_historical_rest_capture(
            **cls.scope,
            endpoint="weather",
            request_params={"session_key": cls.scope["session_id"]},
            raw_response_bytes=cls.raw,
            http_status=200,
            session_end_utc="2026-09-24T13:00:00Z",
            first_observed_utc="2026-10-08T12:12:09.784033Z",
            ingested_utc="2026-10-08T12:12:09.784372Z",
            receipt_created_utc="2026-10-08T12:12:09.784388Z",
            capture_ref="_runtime/k4r3/weather.response.json",
            implementation="dr002_openf1_historical_rest_capture_v1",
        )
        if assessed["status"] != capture.VALIDATED:
            raise AssertionError(assessed)
        cls.receipt_bytes = assessed["source_capture_receipt_bytes"]
        cls.implementation_sha = "a" * 40
        cls.result = cls.compose()
        if cls.result["status"] != m.VALIDATED:
            raise AssertionError(cls.result)

    @classmethod
    def compose(cls, **changes):
        values = {
            "source_capture_receipt_bytes": cls.receipt_bytes,
            "raw_weather_response_bytes": cls.raw,
            **cls.scope,
            "implementation_git_sha": cls.implementation_sha,
        }
        values.update(changes)
        return m.compose_openf1_weather_into_frozen_producer(**values)

    def test_valid_k4r4_weather_and_synthetic_companions_succeed(self):
        result = self.result
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["scope"], self.scope)
        self.assertTrue(result["weather_source_evidence_real"])
        self.assertTrue(result["drivers_synthetic"])
        self.assertTrue(result["starting_grid_synthetic"])
        self.assertTrue(result["mixed_input_mechanics_only"])
        self.assertTrue(result["producer_executed"])

    def test_accepted_k4r4_adapter_is_called_not_reimplemented(self):
        original = m.weather_adapter.adapt_openf1_weather_to_producer_input
        with mock.patch.object(
            m.weather_adapter,
            "adapt_openf1_weather_to_producer_input",
            wraps=original,
        ) as adapted:
            result = self.compose()
        self.assertEqual(result["status"], m.VALIDATED)
        adapted.assert_called_once()

    def test_raw_openf1_identity_is_not_reused_for_derived_weather(self):
        result = self.result
        self.assertNotEqual(result["raw_weather_source_id"],
                            result["derived_weather_source_id"])
        self.assertTrue(result["raw_weather_source_id"].startswith("openf1:weather:"))
        self.assertTrue(result["derived_weather_source_id"].startswith(
            "derived:openf1-weather-csv:"
        ))
        self.assertEqual(result["raw_weather_sha256"],
                         hashlib.sha256(self.raw).hexdigest())

    def test_derived_weather_identity_is_deterministic_and_binds_exact_csv(self):
        data = self.result["producer_input_bytes"]["weather"]
        digest = hashlib.sha256(data).hexdigest()
        expected = "derived:openf1-weather-csv:" + digest
        self.assertEqual(self.result["derived_weather_csv_sha256"], digest)
        self.assertEqual(self.result["derived_weather_source_id"], expected)
        self.assertEqual(m._source_id("weather", data), expected)
        self.assertEqual(m._source_id("weather", bytes(data)), expected)

    def test_frozen_manifest_has_exact_schema_scope_and_three_sources(self):
        result = self.result
        manifest = result["frozen_producer_input_manifest"]
        self.assertEqual(set(manifest), {
            "schema_version", "event_id", "meeting_id", "session_id", "sources"
        })
        self.assertEqual(manifest["schema_version"], m.FROZEN_SCHEMA)
        self.assertEqual(
            {key: manifest[key] for key in self.scope}, self.scope
        )
        self.assertEqual([entry["source_name"] for entry in manifest["sources"]],
                         ["drivers", "starting_grid", "weather"])
        for entry in manifest["sources"]:
            self.assertEqual(set(entry), {
                "source_name", "source_id", "relative_path", "source_sha256"
            })
        data = result["frozen_producer_input_manifest_bytes"]
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         result["frozen_producer_input_manifest_sha256"])
        self.assertEqual(json.loads(data), manifest)

    def test_synthetic_source_ids_are_explicit_deterministic_and_hash_bound(self):
        inputs = self.result["producer_input_bytes"]
        by_name = {entry["source_name"]: entry
                   for entry in self.result["declared_sources"]}
        for name in ("drivers", "starting_grid"):
            digest = hashlib.sha256(inputs[name]).hexdigest()
            self.assertTrue(by_name[name]["source_id"].startswith("synthetic:"))
            self.assertTrue(by_name[name]["source_id"].endswith(digest))
            self.assertEqual(by_name[name]["source_sha256"], digest)
            self.assertEqual(m._source_id(name, inputs[name]),
                             by_name[name]["source_id"])

    def test_all_input_csv_scope_columns_match_declared_scope(self):
        for name, data in self.result["producer_input_bytes"].items():
            rows = csv_rows(data)
            self.assertTrue(rows)
            for row in rows:
                for column, expected in (
                    ("event_id", self.scope["event_id"]),
                    ("meeting_id", self.scope["meeting_id"]),
                    ("meeting_key", self.scope["meeting_id"]),
                    ("session_id", self.scope["session_id"]),
                    ("session_key", self.scope["session_id"]),
                ):
                    if column in row:
                        self.assertEqual(row[column], expected, (name, column))

    def test_real_producer_cli_command_is_exactly_bounded(self):
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
            self.assertIn(flag, command)
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn("--frozen-input-manifest", command)
        self.assertIn("--repo-root", command)
        self.assertIn("--strict-source", command)
        self.assertIn("NOT A PREDICTION", " ".join(command))
        self.assertEqual(self.result["producer_subprocess_attempt_count"], 1)

    def test_current_real_producer_blob_pin_is_exact(self):
        data = m.PRODUCER_PATH.read_bytes()
        self.assertEqual(git_blob_sha(data), m.PRODUCER_BLOB_SHA)
        self.assertEqual(self.result["producer_git_blob_sha"],
                         m.PRODUCER_BLOB_SHA)
        self.assertEqual(self.result["producer_code_sha256"],
                         hashlib.sha256(data).hexdigest())

    def test_audit_proves_frozen_mode_and_discovery_bypass(self):
        audit = json.loads(
            self.result["producer_evidence_bytes"]["producer_audit.json"]
        )
        self.assertEqual(audit["input_mode"], "frozen_manifest")
        self.assertFalse(audit["broad_discovery_used"])
        self.assertEqual(audit["event_id"], self.scope["event_id"])
        self.assertEqual(audit["meeting_id"], self.scope["meeting_id"])
        self.assertEqual(audit["session_id"], self.scope["session_id"])
        self.assertEqual(audit["gates"], ["post_event"])
        self.assertEqual(audit["lanes"], ["experimental_challenger"])
        self.assertFalse(self.result["broad_discovery_used"])

    def test_source_snapshot_binds_derived_weather_and_preserves_raw_separately(self):
        snapshot = csv_rows(
            self.result["producer_evidence_bytes"]["source_snapshot_manifest.csv"]
        )
        weather = next(row for row in snapshot if row["source_name"] == "weather")
        self.assertEqual(weather["source_id"],
                         self.result["derived_weather_source_id"])
        self.assertEqual(weather["source_sha256"],
                         self.result["derived_weather_csv_sha256"])
        self.assertNotEqual(weather["source_id"],
                            self.result["raw_weather_source_id"])
        self.assertNotEqual(weather["source_sha256"],
                            self.result["raw_weather_sha256"])
        self.assertIn("raw_weather_source_receipt_id", self.result)
        self.assertIn("k4r4_frozen_evidence_manifest_sha256", self.result)

    def test_weather_row_count_propagates_exactly(self):
        self.assertEqual(self.result["weather_row_count"], len(self.weather_rows))
        self.assertEqual(self.result["source_counts"]["weather"],
                         len(self.weather_rows))
        snapshot = csv_rows(
            self.result["producer_evidence_bytes"]["source_snapshot_manifest.csv"]
        )
        weather = next(row for row in snapshot if row["source_name"] == "weather")
        self.assertEqual(int(weather["row_count"]), len(self.weather_rows))

    def test_generated_rows_and_source_readiness_match_mixed_inputs(self):
        rows = csv_rows(self.result["producer_evidence_bytes"]["forecast_rows.csv"])
        self.assertEqual(self.result["generated_row_count"], 2)
        self.assertEqual({row["driver_number"] for row in rows}, {"10", "20"})
        self.assertEqual({row["driver_name"] for row in rows},
                         {"Synthetic Ten", "Synthetic Twenty"})
        self.assertEqual({float(row["source_readiness_score"]) for row in rows},
                         {0.48})
        self.assertEqual(self.result["source_readiness"], 0.48)
        self.assertTrue(self.result["forecast_generation_utc"].endswith("Z"))

    def test_checked_out_latest_and_history_are_unchanged(self):
        before = m._checked_out_output_fingerprint()
        self.assertTrue(self.result["checkout_latest_history_unchanged"])
        self.assertEqual(m._checked_out_output_fingerprint(), before)

    def test_producer_outputs_are_confined_to_disposable_sandbox(self):
        paths = self.result["producer_output_paths"]
        self.assertIn("inputs/weather.csv", paths)
        self.assertTrue(any(path.startswith("_runtime/") for path in paths))
        self.assertTrue(any(path.startswith("latest/") for path in paths))
        self.assertTrue(any(path.startswith("history/") for path in paths))
        self.assertTrue(all(path.startswith(("inputs/", "_runtime/", "latest/",
                                             "history/")) for path in paths))

    def test_sandbox_is_disposed_after_in_memory_evidence_extraction(self):
        self.assertTrue(self.result["producer_output_sandbox_disposed"])
        command = self.result["producer_command"]
        repo_root = Path(command[command.index("--repo-root") + 1])
        manifest_path = Path(command[command.index("--frozen-input-manifest") + 1])
        self.assertFalse(repo_root.exists())
        self.assertFalse(manifest_path.exists())
        self.assertTrue(self.result["producer_evidence_bytes"])

    def test_selected_evidence_hashes_recompute(self):
        self.assertEqual(set(self.result["producer_evidence_bytes"]), {
            "producer_audit.json",
            "source_snapshot_manifest.csv",
            "forecast_rows.csv",
            "forecast_metadata.json",
        })
        for name, data in self.result["producer_evidence_bytes"].items():
            self.assertEqual(hashlib.sha256(data).hexdigest(),
                             self.result["producer_evidence_sha256"][name])

    def test_k4r4_hold_prevents_producer_subprocess(self):
        with mock.patch.object(
            m.weather_adapter,
            "adapt_openf1_weather_to_producer_input",
            return_value={"status": m.weather_adapter.HOLD},
        ), mock.patch.object(m.subprocess, "run") as run:
            result = self.compose()
        self.assertEqual(result["status"], m.HOLD)
        self.assertFalse(result["producer_execution_attempted"])
        run.assert_not_called()
        self.assertNotIn("producer_evidence_bytes", result)

    def test_tampered_derived_synthetic_or_manifest_bytes_hold(self):
        original = m._write_checked
        targets = ("weather.csv", "drivers.csv", "frozen_input_manifest.json")
        for target in targets:
            with self.subTest(target=target):
                def tampering_write(path, data, target=target):
                    original(path, data)
                    if path.name == target:
                        path.write_bytes(path.read_bytes() + b" ")

                with mock.patch.object(m, "_write_checked",
                                       side_effect=tampering_write):
                    result = self.compose()
                self.assertEqual(result["status"], m.HOLD)
                self.assertTrue(result["producer_execution_attempted"])
                self.assertNotIn("producer_evidence_bytes", result)

    def test_producer_failure_is_attempted_once_and_cannot_succeed(self):
        failed = subprocess.CompletedProcess(
            args=["producer"], returncode=2, stdout="", stderr="failed"
        )
        with mock.patch.object(m.subprocess, "run", return_value=failed) as run:
            result = self.compose()
        self.assertEqual(result["status"], m.HOLD)
        self.assertTrue(result["producer_execution_attempted"])
        run.assert_called_once()
        self.assertNotIn("producer_run_id", result)
        self.assertNotIn("producer_evidence_bytes", result)

    def test_no_scientific_receipt_or_verified_binding_is_created(self):
        result = self.result
        self.assertFalse(result["new_scientific_receipt_created"])
        self.assertFalse(result["producer_execution_receipt_created"])
        self.assertFalse(result["verified_receipt_bindings_created"])
        self.assertFalse(result["derived_weather_is_source_evidence"])
        self.assertNotIn("producer_execution_receipt", result)
        self.assertNotIn("verified_receipt_bindings", result)

    def test_claim_ceiling_flags_remain_false(self):
        result = self.result
        for field in (
            "stable_engine_executed",
            "production_forecast_generated",
            "blind_validation_eligible",
            "production_authenticated",
            "historical_availability_proven",
            "dr002_activated",
            "promotion_allowed",
        ):
            self.assertIs(result[field], False, field)
        self.assertEqual(result["gate"], "post_event")
        self.assertEqual(result["lane"], "experimental_challenger")

    def test_no_network_github_api_or_environment_secret_access(self):
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
        self.assertNotIn("os.environ", source)
        self.assertNotIn("api.openf1.org", source)
        self.assertNotIn("GITHUB_TOKEN", source)
        signature = inspect.signature(
            m.compose_openf1_weather_into_frozen_producer
        )
        self.assertNotIn("forecast_generation_utc", signature.parameters)

    def test_all_named_dependency_blobs_are_unchanged(self):
        self.assertEqual(m.DEPENDENCY_BLOBS, {
            "scripts/forecast_bundles/dr002_openf1_weather_producer_adapter_v1.py":
                "5061d8007d06c37e164df2c6cc643e385be885f8",
            "tests/test_dr002_openf1_weather_producer_adapter_v1.py":
                "6ef4b05456a9c26687755206dcaea32b2ed7f8d0",
            "scripts/forecasts/produce_actual_forecast_rows_v1.py":
                "af27586668c767de126af829c1131c6bae4634ad",
            "scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py":
                "1d3bfaf713807e799a6323875de670dc8d4e1a85",
            "scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py":
                "8dfd855184b172ce88235ee7de3ea33a68031b2e",
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
                "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
            "docs/DR002_PRE2B7K4R3_ONE_HISTORICAL_OPENF1_REST_SHADOW_RUN_2026-10-08.md":
                "db92fb23ff0adf95e59a80f14dcd527b6d1f9906",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
                "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
        })
        for relative, expected in m.DEPENDENCY_BLOBS.items():
            self.assertEqual(git_blob_sha((ROOT / relative).read_bytes()),
                             expected, relative)

    def test_invalid_scope_or_git_context_holds_before_execution(self):
        cases = (
            {"event_id": ""},
            {"meeting_id": " 1295"},
            {"session_id": "11371\n"},
            {"implementation_git_sha": "not-a-sha"},
        )
        for change in cases:
            with self.subTest(change=change), \
                    mock.patch.object(m.subprocess, "run") as run:
                result = self.compose(**change)
                self.assertEqual(result["status"], m.HOLD)
                self.assertFalse(result["producer_execution_attempted"])
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
