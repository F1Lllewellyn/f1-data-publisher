import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / 'scripts' / 'forecast_bundles'
sys.path.insert(0, str(BUNDLES))

import verify_forecast_integrity_receipts_v1 as gate2b1
import dr002_github_attestation_binding_v1 as bridge


def canonical(value):
    return gate2b1.canonical_json_bytes(value)


def source_receipt(*, live=False):
    if live:
        return {
            "parent_receipt_ids": [],
            "payload": {
                "capture_ref": "_runtime/dr002_gate2b2_capture_pilot/gha-37229086347-1/raw/openf1_weather.response.json",
                "event_time_utc": None,
                "first_observed_utc": "2026-10-04T19:42:34.866980Z",
                "implementation": "scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py",
                "ingested_utc": "2026-10-04T19:42:34.867390Z",
                "publisher_time_utc": None,
                "source_id": "openf1:weather:1295:11371",
                "source_sha256": "bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6",
                "source_uri": "https://api.openf1.org/v1/weather?session_key=11371"
            },
            "receipt_created_utc": "2026-10-04T19:42:34.868462Z",
            "receipt_id": "source_capture:c4564601dd7a9c75648a0fc6594088f2339ed404d5cce721658f50de3190929b",
            "receipt_type": "source_capture",
            "schema_version": "dr002-receipt-v1",
            "scope": {
                "event_id": "2026_1295_azerbaijan_baku_baku",
                "meeting_id": "1295",
                "session_id": "11371"
            }
        }
    return {
        "schema_version": "dr002-receipt-v1",
        "receipt_id": "source_capture:test-fixture",
        "receipt_type": "source_capture",
        "receipt_created_utc": "2026-10-04T19:42:34.868462Z",
        "scope": {"event_id": "event", "meeting_id": "meeting", "session_id": "session"},
        "parent_receipt_ids": [],
        "payload": {
            "source_id": "source",
            "source_uri": "https://example.invalid/source",
            "source_sha256": "1" * 64,
            "event_time_utc": None,
            "publisher_time_utc": None,
            "first_observed_utc": "2026-10-04T19:42:34.100000Z",
            "ingested_utc": "2026-10-04T19:42:34.200000Z",
            "capture_ref": "runtime/source.bin",
            "implementation": "capture.py",
        },
    }


def identity(*, live=False):
    if live:
        return {
            "repository": "F1Lllewellyn/f1-data-publisher",
            "signer_workflow": "F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-capture-provenance-pilot.yml",
            "source_ref": "refs/heads/main",
            "source_digest": "ffe26a8427cf1c783336b67c519c5c177964febe",
            "signer_digest": "ffe26a8427cf1c783336b67c519c5c177964febe",
            "runner_environment": "github-hosted",
            "workflow_trigger": "workflow_dispatch",
            "run_invocation_uri": "https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37229086347/attempts/1",
            "oidc_issuer": "https://token.actions.githubusercontent.com",
        }
    return {
        "repository": "owner/repo",
        "signer_workflow": "owner/repo/.github/workflows/capture.yml",
        "source_ref": "refs/heads/main",
        "source_digest": "a" * 40,
        "signer_digest": "a" * 40,
        "runner_environment": "github-hosted",
        "workflow_trigger": "workflow_dispatch",
        "run_invocation_uri": "https://github.com/owner/repo/actions/runs/123/attempts/1",
        "oidc_issuer": "https://token.actions.githubusercontent.com",
    }


def fixture(*, live=False):
    receipt = source_receipt(live=live)
    receipt_bytes = canonical(receipt)
    digest = hashlib.sha256(receipt_bytes).hexdigest()
    ident = identity(live=live)
    repo_url = "https://github.com/" + ident["repository"]
    workflow_path = ident["signer_workflow"][len(ident["repository"]) + 1:]
    signer_uri = repo_url + "/" + workflow_path + "@" + ident["source_ref"]
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "source_capture_receipt.json", "digest": {"sha256": digest}}],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://actions.github.io/buildtypes/workflow/v1",
                "externalParameters": {
                    "workflow": {
                        "path": workflow_path,
                        "ref": ident["source_ref"],
                        "repository": repo_url,
                    }
                },
                "internalParameters": {
                    "github": {
                        "event_name": ident["workflow_trigger"],
                        "runner_environment": ident["runner_environment"],
                    }
                },
                "resolvedDependencies": [{
                    "digest": {"gitCommit": ident["source_digest"]},
                    "uri": "git+" + repo_url + "@" + ident["source_ref"],
                }],
            },
            "runDetails": {
                "builder": {"id": signer_uri},
                "metadata": {"invocationId": ident["run_invocation_uri"]},
            },
        },
    }
    certificate = {
        "subjectAlternativeName": signer_uri,
        "issuer": ident["oidc_issuer"],
        "githubWorkflowTrigger": ident["workflow_trigger"],
        "githubWorkflowSHA": ident["signer_digest"],
        "githubWorkflowRepository": ident["repository"],
        "githubWorkflowRef": ident["source_ref"],
        "buildSignerURI": signer_uri,
        "buildSignerDigest": ident["signer_digest"],
        "runnerEnvironment": ident["runner_environment"],
        "sourceRepositoryURI": repo_url,
        "sourceRepositoryDigest": ident["source_digest"],
        "sourceRepositoryRef": ident["source_ref"],
        "buildConfigURI": signer_uri,
        "buildConfigDigest": ident["signer_digest"],
        "buildTrigger": ident["workflow_trigger"],
        "runInvocationURI": ident["run_invocation_uri"],
    }
    result = {
        "mediaType": "application/vnd.dev.sigstore.verificationresult+json;version=0.1",
        "signature": {"certificate": certificate},
        "verifiedTimestamps": [{"type": "Tlog", "uri": "https://rekor.sigstore.dev",
                                "timestamp": "2026-10-04T19:42:36Z"}],
        "statement": statement,
    }
    verified = {
        "verification_status": "VERIFIED",
        "verifier": "github_cli_attestation_verify",
        "result": result,
    }
    bundle = {
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "verificationMaterial": {"certificate": {"rawBytes": "fixture"}, "tlogEntries": []},
        "dsseEnvelope": {
            "payload": base64.b64encode(canonical(statement)).decode(),
            "payloadType": "application/vnd.in-toto+json",
            "signatures": [{"sig": "fixture-signature"}],
        },
    }
    ref = ("https://github.com/F1Lllewellyn/f1-data-publisher/attestations/52636060"
           if live else "https://github.com/owner/repo/attestations/456")
    return receipt, receipt_bytes, canonical(bundle), verified, ident, ref


