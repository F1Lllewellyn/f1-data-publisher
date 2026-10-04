"""Offline workflow-contract and auxiliary-evidence tests; no attestation/network execution."""
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/dr002-frozen-producer-shadow-pilot.yml"
TEXT = (ROOT / WORKFLOW_PATH).read_text()
PIN = "1e69f48acb82d1966a394da916b4c1698aa569d6"
SUBJECT = "_runtime/dr002_pre2b7c_frozen_producer_shadow/gha-${{ github.run_id }}-${{ github.run_attempt }}/execution_manifest.json"
WRAPPER = "scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py"
FALSE_FIELDS = ("production_authenticated", "historical_availability_proven",
                "stable_engine_execution_proven", "blind_validation_eligible", "dr002_activated")
CODE = "\n".join(line[10:] for line in TEXT.split("          python - <<'PY'\n", 1)[1].split("          PY\n", 1)[0].splitlines())
WRAPPER_STEP = TEXT.split("      - name: One synthetic frozen-mode producer CLI shadow", 1)[1].split("      - name: Attest", 1)[0]

def git_blob(path):
    body = (ROOT / path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()

class WorkflowContractTests(unittest.TestCase):
    def test_manual_only(self):
        self.assertEqual(TEXT.split("on:\n", 1)[1].split("permissions:", 1)[0], "  workflow_dispatch:\n")

    def test_main_only(self):
        self.assertIn("if: github.ref == 'refs/heads/main'", TEXT)

    def test_exact_minimum_permissions(self):
        self.assertEqual(TEXT.split("permissions:\n", 1)[1].split("jobs:", 1)[0],
                         "  contents: read\n  id-token: write\n  attestations: write\n")
        for forbidden in ("write-all", "contents: write", "actions: write", "packages: write",
                          "deployments: write", "artifact-metadata: write"):
            self.assertNotIn(forbidden, TEXT)

    def test_accepted_wrapper_invocation_exactly_once(self):
        self.assertEqual(TEXT.count("python " + WRAPPER), 1)
        self.assertEqual(WRAPPER_STEP, """
        env:
          PYTHONDONTWRITEBYTECODE: '1'
          IMPLEMENTATION_SHA: ${{ github.sha }}
          SHADOW_RUN_ID: gha-${{ github.run_id }}-${{ github.run_attempt }}
        run: >-
          python scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py
          --implementation-git-sha "$IMPLEMENTATION_SHA"
          --run-id "$SHADOW_RUN_ID"
""")

    def test_sequence_success_only(self):
        names = ["One synthetic frozen-mode producer CLI shadow", "Attest exact successful shadow manifest",
                 "Preserve attestation bundle and factual metadata", "uses: actions/upload-artifact@v4"]
        positions = [TEXT.index(n) for n in names]
        self.assertEqual(positions, sorted(positions))
        before_upload = TEXT.split("      - uses: actions/upload-artifact@v4", 1)[0]
        self.assertNotIn("continue-on-error", TEXT)
        self.assertNotIn("if: always()", before_upload)
        self.assertNotIn("if: failure()", before_upload)
        self.assertNotIn("|| true", TEXT)

    def test_exact_subject_and_pinned_first_party(self):
        self.assertIn("subject-path: " + SUBJECT, TEXT)
        self.assertIn("uses: actions/attest@" + PIN + " # v4.2.2", TEXT)
        for key in ("subject-digest:", "subject-checksums:", "predicate:", "sbom-path:"):
            self.assertNotIn(key, TEXT)
        self.assertIn("push-to-registry: false", TEXT)
        self.assertIn("create-storage-record: false", TEXT)
        self.assertIn("id: attest_shadow", TEXT)

    def test_action_outputs_passed_as_env_not_shell(self):
        for key in ("bundle-path", "attestation-id", "attestation-url"):
            self.assertIn("steps.attest_shadow.outputs." + key, TEXT)
        self.assertNotIn("${{", CODE)

    def test_subject_is_read_only_after_attestation(self):
        self.assertNotIn("subject.write", CODE)
        self.assertIn("subject.read_bytes() != subject_bytes", CODE)
        self.assertIn("subjects[0][\"digest\"].get(\"sha256\") != digest", CODE)

    def test_exact_bundle_copy_and_hash(self):
        self.assertIn('Path(os.environ["ATTESTATION_BUNDLE_PATH"]).read_bytes()', CODE)
        self.assertIn("bundle_target.write_bytes(bundle_bytes)", CODE)
        self.assertIn("hashlib.sha256(subject_bytes).hexdigest()", CODE)

    def test_upload_retains_runtime_evidence_on_failure(self):
        tail = TEXT.split("      - uses: actions/upload-artifact@v4", 1)[1]
        self.assertIn("if: always()", tail)
        self.assertIn("path: _runtime/dr002_pre2b7c_frozen_producer_shadow/**", tail)
        self.assertIn("if-no-files-found: warn", tail)

    def test_no_tokens_in_auxiliary_code_or_env(self):
        for value in ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL",
                      "GITHUB_TOKEN", "secrets.", "print(", "set -x"):
            self.assertNotIn(value, TEXT)
        self.assertNotIn("dict(os.environ)", CODE)

    def test_no_production_network_or_repository_write(self):
        for value in ("curl ", "wget ", "urllib", "requests", "api.openf1.org",
                      "repository_dispatch", "gh workflow", "git add", "git commit", "git push",
                      "latest/", "history/", "workbooks/", "ledgers/"):
            self.assertNotIn(value, TEXT)

    def test_no_scientific_receipt_or_binding(self):
        for value in ("verified_receipt_bindings", "producer_execution_receipt",
                      "engine_execution_receipt", "lock_receipt"):
            self.assertNotIn(value, TEXT)

    def test_accepted_wrapper_and_production_dependencies_unchanged(self):
        expected = {
            WRAPPER: "1d3bfaf713807e799a6323875de670dc8d4e1a85",
            "configs/forecasts/actual_forecast_producer_policy_v1.json": "964f78f67a0e44de9304c10b0e7bf35ea7620694",
            "configs/forecast_bundles/forecast_gate_orchestrator_policy_v1.json": "ebcd6d9d0a071b5cb14d62dbc9687e4d577af266",
            "scripts/forecasts/produce_actual_forecast_rows_v1.py": "af27586668c767de126af829c1131c6bae4634ad",
            ".github/workflows/f1-actual-forecast-producer-v1.yml": "e115718f2b7fed9f0e87a47b1138b3462b9b6cb1",
            ".github/workflows/f1-automated-forecast-gate-orchestrator-v1.yml": "32a1210a2f43065e9d65a9bd858c059b6166700f",
            "scripts/forecast_bundles/orchestrate_forecast_gate_pipeline_v1.py": "1f95311dc6f3874e207fdc889a1a1b49c9acafab",
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob(path), digest)

class AuxiliaryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old_cwd = os.getcwd()
        self.addCleanup(os.chdir, self.old_cwd)
        os.chdir(self.temp.name)
        self.root = Path("_runtime/dr002_pre2b7c_frozen_producer_shadow/gha-123-1")
        self.root.mkdir(parents=True)
        self.subject = self.root / "execution_manifest.json"
        self.manifest = dict(status="SHADOW_EXECUTION_ONLY_NOT_A_PRODUCTION_FORECAST",
                             implementation_git_sha="a" * 40, **{f: False for f in FALSE_FIELDS})
        self.subject_bytes = json.dumps(self.manifest, indent=2).encode() + b"\n"
        self.subject.write_bytes(self.subject_bytes)
        self.digest = hashlib.sha256(self.subject_bytes).hexdigest()
        statement = {"subject": [{"name": "execution_manifest.json", "digest": {"sha256": self.digest}}]}
        self.bundle = Path("action-output.bundle.json")
        self.bundle_bytes = json.dumps({"dsseEnvelope": {
            "payload": base64.b64encode(json.dumps(statement).encode()).decode(),
            "signatures": [{"sig": "SYNTHETIC_NOT_CRYPTOGRAPHIC_EVIDENCE"}]
        }}, indent=2).encode() + b"\n"
        self.bundle.write_bytes(self.bundle_bytes)
        self.env = {
            "RUN_ID": "123", "RUN_ATTEMPT": "1", "HEAD_SHA": "a" * 40,
            "ATTESTATION_BUNDLE_PATH": str(self.bundle.resolve()), "ATTESTATION_ID": "456",
            "ATTESTATION_URL": "https://github.com/example/project/attestations/456",
            "REPOSITORY": "example/project", "WORKFLOW_NAME": "synthetic test",
            "WORKFLOW_REF": "example/project/" + WORKFLOW_PATH + "@refs/heads/main",
        }

    def execute(self):
        with patch.dict(os.environ, self.env, clear=True):
            exec(compile(CODE, WORKFLOW_PATH, "exec"), {})

    def test_preserves_exact_bundle_and_subject(self):
        self.execute()
        self.assertEqual((self.root / "github_attestation.bundle.json").read_bytes(), self.bundle_bytes)
        self.assertEqual(self.subject.read_bytes(), self.subject_bytes)

    def test_metadata_factual_outputs_and_recomputed_hash(self):
        self.execute()
        meta = json.loads((self.root / "github_attestation_metadata.json").read_bytes())
        self.assertEqual(meta["subject_sha256"], self.digest)
        self.assertEqual(meta["subject_relative_path"], self.subject.as_posix())
        self.assertEqual(meta["attestation_id"], "456")
        self.assertEqual(meta["attestation_url"], self.env["ATTESTATION_URL"])
        for key in ("repository", "workflow_name", "workflow_ref", "git_head_sha", "run_id", "run_attempt", "workflow_path"):
            self.assertIn(key, meta)
        for field in FALSE_FIELDS:
            self.assertIs(meta[field], False)
        self.assertEqual(set(meta), {"schema_version", "attestation_id", "attestation_url",
            "subject_relative_path", "subject_sha256", "repository", "workflow_path", "workflow_name",
            "workflow_ref", "git_head_sha", "run_id", "run_attempt", *FALSE_FIELDS})

    def test_missing_subject_fails(self):
        self.subject.unlink()
        with self.assertRaises(FileNotFoundError):
            self.execute()

    def test_missing_bundle_fails(self):
        self.bundle.unlink()
        with self.assertRaises(FileNotFoundError):
            self.execute()

    def test_missing_action_outputs_fail(self):
        for field in ("ATTESTATION_ID", "ATTESTATION_URL"):
            with self.subTest(field=field):
                old = self.env[field]
                self.env[field] = ""
                with self.assertRaises(ValueError):
                    self.execute()
                self.env[field] = old

    def test_changed_subject_after_attestation_fails(self):
        self.subject.write_bytes(self.subject_bytes + b" ")
        with self.assertRaisesRegex(ValueError, "subject/manifest mismatch"):
            self.execute()

    def test_wrong_bundle_subject_fails(self):
        self.bundle.write_text(json.dumps({"dsseEnvelope": {"payload": base64.b64encode(
            json.dumps({"subject": [{"digest": {"sha256": "0" * 64}}]}).encode()).decode()}}))
        with self.assertRaisesRegex(ValueError, "subject/manifest mismatch"):
            self.execute()

    def test_wrong_run_head_fails(self):
        self.env["HEAD_SHA"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "run head"):
            self.execute()

    def test_hold_manifest_fails(self):
        self.manifest["status"] = "HOLD"
        self.subject.write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, "successful synthetic"):
            self.execute()

    def test_trust_upgrade_fails(self):
        self.manifest["production_authenticated"] = True
        body = json.dumps(self.manifest).encode()
        self.subject.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        self.bundle.write_text(json.dumps({"dsseEnvelope": {"payload": base64.b64encode(
            json.dumps({"subject": [{"digest": {"sha256": digest}}]}).encode()).decode()}}))
        with self.assertRaisesRegex(ValueError, "trust claim"):
            self.execute()

    def test_invalid_run_identity_fails(self):
        self.env["RUN_ID"] = "../escape"
        with self.assertRaisesRegex(ValueError, "run identity"):
            self.execute()

if __name__ == "__main__":
    unittest.main()
