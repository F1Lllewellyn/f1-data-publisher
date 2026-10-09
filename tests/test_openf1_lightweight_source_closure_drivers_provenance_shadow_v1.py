import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/openf1/publish_openf1_lightweight_source_closure.py"
WORKFLOW = ROOT / ".github/workflows/f1-openf1-lightweight-source-closure.yml"
POLICY = ROOT / "configs/openf1/openf1_lightweight_source_closure_policy.json"
try:
    import requests  # noqa: F401 - use the real workflow dependency when available
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("real network is forbidden in focused tests")

    requests_stub.get = unexpected_network
    sys.modules["requests"] = requests_stub
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("openf1_drivers_shadow", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


DEPENDENCY_BLOBS = {
    "scripts/openf1/publish_openf1_lightweight_source_closure.py":
        "6e29dac3587c4f1b06734edd75b0d2c429aec04a",
    ".github/workflows/f1-openf1-lightweight-source-closure.yml":
        "506efa4098d3879fcd7374ae755c1daa4bb7f1d3",
    "tests/test_openf1_lightweight_source_closure_provenance_shadow_v1.py":
        "bbe623a48322d273990dd34d05fedf133f1af828",
    "configs/openf1/openf1_lightweight_source_closure_policy.json":
        "8c3a4a52f37aa39b761a45bebfafa1dda7b2e252",
    "scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py":
        "e68fa528cd73cd5c72afd97622a00d6e5b29be19",
    "scripts/forecast_bundles/dr002_openf1_drivers_producer_adapter_v1.py":
        "357ac56a6cfe317e21d9ce71d78c58683e444a5a",
    "scripts/forecast_bundles/dr002_openf1_weather_frozen_producer_composition_v1.py":
        "090c61af27ef932aae51a8fb83fe828c20c13a68",
    "scripts/forecasts/produce_actual_forecast_rows_v1.py":
        "af27586668c767de126af829c1131c6bae4634ad",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
}
MODIFIED_DEPENDENCIES = {
    "scripts/openf1/publish_openf1_lightweight_source_closure.py",
    ".github/workflows/f1-openf1-lightweight-source-closure.yml",
    "configs/openf1/openf1_lightweight_source_closure_policy.json",
}


class Response:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content


class SequencedGet:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected network call")
        return self.responses.pop(0)


class Clock:
    def __init__(self, values, events=None):
        self.values = list(values)
        self.events = events

    def __call__(self):
        if self.events is not None:
            self.events.append("clock")
        if not self.values:
            raise AssertionError("unexpected clock call")
        return self.values.pop(0)


def session_rows(*, duplicate=False, year=2026,
                 date_end="2026-10-07T14:00:00Z"):
    row = {
        "session_key": 11371,
        "meeting_key": 1295,
        "year": year,
        "country_name": "Azerbaijan",
        "location": "Baku",
        "circuit_short_name": "Baku",
        "date_end": date_end,
    }
    rows = [row]
    if duplicate:
        rows.append(dict(row))
    return json.dumps(rows, separators=(",", ":")).encode()


DRIVERS_ROWS = [
    {
        "meeting_key": 1295,
        "session_key": 11371,
        "driver_number": 44,
        "broadcast_name": "L HAMILTON",
        "full_name": "Lewis HAMILTON",
        "team_name": "Scuderia Ferrari HP",
        "country_code": "GBR",
    },
    {
        "meeting_key": "1295",
        "session_key": "11371",
        "driver_number": 1,
        "broadcast_name": "M VERSTAPPEN",
        "full_name": "Max VERSTAPPEN",
        "team_name": "Red Bull Racing",
    },
]
DRIVERS_BYTES = json.dumps(
    DRIVERS_ROWS, separators=(",", ":"), ensure_ascii=True
).encode()
WEATHER_BYTES = b'[{"meeting_key":1295,"session_key":11371,"air_temperature":23.4}]'


class DriversProvenanceShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output_root = Path(self.temp.name)

    def options(self, **changes):
        getter = SequencedGet([
            Response(200, session_rows()),
            Response(200, DRIVERS_BYTES),
        ])
        options = {
            "session_key": "11371",
            "season": 2026,
            "output_root": self.output_root,
            "repository": "F1Lllewellyn/f1-data-publisher",
            "workflow": "F1 OpenF1 Lightweight Source Closure",
            "workflow_ref": (
                "F1Lllewellyn/f1-data-publisher/"
                ".github/workflows/f1-openf1-lightweight-source-closure.yml@refs/heads/main"
            ),
            "ref": "refs/heads/main",
            "head_sha": "a" * 40,
            "run_id": "225",
            "run_attempt": "1",
            "endpoint": "drivers",
            "http_get": getter,
            "clock": Clock([
                "2026-10-07T14:30:00Z",
                "2026-10-07T14:30:01Z",
                "2026-10-07T14:30:02Z",
                "2026-10-07T14:30:03Z",
            ]),
        }
        options.update(changes)
        return options, getter

    def run_valid(self, **changes):
        options, getter = self.options(**changes)
        return m.run_provenance_shadow(**options), getter

    def runtime_root(self, run_id="225", attempt="1"):
        return (self.output_root / "_runtime" / m.SHADOW_RUNTIME_DIR
                / f"gha-{run_id}-{attempt}")

    def test_weather_default_is_unchanged_with_exact_requests_and_five_files(self):
        getter = SequencedGet([
            Response(200, session_rows()),
            Response(200, WEATHER_BYTES),
        ])
        options, _ = self.options(http_get=getter)
        options.pop("endpoint")
        manifest = m.run_provenance_shadow(**options)
        self.assertEqual([call[0] for call in getter.calls], [
            "https://api.openf1.org/v1/sessions?year=2026",
            "https://api.openf1.org/v1/weather?session_key=11371",
        ])
        self.assertNotIn("selected_endpoint", manifest)
        self.assertEqual({path.name for path in self.runtime_root().iterdir()}, {
            "weather.response.json",
            "source_capture_receipt.json",
            "historical_rest_capture_assessment.json",
            "shadow_manifest.json",
            "shadow_report.md",
        })
        report = (self.runtime_root() / "shadow_report.md").read_text()
        self.assertIn("pre-2B-7K4R2", report)
        self.assertNotIn("K4R7", report)

    def test_drivers_uses_one_discovery_then_exact_canonical_request(self):
        manifest, getter = self.run_valid()
        self.assertEqual([call[0] for call in getter.calls], [
            "https://api.openf1.org/v1/sessions?year=2026",
            "https://api.openf1.org/v1/drivers?session_key=11371",
        ])
        self.assertEqual(manifest["selected_endpoint"], "drivers")
        self.assertEqual(manifest["canonical_request_uri"], getter.calls[1][0])
        for _, kwargs in getter.calls:
            self.assertEqual(kwargs["timeout"], m.REQUEST_TIMEOUT)
            self.assertEqual(kwargs["headers"]["Accept-Encoding"], "identity")

    def test_invalid_endpoint_holds_before_network_or_output(self):
        for endpoint in ("", "driver", "DRIVERS", None, 1):
            options, getter = self.options(endpoint=endpoint)
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(
                m.ProvenanceShadowHold, "provenance_shadow_endpoint_unsupported"
            ):
                m.run_provenance_shadow(**options)
            self.assertEqual(getter.calls, [])
            self.assertFalse((self.output_root / "_runtime").exists())

    def test_cli_drivers_without_session_and_unsupported_endpoint_hold_before_legacy(self):
        for endpoint in ("drivers", "unsupported"):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            with mock.patch.object(m, "run_provenance_shadow",
                                   side_effect=AssertionError("shadow must not run")), \
                 mock.patch.object(m, "load_policy",
                                   side_effect=AssertionError("legacy must not run")), \
                 mock.patch.object(sys, "argv", [
                     str(SCRIPT), "--output-root", alternate.name,
                     "--provenance-shadow-session-key", "",
                     "--provenance-shadow-endpoint", endpoint,
                 ]):
                self.assertEqual(m.main(), 1)
            self.assertEqual(list(Path(alternate.name).iterdir()), [])

    def test_empty_weather_cli_remains_legacy(self):
        with mock.patch.object(m, "run_provenance_shadow",
                               side_effect=AssertionError("shadow must not run")), \
             mock.patch.object(m, "load_policy", return_value={}), \
             mock.patch.object(m, "get_sessions", return_value=m.pd.DataFrame()), \
             mock.patch.object(m, "LANES", []), \
             mock.patch.object(sys, "argv", [
                 str(SCRIPT), "--output-root", str(self.output_root),
                 "--provenance-shadow-session-key", "",
                 "--provenance-shadow-endpoint", "weather",
             ]):
            self.assertEqual(m.main(), 0)
        self.assertTrue((self.output_root / "latest/openf1_lightweight_source_closure").exists())
        self.assertTrue((self.output_root / "history/openf1_lightweight_source_closure").exists())

    def test_unique_completed_matching_session_is_required_before_drivers_request(self):
        cases = (
            (b"[]", "selected_session_not_unique"),
            (session_rows(duplicate=True), "selected_session_not_unique"),
            (session_rows(year=2025), "selected_session_year_mismatch"),
            (json.dumps([{"session_key": 11371, "meeting_key": 1295}]).encode(),
             "malformed_session_metadata"),
            (json.dumps([
                json.loads(session_rows())[0],
                {"session_key": True},
            ]).encode(), "malformed_session_metadata"),
        )
        for body, reason in cases:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([Response(200, body)])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.subTest(reason=reason), self.assertRaisesRegex(
                m.ProvenanceShadowHold, reason
            ):
                m.run_provenance_shadow(**options)
            self.assertEqual(len(getter.calls), 1)
            self.assertFalse(any(Path(alternate.name).rglob("drivers.response.json")))

    def test_historical_window_gate_precedes_drivers_request(self):
        getter = SequencedGet([Response(200, session_rows())])
        options, _ = self.options(
            http_get=getter,
            clock=Clock(["2026-10-07T14:29:59.999999Z"]),
        )
        with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                    "selected_session_before_historical_window"):
            m.run_provenance_shadow(**options)
        self.assertEqual(len(getter.calls), 1)

    def test_exact_driver_bytes_readback_hash_and_observation_order(self):
        events = []

        class CompleteDriversResponse:
            status_code = 200

            @property
            def content(self):
                events.append("complete_bytes")
                return DRIVERS_BYTES

        getter = SequencedGet([Response(200, session_rows()), CompleteDriversResponse()])
        options, _ = self.options(
            http_get=getter,
            clock=Clock([
                "2026-10-07T14:30:00Z",
                "2026-10-07T14:30:01Z",
                "2026-10-07T14:30:02Z",
                "2026-10-07T14:30:03Z",
            ], events=events),
        )
        manifest = m.run_provenance_shadow(**options)
        raw = (self.runtime_root() / "drivers.response.json").read_bytes()
        self.assertEqual(raw, DRIVERS_BYTES)
        self.assertEqual(manifest["raw_response_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertLess(events.index("complete_bytes"), events.index("clock", 1))
        self.assertEqual(manifest["first_observed_utc"], "2026-10-07T14:30:01Z")

    def test_unchanged_k4r1_receipt_is_canonical_parentless_and_exactly_scoped(self):
        calls = []

        def assessor(**kwargs):
            calls.append(kwargs)
            return m.historical_rest_contract.assess_openf1_historical_rest_capture(**kwargs)

        manifest, _ = self.run_valid(assessor=assessor)
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["endpoint"], "drivers")
        self.assertEqual(call["request_params"], {"session_key": "11371"})
        self.assertEqual(call["raw_response_bytes"], DRIVERS_BYTES)
        receipt_bytes = (self.runtime_root() / "source_capture_receipt.json").read_bytes()
        receipt = json.loads(receipt_bytes)
        self.assertEqual(
            m.historical_rest_contract.receipt_contract.canonical_json_bytes(receipt),
            receipt_bytes,
        )
        self.assertEqual(receipt["receipt_type"], "source_capture")
        self.assertEqual(receipt["parent_receipt_ids"], [])
        self.assertEqual(receipt["scope"], {
            "event_id": "2026_1295_azerbaijan_baku_baku",
            "meeting_id": "1295",
            "session_id": "11371",
        })
        uri = "https://api.openf1.org/v1/drivers?session_key=11371"
        source_id = "openf1:drivers:" + hashlib.sha256(uri.encode()).hexdigest()
        self.assertEqual(receipt["payload"]["source_uri"], uri)
        self.assertEqual(receipt["payload"]["source_id"], source_id)
        self.assertEqual(manifest["receipt_type"], "source_capture")

    def test_unchanged_k4r6_validates_exact_persisted_bytes_and_records_only_metadata(self):
        calls = []

        def adapter(**kwargs):
            calls.append(kwargs)
            return m.drivers_adapter_contract.adapt_openf1_drivers_to_producer_input(**kwargs)

        manifest, _ = self.run_valid(drivers_adapter=adapter)
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["raw_drivers_response_bytes"],
                         (self.runtime_root() / "drivers.response.json").read_bytes())
        self.assertEqual(call["source_capture_receipt_bytes"],
                         (self.runtime_root() / "source_capture_receipt.json").read_bytes())
        self.assertEqual(manifest["k4r6_status"], m.drivers_adapter_contract.VALIDATED)
        self.assertEqual(manifest["drivers_row_count"], 2)
        self.assertEqual(manifest["drivers_unique_driver_count"], 2)
        derived_sha = manifest["drivers_derived_csv_sha256"]
        self.assertRegex(derived_sha, r"^[0-9a-f]{64}$")
        self.assertEqual(manifest["drivers_derived_runtime_identity"],
                         "derived:openf1-drivers-csv:" + derived_sha)
        self.assertFalse(manifest["derived_csv_is_source_evidence"])
        self.assertFalse(manifest["derived_csv_persisted"])

    def test_success_package_is_exactly_five_files_and_never_persists_csv(self):
        manifest, _ = self.run_valid()
        self.assertEqual(manifest["status"], m.historical_rest_contract.VALIDATED)
        self.assertEqual({path.name for path in self.runtime_root().iterdir()}, {
            "drivers.response.json",
            "source_capture_receipt.json",
            "historical_rest_capture_assessment.json",
            "shadow_manifest.json",
            "shadow_report.md",
        })
        self.assertFalse(any(self.output_root.rglob("*.csv")))
        self.assertFalse((self.output_root / "latest").exists())
        self.assertFalse((self.output_root / "history").exists())
        receipt = json.loads((self.runtime_root() / "source_capture_receipt.json").read_bytes())
        self.assertNotIn("verified_receipt_bindings", receipt)
        self.assertFalse(manifest["verified_receipt_bindings_created"])
        self.assertFalse(manifest["new_scientific_receipt_created"])
        self.assertFalse(manifest["normalization_receipt_created"])

    def test_adapter_hold_fails_closed_without_validated_success(self):
        def holding_adapter(**_kwargs):
            return {
                "status": m.drivers_adapter_contract.HOLD,
                "reason_codes": ["synthetic_adapter_hold"],
            }

        options, _ = self.options(drivers_adapter=holding_adapter)
        with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                    "k4r6_hold:synthetic_adapter_hold"):
            m.run_provenance_shadow(**options)
        manifest = json.loads((self.runtime_root() / "shadow_manifest.json").read_bytes())
        self.assertEqual(manifest["status"], m.historical_rest_contract.HOLD)
        self.assertEqual(manifest["k4r6_status"], m.drivers_adapter_contract.HOLD)
        self.assertFalse(any(self.output_root.rglob("*.csv")))

    def test_k4r1_hold_malformed_drivers_and_readback_failure_hold(self):
        def holding_assessor(**_kwargs):
            return {
                "status": m.historical_rest_contract.HOLD,
                "reason_codes": ["synthetic_k4r1_hold"],
            }

        cases = [
            ({"assessor": holding_assessor}, "k4r1_hold:synthetic_k4r1_hold"),
            ({"http_get": SequencedGet([
                Response(200, session_rows()), Response(200, b"{}")
            ])}, "k4r6_hold:"),
            ({"read_bytes": lambda path: b"changed" if path.name == "drivers.response.json"
              else path.read_bytes()}, "raw_response_readback_mismatch"),
        ]
        for changes, reason in cases:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            options, _ = self.options(output_root=Path(alternate.name), **changes)
            with self.subTest(reason=reason), self.assertRaisesRegex(
                m.ProvenanceShadowHold, reason
            ):
                m.run_provenance_shadow(**options)
            manifests = list(Path(alternate.name).rglob("shadow_manifest.json"))
            self.assertEqual(len(manifests), 1)
            self.assertEqual(json.loads(manifests[0].read_bytes())["status"],
                             m.historical_rest_contract.HOLD)

    def test_wrong_k4r1_request_raw_hash_or_receipt_fails_closed(self):
        def corrupt(kind):
            def assessor(**kwargs):
                result = m.historical_rest_contract.assess_openf1_historical_rest_capture(
                    **kwargs
                )
                if kind == "request":
                    result["canonical_request_uri"] += "&driver_number=44"
                elif kind == "raw_hash":
                    result["raw_response_sha256"] = "0" * 64
                else:
                    receipt = json.loads(result["source_capture_receipt_bytes"])
                    receipt["payload"]["source_uri"] += "&driver_number=44"
                    receipt_bytes = (
                        m.historical_rest_contract.receipt_contract.canonical_json_bytes(
                            receipt
                        )
                    )
                    result["source_capture_receipt_bytes"] = receipt_bytes
                    result["receipt_sha256"] = hashlib.sha256(receipt_bytes).hexdigest()
                return result
            return assessor

        cases = (
            ("request", "k4r1_request_uri_mismatch"),
            ("raw_hash", "k4r1_raw_response_hash_mismatch"),
            ("receipt", "k4r1_receipt_source_uri_mismatch"),
        )
        for kind, reason in cases:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            options, _ = self.options(
                output_root=Path(alternate.name), assessor=corrupt(kind)
            )
            with self.subTest(kind=kind), self.assertRaisesRegex(
                m.ProvenanceShadowHold, reason
            ):
                m.run_provenance_shadow(**options)
            manifests = list(Path(alternate.name).rglob("shadow_manifest.json"))
            self.assertEqual(len(manifests), 1)
            self.assertEqual(json.loads(manifests[0].read_bytes())["status"],
                             m.historical_rest_contract.HOLD)

    def test_drivers_manifest_report_and_provenance_flags_are_explicit(self):
        manifest, _ = self.run_valid()
        stored = json.loads((self.runtime_root() / "shadow_manifest.json").read_bytes())
        self.assertEqual(stored, manifest)
        self.assertEqual(stored["selected_endpoint"], "drivers")
        self.assertEqual(stored["raw_response_filename"], "drivers.response.json")
        for flag in (
            "derived_csv_persisted",
            "derived_csv_is_source_evidence",
            "new_scientific_receipt_created",
            "normalization_receipt_created",
            "openf1_official_f1_roster_authority",
            "historical_availability_before_first_observation_proven",
            "dr002_activated",
            "promotion_allowed",
        ):
            self.assertIs(stored[flag], False)
        report = (self.runtime_root() / "shadow_report.md").read_text()
        self.assertIn("pre-2B-7K4R7", report)
        self.assertIn("Selected endpoint: drivers", report)
        self.assertIn(stored["drivers_derived_csv_sha256"], report)
        self.assertIn(stored["drivers_derived_runtime_identity"], report)
        self.assertIn("no CSV was persisted", report)

    def test_workflow_choice_safe_routing_main_only_and_no_shadow_push(self):
        text = WORKFLOW.read_text()
        self.assertIn("provenance_shadow_endpoint:", text)
        self.assertIn("type: choice", text)
        self.assertIn("- weather", text)
        self.assertIn("- drivers", text)
        self.assertIn("default: weather", text)
        self.assertIn("PROVENANCE_SHADOW_ENDPOINT:", text)
        self.assertIn('--provenance-shadow-endpoint "$PROVENANCE_SHADOW_ENDPOINT"', text)
        self.assertNotIn('${{ github.event.inputs.provenance_shadow_endpoint }}"', text)
        self.assertIn("Reject drivers shadow without explicit session", text)
        self.assertIn("github.ref != 'refs/heads/main'", text)
        self.assertIn(
            "persist-credentials: ${{ github.event_name != 'workflow_dispatch' || "
            "github.event.inputs.provenance_shadow_session_key == '' }}",
            text,
        )
        commit_block = text[text.index("- name: Commit source closure outputs"):]
        self.assertIn("github.event.inputs.provenance_shadow_session_key == ''", commit_block)
        self.assertIn("dr002-pre2b7k4r2-openf1-historical-rest-shadow", text)
        self.assertIn("dr002-pre2b7k4r7-openf1-drivers-historical-rest-shadow", text)

    def test_policy_declares_bounded_drivers_mode_and_preserves_weather_default(self):
        policy = json.loads(POLICY.read_bytes())
        shadow = policy["provenance_shadow"]
        self.assertEqual(shadow["endpoint"], "weather")
        self.assertEqual(shadow["default_endpoint"], "weather")
        self.assertEqual(
            shadow["allowed_endpoints"],
            ["weather", "drivers", "starting_grid"],
        )
        drivers = shadow["drivers_mode"]
        self.assertEqual(drivers["raw_filename"], "drivers.response.json")
        self.assertEqual(drivers["request_parameters"], ["session_key"])
        self.assertTrue(drivers["requires_k4r6_validation"])
        self.assertFalse(drivers["persists_derived_csv"])
        self.assertFalse(drivers["derived_csv_is_source_evidence"])
        self.assertFalse(drivers["openf1_official_f1_roster_authority"])
        self.assertFalse(shadow["scheduled_enabled"])
        self.assertFalse(shadow["commit_or_push_enabled"])
        self.assertFalse(shadow["dr002_activated"])
        self.assertFalse(shadow["promotion_allowed"])

    def test_no_credentials_streaming_self_hosting_pipedream_or_dispatcher_dependency(self):
        combined = SCRIPT.read_text() + WORKFLOW.read_text() + POLICY.read_text()
        for forbidden in (
            "OPENF1_USERNAME", "OPENF1_PASSWORD", "mqtt.openf1.org", "/token",
            "br-g/openf1", "websocket-client", "paho-mqtt", "Pipedream",
            "external_dispatcher", "paid_access",
        ):
            self.assertNotIn(forbidden, combined)

    def test_named_dependency_pins_are_preserved_except_authorized_modifications(self):
        for path, expected in DEPENDENCY_BLOBS.items():
            if path in MODIFIED_DEPENDENCIES:
                result = subprocess.run(
                    ["git", "cat-file", "-e", f"{expected}^{{blob}}"],
                    cwd=ROOT, check=False, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                result = subprocess.run(
                    ["git", "hash-object", path], cwd=ROOT, check=True,
                    capture_output=True, text=True,
                )
                self.assertEqual(result.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