def call(parts):
    _, receipt_bytes, bundle_bytes, verified, ident, ref = parts
    return bridge.build_verified_github_receipt_binding(
        receipt_bytes, bundle_bytes, verified, ident, ref)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.parts = fixture()

    def assertHold(self, parts=None):
        result = call(parts or self.parts)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["verified_receipt_bindings"], {})
        self.assertFalse(result["production_authenticated"])
        return result

    def mutate_verified(self, fn):
        parts = list(copy.deepcopy(self.parts))
        fn(parts[3])
        return tuple(parts)

    def test_01_success_and_gate2b1_shape(self):
        receipt, *_ = self.parts
        result = call(self.parts)
        self.assertEqual(result["status"], "VERIFIED_GITHUB_PROVENANCE_BINDING")
        self.assertEqual(result["canonical_receipt_sha256"], gate2b1.receipt_sha256(receipt))
        self.assertEqual(result["canonical_receipt_sha256"], result["exact_receipt_sha256"])
        gate2b1._external_binding(receipt, result["verified_receipt_bindings"])

    def test_02_noncanonical_receipt_holds(self):
        parts = list(self.parts)
        parts[1] = json.dumps(parts[0], indent=2, sort_keys=True).encode()
        self.assertHold(tuple(parts))

    def test_03_malformed_receipt_holds(self):
        parts = list(self.parts)
        parts[1] = b'{'
        self.assertHold(tuple(parts))

    def test_04_wrong_receipt_type_holds(self):
        parts = list(self.parts)
        receipt = copy.deepcopy(parts[0])
        receipt["receipt_type"] = "producer_execution"
        parts[1] = canonical(receipt)
        self.assertHold(tuple(parts))

    def test_05_parented_source_capture_holds(self):
        parts = list(self.parts)
        receipt = copy.deepcopy(parts[0])
        receipt["parent_receipt_ids"] = ["parent"]
        parts[1] = canonical(receipt)
        self.assertHold(tuple(parts))

    def test_06_missing_verified_result_holds(self):
        parts = list(self.parts)
        parts[3] = None
        self.assertHold(tuple(parts))

    def test_07_failed_verification_status_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v.__setitem__("verification_status", "FAILED")))

    def test_08_subject_digest_mismatch_holds(self):
        parts = list(copy.deepcopy(self.parts))
        parts[3]["result"]["statement"]["subject"][0]["digest"]["sha256"] = "0" * 64
        bundle = json.loads(parts[2])
        bundle["dsseEnvelope"]["payload"] = base64.b64encode(
            canonical(parts[3]["result"]["statement"])).decode()
        parts[2] = canonical(bundle)
        self.assertHold(tuple(parts))

    def test_09_subject_name_or_count_mismatch_holds(self):
        for mode in ("name", "count"):
            parts = list(copy.deepcopy(self.parts))
            statement = parts[3]["result"]["statement"]
            if mode == "name":
                statement["subject"][0]["name"] = "wrong.json"
            else:
                statement["subject"].append(copy.deepcopy(statement["subject"][0]))
            bundle = json.loads(parts[2])
            bundle["dsseEnvelope"]["payload"] = base64.b64encode(canonical(statement)).decode()
            parts[2] = canonical(bundle)
            self.assertHold(tuple(parts))

    def test_10_statement_predicate_build_type_mismatch_holds(self):
        paths = [
            ("_type",),
            ("predicateType",),
            ("predicate", "buildDefinition", "buildType"),
        ]
        for path in paths:
            parts = list(copy.deepcopy(self.parts))
            target = parts[3]["result"]["statement"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = "wrong"
            bundle = json.loads(parts[2])
            bundle["dsseEnvelope"]["payload"] = base64.b64encode(
                canonical(parts[3]["result"]["statement"])).decode()
            parts[2] = canonical(bundle)
            self.assertHold(tuple(parts))

    def test_11_repository_mismatch_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v["result"]["signature"]["certificate"].__setitem__(
                "githubWorkflowRepository", "other/repo")))

    def test_12_workflow_mismatch_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v["result"]["statement"]["predicate"]["buildDefinition"]
            ["externalParameters"]["workflow"].__setitem__("path", ".github/workflows/other.yml")))

    def test_13_source_ref_mismatch_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v["result"]["signature"]["certificate"].__setitem__(
                "githubWorkflowRef", "refs/heads/other")))

    def test_14_source_and_signer_commit_mismatch_holds(self):
        variants = [
            lambda v: v["result"]["signature"]["certificate"].__setitem__(
                "buildSignerDigest", "b" * 40),
            lambda v: v["result"]["signature"]["certificate"].__setitem__(
                "sourceRepositoryDigest", "b" * 40),
        ]
        for fn in variants:
            self.assertHold(self.mutate_verified(fn))

    def test_15_self_hosted_runner_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v["result"]["signature"]["certificate"].__setitem__(
                "runnerEnvironment", "self-hosted")))

    def test_16_trigger_mismatch_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v["result"]["signature"]["certificate"].__setitem__(
                "githubWorkflowTrigger", "push")))

    def test_17_run_attempt_invocation_mismatch_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v["result"]["signature"]["certificate"].__setitem__(
                "runInvocationURI", "https://github.com/owner/repo/actions/runs/123/attempts/2")))

    def test_18_oidc_issuer_mismatch_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v["result"]["signature"]["certificate"].__setitem__(
                "issuer", "https://issuer.invalid")))

    def test_19_missing_verified_tlog_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v["result"].__setitem__("verifiedTimestamps", [])))

    def test_20_tlog_before_receipt_creation_holds(self):
        self.assertHold(self.mutate_verified(
            lambda v: v["result"]["verifiedTimestamps"][0].__setitem__(
                "timestamp", "2026-10-04T19:42:34Z")))

    def test_21_bad_verification_ref_holds(self):
        parts = list(self.parts)
        parts[5] = "https://example.invalid/attestation/1"
        self.assertHold(tuple(parts))

    def test_22_false_trust_ceilings_preserved(self):
        result = call(self.parts)
        for key in (
            "first_observed_clock_authenticated", "publisher_authenticated",
            "production_authenticated", "historical_availability_proven",
            "observation_completeness_proven", "dr002_activated",
        ):
            self.assertIs(result[key], False)

    def test_23_exact_canonical_equality_proved(self):
        result = call(self.parts)
        self.assertEqual(result["exact_receipt_sha256"], result["canonical_receipt_sha256"])
        parts = list(self.parts)
        parts[1] += b"\n"
        self.assertHold(tuple(parts))

    def test_24_accepted_150_compatibility_projection(self):
        parts = fixture(live=True)
        receipt = parts[0]
        self.assertEqual(
            gate2b1.receipt_sha256(receipt),
            "3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69",
        )
        result = call(parts)
        self.assertEqual(result["status"], "VERIFIED_GITHUB_PROVENANCE_BINDING")
        self.assertEqual(
            result["verified_receipt_bindings"],
            {
                "source_capture:c4564601dd7a9c75648a0fc6594088f2339ed404d5cce721658f50de3190929b": {
                    "receipt_sha256": "3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69",
                    "verification_ref": "https://github.com/F1Lllewellyn/f1-data-publisher/attestations/52636060",
                }
            },
        )
        self.assertEqual(result["attested_receipt_existed_by_utc"], "2026-10-04T19:42:36Z")
        self.assertEqual(result["internal_first_observed_utc"], "2026-10-04T19:42:34.866980Z")
        gate2b1._external_binding(receipt, result["verified_receipt_bindings"])

    def test_25_module_is_pure_offline(self):
        source = (BUNDLES / "dr002_github_attestation_binding_v1.py").read_text()
        tree = ast.parse(source)
        forbidden_import_roots = {
            "requests", "socket", "subprocess", "urllib.request", "http", "time", "os"
        }
        imports = set()
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.append(node.func.attr)
        self.assertTrue(all(
            not any(name == bad or name.startswith(bad + ".") for bad in forbidden_import_roots)
            for name in imports))
        for name in (
            "open", "read_bytes", "write_bytes", "read_text", "write_text", "system", "popen"
        ):
            self.assertNotIn(name, calls)

    def test_26_bundle_statement_must_match_verified_result(self):
        parts = list(self.parts)
        bundle = json.loads(parts[2])
        statement = json.loads(base64.b64decode(bundle["dsseEnvelope"]["payload"]))
        statement["predicate"]["runDetails"]["metadata"]["invocationId"] += "-tampered"
        bundle["dsseEnvelope"]["payload"] = base64.b64encode(canonical(statement)).decode()
        parts[2] = canonical(bundle)
        self.assertHold(tuple(parts))


if __name__ == "__main__":
    unittest.main()
