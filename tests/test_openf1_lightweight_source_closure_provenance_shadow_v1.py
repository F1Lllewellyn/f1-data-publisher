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
spec = importlib.util.spec_from_file_location("openf1_lightweight_source_closure", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


BASE_DEPENDENCY_BLOBS = {
    "scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py":
        "e68fa528cd73cd5c72afd97622a00d6e5b29be19",
    "tests/test_dr002_openf1_historical_rest_capture_v1.py":
        "b67ec9ab6ab749e3903f781eca07199285dd144d",
    "scripts/openf1/publish_openf1_lightweight_source_closure.py":
        "ebdba37477b7efdc584c2550295cb7c61cf53481",
    ".github/workflows/f1-openf1-lightweight-source-closure.yml":
        "7521e0e91e201b0610d8771a8524393c59ba1ecb",
    "configs/openf1/openf1_lightweight_source_closure_policy.json":
        "d21765b33e66dfa499b92c9f44a4543608f2c6a4",
    "scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py":
        "b9b1f9acc1be30d5b7cdf42424853e3d652b9466",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
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


def session_rows(*, duplicate=False, date_end="2026-10-07T14:00:00Z"):
    row = {
        "session_key": 11371,
        "meeting_key": 1295,
        "year": 2026,
        "country_name": "Azerbaijan",
        "location": "Baku",
        "circuit_short_name": "Baku",
        "date_end": date_end,
    }
    rows = [row]
    if duplicate:
        rows.append(dict(row))
    return json.dumps(rows, separators=(",", ":")).encode()


WEATHER_BYTES = b'[ {"meeting_key":1295,"session_key":11371,"air_temperature":23.4} ]\n'


class SourceClosureProvenanceShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output_root = Path(self.temp.name)

    def valid_options(self, **changes):
        getter = SequencedGet([
            Response(200, session_rows()),
            Response(200, WEATHER_BYTES),
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
            "run_id": "210",
            "run_attempt": "1",
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
        options, getter = self.valid_options(**changes)
        return m.run_provenance_shadow(**options), getter

    def runtime_root(self, run_id="210", attempt="1"):
        return (self.output_root / "_runtime" / m.SHADOW_RUNTIME_DIR
                / f"gha-{run_id}-{attempt}")

    def test_valid_shadow_writes_exact_required_runtime_package(self):
        manifest, _ = self.run_valid()
        self.assertEqual(manifest["status"], m.historical_rest_contract.VALIDATED)
        self.assertEqual(
            {path.name for path in self.runtime_root().iterdir()},
            {
                "weather.response.json",
                "source_capture_receipt.json",
                "historical_rest_capture_assessment.json",
                "shadow_manifest.json",
                "shadow_report.md",
            },
        )

    def test_exact_single_session_selection_or_hold(self):
        for body in (b"[]", session_rows(duplicate=True)):
            with self.subTest(body=body):
                alternate = tempfile.TemporaryDirectory()
                self.addCleanup(alternate.cleanup)
                getter = SequencedGet([Response(200, body)])
                options, _ = self.valid_options(output_root=Path(alternate.name), http_get=getter)
                with self.assertRaisesRegex(m.ProvenanceShadowHold, "selected_session_not_unique"):
                    m.run_provenance_shadow(**options)
                self.assertEqual(len(getter.calls), 1)

    def test_malformed_or_incomplete_session_metadata_holds_before_weather(self):
        invalid = json.dumps([{"session_key": 11371, "meeting_key": 1295}]).encode()
        getter = SequencedGet([Response(200, invalid)])
        options, _ = self.valid_options(http_get=getter)
        with self.assertRaisesRegex(m.ProvenanceShadowHold, "malformed_session_metadata"):
            m.run_provenance_shadow(**options)
        self.assertEqual(len(getter.calls), 1)

    def test_requires_session_end_plus_1800_seconds_before_weather(self):
        getter = SequencedGet([Response(200, session_rows())])
        options, _ = self.valid_options(
            http_get=getter,
            clock=Clock(["2026-10-07T14:29:59.999999Z"]),
        )
        with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                    "selected_session_before_historical_window"):
            m.run_provenance_shadow(**options)
        self.assertEqual(len(getter.calls), 1)

    def test_baku_event_id_regression_is_exact(self):
        manifest, _ = self.run_valid()
        self.assertEqual(manifest["event_id"], "2026_1295_azerbaijan_baku_baku")
        self.assertEqual(manifest["meeting_id"], "1295")
        self.assertEqual(manifest["session_id"], "11371")

    def test_exact_discovery_and_weather_request_uris(self):
        manifest, getter = self.run_valid()
        self.assertEqual([call[0] for call in getter.calls], [
            "https://api.openf1.org/v1/sessions?year=2026",
            "https://api.openf1.org/v1/weather?session_key=11371",
        ])
        self.assertEqual(manifest["canonical_request_uri"], getter.calls[1][0])
        for _, kwargs in getter.calls:
            self.assertEqual(kwargs["timeout"], m.REQUEST_TIMEOUT)
            self.assertEqual(kwargs["headers"]["Accept-Encoding"], "identity")

    def test_exact_response_bytes_readback_and_hash_are_bound(self):
        manifest, _ = self.run_valid()
        raw = (self.runtime_root() / "weather.response.json").read_bytes()
        self.assertEqual(raw, WEATHER_BYTES)
        self.assertEqual(manifest["raw_response_sha256"], hashlib.sha256(raw).hexdigest())

    def test_readback_mismatch_holds_before_k4r1(self):
        options, _ = self.valid_options(
            read_bytes=lambda path: b"changed" if path.name == "weather.response.json"
            else path.read_bytes()
        )
        with self.assertRaisesRegex(m.ProvenanceShadowHold, "raw_response_readback_mismatch"):
            m.run_provenance_shadow(**options)
        self.assertFalse((self.runtime_root() / "source_capture_receipt.json").exists())

    def test_first_observed_clock_is_sampled_only_after_complete_bytes_exist(self):
        events = []

        class OrderedWeatherResponse:
            status_code = 200

            @property
            def content(self):
                events.append("complete_bytes")
                return WEATHER_BYTES

        getter = SequencedGet([Response(200, session_rows()), OrderedWeatherResponse()])
        options, _ = self.valid_options(
            http_get=getter,
            clock=Clock([
                "2026-10-07T14:30:00Z",
                "2026-10-07T14:30:01Z",
                "2026-10-07T14:30:02Z",
                "2026-10-07T14:30:03Z",
            ], events=events),
        )
        m.run_provenance_shadow(**options)
        self.assertLess(events.index("complete_bytes"), events.index("clock", 1))

    def test_calls_unchanged_k4r1_contract_with_exact_bytes_and_scope(self):
        calls = []

        def assessor(**kwargs):
            calls.append(kwargs)
            return m.historical_rest_contract.assess_openf1_historical_rest_capture(**kwargs)

        self.run_valid(assessor=assessor)
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["raw_response_bytes"], WEATHER_BYTES)
        self.assertEqual(call["request_params"], {"session_key": "11371"})
        self.assertEqual(call["event_id"], "2026_1295_azerbaijan_baku_baku")
        self.assertEqual(call["session_end_utc"], "2026-10-07T14:00:00Z")
        self.assertIs(assessor.__globals__["m"].historical_rest_contract,
                      m.historical_rest_contract)

    def test_k4r1_hold_propagates_and_no_receipt_success_is_written(self):
        def holding_assessor(**_kwargs):
            return {
                "status": m.historical_rest_contract.HOLD,
                "reason_codes": ["synthetic_hold"],
                "raw_response_bytes": WEATHER_BYTES,
                "source_capture_receipt_bytes": None,
            }

        options, _ = self.valid_options(assessor=holding_assessor)
        with self.assertRaisesRegex(m.ProvenanceShadowHold, "k4r1_hold:synthetic_hold"):
            m.run_provenance_shadow(**options)
        self.assertFalse((self.runtime_root() / "source_capture_receipt.json").exists())
        manifest = json.loads((self.runtime_root() / "shadow_manifest.json").read_bytes())
        self.assertEqual(manifest["status"], m.historical_rest_contract.HOLD)

    def test_validated_receipt_bytes_are_persisted_unchanged(self):
        captured = {}

        def assessor(**kwargs):
            result = m.historical_rest_contract.assess_openf1_historical_rest_capture(**kwargs)
            captured["bytes"] = result["source_capture_receipt_bytes"]
            return result

        self.run_valid(assessor=assessor)
        self.assertEqual(
            (self.runtime_root() / "source_capture_receipt.json").read_bytes(),
            captured["bytes"],
        )

    def test_manifest_binds_exact_raw_and_receipt_hashes_and_times(self):
        manifest, _ = self.run_valid()
        stored = json.loads((self.runtime_root() / "shadow_manifest.json").read_bytes())
        self.assertEqual(stored, manifest)
        self.assertEqual(stored["raw_response_sha256"], hashlib.sha256(WEATHER_BYTES).hexdigest())
        receipt_bytes = (self.runtime_root() / "source_capture_receipt.json").read_bytes()
        self.assertEqual(stored["receipt_sha256"], hashlib.sha256(receipt_bytes).hexdigest())
        self.assertEqual(stored["first_observed_utc"], "2026-10-07T14:30:01Z")
        self.assertEqual(stored["ingested_utc"], "2026-10-07T14:30:02Z")
        self.assertEqual(stored["receipt_created_utc"], "2026-10-07T14:30:03Z")
        self.assertEqual(stored["k4r1_status"], m.historical_rest_contract.VALIDATED)

    def test_no_verified_binding_or_new_receipt_type_is_created(self):
        manifest, _ = self.run_valid()
        assessment = json.loads(
            (self.runtime_root() / "historical_rest_capture_assessment.json").read_bytes()
        )
        receipt = json.loads((self.runtime_root() / "source_capture_receipt.json").read_bytes())
        self.assertNotIn("verified_receipt_bindings", assessment)
        self.assertNotIn("verified_receipt_bindings", receipt)
        self.assertEqual(receipt["receipt_type"], "source_capture")
        self.assertEqual(manifest["receipt_type"], "source_capture")
        self.assertFalse(manifest["verified_receipt_bindings_created"])

    def test_shadow_identity_is_main_only_and_exact(self):
        for changes, reason in (
            ({"ref": "refs/heads/feature"}, "shadow_requires_main"),
            ({"repository": "other/repo"}, "workflow_repository_mismatch"),
            ({"workflow": "Other"}, "workflow_name_mismatch"),
            ({"workflow_ref": "wrong"}, "workflow_ref_mismatch"),
            ({"head_sha": "bad"}, "workflow_head_sha_malformed"),
        ):
            with self.subTest(changes=changes):
                alternate = tempfile.TemporaryDirectory()
                self.addCleanup(alternate.cleanup)
                options, _ = self.valid_options(output_root=Path(alternate.name), **changes)
                with self.assertRaisesRegex(m.ProvenanceShadowHold, reason):
                    m.run_provenance_shadow(**options)

    def test_shadow_writes_only_runtime_and_never_latest_or_history(self):
        manifest, _ = self.run_valid()
        self.assertFalse((self.output_root / "latest").exists())
        self.assertFalse((self.output_root / "history").exists())
        self.assertFalse(manifest["latest_or_history_written"])
        self.assertFalse(manifest["repository_mutation_performed"])

    def test_empty_cli_shadow_input_uses_legacy_path(self):
        with mock.patch.object(m, "run_provenance_shadow",
                               side_effect=AssertionError("shadow must not run")), \
             mock.patch.object(m, "load_policy", return_value={}), \
             mock.patch.object(m, "get_sessions", return_value=m.pd.DataFrame()), \
             mock.patch.object(m, "LANES", []), \
             mock.patch.object(sys, "argv", [
                 str(SCRIPT), "--output-root", str(self.output_root),
                 "--provenance-shadow-session-key", "",
             ]):
            self.assertEqual(m.main(), 0)
        self.assertTrue((self.output_root / "latest/openf1_lightweight_source_closure").exists())
        self.assertTrue((self.output_root / "history/openf1_lightweight_source_closure").exists())

    def test_workflow_empty_and_scheduled_paths_remain_legacy(self):
        text = WORKFLOW.read_text()
        self.assertIn("schedule:", text)
        self.assertIn("provenance_shadow_session_key:", text)
        self.assertIn("default: ''", text)
        legacy_condition = (
            "github.event_name != 'workflow_dispatch' || "
            "github.event.inputs.provenance_shadow_session_key == ''"
        )
        self.assertGreaterEqual(text.count(legacy_condition), 2)

    def test_nonempty_workflow_shadow_has_no_commit_or_push_execution(self):
        text = WORKFLOW.read_text()
        commit_position = text.index("- name: Commit source closure outputs")
        commit_block = text[commit_position:]
        self.assertIn("github.event.inputs.provenance_shadow_session_key == ''", commit_block)
        self.assertIn("--provenance-shadow-session-key", text)
        self.assertIn("Upload historical REST provenance shadow artifact", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn(
            "persist-credentials: ${{ github.event_name != 'workflow_dispatch' || "
            "github.event.inputs.provenance_shadow_session_key == '' }}",
            text,
        )

    def test_no_credentials_live_streaming_or_self_hosting_is_added(self):
        combined = SCRIPT.read_text() + WORKFLOW.read_text() + POLICY.read_text()
        for forbidden in (
            "OPENF1_USERNAME", "OPENF1_PASSWORD", "mqtt.openf1.org", "/token",
            "br-g/openf1", "websocket-client", "paho-mqtt",
        ):
            self.assertNotIn(forbidden, combined)

    def test_policy_declares_manual_non_default_capability_and_claim_ceiling(self):
        policy = json.loads(POLICY.read_bytes())
        shadow = policy["provenance_shadow"]
        self.assertEqual(shadow["endpoint"], "weather")
        self.assertEqual(shadow["selected_session_count"], 1)
        self.assertEqual(shadow["historical_window_delay_seconds"], 1800)
        self.assertFalse(shadow["scheduled_enabled"])
        self.assertFalse(shadow["commit_or_push_enabled"])
        self.assertFalse(shadow["requires_credentials_or_paid_live_access"])
        self.assertFalse(shadow["dr002_activated"])
        self.assertFalse(shadow["promotion_allowed"])

    def test_all_work_order_dependency_blob_objects_are_present(self):
        for path, blob in BASE_DEPENDENCY_BLOBS.items():
            with self.subTest(path=path):
                result = subprocess.run(
                    ["git", "cat-file", "-e", f"{blob}^{{blob}}"],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_unmodified_dependency_blobs_still_match_work_order_pins(self):
        unchanged = (
            "scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py",
            "tests/test_dr002_openf1_historical_rest_capture_v1.py",
            "scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md",
        )
        for path in unchanged:
            with self.subTest(path=path):
                result = subprocess.run(
                    ["git", "hash-object", path], cwd=ROOT, check=True,
                    capture_output=True, text=True,
                )
                self.assertEqual(result.stdout.strip(), BASE_DEPENDENCY_BLOBS[path])


if __name__ == "__main__":
    unittest.main()
