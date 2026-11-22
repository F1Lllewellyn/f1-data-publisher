"""FIA Vegas Doc53: original capture bound by existing DR-002 prospective HOLD."""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import json
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "fia_doc53_observer", ROOT / "scripts/ops/f1_vegas_2026_fia_doc53_retrospective_v1.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
UTC = dt.timezone.utc
POST = dt.datetime(2026, 11, 22, 14, 0, tzinfo=UTC)

INDEX = b"<html><h1>Las Vegas Grand Prix</h1>Doc 53 - Final Starting Grid</html>"
DOCUMENT = b"%PDF-1.7\n% FIA Doc 53 exact source fixture\n%%EOF\n"


def reader(url, maximum):
    if url == module.INDEX:
        return INDEX
    if url == module.PDF:
        return DOCUMENT
    raise AssertionError("unexpected source URL")


class FIAAuthorityTests(unittest.TestCase):
    def setUp(self):
        # The PDF in this unit test is a synthetic envelope; original
        # production byte identity is exercised by the actual PR source job.
        pinned = patch.object(module, "EXPECTED_DOCUMENT_SHA256", module.digest(DOCUMENT))
        pinned.start()
        self.addCleanup(pinned.stop)

    def test_fia_original_index_and_pdf_candidate_never_promote_pre_outcome(self):
        self.assertEqual(module.PUBLISHED_UTC, "2026-11-22T03:00:00Z")
        result = module.observe(clock=POST, reader=reader,
                                parser=lambda raw: module.GRID_DIGEST)
        self.assertEqual(result["status"], "FIA_FINAL_GRID_VERIFIED_RETROSPECTIVE_ONLY")
        self.assertEqual(result["original_pdf_sha256"], module.digest(DOCUMENT))
        self.assertTrue(result["source_authority_verified"])
        self.assertEqual(result["race_session_key"], "11420")
        self.assertEqual(result["qualifying_session_key"], "11416")
        for key in ("prediction_locked","forecast_eligible",
                    "stable_engine_executed","promotion_allowed"):
            self.assertIs(result[key], False)
        self.assertEqual(result["reason_codes"],
                         ["OBSERVED_AFTER_RACE_START", "NO_PROSPECTIVE_SOURCE_AUTHORITY"])

    def test_immutable_historical_doc53_receipt_is_nonpromoting_and_idempotent(self):
        report = module.observe(clock=POST, reader=reader,
                                parser=lambda raw: module.GRID_DIGEST)
        self.assertTrue(report["source_authority_verified"])
        with tempfile.TemporaryDirectory() as d:
            paths = module.emit_immutable_retrospective_receipt(d, report)
            self.assertEqual(len(paths), 2)
            self.assertEqual(paths, module.emit_immutable_retrospective_receipt(d, report))
            data = json.loads((Path(d)/paths[0]).read_text())
            self.assertEqual(data["race_session_key"], "11420")
            self.assertEqual(data["original_pdf_sha256"], module.digest(DOCUMENT))
            self.assertFalse(data["prediction_locked"])
            self.assertFalse(data["forecast_eligible"])
            self.assertNotIn("raw_pdf_bytes", data)
            self.assertNotIn("conventional_grid", data)
            with self.assertRaisesRegex(ValueError, "FIA_AUTHORITY_HOLD_IMMUTABLE_RECEIPT_COLLISION"):
                module.emit_immutable_retrospective_receipt(
                    d, dict(report, first_observed_utc="2026-11-22T15:00:00Z"))
            with self.assertRaisesRegex(ValueError, "FIA_AUTHORITY_HOLD_RECEIPT_GUARD"):
                module.emit_immutable_retrospective_receipt(
                    d, dict(report, forecast_eligible=True))

    def test_real_document_revision_hash_is_a_strict_negative(self):
        with patch.object(module, "EXPECTED_DOCUMENT_SHA256", "0"*64):
            result = module.observe(clock=POST, reader=reader,
                                    parser=lambda raw: module.GRID_DIGEST)
        self.assertEqual(result["status"], "FIA_AUTHORITY_HOLD")
        self.assertIn("FIA_AUTHORITY_HOLD_DOCUMENT_REVISION_HASH_MISMATCH",
                      result["reason_codes"])

    def test_missing_index_cannot_grant_grid_authority(self):
        def wrong(url, max_bytes):
            return b"Grand Prix" if url == module.INDEX else DOCUMENT
        result = module.observe(clock=POST, reader=wrong,
                                parser=lambda raw: module.GRID_DIGEST)
        self.assertEqual(result["status"], "FIA_AUTHORITY_HOLD")
        self.assertFalse(result["source_authority_verified"])

    def test_wrong_pdf_digest_and_bad_pdf_are_holds(self):
        for data, grid in ((DOCUMENT, "0"*64), (b"HTTP 200 fake", module.GRID_DIGEST)):
            with self.subTest(grid=grid), patch.object(module, "PDF", module.PDF):
                result = module.observe(clock=POST,
                    reader=lambda url, limit: INDEX if url == module.INDEX else data,
                    parser=lambda raw: grid)
                self.assertEqual(result["status"], "FIA_AUTHORITY_HOLD")
                self.assertIs(result["promotion_allowed"], False)

    def test_observation_clock_cannot_backdate_prospective_cutoff(self):
        before = dt.datetime(2026,11,22,3,30,tzinfo=UTC)
        result = module.observe(clock=before, reader=reader,
                                parser=lambda raw: module.GRID_DIGEST)
        self.assertEqual(result["status"], "FIA_AUTHORITY_HOLD")

    def test_source_host_and_path_scope_is_exact(self):
        with self.assertRaisesRegex(ValueError, "FIA_AUTHORITY_HOLD_URL_SCOPE"):
            module.retrieve("https://attacker.example/fia.pdf", 1)

    def test_if_dr002_claims_prospective_success_from_postcutoff_observation_fail(self):
        with patch.object(module.candidate, "assess_fia_grid_document_candidate",
                          return_value={"status":"VALIDATED","reasons":[]}), \
             patch.object(module, "extract_positions_from_pdf",
                          return_value=module.GRID_DIGEST):
            self.assertEqual(module.observe(clock=POST, reader=reader,
                                parser=module.extract_positions_from_pdf)["status"],
                             "FIA_AUTHORITY_HOLD")


if __name__ == "__main__":
    unittest.main()
