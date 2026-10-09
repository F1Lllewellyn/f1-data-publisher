import ast
import copy
import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/forecast_bundles/dr002_fia_grid_document_candidate_v1.py"
)
SPEC = importlib.util.spec_from_file_location("fia_grid_candidate", MODULE_PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

MOCK_PDF = b"%PDF-1.7\n% MOCK SYNTHETIC TEST PDF - NOT FIA EVIDENCE\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class FiaGridDocumentCandidateTests(unittest.TestCase):
    def setUp(self):
        self.kwargs = {
            "raw_document_bytes": MOCK_PDF,
            "document_type": "provisional_starting_grid",
            "document_number": 49,
            "document_title": "Provisional Starting Grid",
            "document_uri": (
                "https://www.fia.com/documents/championships/fia-formula-one-world-championship-14/"
                "season/season-2026-2072/event/Australian%20Grand%20Prix/document-49.pdf"
            ),
            "official_index_uri": (
                "https://api.fia.com/documents/championships/fia-formula-one-world-championship-14/"
                "season/season-2026-2072/event/Australian%20Grand%20Prix"
            ),
            "event_id": "event-2026-australian-grand-prix",
            "meeting_id": "meeting-2026-01",
            "session_id": "race",
            "published_utc": "2026-03-08T04:00:00Z",
            "first_observed_utc": "2026-03-08T04:01:00Z",
            "ingested_utc": "2026-03-08T04:02:00Z",
            "receipt_created_utc": "2026-03-08T04:03:00Z",
            "forecast_cutoff_utc": "2026-03-08T04:05:00Z",
        }

    def assess(self, **changes):
        values = dict(self.kwargs)
        values.update(changes)
        return m.assess_fia_grid_document_candidate(**values)

    def assert_hold(self, code, **changes):
        result = self.assess(**changes)
        self.assertEqual(result["status"], "HOLD")
        self.assertIn(code, result["reason_codes"])
        self.assertNotIn("document_candidate", result)
        self.assertTrue(all(value is False for value in result["claim_flags"].values()))
        return result

    def test_valid_mock_candidate_remains_unauthenticated(self):
        result = self.assess()
        self.assertEqual(result["status"], m.VALIDATED_STATUS)
        self.assertEqual(result["evidence_chain_status"], "NOT_ESTABLISHED")
        self.assertTrue(all(value is False for value in result["claim_flags"].values()))

    def test_provisional_and_final_types_and_identities_remain_distinct(self):
        provisional = self.assess()
        final = self.assess(
            document_type="final_starting_grid",
            document_number=55,
            document_title="  FINAL   Starting Grid ",
            document_uri=self.kwargs["document_uri"].replace("document-49.pdf", "document-55.pdf"),
        )
        self.assertNotEqual(
            provisional["document_candidate"]["candidate_id"],
            final["document_candidate"]["candidate_id"],
        )
        self.assertNotEqual(
            provisional["document_candidate"]["content_version_id"],
            final["document_candidate"]["content_version_id"],
        )

    def test_unknown_and_forbidden_document_types_hold(self):
        for value in (
            "final_qualifying_classification",
            "sprint_starting_grid",
            "race_result",
            "practice_classification",
            "openf1_driver_record",
            "",
        ):
            with self.subTest(value=value):
                self.assert_hold("unsupported_document_type", document_type=value)

    def test_wrong_document_title_holds(self):
        for value in ("Final Qualifying Classification", "Sprint Grid", "Race Result", "Starting Grid"):
            with self.subTest(value=value):
                self.assert_hold("document_title_type_mismatch", document_title=value)

    def test_document_number_must_be_positive_integer_not_bool(self):
        for value in (True, False, 0, -1, 1.0, "49", None):
            with self.subTest(value=value):
                self.assert_hold("invalid_document_number", document_number=value)

    def test_non_fia_lookalike_http_userinfo_port_encoded_host_and_aliases_hold(self):
        bad_document_uris = (
            "https://example.com/doc.pdf",
            "https://fia.com.evil.example/doc.pdf",
            "http://www.fia.com/doc.pdf",
            "https://user@www.fia.com/doc.pdf",
            "https://www.fia.com:443/doc.pdf",
            "https://f%69a.com/doc.pdf",
            "https://www.fia.com/doc.pdf?download=1",
            "https://www.fia.com/doc.pdf#alias",
            "https://www.fia.com/redirect?to=document.pdf",
            "https://www.fia.com/%64ocument.pdf",
        )
        for value in bad_document_uris:
            with self.subTest(value=value):
                result = self.assess(document_uri=value)
                self.assertEqual(result["status"], "HOLD")

    def test_index_must_be_strict_fia_documents_route(self):
        for value in (
            "https://example.com/documents/event/x",
            "https://fia.com.evil/documents/event/x",
            "http://www.fia.com/documents/event/x",
            "https://user@api.fia.com/documents/event/x",
            "https://api.fia.com:443/documents/event/x",
            "https://api.fia.com/news/event/x",
            "https://api.fia.com/documents/event/x?alias=1",
        ):
            with self.subTest(value=value):
                result = self.assess(official_index_uri=value)
                self.assertEqual(result["status"], "HOLD")

    def test_same_uri_changed_bytes_create_separate_content_versions(self):
        first = self.assess()["document_candidate"]
        changed = self.assess(raw_document_bytes=MOCK_PDF.replace(b"1 0 obj", b"2 0 obj"))[
            "document_candidate"
        ]
        self.assertEqual(first["claimed_source_id"], changed["claimed_source_id"])
        self.assertNotEqual(first["content_version_id"], changed["content_version_id"])
        self.assertNotEqual(first["candidate_id"], changed["candidate_id"])

    def test_different_document_numbers_cannot_collapse_candidate_identity(self):
        first = self.assess()["document_candidate"]
        second = self.assess(document_number=50)["document_candidate"]
        self.assertNotEqual(first["candidate_id"], second["candidate_id"])

    def test_identical_inputs_are_byte_for_byte_deterministic(self):
        first = m.canonical_json_bytes(self.assess())
        second = m.canonical_json_bytes(self.assess())
        self.assertEqual(first, second)

    def test_malformed_empty_missing_eof_excess_and_nonbytes_pdf_hold(self):
        fixtures = (
            (b"", "raw_document_empty"),
            (b"not pdf%%EOF\n", "raw_document_missing_pdf_magic"),
            (b"%PDF-1.7\nmissing eof", "raw_document_missing_plausible_eof"),
            (b"%PDF-" + b"x" * m.MAX_PDF_BYTES + b"%%EOF", "raw_document_size_exceeds_limit"),
            (bytearray(MOCK_PDF), "raw_document_not_exact_bytes"),
            ("%PDF-1.7%%EOF", "raw_document_not_exact_bytes"),
        )
        for value, code in fixtures:
            with self.subTest(code=code):
                self.assert_hold(code, raw_document_bytes=value)

    def test_empty_whitespace_control_and_nonstring_scope_hold(self):
        for field in ("event_id", "meeting_id", "session_id"):
            for value in ("", " value ", "bad\nvalue", None, 123):
                with self.subTest(field=field, value=value):
                    self.assert_hold("invalid_" + field, **{field: value})

    def test_explicit_uri_event_route_mismatch_holds(self):
        self.assert_hold(
            "explicit_event_route_mismatch",
            document_uri=self.kwargs["document_uri"].replace(
                "Australian%20Grand%20Prix", "Japanese%20Grand%20Prix"
            ),
        )

    def test_no_openf1_mapping_is_inferred_from_scope_numbers(self):
        result = self.assess(event_id="999", meeting_id="999", session_id="999")
        self.assertEqual(result["status"], m.VALIDATED_STATUS)
        self.assertEqual(
            result["document_candidate"]["scope_binding_status"],
            "CLAIMED_UNVERIFIED_NO_OPENF1_JOIN",
        )

    def test_invalid_naive_offset_and_impossible_timestamps_hold(self):
        for value in (
            "2026-03-08T04:00:00",
            "2026-03-08T00:00:00-04:00",
            "2026-02-30T04:00:00Z",
            "not-a-time",
            None,
        ):
            with self.subTest(value=value):
                self.assert_hold("invalid_published_utc", published_utc=value)

    def test_every_time_field_is_strictly_validated(self):
        for field in (
            "published_utc",
            "first_observed_utc",
            "ingested_utc",
            "receipt_created_utc",
            "forecast_cutoff_utc",
        ):
            with self.subTest(field=field):
                self.assert_hold("invalid_" + field, **{field: "2026-03-08T04:00:00+00:00"})

    def test_observation_chronology_inversions_hold(self):
        cases = (
            {"published_utc": "2026-03-08T04:02:00Z"},
            {"first_observed_utc": "2026-03-08T04:03:00Z"},
            {"ingested_utc": "2026-03-08T04:04:00Z"},
        )
        for change in cases:
            with self.subTest(change=change):
                self.assert_hold("invalid_document_observation_chronology", **change)

    def test_pre_cutoff_publication_but_post_cutoff_observation_holds(self):
        self.assert_hold(
            "first_observed_after_forecast_cutoff",
            first_observed_utc="2026-03-08T04:06:00Z",
            ingested_utc="2026-03-08T04:07:00Z",
            receipt_created_utc="2026-03-08T04:08:00Z",
        )

    def test_post_cutoff_publication_holds(self):
        result = self.assert_hold(
            "published_after_forecast_cutoff",
            published_utc="2026-03-08T04:06:00Z",
            first_observed_utc="2026-03-08T04:07:00Z",
            ingested_utc="2026-03-08T04:08:00Z",
            receipt_created_utc="2026-03-08T04:09:00Z",
        )
        self.assertIn("first_observed_after_forecast_cutoff", result["reason_codes"])

    def test_under_cutoff_times_remain_metadata_not_historical_proof(self):
        result = self.assess()
        self.assertEqual(
            result["document_candidate"]["temporal_check_status"],
            "CLAIMED_METADATA_ORDERED_AND_AT_OR_BEFORE_CUTOFF",
        )
        self.assertFalse(result["claim_flags"]["historical_availability_verified"])
        self.assertFalse(result["claim_flags"]["blind_validation_eligible"])

    def test_hash_and_typed_id_recomputation(self):
        candidate = self.assess()["document_candidate"]
        raw_hash = m.sha256(MOCK_PDF)
        expected_source = "claimed_fia_pdf_uri:" + m.sha256(
            m.SOURCE_ID_DOMAIN + self.kwargs["document_uri"].encode("utf-8")
        )
        expected_version = "fia_grid_document_content_version:" + m.sha256(
            m.CONTENT_VERSION_DOMAIN
            + m.canonical_json_bytes(
                {"document_uri": self.kwargs["document_uri"], "raw_document_sha256": raw_hash}
            )
        )
        self.assertEqual(candidate["raw_document_sha256"], raw_hash)
        self.assertEqual(candidate["claimed_source_id"], expected_source)
        self.assertEqual(candidate["content_version_id"], expected_version)
        self.assertTrue(candidate["candidate_id"].startswith("fia_grid_document_candidate:"))

    def test_no_raw_pdf_grid_csv_receipt_or_verified_binding_output(self):
        result = self.assess()
        self.assertNotIn("raw_document_bytes", result["document_candidate"])
        self.assertEqual(
            result["outputs"],
            {
                "raw_document_included": False,
                "parsed_grid_emitted": False,
                "starting_grid_csv_emitted": False,
                "source_capture_receipt_created": False,
                "verified_binding_created": False,
            },
        )
        encoded = m.canonical_json_bytes(result)
        self.assertNotIn(MOCK_PDF, encoded)
        self.assertNotIn("receipt_id", result["document_candidate"])
        self.assertNotIn("receipt_type", result["document_candidate"])
        self.assertNotIn("verified_receipt_bindings", result)

    def test_module_has_no_pdf_parser_network_credentials_discovery_or_execution(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imports = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        forbidden_imports = {
            "requests", "httpx", "subprocess", "selenium", "pypdf", "PyPDF2",
            "pdfplumber", "fitz", "boto3", "github", "glob",
        }
        forbidden_attributes = {
            "urlopen", "request", "get", "post", "run", "Popen", "system", "glob", "rglob",
            "iterdir", "walk", "listdir", "scandir", "write_bytes", "write_text", "open",
        }
        self.assertFalse(imports & forbidden_imports)
        self.assertFalse(attributes & forbidden_attributes)

    def test_function_does_not_mutate_caller_inputs(self):
        before = copy.deepcopy(self.kwargs)
        self.assess()
        self.assertEqual(self.kwargs, before)

    def test_all_six_dependency_pins_are_typed_and_exact(self):
        expected = {
            "docs/DR002_PRE2B7K4R10_EXACT_HISTORICAL_ARTIFACTS_DUAL_SOURCE_REPLAY_2026-10-08.md": "b9d57a68ac7eef39e71a6a19ca9de407a68fb09d",
            "scripts/forecast_bundles/dr002_openf1_weather_drivers_frozen_producer_composition_v1.py": "f69a5ac49b6e3055cd13472037f8b49e8ea41265",
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py": "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
            "scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py": "064d93ee5ae30354590a3fb95be598c5fe8b3b9a",
            "scripts/forecasts/produce_actual_forecast_rows_v1.py": "af27586668c767de126af829c1131c6bae4634ad",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
        }
        self.assertEqual(m.DEPENDENCY_PINS, expected)

    def test_missing_required_keyword_is_programming_error_not_successful_hold(self):
        values = dict(self.kwargs)
        values.pop("document_uri")
        with self.assertRaises(TypeError):
            m.assess_fia_grid_document_candidate(**values)


if __name__ == "__main__":
    unittest.main()
