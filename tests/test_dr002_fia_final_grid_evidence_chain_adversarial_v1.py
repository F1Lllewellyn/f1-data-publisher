"""Adversarial offline rehearsal for the FIA final-grid evidence chain.

All source, receipt, and attestation material in this test is synthetic.  The
GitHub verification result is caller-supplied fixture data, not independent
attestation evidence.  A successful control proves internal composition only.
"""
import ast
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_PATH = (
    REPO_ROOT / "scripts/forecast_bundles/dr002_fia_final_grid_capture_pilot_v1.py"
)
EXECUTION_BOUNDARY_PATH = (
    REPO_ROOT
    / "scripts/forecast_bundles/dr002_fia_capture_attestation_execution_binding_v1.py"
)
CAPTURE_SPEC = importlib.util.spec_from_file_location("adversarial_fia_capture", CAPTURE_PATH)
capture = importlib.util.module_from_spec(CAPTURE_SPEC)
CAPTURE_SPEC.loader.exec_module(capture)
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from scripts.forecast_bundles import (  # noqa: E402
    dr002_fia_capture_attestation_execution_binding_v1 as execution_binding,
)
from scripts.forecast_bundles import (  # noqa: E402
    dr002_fia_final_grid_provenance_verifier_v1 as verifier,
)
from scripts.forecast_bundles import (  # noqa: E402
    dr002_verified_source_consumer_v1 as consumer,
)


SYNTHETIC_PDF = (
    b"%PDF-1.7\n% SYNTHETIC OFFLINE ADVERSARIAL FIA GRID EVIDENCE\n"
    b"1 0 obj\n<<>>\nendobj\n%%EOF\n"
)

DEPENDENCY_BLOBS = {
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
    "scripts/forecast_bundles/dr002_fia_grid_document_candidate_v1.py":
        "15867e3d1af56a5c00b2bd35c1220541e7e4f619",
    "scripts/forecast_bundles/dr002_fia_final_grid_capture_pilot_v1.py":
        "77da722beb1e22ff99eac6e2a26e5dd04fb4b69c",
    "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
        "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
    "scripts/forecast_bundles/dr002_github_attestation_binding_v1.py":
        "215f012b79aa9e6f33aff6ad62ca7efba53a9627",
    "scripts/forecast_bundles/dr002_verified_source_consumer_v1.py":
        "e402939202ed579c368499f3baefb3641de27de7",
    "scripts/forecast_bundles/dr002_fia_final_grid_provenance_verifier_v1.py":
        "2f9f2266a87f8a2a743bc64a55fd0bd7f8fba204",
    "scripts/forecast_bundles/dr002_fia_capture_attestation_execution_binding_v1.py":
        "8224c9d0efc9790533ba5e5279d59cbc44286f80",
    "tests/test_dr002_github_attestation_binding_v1.py":
        "1d764c840202463e091110132521f23f34853ad0",
    "tests/test_dr002_fia_grid_document_candidate_v1.py":
        "85f6c8bb78110f927441b71e69d664742082da9e",
    "tests/test_dr002_fia_final_grid_capture_pilot_v1.py":
        "761303a365a59c11dd41f5e7a6fdc93dbc9a0713",
    "tests/test_dr002_verified_source_consumer_v1.py":
        "147ac565554f6912f04613baebb79fbe14704ec6",
    "tests/test_dr002_fia_final_grid_provenance_verifier_v1.py":
        "0b1fbc684cfd91f00b1cd940add995af3c441ede",
}


class FiaFinalGridEvidenceChainAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime_root = Path(self.temp.name) / "runtime"
        self.calls = 0
        self.capture_profile = self._capture_profile()
        self.capture_result, output_root = self._run_actual_capture()
        self.capture_manifest_bytes = (output_root / "capture_manifest.json").read_bytes()
        self.capture_manifest = json.loads(self.capture_manifest_bytes)
        self.receipt_bytes = (output_root / "source_capture_receipt.json").read_bytes()
        self.source_bytes = (
            output_root / "raw/fia_final_starting_grid_doc_51.pdf"
        ).read_bytes()
        self.receipt = json.loads(self.receipt_bytes)
        self._assert_capture_manifest_execution()
        self.bridge_parts = self._attestation_parts(
            self.receipt_bytes, self.capture_manifest
        )
        self.bridge_result = self._call_execution_boundary(self.bridge_parts)
        self.observed_rows = self._matching_rows()
        self.observed_grid_bytes = consumer.receipts.canonical_json_bytes(self.observed_rows)
        self.reference_profile = self._reference_profile()

        self.assertEqual(self.calls, 1)
        self.assertEqual(
            self.capture_result["validation_status"], "CAPTURED_UNBOUND_CANDIDATE"
        )
        self.assertTrue(
            all(
                self.capture_result[name] is False
                for name in capture.INTAKE_FALSE_CLAIMS
            )
        )
        self.assertEqual(
            self.bridge_result["status"], "VERIFIED_GITHUB_PROVENANCE_BINDING"
        )
        self.assertTrue(
            all(
                self.bridge_result[name] is False
                for name in consumer.bridge.HOLD_TRUST
            )
        )

    def tearDown(self):
        self.temp.cleanup()

    def _capture_profile(self):
        event_id = "2026_1300_example_grand_prix_example"
        index_uri = (
            "https://www.fia.com/documents/championships/"
            "fia-formula-one-world-championship-14/event/Example%20Grand%20Prix"
        )
        return {
            "schema_version": capture.CAPTURE_PROFILE_SCHEMA_VERSION,
            "profile_id": event_id + ":document-51",
            "document_type": "final_starting_grid",
            "document_number": 51,
            "document_title": "Final Starting Grid",
            "document_uri": (
                "https://www.fia.com/system/files/decision-document/"
                "2026_example_grand_prix_-_final_starting_grid.pdf"
            ),
            "official_index_uri": index_uri,
            "event_id": event_id,
            "meeting_id": "1300",
            "session_id": "11400",
            "claimed_published_utc": "2026-11-01T15:00:00Z",
            "publication_evidence": {
                "official_index_uri": index_uri,
                "claimed_published_utc": "2026-11-01T15:00:00Z",
                "index_publication_text": "01.11.26 15:00",
                "document_header_date": "01 November 2026",
                "document_header_time": "15:00",
            },
            "expected_document_sha256": capture.sha256(SYNTHETIC_PDF),
        }

    def _run_actual_capture(self):
        profile_bytes = capture.canonical_json_bytes(self.capture_profile)
        times = iter((
            "2026-11-01T16:00:00Z",
            "2026-11-01T16:00:01Z",
            "2026-11-01T16:00:02Z",
            "2026-11-01T16:00:03Z",
        ))

        def request(uri):
            self.calls += 1
            self.assertEqual(uri, self.capture_profile["document_uri"])
            return {
                "status": 200,
                "body": SYNTHETIC_PDF,
                "content_type": "application/pdf",
                "content_length": len(SYNTHETIC_PDF),
                "final_url": uri,
                "complete": True,
                "redirected": False,
            }

        result = capture.capture_fia_final_grid_intake(
            capture_profile_bytes=profile_bytes,
            expected_capture_profile_sha256=capture.sha256(profile_bytes),
            prior_receipt_bytes=(),
            github_run_id="86420",
            github_run_attempt="1",
            repository=capture.REPOSITORY,
            git_commit="c" * 40,
            workflow_ref=(
                capture.REPOSITORY + "/" + capture.WORKFLOW_PATH + "@refs/heads/main"
            ),
            request=request,
            clock=lambda: next(times),
            runtime_root=self.runtime_root,
        )
        return result, self.runtime_root / "gha-86420-1"

    def _assert_capture_manifest_execution(self):
        expected_workflow = (
            capture.REPOSITORY + "/" + capture.WORKFLOW_PATH + "@refs/heads/main"
        )
        self.assertEqual(self.capture_manifest_bytes, capture.canonical_json_bytes(
            self.capture_manifest
        ))
        self.assertEqual(self.capture_manifest["repository"], capture.REPOSITORY)
        self.assertEqual(self.capture_manifest["implementation_git_sha"], "c" * 40)
        self.assertEqual(self.capture_manifest["workflow_ref"], expected_workflow)
        self.assertEqual(self.capture_manifest["github_run_id"], "86420")
        self.assertEqual(self.capture_manifest["github_run_attempt"], "1")
        self.assertEqual(self.capture_manifest["run_id"], "gha-86420-1")
        self.assertEqual(
            self.capture_manifest["source_capture_receipt_sha256"],
            consumer.receipts.sha256(self.receipt_bytes),
        )

    def _identity_from_capture_manifest(self, manifest):
        repository = manifest["repository"]
        signer_workflow, separator, source_ref = manifest["workflow_ref"].rpartition("@")
        self.assertEqual(separator, "@")
        self.assertTrue(signer_workflow.startswith(repository + "/"))
        run_uri = (
            "https://github.com/" + repository + "/actions/runs/"
            + manifest["github_run_id"] + "/attempts/"
            + manifest["github_run_attempt"]
        )
        return {
            "repository": repository,
            "signer_workflow": signer_workflow,
            "source_ref": source_ref,
            "source_digest": manifest["implementation_git_sha"],
            "signer_digest": manifest["implementation_git_sha"],
            "runner_environment": "github-hosted",
            "workflow_trigger": "workflow_dispatch",
            "run_invocation_uri": run_uri,
            "oidc_issuer": "https://token.actions.githubusercontent.com",
        }

    def _attestation_parts(self, receipt_bytes, manifest=None):
        """Build coherent simulated proof; no cryptographic verification occurs."""
        manifest = self.capture_manifest if manifest is None else manifest
        identity = self._identity_from_capture_manifest(manifest)
        repository = identity["repository"]
        repo_url = "https://github.com/" + repository
        workflow_path = identity["signer_workflow"][len(repository) + 1:]
        signer_uri = repo_url + "/" + workflow_path + "@" + identity["source_ref"]
        statement = {
            "_type": consumer.bridge.STATEMENT_TYPE,
            "subject": [{
                "name": "source_capture_receipt.json",
                "digest": {"sha256": consumer.receipts.sha256(receipt_bytes)},
            }],
            "predicateType": consumer.bridge.PREDICATE_TYPE,
            "predicate": {
                "buildDefinition": {
                    "buildType": consumer.bridge.BUILD_TYPE,
                    "externalParameters": {"workflow": {
                        "path": workflow_path,
                        "ref": identity["source_ref"],
                        "repository": repo_url,
                    }},
                    "internalParameters": {"github": {
                        "event_name": identity["workflow_trigger"],
                        "runner_environment": identity["runner_environment"],
                    }},
                    "resolvedDependencies": [{
                        "digest": {"gitCommit": identity["source_digest"]},
                        "uri": "git+" + repo_url + "@" + identity["source_ref"],
                    }],
                },
                "runDetails": {
                    "builder": {"id": signer_uri},
                    "metadata": {"invocationId": identity["run_invocation_uri"]},
                },
            },
        }
        certificate = {
            "subjectAlternativeName": signer_uri,
            "issuer": identity["oidc_issuer"],
            "githubWorkflowTrigger": identity["workflow_trigger"],
            "githubWorkflowSHA": identity["signer_digest"],
            "githubWorkflowRepository": repository,
            "githubWorkflowRef": identity["source_ref"],
            "buildSignerURI": signer_uri,
            "buildSignerDigest": identity["signer_digest"],
            "runnerEnvironment": identity["runner_environment"],
            "sourceRepositoryURI": repo_url,
            "sourceRepositoryDigest": identity["source_digest"],
            "sourceRepositoryRef": identity["source_ref"],
            "buildConfigURI": signer_uri,
            "buildConfigDigest": identity["signer_digest"],
            "buildTrigger": identity["workflow_trigger"],
            "runInvocationURI": identity["run_invocation_uri"],
        }
        bundle = {
            "mediaType": consumer.bridge.BUNDLE_MEDIA_TYPE,
            "verificationMaterial": {
                "certificate": {"rawBytes": "synthetic-fixture"},
                "tlogEntries": [],
            },
            "dsseEnvelope": {
                "payload": base64.b64encode(
                    consumer.receipts.canonical_json_bytes(statement)
                ).decode(),
                "payloadType": consumer.bridge.DSSE_PAYLOAD_TYPE,
                "signatures": [{"sig": "synthetic-fixture-signature"}],
            },
        }
        verified = {
            "verification_status": "VERIFIED",
            "verifier": consumer.bridge.APPROVED_VERIFIER,
            "result": {
                "mediaType": consumer.bridge.VERIFICATION_MEDIA_TYPE,
                "signature": {"certificate": certificate},
                "verifiedTimestamps": [{
                    "type": "Tlog",
                    "uri": "https://rekor.sigstore.dev",
                    "timestamp": "2026-11-01T16:00:04Z",
                }],
                "statement": copy.deepcopy(statement),
                "bundle": copy.deepcopy(bundle),
            },
        }
        return {
            "receipt_bytes": receipt_bytes,
            "bundle_bytes": consumer.receipts.canonical_json_bytes(bundle),
            "verified": verified,
            "identity": identity,
            "verification_ref": repo_url + "/attestations/456",
        }

    def _rebind_statement(self, parts, mutate):
        changed = copy.deepcopy(parts)
        statement = copy.deepcopy(changed["verified"]["result"]["statement"])
        mutate(statement)
        bundle = copy.deepcopy(changed["verified"]["result"]["bundle"])
        bundle["dsseEnvelope"]["payload"] = base64.b64encode(
            consumer.receipts.canonical_json_bytes(statement)
        ).decode()
        changed["verified"]["result"]["statement"] = copy.deepcopy(statement)
        changed["verified"]["result"]["bundle"] = copy.deepcopy(bundle)
        changed["bundle_bytes"] = consumer.receipts.canonical_json_bytes(bundle)
        return changed

    def _call_bridge(self, parts):
        return consumer.bridge.build_verified_github_receipt_binding(
            parts["receipt_bytes"],
            parts["bundle_bytes"],
            parts["verified"],
            parts["identity"],
            parts["verification_ref"],
        )

    def _call_execution_boundary(self, parts, manifest_bytes=None):
        return execution_binding.build_capture_bound_verified_github_receipt_binding(
            capture_manifest_bytes=(
                self.capture_manifest_bytes if manifest_bytes is None else manifest_bytes
            ),
            receipt_bytes=parts["receipt_bytes"],
            attestation_bundle_bytes=parts["bundle_bytes"],
            verified_attestation_result=parts["verified"],
            attested_identity=parts["identity"],
            verification_ref=parts["verification_ref"],
        )

    def _coherent_alternate_execution(self, **changes):
        manifest = copy.deepcopy(self.capture_manifest)
        original_repository = manifest["repository"]
        manifest.update(changes)
        if "repository" in changes and "workflow_ref" not in changes:
            suffix = manifest["workflow_ref"][len(original_repository):]
            manifest["workflow_ref"] = manifest["repository"] + suffix
        manifest["run_id"] = (
            "gha-" + manifest["github_run_id"] + "-" + manifest["github_run_attempt"]
        )
        return self._attestation_parts(self.receipt_bytes, manifest)

    def _matching_rows(self):
        rows = [
            {
                "driver_number": driver,
                "meeting_key": 1300,
                "position": position,
                "session_key": 11399,
                "start_classification": "grid",
            }
            for position, driver in ((1, 1), (2, 2), (3, 3), (4, 4))
        ]
        rows.append({
            "driver_number": 5,
            "meeting_key": 1300,
            "position": None,
            "session_key": 11399,
            "start_classification": "pit_lane",
        })
        return rows

    def _reference_profile(self):
        publication = self.capture_profile["publication_evidence"]
        return {
            "profile_schema_version": verifier.PROFILE_SCHEMA_VERSION,
            "profile_id": self.capture_profile["profile_id"],
            "event_id": self.capture_profile["event_id"],
            "meeting_id": self.capture_profile["meeting_id"],
            "race_session_id": self.capture_profile["session_id"],
            "observed_source_session_id": 11399,
            "document_uri": self.capture_profile["document_uri"],
            "official_index_uri": self.capture_profile["official_index_uri"],
            "document_number": self.capture_profile["document_number"],
            "document_title": self.capture_profile["document_title"],
            "document_type": self.capture_profile["document_type"],
            "raw_document_sha256": consumer.receipts.sha256(self.source_bytes),
            "raw_document_size_bytes": len(self.source_bytes),
            "observed_grid_sha256": consumer.receipts.sha256(
                self.observed_grid_bytes
            ),
            "published_utc": self.capture_profile["claimed_published_utc"],
            "race_start_utc": "2026-11-01T15:30:00Z",
            "index_publication_text": publication["index_publication_text"],
            "document_header_date": publication["document_header_date"],
            "document_header_time": publication["document_header_time"],
            "conventional_grid": [[1, 1], [2, 2], [3, 3], [4, 4]],
            "pit_lane_drivers": [5],
        }

    def _verify(
        self, *, profile=None, rows=None, source_bytes=None, receipt_bytes=None,
        bridge_result=None,
    ):
        profile = copy.deepcopy(self.reference_profile if profile is None else profile)
        if rows is None:
            observed_grid_bytes = self.observed_grid_bytes
        else:
            observed_grid_bytes = consumer.receipts.canonical_json_bytes(rows)
            profile["observed_grid_sha256"] = consumer.receipts.sha256(
                observed_grid_bytes
            )
        profile_bytes = consumer.receipts.canonical_json_bytes(profile)
        return verifier.verify_final_starting_grid(
            reference_profile_bytes=profile_bytes,
            expected_reference_profile_sha256=consumer.receipts.sha256(profile_bytes),
            raw_document_bytes=(self.source_bytes if source_bytes is None else source_bytes),
            source_capture_receipt_bytes=(
                self.receipt_bytes if receipt_bytes is None else receipt_bytes
            ),
            bridge_result=(self.bridge_result if bridge_result is None else bridge_result),
            observed_grid_bytes=observed_grid_bytes,
        )

    def _assert_bridge_hold(self, result, reason):
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason_codes"], [reason])
        self.assertEqual(result["verified_receipt_bindings"], {})
        self.assertTrue(
            all(result[name] is False for name in consumer.bridge.HOLD_TRUST)
        )

    def _assert_verifier_fail_closed(self, result, status, reason):
        self.assertEqual(result["status"], status)
        self.assertEqual(result["reason_codes"], [reason])
        self.assertTrue(all(result[name] is False for name in verifier._ALWAYS_FALSE))
        for forbidden in (
            "corrected_grid", "corrected_observed_grid", "published_grid",
            "source_readiness", "forecast_eligibility",
        ):
            self.assertNotIn(forbidden, result)

    def test_capture_manifest_builds_one_coherent_synthetic_attestation(self):
        identity = self.bridge_parts["identity"]
        expected_identity = self._identity_from_capture_manifest(self.capture_manifest)
        self.assertEqual(identity, expected_identity)

        verified_result = self.bridge_parts["verified"]["result"]
        statement = verified_result["statement"]
        saved_bundle = json.loads(self.bridge_parts["bundle_bytes"])
        decoded_statement = json.loads(base64.b64decode(
            saved_bundle["dsseEnvelope"]["payload"], validate=True
        ))
        certificate = verified_result["signature"]["certificate"]
        workflow_path = identity["signer_workflow"][len(identity["repository"]) + 1:]

        self.assertEqual(decoded_statement, statement)
        self.assertEqual(saved_bundle, verified_result["bundle"])
        self.assertEqual(
            statement["subject"][0]["digest"]["sha256"],
            consumer.receipts.sha256(self.receipt_bytes),
        )
        self.assertEqual(
            statement["predicate"]["buildDefinition"]["externalParameters"][
                "workflow"
            ],
            {
                "path": workflow_path,
                "ref": identity["source_ref"],
                "repository": "https://github.com/" + identity["repository"],
            },
        )
        self.assertEqual(
            statement["predicate"]["buildDefinition"]["resolvedDependencies"][0][
                "digest"
            ]["gitCommit"],
            self.capture_manifest["implementation_git_sha"],
        )
        self.assertEqual(
            statement["predicate"]["runDetails"]["metadata"]["invocationId"],
            identity["run_invocation_uri"],
        )
        self.assertEqual(
            certificate["githubWorkflowRepository"],
            self.capture_manifest["repository"],
        )
        self.assertEqual(
            certificate["sourceRepositoryDigest"],
            self.capture_manifest["implementation_git_sha"],
        )
        self.assertEqual(
            certificate["buildConfigURI"],
            "https://github.com/" + identity["signer_workflow"]
            + "@" + identity["source_ref"],
        )
        self.assertEqual(
            certificate["runInvocationURI"], identity["run_invocation_uri"]
        )
        self.assertEqual(
            self._call_bridge(self.bridge_parts)["status"],
            "VERIFIED_GITHUB_PROVENANCE_BINDING",
        )
        self.assertEqual(
            self._call_execution_boundary(self.bridge_parts)["status"],
            "VERIFIED_GITHUB_PROVENANCE_BINDING",
        )

    def test_capture_vs_attestation_execution_identity_mismatches_fail_closed(self):
        cases = (
            (
                "repository",
                self._coherent_alternate_execution(repository="other/repository"),
                "capture_attestation_repository_mismatch",
            ),
            (
                "checkout_commit",
                self._coherent_alternate_execution(implementation_git_sha="d" * 40),
                "capture_attestation_commit_mismatch",
            ),
            (
                "workflow",
                self._coherent_alternate_execution(workflow_ref=(
                    capture.REPOSITORY
                    + "/.github/workflows/other.yml@refs/heads/main"
                )),
                "capture_attestation_workflow_mismatch",
            ),
            (
                "run_id",
                self._coherent_alternate_execution(github_run_id="99999"),
                "capture_attestation_run_id_mismatch",
            ),
            (
                "run_attempt",
                self._coherent_alternate_execution(github_run_attempt="2"),
                "capture_attestation_run_attempt_mismatch",
            ),
        )
        for label, coherent_wrong_execution, reason in cases:
            with self.subTest(label=label):
                self.assertEqual(
                    self._call_bridge(coherent_wrong_execution)["status"],
                    "VERIFIED_GITHUB_PROVENANCE_BINDING",
                )
                held = self._call_execution_boundary(coherent_wrong_execution)
                self._assert_bridge_hold(held, reason)
                self._assert_verifier_fail_closed(
                    self._verify(bridge_result=held),
                    "HOLD",
                    "document_custody_not_verified",
                )

    def test_capture_manifest_receipt_identity_mismatch_fails_closed(self):
        changed_receipt = copy.deepcopy(self.receipt)
        changed_receipt["payload"]["source_id"] = "claimed_fia_pdf_uri:rebound"
        changed_bytes = consumer.receipts.canonical_json_bytes(changed_receipt)
        coherently_rebound = self._attestation_parts(changed_bytes)
        self.assertEqual(
            self._call_bridge(coherently_rebound)["status"],
            "VERIFIED_GITHUB_PROVENANCE_BINDING",
        )
        held = self._call_execution_boundary(coherently_rebound)
        self._assert_bridge_hold(held, "capture_manifest_receipt_digest_mismatch")
        self._assert_verifier_fail_closed(
            self._verify(receipt_bytes=changed_bytes, bridge_result=held),
            "HOLD",
            "document_custody_not_verified",
        )

    def test_capture_manifest_malformed_states_fail_with_exact_reasons(self):
        def changed(**values):
            manifest = copy.deepcopy(self.capture_manifest)
            manifest.update(values)
            return consumer.receipts.canonical_json_bytes(manifest)

        missing = copy.deepcopy(self.capture_manifest)
        del missing["repository"]
        cases = (
            ("malformed_json", b"{", "malformed_capture_manifest"),
            (
                "noncanonical",
                json.dumps(self.capture_manifest, indent=2).encode(),
                "noncanonical_capture_manifest_bytes",
            ),
            ("duplicate_key", b'{"a":1,"a":2}', "duplicate_json_key"),
            ("nonfinite", b'{"a":NaN}', "nonfinite_json"),
            (
                "missing_identity",
                consumer.receipts.canonical_json_bytes(missing),
                "missing_capture_manifest_identity_field",
            ),
            (
                "unsupported_schema",
                changed(schema_version="unknown"),
                "unsupported_capture_manifest_schema",
            ),
            (
                "held_capture",
                changed(validation_status="HOLD"),
                "capture_manifest_not_successful_unbound_candidate",
            ),
            (
                "malformed_repository",
                changed(repository=[]),
                "malformed_capture_manifest_identity",
            ),
            (
                "malformed_workflow",
                changed(workflow_ref="not-a-workflow"),
                "malformed_capture_manifest_workflow_identity",
            ),
            (
                "invalid_run_id",
                changed(github_run_id="0"),
                "malformed_capture_manifest_run_identity",
            ),
            (
                "invalid_attempt",
                changed(github_run_attempt="0"),
                "malformed_capture_manifest_run_identity",
            ),
            (
                "inconsistent_run_identity",
                changed(run_id="gha-86420-9"),
                "capture_manifest_run_identity_mismatch",
            ),
        )
        for label, manifest_bytes, reason in cases:
            with self.subTest(label=label):
                held = self._call_execution_boundary(
                    self.bridge_parts, manifest_bytes=manifest_bytes
                )
                self._assert_bridge_hold(held, reason)
                self._assert_verifier_fail_closed(
                    self._verify(bridge_result=held),
                    "HOLD",
                    "document_custody_not_verified",
                )

    def test_excessively_nested_capture_manifest_fails_closed(self):
        nested_manifest = b'{"nested":' + b"[" * 10000 + b"0" + b"]" * 10000 + b"}"
        held = self._call_execution_boundary(
            self.bridge_parts, manifest_bytes=nested_manifest
        )
        self._assert_bridge_hold(held, "malformed_capture_manifest")
        self._assert_verifier_fail_closed(
            self._verify(bridge_result=held),
            "HOLD",
            "document_custody_not_verified",
        )

    def test_valid_control_is_actual_capture_to_retrospective_match_only(self):
        result = self._verify()
        self.assertEqual(result["status"], verifier.VERIFIED_MATCH)
        self.assertTrue(result["document_custody_verified"])
        self.assertTrue(result["github_execution_provenance_verified"])
        self.assertTrue(result["observed_grid_matches_official"])
        self.assertTrue(result["publication_time_evidence"]["retrospective_only"])
        self.assertGreater(
            consumer.receipts._time(self.receipt["payload"]["first_observed_utc"]),
            consumer.receipts._time(self.reference_profile["race_start_utc"]),
        )
        self.assertGreater(
            consumer.receipts._time(
                self.bridge_result["attested_receipt_existed_by_utc"]
            ),
            consumer.receipts._time(self.reference_profile["race_start_utc"]),
        )
        self.assertTrue(all(result[name] is False for name in verifier._ALWAYS_FALSE))

    def test_altered_document_bytes_fail_exact_revision_identity(self):
        changed = self.source_bytes.replace(b"SYNTHETIC", b"TAMPERED!")
        self.assertEqual(len(changed), len(self.source_bytes))
        result = self._verify(source_bytes=changed)
        self._assert_verifier_fail_closed(
            result, "HOLD", "unrecognized_document_revision"
        )

    def test_receipt_bytes_and_source_identity_fail_closed(self):
        noncanonical = json.dumps(self.receipt, indent=2).encode()
        parts = self._attestation_parts(noncanonical)
        bridge_hold = self._call_bridge(parts)
        self._assert_bridge_hold(bridge_hold, "noncanonical_receipt_bytes")
        self._assert_verifier_fail_closed(
            self._verify(receipt_bytes=noncanonical, bridge_result=bridge_hold),
            "HOLD",
            "document_custody_not_verified",
        )

        changed_receipt = copy.deepcopy(self.receipt)
        changed_receipt["payload"]["source_id"] = "claimed_fia_pdf_uri:altered"
        changed_bytes = consumer.receipts.canonical_json_bytes(changed_receipt)
        rebound = self._call_bridge(self._attestation_parts(changed_bytes))
        self.assertEqual(rebound["status"], "VERIFIED_GITHUB_PROVENANCE_BINDING")
        self._assert_verifier_fail_closed(
            self._verify(receipt_bytes=changed_bytes, bridge_result=rebound),
            "HOLD",
            "receipt_source_identity_mismatch",
        )

    def test_attestation_subject_digest_mismatch_returns_no_binding(self):
        parts = self._rebind_statement(
            self.bridge_parts,
            lambda statement: statement["subject"][0]["digest"].update(
                sha256="0" * 64
            ),
        )
        self._assert_bridge_hold(self._call_bridge(parts), "subject_digest_mismatch")
        self._assert_bridge_hold(
            self._call_execution_boundary(parts), "subject_digest_mismatch"
        )

    def test_attestation_workflow_commit_and_run_identity_fail_exactly(self):
        cases = (
            (
                "statement_workflow_mismatch",
                lambda statement: statement["predicate"]["buildDefinition"][
                    "externalParameters"
                ]["workflow"].update(path=".github/workflows/other.yml"),
            ),
            (
                "source_commit_mismatch",
                lambda statement: statement["predicate"]["buildDefinition"][
                    "resolvedDependencies"
                ][0]["digest"].update(gitCommit="d" * 40),
            ),
            (
                "statement_run_invocation_mismatch",
                lambda statement: statement["predicate"]["runDetails"][
                    "metadata"
                ].update(
                    invocationId="https://github.com/owner/repo/actions/runs/999/attempts/1"
                ),
            ),
        )
        for reason, mutate in cases:
            with self.subTest(reason=reason):
                parts = self._rebind_statement(self.bridge_parts, mutate)
                self._assert_bridge_hold(self._call_bridge(parts), reason)

    def test_attestation_tlog_before_receipt_creation_fails_closed(self):
        parts = copy.deepcopy(self.bridge_parts)
        parts["verified"]["result"]["verifiedTimestamps"] = [{
            "type": "Tlog",
            "uri": "https://rekor.sigstore.dev",
            "timestamp": "2026-11-01T16:00:02Z",
        }]
        self._assert_bridge_hold(
            self._call_bridge(parts), "verified_tlog_before_receipt_creation"
        )

    def test_event_meeting_and_race_session_substitutions_fail_custody(self):
        cases = (
            ("event_id", "2026_9999_other_event", "event_mismatch"),
            ("meeting_id", "9999", "meeting_mismatch"),
            ("race_session_id", "99999", "session_mismatch"),
        )
        for field, value, consumer_reason in cases:
            with self.subTest(field=field):
                profile = copy.deepcopy(self.reference_profile)
                profile[field] = value
                scope = {
                    "event_id": profile["event_id"],
                    "meeting_id": profile["meeting_id"],
                    "allowed_session_ids": [profile["race_session_id"]],
                }
                consumed = consumer.consume_verified_source(
                    receipt_bytes=self.receipt_bytes,
                    source_bytes=self.source_bytes,
                    request_scope=scope,
                    bridge_result=self.bridge_result,
                )
                self.assertEqual(consumed["status"], "HOLD")
                self.assertEqual(consumed["reason_codes"], [consumer_reason])
                self.assertTrue(
                    all(
                        consumed[name] is False
                        for name in consumer.bridge.HOLD_TRUST
                    )
                )
                self._assert_verifier_fail_closed(
                    self._verify(profile=profile),
                    "HOLD",
                    "document_custody_not_verified",
                )

    def test_publication_and_observation_chronology_fail_closed(self):
        after_race = copy.deepcopy(self.reference_profile)
        after_race["published_utc"] = "2026-11-01T15:31:00Z"
        self._assert_verifier_fail_closed(
            self._verify(profile=after_race),
            "HOLD",
            "publication_time_evidence_mismatch",
        )

        wrong_claim = copy.deepcopy(self.reference_profile)
        wrong_claim["published_utc"] = "2026-11-01T14:59:00Z"
        self._assert_verifier_fail_closed(
            self._verify(profile=wrong_claim),
            "HOLD",
            "publication_time_receipt_mismatch",
        )

        regressed = copy.deepcopy(self.receipt)
        regressed["payload"]["ingested_utc"] = "2026-11-01T16:00:00Z"
        regressed_bytes = consumer.receipts.canonical_json_bytes(regressed)
        bridge_hold = self._call_bridge(self._attestation_parts(regressed_bytes))
        self._assert_bridge_hold(bridge_hold, "inconsistent_capture_times")
        self._assert_verifier_fail_closed(
            self._verify(receipt_bytes=regressed_bytes, bridge_result=bridge_hold),
            "HOLD",
            "document_custody_not_verified",
        )

    def test_receipt_scope_identity_rebound_still_cannot_cross_event(self):
        changed = copy.deepcopy(self.receipt)
        changed["scope"]["event_id"] = "2026_9999_other_event"
        changed_bytes = consumer.receipts.canonical_json_bytes(changed)
        rebound = self._call_bridge(self._attestation_parts(changed_bytes))
        self.assertEqual(rebound["status"], "VERIFIED_GITHUB_PROVENANCE_BINDING")
        self._assert_verifier_fail_closed(
            self._verify(receipt_bytes=changed_bytes, bridge_result=rebound),
            "HOLD",
            "document_custody_not_verified",
        )

    def test_observed_driver_identity_fails_before_comparison(self):
        rows = copy.deepcopy(self.observed_rows)
        rows[-1]["driver_number"] = 99
        self._assert_verifier_fail_closed(
            self._verify(rows=rows), "HOLD", "driver_universe_mismatch"
        )

    def test_position_and_pit_lane_discrepancies_never_correct_or_unlock(self):
        position_rows = copy.deepcopy(self.observed_rows)
        position_rows[0]["position"], position_rows[1]["position"] = 2, 1

        classification_rows = copy.deepcopy(self.observed_rows)
        classification_rows[-1]["start_classification"] = "grid"
        classification_rows[-1]["position"] = 5

        for label, rows in (
            ("position", position_rows),
            ("pit_lane_classification", classification_rows),
        ):
            with self.subTest(label=label):
                result = self._verify(rows=rows)
                self._assert_verifier_fail_closed(
                    result,
                    verifier.DISCREPANCY_HOLD,
                    "observed_grid_differs_from_fia_final_grid",
                )
                self.assertFalse(result["observed_grid_matches_official"])
                self.assertTrue(result["differences"])
                self.assertTrue(result["document_custody_verified"])
                self.assertTrue(result["github_execution_provenance_verified"])

    def test_execution_boundary_is_pure_offline_and_dependency_acyclic(self):
        raw = EXECUTION_BOUNDARY_PATH.read_bytes()
        tree = ast.parse(raw)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.update(alias.name.split(".")[0] for alias in node.names)
        self.assertEqual(
            imported,
            {
                "json",
                "re",
                "dr002_github_attestation_binding_v1",
                "verify_forecast_integrity_receipts_v1",
            },
        )
        text = raw.decode("utf-8")
        self.assertNotIn("tests/", text)
        self.assertNotIn("test_dr002_fia_final_grid_evidence_chain", text)
        self.assertNotIn("dr002_fia_final_grid_capture_pilot_v1", text)

    def test_all_protected_dependency_blobs_are_exact(self):
        def git_blob(path):
            data = (REPO_ROOT / path).read_bytes()
            header = b"blob " + str(len(data)).encode() + b"\0"
            return hashlib.sha1(header + data).hexdigest()

        self.assertEqual(
            {path: git_blob(path) for path in DEPENDENCY_BLOBS},
            DEPENDENCY_BLOBS,
        )


if __name__ == "__main__":
    unittest.main()
