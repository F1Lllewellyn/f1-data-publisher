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
    import requests  # noqa: F401 - workflow dependency when installed
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("real network is forbidden in focused tests")

    requests_stub.get = unexpected_network
    sys.modules["requests"] = requests_stub
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("openf1_starting_grid_shadow", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


DEPENDENCY_BLOBS = {
    "scripts/openf1/publish_openf1_lightweight_source_closure.py":
        "f2e28d326255a48a48f873d101cd3e3e99955c1f",
    ".github/workflows/f1-openf1-lightweight-source-closure.yml":
        "c32bd7bb2f8a84d1bb4e8995be246c389418f512",
    "configs/openf1/openf1_lightweight_source_closure_policy.json":
        "f386d8b6dd7025b313a1ea082ef699c4b1bd2e7c",
    "tests/test_openf1_lightweight_source_closure_provenance_shadow_v1.py":
        "bbe623a48322d273990dd34d05fedf133f1af828",
    "tests/test_openf1_lightweight_source_closure_drivers_provenance_shadow_v1.py":
        "97d3e8f2cfb8786410f13cb7fac40c11b1a91ee8",
    "scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py":
        "e68fa528cd73cd5c72afd97622a00d6e5b29be19",
    "scripts/forecast_bundles/dr002_openf1_starting_grid_producer_adapter_v1.py":
        "6c435ccaa03515f3d8d9c6aa88bc9070cfe824be",
    "scripts/forecast_bundles/dr002_openf1_drivers_producer_adapter_v1.py":
        "357ac56a6cfe317e21d9ce71d78c58683e444a5a",
    "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
        "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
}
MODIFIED = {
    "scripts/openf1/publish_openf1_lightweight_source_closure.py",
    ".github/workflows/f1-openf1-lightweight-source-closure.yml",
    "configs/openf1/openf1_lightweight_source_closure_policy.json",
}


class Response:
    def __init__(self, status_code, content, url, *, history=None, headers=None):
        self.status_code = status_code
        self.content = content
        self.url = url
        self.history = [] if history is None else history
        self.headers = {"Content-Type": "application/json"} if headers is None else headers


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


DISCOVERY_URI = "https://api.openf1.org/v1/sessions?year=2026"
GRID_URI = "https://api.openf1.org/v1/starting_grid?session_key=11442"


def session_bytes(**changes):
    row = {
        "session_key": 11442,
        "meeting_key": 1279,
        "year": 2026,
        "country_name": "Australia",
        "location": "Melbourne",
        "circuit_short_name": "Melbourne",
        "session_name": "Race",
        "session_type": "Race",
        "date_end": "2026-03-08T06:00:00Z",
    }
    row.update(changes)
    return json.dumps([row], separators=(",", ":")).encode()


GRID_ROWS = [
    {"position": 1, "driver_number": 44, "lap_duration": 75.1,
     "meeting_key": 1279, "session_key": 11442},
    {"position": 2, "driver_number": 16, "lap_duration": None,
     "meeting_key": 1279, "session_key": 11442},
]
GRID_BYTES = json.dumps(GRID_ROWS, separators=(",", ":")).encode()


class StartingGridProvenanceShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output_root = Path(self.temp.name)

    def options(self, **changes):
        getter = SequencedGet([
            Response(200, session_bytes(), DISCOVERY_URI),
            Response(200, GRID_BYTES, GRID_URI),
        ])
        options = {
            "session_key": "11442",
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
            "run_id": "247",
            "run_attempt": "1",
            "endpoint": "starting_grid",
            "http_get": getter,
            "clock": Clock([
                "2026-10-09T12:00:00Z",
                "2026-10-09T12:00:01Z",
                "2026-10-09T12:00:02Z",
                "2026-10-09T12:00:03Z",
                "2026-10-09T12:00:04Z",
            ]),
        }
        options.update(changes)
        return options, getter

    def run_valid(self, **changes):
        options, getter = self.options(**changes)
        return m.run_provenance_shadow(**options), getter

    def runtime_root(self):
        return (self.output_root / "_runtime" / m.SHADOW_RUNTIME_DIR
                / "gha-247-1")

    # 1
    def test_valid_shadow_writes_exact_six_file_package(self):
        manifest, _ = self.run_valid()
        self.assertEqual(manifest["status"], m.historical_rest_contract.VALIDATED)
        self.assertEqual({path.name for path in self.runtime_root().iterdir()}, {
            "sessions.response.json", "starting_grid.response.json",
            "source_capture_receipt.json",
            "historical_rest_capture_assessment.json", "shadow_manifest.json",
            "shadow_report.md",
        })

    # 2
    def test_exactly_one_discovery_and_one_grid_request(self):
        manifest, getter = self.run_valid()
        self.assertEqual([call[0] for call in getter.calls], [DISCOVERY_URI, GRID_URI])
        self.assertEqual(manifest["canonical_request_uri"], GRID_URI)
        for _, kwargs in getter.calls:
            self.assertEqual(kwargs, {
                "timeout": m.REQUEST_TIMEOUT,
                "headers": {"Accept": "application/json", "Accept-Encoding": "identity"},
                "allow_redirects": False,
            })

    # 3
    def test_discovery_bytes_are_persisted_read_back_hashed_and_observed(self):
        manifest, _ = self.run_valid()
        raw = (self.runtime_root() / "sessions.response.json").read_bytes()
        self.assertEqual(raw, session_bytes())
        self.assertEqual(manifest["session_discovery_request_uri"], DISCOVERY_URI)
        self.assertEqual(manifest["session_discovery_raw_sha256"],
                         hashlib.sha256(raw).hexdigest())
        self.assertEqual(manifest["session_discovery_actual_received_utc"],
                         "2026-10-09T12:00:00Z")

    # 4
    def test_discovery_status_must_be_200(self):
        getter = SequencedGet([Response(503, b"[]", DISCOVERY_URI)])
        options, _ = self.options(http_get=getter)
        with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                    "session_discovery_http_status_not_200"):
            m.run_provenance_shadow(**options)
        self.assertEqual(len(getter.calls), 1)

    # 5
    def test_both_final_urls_must_be_exact(self):
        cases = (
            [Response(200, session_bytes(), DISCOVERY_URI + "#x")],
            [Response(200, session_bytes(), DISCOVERY_URI),
             Response(200, GRID_BYTES, GRID_URI + "&driver_number=44")],
        )
        for responses in cases:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            options, _ = self.options(
                output_root=Path(alternate.name), http_get=SequencedGet(responses)
            )
            with self.assertRaisesRegex(m.ProvenanceShadowHold, "final_url_mismatch"):
                m.run_provenance_shadow(**options)

    # 6
    def test_redirects_are_forbidden_for_both_requests(self):
        for first in (True, False):
            responses = [
                Response(200, session_bytes(), DISCOVERY_URI,
                         history=[object()] if first else []),
                Response(200, GRID_BYTES, GRID_URI,
                         history=[] if first else [object()]),
            ]
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            options, _ = self.options(
                output_root=Path(alternate.name), http_get=SequencedGet(responses)
            )
            with self.assertRaisesRegex(m.ProvenanceShadowHold, "redirect_forbidden"):
                m.run_provenance_shadow(**options)

    # 7
    def test_exposed_content_type_must_be_json_case_insensitively(self):
        good = SequencedGet([
            Response(200, session_bytes(), DISCOVERY_URI,
                     headers={"content-type": "application/json; charset=utf-8"}),
            Response(200, GRID_BYTES, GRID_URI, headers={}),
        ])
        options, _ = self.options(http_get=good)
        m.run_provenance_shadow(**options)
        alternate = tempfile.TemporaryDirectory()
        self.addCleanup(alternate.cleanup)
        bad = SequencedGet([
            Response(200, session_bytes(), DISCOVERY_URI),
            Response(200, GRID_BYTES, GRID_URI, headers={"Content-Type": "text/html"}),
        ])
        options, _ = self.options(output_root=Path(alternate.name), http_get=bad)
        with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                    "starting_grid_content_type_not_json"):
            m.run_provenance_shadow(**options)

    # 8
    def test_discovery_response_is_nonempty_bytes_and_at_most_8_mib(self):
        for content in (b"", b"x" * (m.SHADOW_MAX_RESPONSE_BYTES + 1), "[]"):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([Response(200, content, DISCOVERY_URI)])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.assertRaises(m.ProvenanceShadowHold):
                m.run_provenance_shadow(**options)

    # 9
    def test_grid_response_is_nonempty_bytes_and_at_most_8_mib(self):
        for content in (b"", b"x" * (m.SHADOW_MAX_RESPONSE_BYTES + 1), "[]"):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([
                Response(200, session_bytes(), DISCOVERY_URI),
                Response(200, content, GRID_URI),
            ])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.assertRaises(m.ProvenanceShadowHold):
                m.run_provenance_shadow(**options)

    # 10
    def test_discovery_json_must_be_strict_list(self):
        for content in (b"{}", b"[", b'[{"session_key":11442,"session_key":11442}]',
                        b'[{"session_key":NaN}]'):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([Response(200, content, DISCOVERY_URI)])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                        "malformed_session_discovery_response"):
                m.run_provenance_shadow(**options)
            self.assertEqual(len(getter.calls), 1)

    # 11
    def test_selected_session_must_be_unique(self):
        row = json.loads(session_bytes())[0]
        for rows in ([], [row, dict(row)]):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            raw = json.dumps(rows, separators=(",", ":")).encode()
            getter = SequencedGet([Response(200, raw, DISCOVERY_URI)])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                        "selected_session_not_unique"):
                m.run_provenance_shadow(**options)

    # 12
    def test_every_discovery_row_must_have_canonical_positive_session_key(self):
        row = json.loads(session_bytes())[0]
        raw = json.dumps([row, {"session_key": True}], separators=(",", ":")).encode()
        getter = SequencedGet([Response(200, raw, DISCOVERY_URI)])
        options, _ = self.options(http_get=getter)
        with self.assertRaisesRegex(m.ProvenanceShadowHold, "malformed_session_metadata"):
            m.run_provenance_shadow(**options)
        self.assertEqual(len(getter.calls), 1)

    # 13
    def test_selected_session_name_and_type_must_both_be_exact_race(self):
        for changes in ({"session_name": "race"}, {"session_type": "Sprint"},
                        {"session_name": None}, {"session_type": "Race "}):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([
                Response(200, session_bytes(**changes), DISCOVERY_URI)
            ])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                        "selected_session_not_race"):
                m.run_provenance_shadow(**options)

    # 14
    def test_selected_session_year_ids_and_completed_end_are_required(self):
        cases = ({"year": 2025}, {"meeting_key": 0}, {"date_end": None},
                 {"date_end": "2026-03-08T06:00:00"})
        for changes in cases:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([
                Response(200, session_bytes(**changes), DISCOVERY_URI)
            ])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.assertRaises(m.ProvenanceShadowHold):
                m.run_provenance_shadow(**options)

    # 15
    def test_historical_window_gate_precedes_grid_request(self):
        getter = SequencedGet([Response(200, session_bytes(), DISCOVERY_URI)])
        options, _ = self.options(
            http_get=getter,
            clock=Clock(["2026-03-08T06:29:59Z", "2026-03-08T06:29:59Z"]),
        )
        with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                    "selected_session_before_historical_window"):
            m.run_provenance_shadow(**options)
        self.assertEqual(len(getter.calls), 1)

    # 16
    def test_capture_clocks_are_utc_and_monotonic(self):
        options, _ = self.options(clock=Clock([
            "2026-10-09T12:00:00Z", "2026-10-09T12:00:01Z",
            "2026-10-09T11:59:59Z", "2026-10-09T12:00:03Z",
            "2026-10-09T12:00:04Z",
        ]))
        with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                    "shadow_clock_chronology_invalid"):
            m.run_provenance_shadow(**options)

    # 17
    def test_exact_grid_bytes_readback_hash_and_observation_order(self):
        events = []

        class GridResponse(Response):
            def __init__(self):
                super().__init__(200, GRID_BYTES, GRID_URI)

            @property
            def content(self):
                events.append("complete_grid_bytes")
                return self._content

            @content.setter
            def content(self, value):
                self._content = value

        getter = SequencedGet([
            Response(200, session_bytes(), DISCOVERY_URI), GridResponse()
        ])
        options, _ = self.options(
            http_get=getter,
            clock=Clock([
                "2026-10-09T12:00:00Z", "2026-10-09T12:00:01Z",
                "2026-10-09T12:00:02Z", "2026-10-09T12:00:03Z",
                "2026-10-09T12:00:04Z",
            ], events=events),
        )
        manifest = m.run_provenance_shadow(**options)
        raw = (self.runtime_root() / "starting_grid.response.json").read_bytes()
        self.assertEqual(raw, GRID_BYTES)
        self.assertEqual(manifest["raw_response_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertLess(events.index("complete_grid_bytes"), events.index("clock", 2))

    # 18
    def test_unchanged_k4r1_receives_exact_grid_capture(self):
        calls = []

        def assessor(**kwargs):
            calls.append(kwargs)
            return m.historical_rest_contract.assess_openf1_historical_rest_capture(**kwargs)

        self.run_valid(assessor=assessor)
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["endpoint"], "starting_grid")
        self.assertEqual(call["request_params"], {"session_key": "11442"})
        self.assertEqual(call["raw_response_bytes"], GRID_BYTES)
        self.assertEqual(call["session_end_utc"], "2026-03-08T06:00:00Z")

    # 19
    def test_receipt_is_canonical_parentless_and_exactly_bound(self):
        manifest, _ = self.run_valid()
        receipt_bytes = (self.runtime_root() / "source_capture_receipt.json").read_bytes()
        receipt = json.loads(receipt_bytes)
        self.assertEqual(
            m.historical_rest_contract.receipt_contract.canonical_json_bytes(receipt),
            receipt_bytes,
        )
        self.assertEqual(receipt["parent_receipt_ids"], [])
        self.assertEqual(receipt["payload"]["source_uri"], GRID_URI)
        self.assertEqual(receipt["payload"]["source_sha256"],
                         manifest["raw_response_sha256"])

    # 20
    def test_unchanged_k4r14_receives_readback_bytes_and_race_assertion(self):
        calls = []

        def adapter(**kwargs):
            calls.append(kwargs)
            return m.starting_grid_adapter_contract.adapt_openf1_starting_grid_to_producer_input(
                **kwargs
            )

        manifest, _ = self.run_valid(starting_grid_adapter=adapter)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["session_kind"], "Race")
        self.assertEqual(calls[0]["raw_starting_grid_response_bytes"], GRID_BYTES)
        self.assertEqual(manifest["k4r14_status"],
                         m.starting_grid_adapter_contract.VALIDATED)
        self.assertEqual(manifest["starting_grid_row_count"], 2)

    # 21
    def test_k4r1_and_k4r14_holds_propagate_without_false_csv_success(self):
        def holding_assessor(**_kwargs):
            return {"status": m.historical_rest_contract.HOLD,
                    "reason_codes": ["synthetic_k4r1_hold"]}

        def holding_adapter(**_kwargs):
            return {"status": m.starting_grid_adapter_contract.HOLD,
                    "reason_codes": ["synthetic_k4r14_hold"]}

        for changes, reason in (({"assessor": holding_assessor}, "k4r1_hold"),
                                ({"starting_grid_adapter": holding_adapter}, "k4r14_hold")):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            options, _ = self.options(output_root=Path(alternate.name), **changes)
            with self.assertRaisesRegex(m.ProvenanceShadowHold, reason):
                m.run_provenance_shadow(**options)
            self.assertFalse(any(Path(alternate.name).rglob("*.csv")))
            manifest_path = next(Path(alternate.name).rglob("shadow_manifest.json"))
            self.assertEqual(json.loads(manifest_path.read_bytes())["status"],
                             m.historical_rest_contract.HOLD)

    # 22
    def test_manifest_records_unbound_adapter_metadata_and_all_claim_ceilings(self):
        manifest, _ = self.run_valid()
        self.assertEqual(manifest["session_metadata_source_type"],
                         "OPENF1_PROVIDER_DISCOVERY_CLAIM")
        self.assertEqual(manifest["race_session_name"], "Race")
        self.assertEqual(manifest["race_session_type"], "Race")
        self.assertTrue(manifest["race_session_name_asserted"])
        self.assertTrue(manifest["race_session_type_asserted"])
        self.assertEqual(manifest["discovery_response_sha256"],
                         manifest["session_discovery_raw_sha256"])
        self.assertEqual(manifest["starting_grid_raw_sha256"],
                         manifest["raw_response_sha256"])
        self.assertRegex(manifest["starting_grid_derived_csv_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            manifest["starting_grid_derived_runtime_identity"],
            "derived:openf1-starting-grid-csv:"
            + manifest["starting_grid_derived_csv_sha256"],
        )
        for flag in m.starting_grid_adapter_contract.CLAIM_CEILINGS:
            self.assertIs(manifest[flag], False)
        self.assertEqual(manifest["frozen_evidence_binding_status"], "UNBOUND")
        self.assertEqual(manifest["grid_row_count"], 2)
        self.assertEqual(manifest["unique_driver_count"], 2)
        self.assertEqual(manifest["slot_count"], 2)
        self.assertFalse(manifest["commercial_or_redistribution_permission_claimed"])
        self.assertFalse(manifest["derived_csv_persisted"])

    # 23
    def test_no_csv_latest_history_credentials_or_repository_mutation(self):
        manifest, _ = self.run_valid()
        self.assertFalse(any(self.output_root.rglob("*.csv")))
        self.assertFalse((self.output_root / "latest").exists())
        self.assertFalse((self.output_root / "history").exists())
        self.assertFalse(manifest["latest_or_history_written"])
        self.assertFalse(manifest["repository_mutation_performed"])
        text = SCRIPT.read_text() + WORKFLOW.read_text() + POLICY.read_text()
        self.assertNotIn("OPENF1_USERNAME", text)
        self.assertNotIn("OPENF1_PASSWORD", text)

    # 24
    def test_cli_starting_grid_requires_nonempty_explicit_key_before_legacy(self):
        with mock.patch.object(m, "run_provenance_shadow",
                               side_effect=AssertionError("shadow must not run")), \
             mock.patch.object(m, "load_policy",
                               side_effect=AssertionError("legacy must not run")), \
             mock.patch.object(sys, "argv", [
                 str(SCRIPT), "--output-root", str(self.output_root),
                 "--provenance-shadow-endpoint", "starting_grid",
                 "--provenance-shadow-session-key", "",
             ]):
            self.assertEqual(m.main(), 1)
        self.assertEqual(list(self.output_root.iterdir()), [])

    # 25
    def test_workflow_adds_choice_precheckout_guard_and_distinct_artifact(self):
        text = WORKFLOW.read_text()
        self.assertIn("- starting_grid", text)
        checkout = text.index("- name: Checkout repository")
        self.assertLess(text.index("Reject unsupported provenance shadow endpoint"), checkout)
        self.assertLess(text.index("Reject starting-grid shadow without explicit session"),
                        checkout)
        self.assertIn("dr002-pre2b7k4r15-openf1-starting-grid-historical-shadow", text)
        self.assertIn("github.ref != 'refs/heads/main'", text)
        self.assertIn("persist-credentials:", text)

    # 26
    def test_policy_declares_bounded_manual_starting_grid_mode(self):
        mode = json.loads(POLICY.read_bytes())["provenance_shadow"]
        self.assertEqual(mode["allowed_endpoints"],
                         ["weather", "drivers", "starting_grid"])
        grid = mode["starting_grid_mode"]
        self.assertTrue(grid["manual_only"])
        self.assertEqual(grid["maximum_response_bytes"], 8 * 1024 * 1024)
        self.assertEqual(grid["required_session_name"], "Race")
        self.assertEqual(grid["required_session_type"], "Race")
        self.assertTrue(grid["requires_k4r1_validation"])
        self.assertTrue(grid["requires_k4r14_validation"])
        self.assertFalse(grid["persists_derived_csv"])

    # 27
    def test_grid_http_errors_hold_without_retry(self):
        for status in (400, 403, 404, 429, 500, 503):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([
                Response(200, session_bytes(), DISCOVERY_URI),
                Response(status, b"[]", GRID_URI),
            ])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.subTest(status=status), self.assertRaisesRegex(
                m.ProvenanceShadowHold, "starting_grid_http_status_not_200"
            ):
                m.run_provenance_shadow(**options)
            self.assertEqual(len(getter.calls), 2)

    # 28
    def test_malformed_duplicate_and_holey_grid_rows_hold_without_retry(self):
        malformed_rows = (
            b"[",
            json.dumps([GRID_ROWS[0], GRID_ROWS[0]], separators=(",", ":")).encode(),
            json.dumps([
                GRID_ROWS[0], {**GRID_ROWS[1], "position": 3}
            ], separators=(",", ":")).encode(),
        )
        for raw in malformed_rows:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([
                Response(200, session_bytes(), DISCOVERY_URI),
                Response(200, raw, GRID_URI),
            ])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.assertRaises(m.ProvenanceShadowHold):
                m.run_provenance_shadow(**options)
            self.assertEqual(len(getter.calls), 2)
            self.assertFalse(any(Path(alternate.name).rglob("*.csv")))

    # 29
    def test_discovery_and_grid_readback_failures_hold(self):
        for filename in ("sessions.response.json", "starting_grid.response.json"):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)

            def reader(path, target=filename):
                return b"changed" if path.name == target else path.read_bytes()

            options, _ = self.options(
                output_root=Path(alternate.name), read_bytes=reader
            )
            with self.subTest(filename=filename), self.assertRaisesRegex(
                m.ProvenanceShadowHold, "readback_mismatch"
            ):
                m.run_provenance_shadow(**options)
            self.assertFalse(any(Path(alternate.name).rglob("*.csv")))

    # 30
    def test_wrong_k4r1_source_hash_and_k4r14_binding_hold(self):
        def bad_assessor(**kwargs):
            result = m.historical_rest_contract.assess_openf1_historical_rest_capture(
                **kwargs
            )
            result["raw_response_sha256"] = "0" * 64
            return result

        def bad_adapter(**kwargs):
            result = m.starting_grid_adapter_contract.adapt_openf1_starting_grid_to_producer_input(
                **kwargs
            )
            result["raw_source_id"] = "openf1:starting_grid:" + "0" * 64
            return result

        for changes, reason in (({"assessor": bad_assessor}, "k4r1_raw_response_hash_mismatch"),
                                ({"starting_grid_adapter": bad_adapter},
                                 "k4r14_raw_source_id_mismatch")):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            options, _ = self.options(output_root=Path(alternate.name), **changes)
            with self.assertRaisesRegex(m.ProvenanceShadowHold, reason):
                m.run_provenance_shadow(**options)

    # 31
    def test_future_race_holds_before_grid_get(self):
        getter = SequencedGet([
            Response(200, session_bytes(date_end="2027-03-08T06:00:00Z"), DISCOVERY_URI)
        ])
        options, _ = self.options(http_get=getter)
        with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                    "selected_session_before_historical_window"):
            m.run_provenance_shadow(**options)
        self.assertEqual(len(getter.calls), 1)

    # 32
    def test_invalid_endpoint_holds_before_network_or_output(self):
        for endpoint in ("grid", "STARTING_GRID", "", None, 1):
            options, getter = self.options(endpoint=endpoint)
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(
                m.ProvenanceShadowHold, "provenance_shadow_endpoint_unsupported"
            ):
                m.run_provenance_shadow(**options)
            self.assertEqual(getter.calls, [])
            self.assertFalse((self.output_root / "_runtime").exists())

    # 33
    def test_injected_writer_observes_only_six_success_members(self):
        written = []

        def writer(path, data):
            written.append(path.name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        self.run_valid(write_bytes=writer)
        self.assertEqual(written, [
            "sessions.response.json", "starting_grid.response.json",
            "source_capture_receipt.json",
            "historical_rest_capture_assessment.json", "shadow_manifest.json",
            "shadow_report.md",
        ])

    # 34
    def test_all_exact_dependency_pins_are_preserved(self):
        for path, expected in DEPENDENCY_BLOBS.items():
            with self.subTest(path=path):
                if path in MODIFIED:
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
