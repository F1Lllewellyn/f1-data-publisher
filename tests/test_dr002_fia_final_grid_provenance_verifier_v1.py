"""Deterministic offline tests for Austin FIA Document 50 verification."""
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_dr002_github_attestation_binding_v1 as bridge_fixture  # noqa: E402
from scripts.forecast_bundles import (  # noqa: E402
    dr002_fia_final_grid_provenance_verifier_v1 as verifier,
)


HISTORICAL_GRID = (
    ROOT / "history/session_data_processor/2026_1297_united_states_austin_austin/"
    "20261027T045604Z/race_11396/raw/openf1_starting_grid.json"
)


def git_blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def classified_grid_bytes(profile):
    rows = [
        {
            "driver_number": driver,
            "meeting_key": int(profile["meeting_id"]),
            "position": position,
            "session_key": profile["observed_source_session_id"],
            "start_classification": "grid",
        }
        for position, driver in profile["conventional_grid"]
    ]
    rows.extend({
        "driver_number": driver,
        "meeting_key": int(profile["meeting_id"]),
        "position": None,
        "session_key": profile["observed_source_session_id"],
        "start_classification": "pit_lane",
    } for driver in profile["pit_lane_drivers"])
    return verifier.consumer.receipts.canonical_json_bytes(rows)


def synthetic_fixture(*, observed_grid_bytes=None):
    profile = verifier._austin_profile()
    source = b"%PDF-1.4\n% MOCK TEST BYTES ONLY\n%%EOF\n"
    profile["raw_document_sha256"] = verifier.consumer.receipts.sha256(source)
    profile["raw_document_size_bytes"] = len(source)
    observed = observed_grid_bytes if observed_grid_bytes is not None else HISTORICAL_GRID.read_bytes()
    profile["observed_grid_sha256"] = verifier.consumer.receipts.sha256(observed)

    receipt, _, _, verified, identity, verification_ref = bridge_fixture.fixture()
    receipt = copy.deepcopy(receipt)
    receipt.update(
        receipt_id="source_capture:austin-doc50-test-fixture",
        receipt_created_utc="2026-10-28T20:00:02Z",
        scope={
            "event_id": profile["event_id"],
            "meeting_id": profile["meeting_id"],
            "session_id": profile["race_session_id"],
        },
    )
    claimed_source_id = "claimed_fia_pdf_uri:" + verifier.candidate.sha256(
        verifier.candidate.SOURCE_ID_DOMAIN + profile["document_uri"].encode("utf-8")
    )
    receipt["payload"].update(
        source_id=claimed_source_id,
        source_uri=profile["document_uri"],
        source_sha256=profile["raw_document_sha256"],
        event_time_utc=profile["race_start_utc"],
        publisher_time_utc=profile["published_utc"],
        first_observed_utc="2026-10-28T20:00:00Z",
        ingested_utc="2026-10-28T20:00:01Z",
        capture_ref="runtime/austin-doc50.pdf",
        implementation="synthetic-offline-test-fixture",
    )
    receipt_bytes = verifier.consumer.receipts.canonical_json_bytes(receipt)
    receipt_digest = verifier.consumer.receipts.sha256(receipt_bytes)

    verified = copy.deepcopy(verified)
    statement = verified["result"]["statement"]
    statement["subject"][0]["digest"]["sha256"] = receipt_digest
    bundle = verified["result"]["bundle"]
    bundle["dsseEnvelope"]["payload"] = base64.b64encode(
        verifier.consumer.receipts.canonical_json_bytes(statement)
    ).decode()
    verified["result"]["bundle"] = copy.deepcopy(bundle)
    verified["result"]["statement"] = statement
    verified["result"]["verifiedTimestamps"] = [{
        "type": "Tlog",
        "uri": "https://rekor.sigstore.dev",
        "timestamp": "2026-10-28T20:00:03Z",
    }]
    bridge_result = verifier.consumer.bridge.build_verified_github_receipt_binding(
        receipt_bytes,
        verifier.consumer.receipts.canonical_json_bytes(bundle),
        verified,
        identity,
        verification_ref,
    )
    assert bridge_result["status"] == "VERIFIED_GITHUB_PROVENANCE_BINDING"
    return profile, {
        "raw_document_bytes": source,
        "source_capture_receipt_bytes": receipt_bytes,
        "bridge_result": bridge_result,
        "observed_grid_bytes": observed,
    }


