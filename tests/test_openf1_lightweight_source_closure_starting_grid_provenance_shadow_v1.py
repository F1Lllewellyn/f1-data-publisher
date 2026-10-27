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
        "68ac7f83e4544576ae2e7074129071d95251e956",
    "tests/test_openf1_lightweight_source_closure_starting_grid_provenance_shadow_v1.py":
        "7b08a523c4df270c6c8fe367ed21804315f2a236",
    ".github/workflows/f1-openf1-lightweight-source-closure.yml":
        "d277ceaaffbb148dbde4b0c32bfbbcd8664e4329",
    "configs/openf1/openf1_lightweight_source_closure_policy.json":
        "6ebb40e5fd42623a769eba8ee4feab09765c4b00",
    "tests/test_openf1_lightweight_source_closure_provenance_shadow_v1.py":
        "bbe623a48322d273990dd34d05fedf133f1af828",
    "tests/test_openf1_lightweight_source_closure_drivers_provenance_shadow_v1.py":
        "68ef40e9caaadf8c096c362accfc54f3fa994937",
    "scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py":
        "e68fa528cd73cd5c72afd97622a00d6e5b29be19",
    "scripts/forecast_bundles/dr002_openf1_starting_grid_producer_adapter_v1.py":
        "702a1219c4b97450d7aeec16b5dd8409f2b73d75",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
}
MODIFIED = {
    "scripts/openf1/publish_openf1_lightweight_source_closure.py",
    "tests/test_openf1_lightweight_source_closure_starting_grid_provenance_shadow_v1.py",
}

HISTORICAL_WORKFLOW_BLOB = "d277ceaaffbb148dbde4b0c32bfbbcd8664e4329"
PREDECESSOR_WORKFLOW_BLOB = "6768b09449905cd61281386d6fc147f0fa18d01c"
SUCCESSOR_WORKFLOW_BLOB = "bf56b47b3325458384bbb60148e3bb65030c41e6"
PREDECESSOR_PUBLICATION_BLOCK = b'''      - name: Commit source closure outputs
        if: ${{ success() && (github.event_name != 'workflow_dispatch' || github.event.inputs.provenance_shadow_session_key == '') }}
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add latest/openf1_lightweight_source_closure history/openf1_lightweight_source_closure || true
          if git diff --cached --quiet; then
            echo "No source-closure changes to commit."
          else
            git commit -m "Update OpenF1 lightweight source closure artifacts"
            bash scripts/ops/safe_git_push_rebase_retry.sh


          fi
'''
SUCCESSOR_PUBLICATION_BLOCK = b'''      - name: Commit source closure outputs
        if: ${{ success() && (github.event_name != 'workflow_dispatch' || github.event.inputs.provenance_shadow_session_key == '') }}
        run: |
          set -euo pipefail
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          python scripts/ops/f1_source_closure_publish_guard_v1.py \\
            --repo-root "$GITHUB_WORKSPACE" \\
            --remote origin \\
            --branch "$GITHUB_REF_NAME" \\
            --expected-season "${{ github.event.inputs.season || '2026' }}" \\
            --expected-completed-only "${{ github.event.inputs.completed_only || 'true' }}" \\
            --github-run-id "$GITHUB_RUN_ID" \\
            --artifact-uploaded-for-run "$GITHUB_RUN_ID"
'''


def git_blob_bytes(blob_sha):
    return subprocess.run(
        ["git", "cat-file", "blob", blob_sha], cwd=ROOT, check=True,
        capture_output=True,
    ).stdout


def git_blob_sha(data):
    return subprocess.run(
        ["git", "hash-object", "--stdin"], cwd=ROOT, check=True,
        input=data, capture_output=True,
    ).stdout.decode().strip()


