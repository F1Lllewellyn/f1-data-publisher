import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/forecast_bundles/event_scoped_forecast_input_lock_v1.py"
FIXTURE = ROOT / "tests/fixtures/event_scoped_forecast_input_lock_v1.json"
SPEC = importlib.util.spec_from_file_location("event_scoped_forecast_input_lock_v1", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EventScopedInputContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def build_package(self, root, mutate=None):
        request = {
            "schema_version": MODULE.SCHEMA,
            "event_id": self.fixture["event_id"],
            "meeting_id": self.fixture["meeting_id"],
            "target_session_id": self.fixture["target_session_id"],
            "allowed_session_ids": self.fixture["allowed_session_ids"],
            "forecast_cutoff_utc": self.fixture["forecast_cutoff_utc"],
            "forecast_deadline_utc": self.fixture["forecast_deadline_utc"],
            "forecast_generation_utc": self.fixture["forecast_generation_utc"],
            "forecast_lock_utc": self.fixture["forecast_lock_utc"],
            "gate": self.fixture["gate"],
            "lane_name": self.fixture["lane_name"],
            "race_name": self.fixture["race_name"],
            "product_contract_id": self.fixture["product_contract_id"],
            "execution_mode": self.fixture["execution_mode"],
            "contract_approved": self.fixture["contract_approved"],
            "participants": {
                "source_name": "drivers",
                "driver_numbers": self.fixture["participants"],
            },
            "sources": [],
            "producer_git_commit": self.fixture["producer_git_commit"],
        }
        for name, text in sorted(self.fixture["inputs"].items()):
            data = text.encode("utf-8")
            source_path = "inputs/" + name + ".csv"
            receipt_path = "receipts/" + name + ".json"
            source_id = "synthetic:" + name
            digest = hashlib.sha256(data).hexdigest()
            receipt = {
                "schema_version": "dr002-receipt-v1",
                "receipt_id": "capture:" + name,
                "receipt_type": "source_capture",
                "receipt_created_utc": self.fixture["receipt_created_utc"],
                "scope": {
                    "event_id": self.fixture["event_id"],
                    "meeting_id": self.fixture["meeting_id"],
                    "session_id": self.fixture["target_session_id"],
                },
                "parent_receipt_ids": [],
                "payload": {
                    "source_id": source_id,
                    "source_uri": "fixture:" + source_path,
                    "source_sha256": digest,
                    "event_time_utc": None,
                    "publisher_time_utc": None,
                    "first_observed_utc": self.fixture["source_first_observed_utc"],
                    "ingested_utc": self.fixture["source_ingested_utc"],
                    "capture_ref": "fixture:" + receipt_path,
                    "implementation": "synthetic-fixture-v1",
                },
            }
            receipt_digest = MODULE.receipts.receipt_sha256(receipt)
            (root / source_path).parent.mkdir(parents=True, exist_ok=True)
            (root / receipt_path).parent.mkdir(parents=True, exist_ok=True)
            (root / source_path).write_bytes(data)
            (root / receipt_path).write_bytes(MODULE.canonical_json_bytes(receipt))
            request["sources"].append(
                {
                    "source_name": name,
                    "source_id": source_id,
                    "session_id": self.fixture["target_session_id"],
                    "relative_path": source_path,
                    "source_sha256": digest,
                    "receipt_relative_path": receipt_path,
                    "receipt_sha256": receipt_digest,
                    "ingestion_required_at_cutoff": True,
                    "verified_binding": {
                        "receipt_sha256": receipt_digest,
                        "verification_ref": "synthetic-fixture-binding:" + name,
                    },
                }
            )
        if mutate:
            mutate(request, root)
        return request, MODULE.canonical_json_bytes(request)

    def validate(self, mutate=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, request_bytes = self.build_package(root, mutate)
            return MODULE.validate_event_scoped_input_package(root, request_bytes)

    def replace_source(self, request, root, source_name, data):
        source = next(
            item for item in request["sources"] if item["source_name"] == source_name
        )
        path = root / source["relative_path"]
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        source["source_sha256"] = digest
        receipt_path = root / source["receipt_relative_path"]
        receipt = MODULE.strict_json(receipt_path.read_bytes())
        receipt["payload"]["source_sha256"] = digest
        receipt_path.write_bytes(MODULE.canonical_json_bytes(receipt))
        receipt_digest = MODULE.receipts.receipt_sha256(receipt)
        source["receipt_sha256"] = receipt_digest
        source["verified_binding"]["receipt_sha256"] = receipt_digest

    def test_valid_package_binds_exact_participants_and_sources(self):
        result = self.validate()
        self.assertEqual(result["status"], "EVENT_SCOPED_INPUT_PACKAGE_VALIDATED")
        self.assertEqual(result["participant_driver_numbers"], [1, 2])
        self.assertEqual(len(result["sources"]), 4)
        self.assertEqual(result["source_driver_sets"]["position"], [1, 2])
        self.assertFalse(result["broad_discovery_used"])
        self.assertFalse(result["provider_request_made"])

    def test_mutated_source_bytes_fail_closed(self):
        def mutate(_, root):
            (root / "inputs/drivers.csv").write_bytes(b"mutated\n")

        with self.assertRaisesRegex(MODULE.EventScopedInputError, "source_hash_mismatch"):
            self.validate(mutate)

    def test_cross_event_receipt_fails_closed(self):
        def mutate(request, root):
            source = request["sources"][0]
            path = root / source["receipt_relative_path"]
            receipt = MODULE.strict_json(path.read_bytes())
            receipt["scope"]["event_id"] = "other-event"
            path.write_bytes(MODULE.canonical_json_bytes(receipt))
            digest = MODULE.receipts.receipt_sha256(receipt)
            source["receipt_sha256"] = digest
            source["verified_binding"]["receipt_sha256"] = digest

        with self.assertRaisesRegex(MODULE.EventScopedInputError, "receipt_scope_mismatch"):
            self.validate(mutate)

    def test_post_cutoff_source_fails_closed(self):
        def mutate(request, root):
            source = request["sources"][0]
            path = root / source["receipt_relative_path"]
            receipt = MODULE.strict_json(path.read_bytes())
            receipt["payload"]["first_observed_utc"] = "2026-10-22T20:00:01Z"
            receipt["payload"]["ingested_utc"] = "2026-10-22T20:00:01Z"
            receipt["receipt_created_utc"] = "2026-10-22T20:00:01Z"
            path.write_bytes(MODULE.canonical_json_bytes(receipt))
            digest = MODULE.receipts.receipt_sha256(receipt)
            source["receipt_sha256"] = digest
            source["verified_binding"]["receipt_sha256"] = digest

        with self.assertRaisesRegex(MODULE.EventScopedInputError, "invalid_source_capture_receipt"):
            self.validate(mutate)

    def test_extra_event_driver_fails_closed(self):
        def mutate(request, root):
            source = next(item for item in request["sources"] if item["source_name"] == "drivers")
            path = root / source["relative_path"]
            data = path.read_bytes() + (
                b"event-synthetic,meeting-synthetic,session-race,99,OUTSIDER,Other Team\n"
            )
            path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            source["source_sha256"] = digest
            receipt_path = root / source["receipt_relative_path"]
            receipt = MODULE.strict_json(receipt_path.read_bytes())
            receipt["payload"]["source_sha256"] = digest
            receipt_path.write_bytes(MODULE.canonical_json_bytes(receipt))
            receipt_digest = MODULE.receipts.receipt_sha256(receipt)
            source["receipt_sha256"] = receipt_digest
            source["verified_binding"]["receipt_sha256"] = receipt_digest

        with self.assertRaisesRegex(
            MODULE.EventScopedInputError, "participant_source_universe_mismatch"
        ):
            self.validate(mutate)

    def test_source_observation_after_cutoff_rejected_but_future_schedule_allowed(self):
        def future_schedule(request, root):
            source = next(
                item for item in request["sources"] if item["source_name"] == "weather"
            )
            path = root / source["relative_path"]
            rows = path.read_bytes().replace(
                b"date,air_temperature",
                b"date,air_temperature,date_start",
            ).replace(
                b",25.0\n",
                b",25.0,2026-10-25T19:00:00Z\n",
            )
            self.replace_source(request, root, "weather", rows)

        accepted = self.validate(future_schedule)
        self.assertEqual(accepted["status"], "EVENT_SCOPED_INPUT_PACKAGE_VALIDATED")

        def future_observation(request, root):
            source = next(
                item for item in request["sources"] if item["source_name"] == "position"
            )
            path = root / source["relative_path"]
            rows = path.read_bytes().replace(
                b"2026-10-22T19:01:00Z",
                b"2026-10-22T20:00:01Z",
                1,
            )
            self.replace_source(request, root, "position", rows)

        with self.assertRaisesRegex(
            MODULE.EventScopedInputError, "source_observation_after_cutoff:position"
        ):
            self.validate(future_observation)

    def test_required_driver_identity_fails_closed_per_row(self):
        for invalid in (
            b"",
            b"malformed",
            b"NaN",
            b"Infinity",
            b"-Infinity",
            b"0",
            b"-1",
        ):
            with self.subTest(driver_number=invalid):
                def mutate(request, root, invalid=invalid):
                    source = next(
                        item
                        for item in request["sources"]
                        if item["source_name"] == "position"
                    )
                    path = root / source["relative_path"]
                    rows = path.read_bytes() + (
                        b"event-synthetic,meeting-synthetic,session-race,"
                        + invalid
                        + b",3,2026-10-22T19:02:00Z\n"
                    )
                    self.replace_source(request, root, "position", rows)

                with self.assertRaisesRegex(
                    MODULE.EventScopedInputError,
                    "missing_or_invalid_driver_number:position",
                ):
                    self.validate(mutate)

    def test_fractional_driver_id_is_not_lossily_truncated(self):
        for invalid in (b"1.5", b"2.9"):
            with self.subTest(driver_number=invalid):
                def mutate(request, root, invalid=invalid):
                    source = next(
                        item
                        for item in request["sources"]
                        if item["source_name"] == "position"
                    )
                    path = root / source["relative_path"]
                    rows = path.read_bytes() + (
                        b"event-synthetic,meeting-synthetic,session-race,"
                        + invalid
                        + b",3,2026-10-22T19:02:00Z\n"
                    )
                    self.replace_source(request, root, "position", rows)

                with self.assertRaisesRegex(
                    MODULE.EventScopedInputError,
                    "missing_or_invalid_driver_number:position",
                ):
                    self.validate(mutate)

    def test_integral_driver_representations_and_repeated_rows_remain_valid(self):
        def mutate(request, root):
            source = next(
                item for item in request["sources"] if item["source_name"] == "position"
            )
            path = root / source["relative_path"]
            rows = path.read_bytes().replace(
                b",1,1,2026-10-22T19:00:00Z",
                b",1.0,1,2026-10-22T19:00:00Z",
            ).replace(
                b",2,2,2026-10-22T19:00:00Z",
                b",2e0,2,2026-10-22T19:00:00Z",
            )
            self.replace_source(request, root, "position", rows)

        result = self.validate(mutate)
        self.assertEqual(result["source_driver_sets"]["position"], [1, 2])

    def test_unchanged_producer_output_is_locked_with_exact_input_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "package"
            output = Path(directory) / "locked"
            root.mkdir()
            _, request_bytes = self.build_package(root)
            result = MODULE.produce_and_lock_event_scoped_forecast(
                root, request_bytes, output, repo_root=ROOT
            )
            self.assertEqual(result["status"], "LOCKED_OUTPUT_WITH_RETAINED_INPUT_EVIDENCE")
            self.assertEqual(result["participant_driver_numbers"], [1, 2])
            self.assertEqual(result["row_count"], 2)
            self.assertFalse(result["production_authenticated"])
            self.assertFalse(result["contract_approved"])
            manifest = MODULE.strict_json((output / "bundle_evidence_manifest.json").read_bytes())
            for item in manifest["files"]:
                data = (output / item["relative_path"]).read_bytes()
                self.assertEqual(len(data), item["byte_count"])
                self.assertEqual(MODULE.sha256(data), item["sha256"])
            lock = MODULE.strict_json((output / "forecast_lock_receipt.json").read_bytes())
            payload = (output / "forecast_payload.csv").read_bytes()
            self.assertEqual(lock["payload"]["forecast_payload_sha256"], MODULE.sha256(payload))
            rows = list(__import__("csv").DictReader(payload.decode("utf-8").splitlines()))
            self.assertEqual({int(row["driver_number"]) for row in rows}, {1, 2})

    def test_failed_validation_leaves_no_output_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "package"
            output = Path(directory) / "locked"
            root.mkdir()

            def mutate(request, package_root):
                source = request["sources"][0]
                path = package_root / source["relative_path"]
                path.write_bytes(b"mutated\n")

            _, request_bytes = self.build_package(root, mutate)
            with self.assertRaisesRegex(MODULE.EventScopedInputError, "source_hash_mismatch"):
                MODULE.produce_and_lock_event_scoped_forecast(
                    root, request_bytes, output, repo_root=ROOT
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
