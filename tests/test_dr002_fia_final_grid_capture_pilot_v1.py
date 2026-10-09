import ast
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/forecast_bundles/dr002_fia_final_grid_capture_pilot_v1.py"
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/dr002-fia-final-grid-capture-shadow.yml"
SPEC = importlib.util.spec_from_file_location("fia_capture", MODULE_PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

MOCK_PDF = (
    b"%PDF-1.7\n% MOCK SYNTHETIC FIA-CAPTURE TEST BYTES - NOT LIVE EVIDENCE\n"
    b"1 0 obj\n<<>>\nendobj\n%%EOF\n"
)


class FiaFinalGridCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime_root = Path(self.temp.name) / "runtime"
        self.calls = 0
        self.times = (
            "2026-10-09T12:00:00Z",
            "2026-10-09T12:00:01Z",
            "2026-10-09T12:00:02Z",
            "2026-10-09T12:00:03Z",
        )
        self.base = {
            "github_run_id": "12345",
            "github_run_attempt": "1",
            "repository": m.REPOSITORY,
            "git_commit": "a" * 40,
            "workflow_ref": m.REPOSITORY + "/" + m.WORKFLOW_PATH + "@refs/heads/main",
            "runtime_root": self.runtime_root,
        }

    def tearDown(self):
        self.temp.cleanup()

    def response(self, **changes):
        result = {
            "status": 200,
            "body": MOCK_PDF,
            "content_type": "application/pdf; charset=binary",
            "content_length": len(MOCK_PDF),
            "final_url": m.PDF_URI,
            "complete": True,
            "redirected": False,
        }
        result.update(changes)
        return result

    def run_capture(self, response=None, times=None, **changes):
        response = self.response() if response is None else response
        values = iter(self.times if times is None else times)

        def request():
            self.calls += 1
            return response

        args = dict(self.base)
        args.update(changes)
        return m.capture(request=request, clock=lambda: next(values), **args)

    def final_root(self, attempt="1"):
        return self.runtime_root / ("gha-12345-" + attempt)

    def assert_hold(self, response=None, times=None, **changes):
        result = self.run_capture(response=response, times=times, **changes)
        self.assertEqual(result["validation_status"], "HOLD")
        self.assertIsNone(result["receipt_path"])
        self.assertIsNone(result["source_capture_receipt_id"])
        self.assertIsNone(result["candidate_id"])
        self.assertFalse((self.final_root() / "source_capture_receipt.json").exists())
        self.assertEqual(self.calls, 1)
        return result

    def test_success_fixed_uri_one_call_exact_bytes_hash_and_readback(self):
        result = self.run_capture()
        root = self.final_root()
        raw = (root / "raw/fia_final_starting_grid_doc_55.pdf").read_bytes()
        self.assertEqual(result["validation_status"], "CAPTURED_UNBOUND_CANDIDATE")
        self.assertEqual(self.calls, 1)
        self.assertEqual(result["request_uri"], m.PDF_URI)
        self.assertEqual(raw, MOCK_PDF)
        self.assertEqual(result["raw_document_sha256"], m.sha256(MOCK_PDF))
        self.assertEqual(result["readback_sha256"], m.sha256(MOCK_PDF))
        self.assertTrue(result["readback_verified"])

    def test_success_has_canonical_parentless_existing_receipt_and_deterministic_id(self):
        first = self.run_capture()
        receipt_path = self.final_root() / "source_capture_receipt.json"
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes)
        self.assertEqual(receipt_bytes, m.canonical_json_bytes(receipt))
        self.assertEqual(receipt["schema_version"], m.RECEIPT_VERSION)
        self.assertEqual(receipt["receipt_type"], "source_capture")
        self.assertEqual(receipt["parent_receipt_ids"], [])
        self.assertEqual(receipt["scope"], m.SCOPE)
        self.assertEqual(first["source_capture_receipt_sha256"], m.sha256(receipt_bytes))
        identity = {
            "source_id": receipt["payload"]["source_id"],
            **m.SCOPE,
            "source_sha256": m.sha256(MOCK_PDF),
            "first_observed_utc": self.times[1],
        }
        expected = "source_capture:" + m.sha256(m.canonical_json_bytes(identity))
        self.assertEqual(receipt["receipt_id"], expected)

    def test_k4r11_candidate_status_and_all_false_claims_are_preserved(self):
        result = self.run_capture()
        candidate = json.loads((self.final_root() / "source_candidate_manifest.json").read_bytes())
        self.assertEqual(result["candidate_status"], m.CANDIDATE_VALIDATED_STATUS)
        self.assertEqual(candidate["candidate_status"], m.CANDIDATE_VALIDATED_STATUS)
        self.assertEqual(candidate["evidence_chain_status"], "NOT_ESTABLISHED")
        self.assertTrue(all(value is False for value in candidate["claim_flags"].values()))
        self.assertTrue(all(result[key] is False for key in m.FALSE_CLAIMS))

    def test_observation_is_actual_post_event_time_not_publication_or_race_cutoff(self):
        result = self.run_capture()
        receipt = json.loads((self.final_root() / "source_capture_receipt.json").read_bytes())
        self.assertEqual(result["claimed_published_utc"], "2026-03-08T03:00:00Z")
        self.assertEqual(result["first_observed_utc"], "2026-10-09T12:00:01Z")
        self.assertEqual(result["shadow_review_cutoff_utc"], result["receipt_created_utc"])
        self.assertEqual(receipt["payload"]["publisher_time_utc"], m.CLAIMED_PUBLISHED_UTC)
        self.assertEqual(receipt["payload"]["first_observed_utc"], result["first_observed_utc"])
        self.assertFalse(result["historical_availability_verified"])

    def test_wrong_http_statuses_hold_without_retry(self):
        for status in (301, 302, 206, 404, 500):
            with self.subTest(status=status):
                self.calls = 0
                response = self.response(status=status)
                if 300 <= status < 400:
                    response["redirected"] = True
                self.assert_hold(response=response)
                self.temp.cleanup()
                self.temp = tempfile.TemporaryDirectory()
                self.runtime_root = Path(self.temp.name) / "runtime"
                self.base["runtime_root"] = self.runtime_root

    def test_redirect_or_changed_final_url_holds(self):
        self.assert_hold(
            response=self.response(
                final_url="https://admin.fia.com/other.pdf", redirected=True
            )
        )

    def test_non_pdf_and_missing_eof_hold(self):
        for body in (b"not a pdf", b"%PDF-1.7\nmissing eof"):
            with self.subTest(body=body):
                self.calls = 0
                self.assert_hold(response=self.response(body=body, content_length=len(body)))
                self.temp.cleanup()
                self.temp = tempfile.TemporaryDirectory()
                self.runtime_root = Path(self.temp.name) / "runtime"
                self.base["runtime_root"] = self.runtime_root

    def test_oversized_body_holds(self):
        body = b"%PDF-" + b"x" * m.MAX_BODY_BYTES + b"%%EOF"
        self.assert_hold(response=self.response(body=body, content_length=len(body)))

    def test_incomplete_or_truncated_response_holds(self):
        cases = (
            self.response(complete=False),
            self.response(content_length=len(MOCK_PDF) + 10),
            self.response(content_length="not-an-integer"),
        )
        for response in cases:
            with self.subTest(response=response):
                self.calls = 0
                self.assert_hold(response=response)
                self.temp.cleanup()
                self.temp = tempfile.TemporaryDirectory()
                self.runtime_root = Path(self.temp.name) / "runtime"
                self.base["runtime_root"] = self.runtime_root

    def test_invalid_content_type_holds(self):
        for value in ("text/html", "application/octet-stream", "", None):
            with self.subTest(value=value):
                self.calls = 0
                self.assert_hold(response=self.response(content_type=value))
                self.temp.cleanup()
                self.temp = tempfile.TemporaryDirectory()
                self.runtime_root = Path(self.temp.name) / "runtime"
                self.base["runtime_root"] = self.runtime_root

    def test_out_of_order_times_hold(self):
        self.assert_hold(
            times=(
                "2026-10-09T12:00:02Z",
                "2026-10-09T12:00:01Z",
                "2026-10-09T12:00:03Z",
                "2026-10-09T12:00:04Z",
            )
        )

    def test_raw_write_failure_holds_and_publishes_no_receipt(self):
        def writer(path, data):
            if path.suffix == ".pdf":
                raise OSError("mock_raw_write_failure")
            m.write_bytes(path, data)

        result = self.assert_hold(writer=writer)
        self.assertIn("mock_raw_write_failure", result["reason_codes"])

    def test_raw_readback_failure_holds_and_publishes_no_receipt(self):
        def reader(path):
            if path.suffix == ".pdf":
                return b"corrupt"
            return path.read_bytes()

        result = self.assert_hold(reader=reader)
        self.assertIn("raw_document_readback_hash_mismatch", result["reason_codes"])

    def test_receipt_persistence_failure_holds_and_publishes_no_receipt(self):
        def writer(path, data):
            if path.name == "receipt_candidate.diagnostic.json":
                raise OSError("mock_receipt_write_failure")
            m.write_bytes(path, data)

        result = self.assert_hold(writer=writer)
        self.assertIn("mock_receipt_write_failure", result["reason_codes"])

    def test_source_candidate_manifest_readback_failure_holds(self):
        def reader(path):
            if path.name == "source_candidate_manifest.json":
                return b"corrupt"
            return path.read_bytes()

        result = self.assert_hold(reader=reader)
        self.assertIn("source_candidate_manifest_readback_mismatch", result["reason_codes"])

    def test_capture_manifest_persistence_failure_holds_and_removes_success_receipt(self):
        state = {"failed": False}

        def writer(path, data):
            if path.name == "capture_manifest.json" and not state["failed"]:
                state["failed"] = True
                raise OSError("mock_manifest_write_failure")
            m.write_bytes(path, data)

        result = self.assert_hold(writer=writer)
        self.assertIn("mock_manifest_write_failure", result["reason_codes"])

    def test_exclusive_runtime_directory_prevents_overwrite(self):
        self.run_capture()
        original = (self.final_root() / "raw/fia_final_starting_grid_doc_55.pdf").read_bytes()
        self.calls = 0
        with self.assertRaises(FileExistsError):
            self.run_capture()
        self.assertEqual(self.calls, 0)
        self.assertEqual(
            (self.final_root() / "raw/fia_final_starting_grid_doc_55.pdf").read_bytes(), original
        )

    def test_source_identity_and_scope_do_not_depend_on_index_publication_or_openf1(self):
        result = self.run_capture()
        receipt = json.loads((self.final_root() / "source_capture_receipt.json").read_bytes())
        self.assertEqual(receipt["payload"]["source_id"], result["claimed_source_id"])
        self.assertEqual(receipt["scope"], m.SCOPE)
        self.assertNotIn("openf1", json.dumps(receipt).casefold())
        self.assertNotIn("1295", json.dumps(receipt))
        self.assertNotIn("11371", json.dumps(receipt))
        self.assertNotIn(m.INDEX_URI, receipt["receipt_id"])
        self.assertNotIn(m.CLAIMED_PUBLISHED_UTC, receipt["receipt_id"])

    def test_same_exact_inputs_preserve_candidate_and_receipt_identity(self):
        first = self.run_capture()
        with tempfile.TemporaryDirectory() as other:
            self.calls = 0
            second = self.run_capture(runtime_root=Path(other) / "runtime")
        self.assertEqual(first["candidate_id"], second["candidate_id"])
        self.assertEqual(first["source_capture_receipt_id"], second["source_capture_receipt_id"])

    def test_transport_is_called_once_even_when_candidate_holds(self):
        body = b"%PDF-1.7\nno eof"
        self.assert_hold(response=self.response(body=body, content_length=len(body)))
        self.assertEqual(self.calls, 1)

    def test_fixed_target_has_no_arbitrary_network_cli_flags(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            m.PDF_URI,
            "https://www.fia.com/system/files/decision-document/"
            "2026_australian_grand_prix_-_final_starting_grid.pdf",
        )
        self.assertEqual(
            m.INDEX_URI,
            "https://www.fia.com/documents/championships/"
            "fia-formula-one-world-championship-14/event/Australian%20Grand%20Prix",
        )
        self.assertNotIn('add_argument("--url"', source)
        self.assertNotIn('add_argument("--event"', source)
        self.assertNotIn('add_argument("--season"', source)

    def test_no_pdf_parser_producer_model_or_filesystem_discovery(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertFalse(imports & {"pypdf", "PyPDF2", "pdfplumber", "fitz", "subprocess", "requests"})
        self.assertFalse(attributes & {"Popen", "system", "glob", "rglob", "iterdir", "walk", "listdir"})

    def test_exact_seven_dependency_pins(self):
        expected = {
            "scripts/forecast_bundles/dr002_fia_grid_document_candidate_v1.py": "15867e3d1af56a5c00b2bd35c1220541e7e4f619",
            "docs/DR002_PRE2B7K4R11_FIA_GRID_DOCUMENT_CANDIDATE_CONTRACT_2026-10-09.md": "54efa78ccf72efee9d58f34d330076b562d9b803",
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py": "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
            ".github/workflows/dr002-capture-provenance-pilot.yml": "883fcbc1a00ec9ae1dd6dd40423a03af05ae1fe3",
            "scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py": "b9b1f9acc1be30d5b7cdf42424853e3d652b9466",
            "scripts/forecast_bundles/dr002_github_attestation_binding_v1.py": "215f012b79aa9e6f33aff6ad62ca7efba53a9627",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
        }
        self.assertEqual(m.DEPENDENCY_PINS, expected)

    def test_authorized_scope_is_exactly_four_additions(self):
        self.assertEqual(
            m.AUTHORIZED_PATHS,
            frozenset({
                "scripts/forecast_bundles/dr002_fia_final_grid_capture_pilot_v1.py",
                "tests/test_dr002_fia_final_grid_capture_pilot_v1.py",
                ".github/workflows/dr002-fia-final-grid-capture-shadow.yml",
                "docs/DR002_PRE2B7K4R12_FIA_FINAL_GRID_CAPTURE_ATTESTATION_SHADOW_2026-10-09.md",
            }),
        )

    def test_workflow_only_manual_trigger_and_main_gate_before_capture(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        trigger = re.search(r"(?ms)^on:\n(.*?)(?=^permissions:)", text).group(1)
        self.assertIn("workflow_dispatch:", trigger)
        self.assertNotIn("schedule:", trigger)
        self.assertNotIn("push:", trigger)
        self.assertNotIn("pull_request:", trigger)
        self.assertLess(text.index("if: github.ref == 'refs/heads/main'"), text.index(m.IMPLEMENTATION))

    def test_workflow_permissions_checkout_and_actions_are_bounded(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("contents: read", text)
        self.assertIn("id-token: write", text)
        self.assertIn("attestations: write", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("actions/checkout@v4", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("actions/setup-python@v5", text)
        self.assertEqual(text.count("actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"), 1)

    def test_workflow_attests_one_success_receipt_and_uploads_diagnostics_always(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        subject = (
            "subject-path: _runtime/dr002_fia_final_grid_capture_shadow/"
            "gha-${{ github.run_id }}-${{ github.run_attempt }}/source_capture_receipt.json"
        )
        self.assertEqual(text.count(subject), 1)
        attest_block = text[text.index("- name: Attest exact"):text.index("- name: Preserve attestation")]
        self.assertNotIn("if: always()", attest_block)
        upload_block = text[text.index("- name: Upload runtime-only"):]
        self.assertIn("if: always()", upload_block)
        self.assertIn("retention-days: 14", upload_block)

    def test_workflow_has_no_repo_write_push_or_embedded_live_pdf(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertNotIn("git push", text)
        self.assertNotIn("latest/", text)
        self.assertNotIn("history/", text)
        self.assertNotIn("%PDF-", text)
        self.assertNotIn("secrets.", text)


if __name__ == "__main__":
    unittest.main()