def assert_authorized_workflow_compatibility(testcase, workflow):
    historical = git_blob_bytes(HISTORICAL_WORKFLOW_BLOB)
    predecessor = git_blob_bytes(PREDECESSOR_WORKFLOW_BLOB)
    successor = git_blob_bytes(SUCCESSOR_WORKFLOW_BLOB)

    testcase.assertEqual(git_blob_sha(historical), HISTORICAL_WORKFLOW_BLOB)
    testcase.assertEqual(git_blob_sha(predecessor), PREDECESSOR_WORKFLOW_BLOB)
    testcase.assertEqual(git_blob_sha(successor), SUCCESSOR_WORKFLOW_BLOB)
    testcase.assertEqual(DEPENDENCY_BLOBS[str(WORKFLOW.relative_to(ROOT))],
                         HISTORICAL_WORKFLOW_BLOB)
    testcase.assertEqual(predecessor.count(PREDECESSOR_PUBLICATION_BLOCK), 1)
    testcase.assertEqual(predecessor.count(SUCCESSOR_PUBLICATION_BLOCK), 0)
    testcase.assertEqual(successor.count(PREDECESSOR_PUBLICATION_BLOCK), 0)
    testcase.assertEqual(successor.count(SUCCESSOR_PUBLICATION_BLOCK), 1)
    testcase.assertEqual(
        successor.replace(SUCCESSOR_PUBLICATION_BLOCK,
                          PREDECESSOR_PUBLICATION_BLOCK, 1),
        predecessor,
    )

    active_blob = git_blob_sha(workflow)
    testcase.assertIn(active_blob, {
        PREDECESSOR_WORKFLOW_BLOB, SUCCESSOR_WORKFLOW_BLOB,
    })
    testcase.assertEqual(
        workflow,
        predecessor if active_blob == PREDECESSOR_WORKFLOW_BLOB else successor,
    )
    return active_blob


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
GRID_URI = "https://api.openf1.org/v1/starting_grid?session_key=11230"


def session_bytes(*, target_changes=None, extra_rows=None, **changes):
    source = {
        "session_key": 11230,
        "meeting_key": 1279,
        "year": 2026,
        "country_name": "Australia",
        "location": "Melbourne",
        "circuit_short_name": "Melbourne",
        "session_name": "Qualifying",
        "session_type": "Qualifying",
        "date_start": "2026-03-07T05:00:00Z",
        "date_end": "2026-03-07T06:00:00Z",
    }
    target = {
        "session_key": 11234,
        "meeting_key": 1279,
        "year": 2026,
        "country_name": "Australia",
        "location": "Melbourne",
        "circuit_short_name": "Melbourne",
        "session_name": "Race",
        "session_type": "Race",
        "date_start": "2026-03-08T04:00:00Z",
        "date_end": "2026-03-08T06:00:00Z",
    }
    source.update(changes)
    target.update(target_changes or {})
    rows = [source, target]
    rows.extend(extra_rows or [])
    return json.dumps(rows, separators=(",", ":")).encode()