def call(profile, args):
    with patch.object(verifier, "_austin_profile", return_value=copy.deepcopy(profile)):
        return verifier.verify_austin_final_starting_grid(**args)


class AustinDocument50VerificationTests(unittest.TestCase):
    def assert_hold(self, profile, args, reason=None):
        result = call(profile, args)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["document_custody_verified"])
        self.assertFalse(result["official_final_grid_reference_verified"])
        self.assertEqual(result["differences"], [])
        if reason is not None:
            self.assertEqual(result["reason_codes"], [reason])
        self.assertTrue(all(result[key] is False for key in verifier._ALWAYS_FALSE))

    def test_reference_identity_is_exact_austin_document_50(self):
        profile = verifier._austin_profile()
        self.assertEqual(profile["profile_id"], "fia:2026-united-states-grand-prix:document-50")
        self.assertEqual(profile["raw_document_sha256"],
                         "68175d2f0e065da67b78ef38486b0d0aca4e8e370c7b35266614c0afb7bd0454")
        self.assertEqual(profile["raw_document_size_bytes"], 510017)
        self.assertEqual(profile["document_number"], 50)
        self.assertEqual(profile["published_utc"], "2026-10-25T19:00:00Z")
        self.assertEqual(profile["race_start_utc"], "2026-10-25T20:00:00Z")
        self.assertEqual(profile["index_publication_text"], "25.10.26 20:00 CET")
        self.assertEqual(profile["document_header_time"], "14:00")

    def test_official_grid_has_22_drivers_21_positions_and_one_pit_lane(self):
        profile = verifier._austin_profile()
        self.assertEqual(tuple(position for position, _ in profile["conventional_grid"]),
                         tuple(range(1, 22)))
        self.assertEqual(len(profile["conventional_grid"]), 21)
        self.assertEqual(profile["pit_lane_drivers"], (18,))
        drivers = [driver for _, driver in profile["conventional_grid"]]
        self.assertEqual(len(set(drivers) | set(profile["pit_lane_drivers"])), 22)
        self.assertNotIn(18, drivers)

    def test_retained_austin_grid_identity_is_immutable_history(self):
        raw = HISTORICAL_GRID.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), verifier.AUSTIN_OBSERVED_GRID_SHA256)
        self.assertEqual(git_blob_sha(raw), "61a7d713c864a270bec18ba4de35cc50a009fd89")
        rows = json.loads(raw)
        self.assertEqual([row["driver_number"] for row in rows],
                         [12, 3, 6, 16, 44, 63, 81, 1, 30, 10, 27, 14,
                          87, 41, 31, 18, 55, 23, 11, 77, 43, 5])
        self.assertEqual({row["session_key"] for row in rows}, {11392})

    def test_austin_regression_returns_exact_discrepancy_hold(self):
        profile, args = synthetic_fixture()
        result = call(profile, args)
        self.assertEqual(result["status"], verifier.DISCREPANCY_HOLD)
        self.assertEqual(result["reason_codes"], ["observed_grid_differs_from_fia_final_grid"])
        self.assertTrue(result["document_custody_verified"])
        self.assertTrue(result["official_final_grid_reference_verified"])
        self.assertFalse(result["observed_grid_matches_official"])
        self.assertEqual(result["official_driver_count"], 22)
        self.assertEqual(result["official_conventional_position_count"], 21)
        self.assertEqual(result["official_pit_lane_driver_count"], 1)
        self.assertEqual(result["observed_driver_count"], 22)
        self.assertEqual(result["custody_trust_scope"], "GITHUB_EXECUTION_PROVENANCE_ONLY")

    def test_car_18_is_pit_lane_not_position_16(self):
        profile, args = synthetic_fixture()
        result = call(profile, args)
        difference = next(x for x in result["differences"] if x["driver_number"] == 18)
        self.assertEqual(difference, {
            "driver_number": 18,
            "observed_classification": "grid",
            "observed_position": 16,
            "official_classification": "pit_lane",
            "official_position": None,
        })

    def test_all_seven_austin_differences_are_exact(self):
        profile, args = synthetic_fixture()
        result = call(profile, args)
        compact = [
            (x["driver_number"], x["observed_position"], x["official_position"],
             x["official_classification"])
            for x in result["differences"]
        ]
        self.assertEqual(compact, [
            (55, 17, 16, "grid"), (23, 18, 17, "grid"),
            (11, 19, 18, "grid"), (77, 20, 19, "grid"),
            (43, 21, 20, "grid"), (5, 22, 21, "grid"),
            (18, 16, None, "pit_lane"),
        ])

    def test_exact_classified_match_is_retrospective_only(self):
        base = verifier._austin_profile()
        observed = classified_grid_bytes(base)
        profile, args = synthetic_fixture(observed_grid_bytes=observed)
        result = call(profile, args)
        self.assertEqual(result["status"], verifier.VERIFIED_MATCH)
        self.assertEqual(result["differences"], [])
        self.assertTrue(result["observed_grid_matches_official"])
        self.assertTrue(result["document_custody_verified"])
        self.assertTrue(result["publication_time_evidence"]["retrospective_only"])
        self.assertTrue(all(result[key] is False for key in verifier._ALWAYS_FALSE))

    def test_discrepancy_never_returns_a_corrected_grid(self):
        profile, args = synthetic_fixture()
        result = call(profile, args)
        self.assertNotIn("corrected_grid", result)
        self.assertNotIn("official_grid", result)
        self.assertFalse(result["corrected_grid_published"])
        self.assertFalse(result["race_predictions_unlocked"])
        self.assertFalse(result["fantasy_predictions_unlocked"])

    def test_document_bytes_and_size_are_pinned(self):
        profile, args = synthetic_fixture()
        args["raw_document_bytes"] += b"mutation"
        self.assert_hold(profile, args, "unrecognized_document_size")
        profile, args = synthetic_fixture()
        changed = bytearray(args["raw_document_bytes"]); changed[-3] ^= 1
        args["raw_document_bytes"] = bytes(changed)
        self.assert_hold(profile, args, "unrecognized_document_revision")

    def test_observed_grid_revision_is_pinned(self):
        profile, args = synthetic_fixture()
        rows = json.loads(args["observed_grid_bytes"])
        rows[0]["driver_number"] = 999
        args["observed_grid_bytes"] = json.dumps(rows).encode()
        self.assert_hold(profile, args, "unrecognized_observed_grid_revision")

    def test_custody_receipt_and_binding_are_required(self):
        for field, value in [
            ("source_capture_receipt_bytes", b"{}"),
            ("bridge_result", None),
        ]:
            with self.subTest(field=field):
                profile, args = synthetic_fixture(); args[field] = value
                self.assert_hold(profile, args, "document_custody_not_verified")

    def test_receipt_uri_publisher_time_and_source_identity_are_exact(self):
        changes = [
            ("source_uri", "https://www.fia.com/wrong.pdf", "document_uri_mismatch"),
            ("publisher_time_utc", "2026-10-25T18:59:59Z",
             "publication_time_receipt_mismatch"),
            ("source_id", "claimed_fia_pdf_uri:wrong", "receipt_source_identity_mismatch"),
        ]
        for field, value, reason in changes:
            with self.subTest(field=field):
                profile, args = synthetic_fixture()
                receipt = json.loads(args["source_capture_receipt_bytes"])
                receipt["payload"][field] = value
                args["source_capture_receipt_bytes"] = verifier.consumer.receipts.canonical_json_bytes(receipt)
                # The original binding no longer matches changed receipt bytes, so custody fails first.
                self.assert_hold(profile, args, "document_custody_not_verified")

    def test_event_meeting_and_race_session_are_bound_by_custody(self):
        for field in ["event_id", "meeting_id", "session_id"]:
            with self.subTest(field=field):
                profile, args = synthetic_fixture()
                receipt = json.loads(args["source_capture_receipt_bytes"])
                receipt["scope"][field] = "wrong"
                args["source_capture_receipt_bytes"] = verifier.consumer.receipts.canonical_json_bytes(receipt)
                self.assert_hold(profile, args, "document_custody_not_verified")

    def test_publication_evidence_profile_changes_hold(self):
        for field, value in [
            ("published_utc", "2026-10-25T18:59:59Z"),
            ("index_publication_text", "25.10.26 19:59 CET"),
            ("document_header_time", "13:59"),
        ]:
            with self.subTest(field=field):
                profile, args = synthetic_fixture(); profile[field] = value
                self.assert_hold(profile, args, "publication_time_evidence_mismatch")

    def test_malformed_official_pit_lane_or_positions_hold(self):
        changes = []
        profile, args = synthetic_fixture(); profile["pit_lane_drivers"] = (); changes.append((profile, args))
        profile, args = synthetic_fixture(); profile["pit_lane_drivers"] = (18, 18); changes.append((profile, args))
        profile, args = synthetic_fixture(); profile["conventional_grid"] = profile["conventional_grid"][:-1]; changes.append((profile, args))
        profile, args = synthetic_fixture();
        profile["conventional_grid"] = ((2, 12),) + profile["conventional_grid"][1:]; changes.append((profile, args))
        for profile, args in changes:
            with self.subTest(profile=profile):
                self.assertEqual(call(profile, args)["status"], "HOLD")

    def test_malformed_observed_schema_duplicate_and_hole_hold(self):
        base = verifier._austin_profile()
        fixtures = []
        rows = json.loads(classified_grid_bytes(base)); del rows[0]["start_classification"]; fixtures.append(rows)
        rows = json.loads(classified_grid_bytes(base)); rows[1]["position"] = 1; fixtures.append(rows)
        rows = json.loads(classified_grid_bytes(base)); rows[0]["position"] = 99; fixtures.append(rows)
        rows = json.loads(classified_grid_bytes(base)); rows[-1]["start_classification"] = "grid"; rows[-1]["position"] = 22; fixtures.append(rows)
        for rows in fixtures:
            observed = verifier.consumer.receipts.canonical_json_bytes(rows)
            profile, args = synthetic_fixture(observed_grid_bytes=observed)
            self.assertEqual(call(profile, args)["status"], "HOLD")

    def test_wrong_meeting_source_session_and_driver_universe_hold(self):
        base = verifier._austin_profile()
        mutations = []
        rows = json.loads(classified_grid_bytes(base)); rows[0]["meeting_key"] = 999; mutations.append(rows)
        rows = json.loads(classified_grid_bytes(base)); rows[0]["session_key"] = 11396; mutations.append(rows)
        rows = json.loads(classified_grid_bytes(base)); rows[0]["driver_number"] = 999; mutations.append(rows)
        for rows in mutations:
            observed = verifier.consumer.receipts.canonical_json_bytes(rows)
            profile, args = synthetic_fixture(observed_grid_bytes=observed)
            self.assertEqual(call(profile, args)["status"], "HOLD")

    def test_inputs_are_not_mutated_and_result_is_deterministic(self):
        profile, args = synthetic_fixture()
        before_profile = copy.deepcopy(profile); before_args = copy.deepcopy(args)
        first = call(profile, args)
        self.assertEqual(first, call(profile, args))
        self.assertEqual(profile, before_profile)
        self.assertEqual(args, before_args)

    def test_no_network_filesystem_subprocess_or_pdf_parser(self):
        tree = ast.parse(Path(verifier.__file__).read_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            (node.module or "").split(".")[0]
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        self.assertFalse(imported & {
            "requests", "urllib", "socket", "subprocess", "pypdf", "PyPDF2",
            "pdfplumber", "fitz", "pathlib", "os",
        })
        profile, args = synthetic_fixture()
        with patch("builtins.open", side_effect=AssertionError("file I/O")), \
             patch.object(Path, "read_bytes", side_effect=AssertionError("path I/O")), \
             patch.object(socket, "socket", side_effect=AssertionError("network")):
            self.assertEqual(call(profile, args)["status"], verifier.DISCREPANCY_HOLD)

    def test_dependency_blobs_are_unchanged(self):
        expected = {
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
            "scripts/forecast_bundles/dr002_fia_grid_document_candidate_v1.py": "15867e3d1af56a5c00b2bd35c1220541e7e4f619",
            "scripts/forecast_bundles/dr002_fia_final_grid_capture_pilot_v1.py": "b8e017e247954e0955285e8910a145fe4ee89d52",
            "scripts/forecast_bundles/dr002_verified_source_consumer_v1.py": "e402939202ed579c368499f3baefb3641de27de7",
            "scripts/forecast_bundles/dr002_github_attestation_binding_v1.py": "215f012b79aa9e6f33aff6ad62ca7efba53a9627",
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py": "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
            "scripts/session_data_processor/session_data_processor_loop_v1.py": "6a9af69e13a937230788cfb08f889bdc36e95018",
            "docs/F1_PROJECT_ROADMAP_AND_CONTINUITY.md": "23f7ee1f673a02fa676ca29f4ba1ab9f049e7189",
            "docs/GRID_PROVENANCE_CHECKPOINT_2026-09-16.md": "7bed9ea1a96d2e5d6f2eceff28fcb4ac0ae48b09",
        }
        for path, expected_blob in expected.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob_sha((ROOT / path).read_bytes()), expected_blob)


if __name__ == "__main__":
    unittest.main()