GRID_ROWS = [
    {"position": 1, "driver_number": 44, "lap_duration": 75.1,
     "meeting_key": 1279, "session_key": 11230},
    {"position": 2, "driver_number": 16, "lap_duration": None,
     "meeting_key": 1279, "session_key": 11230},
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
            "session_key": "11230",
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

    def persisted_diagnostics(self, output_root=None):
        root = (Path(output_root or self.output_root) / "_runtime"
                / m.SHADOW_RUNTIME_DIR / "gha-247-1")
        manifest = json.loads((root / "shadow_manifest.json").read_bytes())
        assessment = json.loads(
            (root / "historical_rest_capture_assessment.json").read_bytes()
        )
        report = (root / "shadow_report.md").read_text()
        return root, manifest, assessment, report

    # 1
    def test_valid_shadow_writes_exact_six_file_package(self):
        manifest, _ = self.run_valid()
        self.assertEqual(manifest["status"], m.historical_rest_contract.VALIDATED)
        self.assertTrue(manifest["session_discovery_request_attempted"])
        self.assertEqual(manifest["session_discovery_http_status_code"], 200)
        self.assertTrue(manifest["starting_grid_request_attempted"])
        self.assertEqual(manifest["starting_grid_http_status_code"], 200)
        self.assertEqual({path.name for path in self.runtime_root().iterdir()}, {
            "sessions.response.json", "starting_grid.response.json",
            "source_capture_receipt.json",
            "historical_rest_capture_assessment.json", "shadow_manifest.json",
            "shadow_report.md",
        })
        report = (self.runtime_root() / "shadow_report.md").read_text()
        self.assertIn("The raw sessions discovery links", report)
        self.assertNotIn("No raw session-discovery data was accepted", report)

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
        for status in (429, 403, 404, 500, 503):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([Response(status, b"[]", DISCOVERY_URI)])
            options, _ = self.options(
                output_root=Path(alternate.name), http_get=getter
            )
            with self.subTest(status=status), self.assertRaisesRegex(
                m.ProvenanceShadowHold, "session_discovery_http_status_not_200"
            ):
                m.run_provenance_shadow(**options)
            root, manifest, assessment, report = self.persisted_diagnostics(
                alternate.name
            )
            self.assertEqual(len(getter.calls), 1)
            self.assertEqual({path.name for path in root.iterdir()}, {
                "historical_rest_capture_assessment.json",
                "shadow_manifest.json",
                "shadow_report.md",
            })
            self.assertEqual(manifest["status"], m.historical_rest_contract.HOLD)
            self.assertTrue(manifest["session_discovery_request_attempted"])
            self.assertEqual(manifest["session_discovery_http_status_code"], status)
            self.assertFalse(manifest["starting_grid_request_attempted"])
            self.assertIsNone(manifest["starting_grid_http_status_code"])
            self.assertIsNone(manifest["session_discovery_raw_sha256"])
            self.assertIsNone(manifest["grid_source_session_id"])
            self.assertIsNone(manifest["grid_source_session_kind"])
            self.assertIsNone(manifest["grid_target_race_session_id"])
            self.assertIsNone(manifest["grid_target_race_session_kind"])
            self.assertIsNone(manifest["source_to_race_link_evidence_type"])
            self.assertEqual(
                assessment["reason_codes"],
                ["session_discovery_http_status_not_200"],
            )
            self.assertIn(
                "No raw session-discovery data was accepted; no source-to-Race link was established.",
                report,
            )
            self.assertNotIn("The raw sessions discovery links", report)

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
        for content in (b"{}", b"[", b'[{"session_key":11230,"session_key":11230}]',
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
    def test_selected_source_name_and_type_must_both_be_exact_qualifying(self):
        for changes in ({"session_name": "Sprint Qualifying"},
                        {"session_type": "Sprint"}, {"session_name": "Race"},
                        {"session_name": "Practice 2"}, {"session_name": None},
                        {"session_type": "Qualifying "}):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([
                Response(200, session_bytes(**changes), DISCOVERY_URI)
            ])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.assertRaisesRegex(m.ProvenanceShadowHold,
                                        "selected_grid_source_not_qualifying"):
                m.run_provenance_shadow(**options)

    # 14
    def test_selected_session_year_ids_and_completed_end_are_required(self):
        cases = ({"year": 2025}, {"meeting_key": 0}, {"date_end": None},
                 {"date_start": None},
                 {"date_end": "2026-03-08T06:00:00"},
                 {"date_start": "2026-03-07T07:00:00Z"})
        for changes in cases:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([
                Response(200, session_bytes(**changes), DISCOVERY_URI)
            ])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.assertRaises(m.ProvenanceShadowHold):
                m.run_provenance_shadow(**options)

    def test_target_race_must_be_exactly_one_distinct_same_meeting_row(self):
        source, target = json.loads(session_bytes())
        cases = (
            ([source], "target_race_not_unique"),
            ([source, target, dict(target, session_key=11235)],
             "target_race_not_unique"),
            ([source, dict(target, meeting_key=9999)], "target_race_not_unique"),
            ([source, dict(target, session_key=11230)],
             "selected_session_not_unique"),
        )
        for rows, reason in cases:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            raw = json.dumps(rows, separators=(",", ":")).encode()
            getter = SequencedGet([Response(200, raw, DISCOVERY_URI)])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.subTest(reason=reason), self.assertRaisesRegex(
                m.ProvenanceShadowHold, reason
            ):
                m.run_provenance_shadow(**options)
            self.assertEqual(len(getter.calls), 1)

    def test_target_race_identity_and_chronology_are_fail_closed(self):
        cases = (
            ({"year": 2025}, "target_race_year_mismatch"),
            ({"circuit_short_name": "Albert Park"},
             "target_race_event_identity_mismatch"),
            ({"location": "Sydney"}, "target_race_event_identity_mismatch"),
            ({"date_start": "2026-03-07T05:30:00Z"},
             "target_race_not_after_qualifying_source"),
            ({"date_start": "2026-03-08T07:00:00Z",
              "date_end": "2026-03-08T06:00:00Z"},
             "target_race_chronology_invalid"),
        )
        for changes, reason in cases:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([
                Response(200, session_bytes(target_changes=changes), DISCOVERY_URI)
            ])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.subTest(reason=reason), self.assertRaisesRegex(
                m.ProvenanceShadowHold, reason
            ):
                m.run_provenance_shadow(**options)
            self.assertEqual(len(getter.calls), 1)

    def test_cancelled_source_or_target_holds_before_grid_get(self):
        cases = (
            ({"cancelled": True}, None, "selected_grid_source_cancelled"),
            ({}, {"status": "Cancelled"}, "target_race_cancelled"),
        )
        for source_changes, target_changes, reason in cases:
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([Response(
                200,
                session_bytes(target_changes=target_changes, **source_changes),
                DISCOVERY_URI,
            )])
            options, _ = self.options(output_root=Path(alternate.name), http_get=getter)
            with self.subTest(reason=reason), self.assertRaisesRegex(
                m.ProvenanceShadowHold, reason
            ):
                m.run_provenance_shadow(**options)
            self.assertEqual(len(getter.calls), 1)

    # 15
    def test_historical_window_gate_precedes_grid_request(self):
        getter = SequencedGet([Response(200, session_bytes(), DISCOVERY_URI)])
        options, _ = self.options(
            http_get=getter,
            clock=Clock(["2026-03-07T06:29:59Z", "2026-03-07T06:29:59Z"]),
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
        self.assertEqual(call["request_params"], {"session_key": "11230"})
        self.assertEqual(call["raw_response_bytes"], GRID_BYTES)
        self.assertEqual(call["session_end_utc"], "2026-03-07T06:00:00Z")

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
    def test_corrected_k4r14_receives_source_bytes_and_distinct_target(self):
        calls = []

        def adapter(**kwargs):
            calls.append(kwargs)
            return m.starting_grid_adapter_contract.adapt_openf1_starting_grid_to_producer_input(
                **kwargs
            )

        manifest, _ = self.run_valid(starting_grid_adapter=adapter)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["source_session_kind"], "Qualifying")
        self.assertEqual(calls[0]["target_race_session_id"], "11234")
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
        self.assertEqual(manifest["grid_source_session_id"], "11230")
        self.assertEqual(manifest["grid_source_session_kind"], "Qualifying")
        self.assertEqual(manifest["grid_target_race_session_id"], "11234")
        self.assertEqual(manifest["grid_target_race_session_kind"], "Race")
        self.assertEqual(manifest["source_to_race_link_evidence_type"],
                         "OPENF1_PROVIDER_DISCOVERY_CLAIM")
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
        self.assertFalse(manifest["producer_input_csv_is_target_race_scoped"])
        self.assertFalse(manifest["cross_session_join_authorized"])

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
        self.assertEqual(grid["required_source_session_name"], "Qualifying")
        self.assertEqual(grid["required_source_session_type"], "Qualifying")
        self.assertEqual(grid["required_target_session_name"], "Race")
        self.assertEqual(grid["required_target_session_type"], "Race")
        self.assertTrue(grid["requires_k4r1_validation"])
        self.assertTrue(grid["requires_k4r14_validation"])
        self.assertFalse(grid["persists_derived_csv"])

    # 27
    def test_grid_http_errors_hold_without_retry(self):
        for status in (429, 404, 503):
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
            root, manifest, assessment, report = self.persisted_diagnostics(
                alternate.name
            )
            self.assertEqual(len(getter.calls), 2)
            self.assertEqual({path.name for path in root.iterdir()}, {
                "sessions.response.json",
                "historical_rest_capture_assessment.json",
                "shadow_manifest.json",
                "shadow_report.md",
            })
            self.assertEqual(manifest["session_discovery_http_status_code"], 200)
            self.assertEqual(manifest["starting_grid_http_status_code"], status)
            self.assertTrue(manifest["starting_grid_request_attempted"])
            self.assertRegex(manifest["session_discovery_raw_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(manifest["grid_target_race_session_id"], "11234")
            self.assertIsNone(manifest["starting_grid_raw_sha256"])
            self.assertEqual(
                assessment["reason_codes"], ["starting_grid_http_status_not_200"]
            )
            self.assertIn("The subsequent starting-grid", report)
            self.assertIn("response was rejected", report)
            self.assertNotIn("The parentless K4R1", report)

    def test_untrusted_error_body_and_headers_are_not_persisted_or_retried(self):
        secret_markers = ("token-SHOULD-NOT-LEAK", "Cookie=private", "password=hunter2")
        response = Response(
            429,
            json.dumps({"error": secret_markers[0], "password": secret_markers[2]}).encode(),
            DISCOVERY_URI,
            headers={
                "Content-Type": "application/json",
                "Retry-After": "1",
                "Set-Cookie": secret_markers[1],
            },
        )
        getter = SequencedGet([response])
        options, _ = self.options(http_get=getter)
        with self.assertRaisesRegex(
            m.ProvenanceShadowHold, "session_discovery_http_status_not_200"
        ):
            m.run_provenance_shadow(**options)
        root, manifest, _, report = self.persisted_diagnostics()
        persisted = report + json.dumps(manifest, sort_keys=True)
        persisted += "".join(
            path.read_text() for path in root.iterdir() if path.suffix in {".json", ".md"}
        )
        self.assertEqual(len(getter.calls), 1)
        for marker in secret_markers:
            self.assertNotIn(marker, persisted)

    def test_invalid_status_types_hold_without_fabricated_numeric_code(self):
        for status in (True, "429", None, 99, 600):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([Response(status, b"[]", DISCOVERY_URI)])
            options, _ = self.options(
                output_root=Path(alternate.name), http_get=getter
            )
            with self.subTest(status=status), self.assertRaisesRegex(
                m.ProvenanceShadowHold, "session_discovery_http_status_unavailable"
            ):
                m.run_provenance_shadow(**options)
            root, manifest, assessment, _ = self.persisted_diagnostics(alternate.name)
            self.assertEqual(len(getter.calls), 1)
            self.assertIsNone(manifest["session_discovery_http_status_code"])
            self.assertFalse(manifest["starting_grid_request_attempted"])
            self.assertEqual(
                assessment["reason_codes"],
                ["session_discovery_http_status_unavailable"],
            )
            self.assertFalse((root / "sessions.response.json").exists())

    def test_invalid_grid_status_types_hold_without_fabricated_numeric_code(self):
        for status in (False, "503", None, 600):
            alternate = tempfile.TemporaryDirectory()
            self.addCleanup(alternate.cleanup)
            getter = SequencedGet([
                Response(200, session_bytes(), DISCOVERY_URI),
                Response(status, b"[]", GRID_URI),
            ])
            options, _ = self.options(
                output_root=Path(alternate.name), http_get=getter
            )
            with self.subTest(status=status), self.assertRaisesRegex(
                m.ProvenanceShadowHold, "starting_grid_http_status_unavailable"
            ):
                m.run_provenance_shadow(**options)
            root, manifest, assessment, report = self.persisted_diagnostics(
                alternate.name
            )
            self.assertEqual(len(getter.calls), 2)
            self.assertIsNone(manifest["starting_grid_http_status_code"])
            self.assertEqual(manifest["session_discovery_http_status_code"], 200)
            self.assertTrue((root / "sessions.response.json").exists())
            self.assertFalse((root / "starting_grid.response.json").exists())
            self.assertEqual(
                assessment["reason_codes"], ["starting_grid_http_status_unavailable"]
            )
            self.assertIn("The subsequent starting-grid", report)

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
    def test_future_qualifying_source_holds_before_grid_get(self):
        getter = SequencedGet([
            Response(200, session_bytes(
                date_end="2027-03-07T06:00:00Z",
                target_changes={
                    "date_start": "2027-03-08T04:00:00Z",
                    "date_end": "2027-03-08T06:00:00Z",
                },
            ), DISCOVERY_URI)
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
                if path == str(WORKFLOW.relative_to(ROOT)):
                    result = subprocess.run(
                        ["git", "cat-file", "-e", f"{expected}^{{blob}}"],
                        cwd=ROOT, check=False, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    assert_authorized_workflow_compatibility(
                        self, WORKFLOW.read_bytes()
                    )
                elif path in MODIFIED:
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

    # 35
    def test_workflow_compatibility_rejects_unauthorized_mutations(self):
        predecessor = git_blob_bytes(PREDECESSOR_WORKFLOW_BLOB)
        successor = git_blob_bytes(SUCCESSOR_WORKFLOW_BLOB)
        cases = {
            "manual_input": predecessor.replace(
                b"          - weather\n", b"          - weather_changed\n", 1
            ),
            "predecessor_publication": predecessor.replace(
                b"safe_git_push_rebase_retry.sh",
                b"safe_git_push_rebase_retry_changed.sh", 1,
            ),
            "successor_publication": successor.replace(
                b"--artifact-uploaded-for-run", b"--artifact-not-bound", 1
            ),
            "custody_suffix": predecessor.replace(
                b"actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
                b"actions/download-artifact@unauthorized", 1,
            ),
            "custody_permission": successor.replace(
                b"      attestations: write", b"      attestations: read", 1
            ),
        }
        for label, changed in cases.items():
            with self.subTest(label=label), self.assertRaises(AssertionError):
                assert_authorized_workflow_compatibility(self, changed)


if __name__ == "__main__":
    unittest.main()
