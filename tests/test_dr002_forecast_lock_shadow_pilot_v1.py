"""Focused offline tests for the pre-2B-7H1 lock-shadow capability."""
import ast
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts/forecast_bundles"
sys.path.insert(0, str(SCRIPTS))
import dr002_forecast_lock_shadow_pilot_v1 as pilot

WORKFLOW_PATH = ".github/workflows/dr002-forecast-lock-shadow-pilot.yml"
WORKFLOW = (ROOT / WORKFLOW_PATH).read_text(encoding="utf-8")
PIN = "1e69f48acb82d1966a394da916b4c1698aa569d6"
ACCEPTED_WRAPPER = "scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py"
LOCK_WRAPPER = "scripts/forecast_bundles/dr002_forecast_lock_shadow_pilot_v1.py"
SUBJECT = (
    "_runtime/dr002_pre2b7h_forecast_lock_shadow/"
    "gha-${{ github.run_id }}-${{ github.run_attempt }}/lock_execution_manifest.json"
)
FALSE_FIELDS = pilot.FALSE_FLAGS
PRESERVE_CODE = "\n".join(
    line[10:]
    for line in WORKFLOW.split("          python - <<'PY'\n", 1)[1]
    .split("          PY\n", 1)[0]
    .splitlines()
)


def git_blob(path):
    body = (ROOT / path).read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(body)).encode("ascii") + b"\0" + body
    ).hexdigest()


def plus_seconds(value, seconds):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        (parsed + timedelta(seconds=seconds))
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class WorkflowContractTests(unittest.TestCase):
    def test_manual_only_and_main_only(self):
        trigger = WORKFLOW.split("on:\n", 1)[1].split("permissions:", 1)[0]
        self.assertEqual(trigger, "  workflow_dispatch:\n")
        self.assertIn("if: github.ref == 'refs/heads/main'", WORKFLOW)

    def test_exact_minimum_permissions_and_github_runner(self):
        permissions = WORKFLOW.split("permissions:\n", 1)[1].split("jobs:", 1)[0]
        self.assertEqual(
            permissions,
            "  contents: read\n  id-token: write\n  attestations: write\n",
        )
        self.assertIn("runs-on: ubuntu-latest", WORKFLOW)
        for forbidden in (
            "contents: write",
            "actions: write",
            "packages: write",
            "deployments: write",
            "write-all",
        ):
            self.assertNotIn(forbidden, WORKFLOW)

    def test_each_shadow_wrapper_invoked_once_with_same_identity(self):
        self.assertEqual(WORKFLOW.count("python " + ACCEPTED_WRAPPER), 1)
        self.assertEqual(WORKFLOW.count("python " + LOCK_WRAPPER), 1)
        self.assertEqual(WORKFLOW.count("SHADOW_RUN_ID: gha-${{ github.run_id }}-${{ github.run_attempt }}"), 2)
        self.assertEqual(WORKFLOW.count("IMPLEMENTATION_SHA: ${{ github.sha }}"), 2)
        self.assertEqual(WORKFLOW.count('--run-id "$SHADOW_RUN_ID"'), 2)
        self.assertEqual(WORKFLOW.count('--implementation-git-sha "$IMPLEMENTATION_SHA"'), 2)

    def test_required_success_order(self):
        names = (
            "One accepted synthetic frozen producer shadow",
            "One Gate 2B-4 synthetic forecast lock shadow",
            "Attest exact successful lock manifest",
            "Preserve attestation bundle and factual metadata",
            "uses: actions/upload-artifact@v4",
        )
        positions = [WORKFLOW.index(name) for name in names]
        self.assertEqual(positions, sorted(positions))
        before_upload = WORKFLOW.split("      - uses: actions/upload-artifact@v4", 1)[0]
        self.assertNotIn("continue-on-error", WORKFLOW)
        self.assertNotIn("if: always()", before_upload)
        self.assertNotIn("|| true", WORKFLOW)

    def test_exact_attestation_pin_subject_and_action_outputs(self):
        self.assertIn("uses: actions/attest@" + PIN + " # v4.2.2", WORKFLOW)
        self.assertIn("subject-path: " + SUBJECT, WORKFLOW)
        self.assertIn("id: attest_lock", WORKFLOW)
        self.assertIn("push-to-registry: false", WORKFLOW)
        self.assertIn("create-storage-record: false", WORKFLOW)
        for output in ("bundle-path", "attestation-id", "attestation-url"):
            self.assertIn("steps.attest_lock.outputs." + output, WORKFLOW)
        for alternate in ("subject-digest:", "subject-checksums:", "predicate:", "sbom-path:"):
            self.assertNotIn(alternate, WORKFLOW)

    def test_runtime_only_artifact_and_no_production_or_repository_write(self):
        tail = WORKFLOW.split("      - uses: actions/upload-artifact@v4", 1)[1]
        self.assertIn("_runtime/dr002_pre2b7c_frozen_producer_shadow/**", tail)
        self.assertIn("_runtime/dr002_pre2b7h_forecast_lock_shadow/**", tail)
        for forbidden in (
            "repository_dispatch",
            "workflow_call",
            "schedule:",
            "gh workflow",
            "git add",
            "git commit",
            "git push",
            "curl ",
            "wget ",
            "requests",
            "urllib",
            "api.openf1.org",
            "pipedream",
            "gmail",
            "create_forecast_bundles_v1.py",
            "latest/",
            "history/",
        ):
            self.assertNotIn(forbidden, WORKFLOW.lower())

    def test_auxiliary_code_does_not_access_tokens_or_mutate_subject(self):
        self.assertNotIn("${{", PRESERVE_CODE)
        self.assertNotIn("subject.write", PRESERVE_CODE)
        self.assertIn("subject.read_bytes() != subject_bytes", PRESERVE_CODE)
        self.assertIn("bundle_target.write_bytes(bundle_bytes)", PRESERVE_CODE)
        for forbidden in (
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
            "ACTIONS_ID_TOKEN_REQUEST_URL",
            "GITHUB_TOKEN",
            "secrets.",
            "dict(os.environ)",
        ):
            self.assertNotIn(forbidden, WORKFLOW)


class LockShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = tempfile.TemporaryDirectory()
        cls.fixture_root = Path(cls.fixture_temp.name) / "producer"
        with patch.object(pilot.producer_shadow, "RUNTIME_ROOT", cls.fixture_root):
            pilot.producer_shadow.run_pilot(
                run_id="gha-123-1", implementation_git_sha="a" * 40
            )

    @classmethod
    def tearDownClass(cls):
        cls.fixture_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.producer_root = self.work / "producer"
        shutil.copytree(self.fixture_root, self.producer_root)
        self.lock_root = self.work / "lock"
        self.patch_producer_root = patch.object(
            pilot, "PRODUCER_RUNTIME_ROOT", self.producer_root
        )
        self.patch_lock_root = patch.object(pilot, "LOCK_RUNTIME_ROOT", self.lock_root)
        self.patch_producer_root.start()
        self.patch_lock_root.start()
        self.addCleanup(self.patch_producer_root.stop)
        self.addCleanup(self.patch_lock_root.stop)

    def run_shadow(
        self,
        workflow_path=WORKFLOW_PATH,
        workflow_name="DR-002 synthetic forecast lock shadow pilot",
        lock_root=None,
    ):
        source_manifest = json.loads(
            (self.producer_root / "gha-123-1/execution_manifest.json").read_bytes()
        )
        times = iter(
            (
                plus_seconds(source_manifest["forecast_generation_utc"], 1),
                plus_seconds(source_manifest["forecast_generation_utc"], 2),
            )
        )
        selected_root = lock_root or self.lock_root
        with patch.object(pilot, "LOCK_RUNTIME_ROOT", selected_root):
            result = pilot.run_lock_shadow(
                run_id="gha-123-1",
                implementation_git_sha="a" * 40,
                repository="example/project",
                workflow=workflow_name,
                workflow_ref="example/project/" + workflow_path + "@refs/heads/main",
                git_ref="refs/heads/main",
                github_run_id="123",
                github_run_attempt="1",
                clock=lambda: next(times),
            )
        return result, selected_root / "gha-123-1"

    def test_direct_and_composed_workflow_identity_are_recorded_truthfully(self):
        manifest, _ = self.run_shadow()
        self.assertEqual(manifest["workflow_path"], WORKFLOW_PATH)
        self.assertEqual(
            manifest["workflow_ref"],
            "example/project/" + WORKFLOW_PATH + "@refs/heads/main",
        )
        self.assertEqual(manifest["workflow_name"], "DR-002 synthetic forecast lock shadow pilot")

    def test_composed_outcome_workflow_identity_is_accepted_and_recorded(self):
        composed = ".github/workflows/dr002-outcome-boundary-shadow-pilot.yml"
        name = "DR-002 synthetic outcome boundary shadow pilot"
        manifest, _ = self.run_shadow(workflow_path=composed, workflow_name=name)
        self.assertEqual(manifest["workflow_path"], composed)
        self.assertEqual(
            manifest["workflow_ref"],
            "example/project/" + composed + "@refs/heads/main",
        )
        self.assertEqual(manifest["workflow_name"], name)

    def test_composition_changes_identity_only_not_lock_mechanics(self):
        direct_manifest, direct = self.run_shadow(lock_root=self.work / "direct-lock")
        composed_path = ".github/workflows/dr002-outcome-boundary-shadow-pilot.yml"
        composed_manifest, composed = self.run_shadow(
            workflow_path=composed_path,
            workflow_name="DR-002 synthetic outcome boundary shadow pilot",
            lock_root=self.work / "composed-lock",
        )
        for name in (
            "forecast_payload.csv",
            "producer_execution_receipt.json",
            "forecast_lock_receipt.json",
            "lock_report.md",
        ):
            self.assertEqual((direct / name).read_bytes(), (composed / name).read_bytes())
        for field in (
            "forecast_payload_sha256",
            "producer_receipt_sha256",
            "lock_receipt_sha256",
            "internal_lock_utc",
            "lock_receipt_created_utc",
            "storage_ref",
            "evidence_sha256",
        ):
            self.assertEqual(direct_manifest[field], composed_manifest[field])

    def test_exact_forecast_payload_copy_and_all_pre_attestation_hashes(self):
        manifest, output = self.run_shadow()
        source = self.producer_root / "gha-123-1/evidence/forecast_rows.csv"
        payload = output / "forecast_payload.csv"
        self.assertEqual(payload.read_bytes(), source.read_bytes())
        producer_manifest = json.loads(
            (self.producer_root / "gha-123-1/execution_manifest.json").read_bytes()
        )
        self.assertEqual(
            hashlib.sha256(payload.read_bytes()).hexdigest(),
            producer_manifest["evidence_sha256"]["forecast_rows.csv"],
        )
        self.assertEqual(
            manifest["forecast_payload_sha256"],
            hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            set(manifest["evidence_sha256"]),
            {
                "forecast_payload.csv",
                "producer_execution_receipt.json",
                "forecast_lock_receipt.json",
                "lock_report.md",
            },
        )
        for name, digest in manifest["evidence_sha256"].items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)

    def test_accepted_producer_fingerprint_is_enforced(self):
        manifest, _ = self.run_shadow()
        source = json.loads(
            (self.producer_root / "gha-123-1/execution_manifest.json").read_bytes()
        )
        self.assertEqual(source["producer_git_blob_sha"], "af27586668c767de126af829c1131c6bae4634ad")
        self.assertEqual(
            source["producer_code_sha256"],
            hashlib.sha256((ROOT / "scripts/forecasts/produce_actual_forecast_rows_v1.py").read_bytes()).hexdigest(),
        )
        self.assertEqual(
            manifest["producer_shadow_manifest_sha256"],
            hashlib.sha256((self.producer_root / "gha-123-1/execution_manifest.json").read_bytes()).hexdigest(),
        )

    def test_unchanged_gate2b4_constructor_is_actually_called_once(self):
        original = pilot.lock_contract.build_forecast_lock
        with patch.object(
            pilot.lock_contract, "build_forecast_lock", wraps=original
        ) as constructor:
            self.run_shadow()
        constructor.assert_called_once()

    def test_lock_parent_and_exact_payload_hash_are_bound(self):
        manifest, output = self.run_shadow()
        producer = json.loads((output / "producer_execution_receipt.json").read_bytes())
        lock = json.loads((output / "forecast_lock_receipt.json").read_bytes())
        payload_digest = hashlib.sha256((output / "forecast_payload.csv").read_bytes()).hexdigest()
        self.assertEqual(lock["parent_receipt_ids"], [producer["receipt_id"]])
        self.assertEqual(producer["payload"]["forecast_payload_sha256"], payload_digest)
        self.assertEqual(lock["payload"]["forecast_payload_sha256"], payload_digest)
        self.assertEqual(lock["payload"]["stored_payload_sha256"], payload_digest)
        self.assertEqual(manifest["forecast_payload_sha256"], payload_digest)
        self.assertIs(manifest["synthetic_inputs"], True)
        self.assertIs(manifest["exact_forecast_payload_bound"], True)
        self.assertIs(manifest["gate2b4_lock_constructor_used"], True)

    def test_no_engine_execution_or_external_bindings_are_manufactured(self):
        manifest, output = self.run_shadow()
        producer = json.loads((output / "producer_execution_receipt.json").read_bytes())
        self.assertEqual(producer["parent_receipt_ids"], [])
        self.assertIsNone(producer["payload"]["engine_implementation"])
        self.assertIsNone(producer["payload"]["engine_receipt_id"])
        self.assertIsNone(producer["payload"]["engine_result_sha256"])
        self.assertNotIn("verified_receipt_bindings", manifest)
        for field in FALSE_FIELDS:
            self.assertIs(manifest[field], False)

    def test_tampered_producer_payload_fails_closed(self):
        payload = self.producer_root / "gha-123-1/evidence/forecast_rows.csv"
        payload.write_bytes(payload.read_bytes() + b"tampered")
        with self.assertRaisesRegex(pilot.LockShadowError, "producer_evidence_hash_mismatch"):
            self.run_shadow()
        self.assertFalse((self.lock_root / "gha-123-1/lock_execution_manifest.json").exists())

    def test_tampered_producer_manifest_fails_closed(self):
        path = self.producer_root / "gha-123-1/execution_manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["production_authenticated"] = True
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(pilot.LockShadowError, "unsupported_producer_trust_claim"):
            self.run_shadow()
        self.assertFalse((self.lock_root / "gha-123-1/lock_execution_manifest.json").exists())

    def test_constructor_failure_leaves_hold_not_success(self):
        with patch.object(
            pilot.lock_contract,
            "build_forecast_lock",
            side_effect=ValueError("synthetic failure"),
        ):
            with self.assertRaisesRegex(ValueError, "synthetic failure"):
                self.run_shadow()
        output = self.lock_root / "gha-123-1"
        self.assertFalse((output / "lock_execution_manifest.json").exists())
        self.assertIn("HOLD", (output / "hold_report.md").read_text(encoding="utf-8"))

    def test_invalid_run_or_non_main_identity_is_rejected(self):
        common = dict(
            run_id="gha-123-1",
            implementation_git_sha="a" * 40,
            repository="example/project",
            workflow="shadow",
            workflow_ref="example/project/" + WORKFLOW_PATH + "@refs/heads/main",
            git_ref="refs/heads/main",
            github_run_id="123",
            github_run_attempt="1",
        )
        for field, value in (("run_id", "wrong"), ("git_ref", "refs/heads/topic")):
            with self.subTest(field=field), self.assertRaises(pilot.LockShadowError):
                pilot.run_lock_shadow(**{**common, field: value})

    def test_malformed_or_mismatched_workflow_identity_fails_closed(self):
        common = dict(
            run_id="gha-123-1",
            implementation_git_sha="a" * 40,
            repository="example/project",
            workflow="caller display name",
            git_ref="refs/heads/main",
            github_run_id="123",
            github_run_attempt="1",
        )
        invalid = (
            ("other/project/.github/workflows/caller.yml@refs/heads/main", "workflow_repository_mismatch"),
            ("example/project/.github/workflows/caller.yml@refs/heads/topic", "workflow_ref_mismatch"),
            ("not-a-workflow-ref", "malformed_workflow_ref"),
            ("example/project/.github/workflows/../caller.yml@refs/heads/main", "workflow_path_not_normalized"),
            ("example/project/scripts/caller.yml@refs/heads/main", "workflow_path_not_normalized"),
            ("example/project/.github/workflows/@refs/heads/main", "workflow_path_not_normalized"),
            ("example/project/.github/workflows/caller.txt@refs/heads/main", "malformed_workflow_filename"),
            ("example/project/.github/workflows/sub/caller.yml@refs/heads/main", "workflow_path_not_normalized"),
        )
        for workflow_ref, reason in invalid:
            with self.subTest(workflow_ref=workflow_ref), self.assertRaisesRegex(
                pilot.LockShadowError, reason
            ):
                pilot.run_lock_shadow(**common, workflow_ref=workflow_ref)


class AttestationPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old_cwd = os.getcwd()
        self.addCleanup(os.chdir, self.old_cwd)
        os.chdir(self.temp.name)
        self.root = Path("_runtime/dr002_pre2b7h_forecast_lock_shadow/gha-123-1")
        self.root.mkdir(parents=True)
        self.subject = self.root / "lock_execution_manifest.json"
        self.manifest = {
            "status": pilot.STATUS,
            "implementation_git_sha": "a" * 40,
            "github_run_id": "123",
            "github_run_attempt": "1",
            "synthetic_inputs": True,
            "exact_forecast_payload_bound": True,
            "gate2b4_lock_constructor_used": True,
            **{field: False for field in FALSE_FIELDS},
        }
        self.subject_bytes = json.dumps(self.manifest, sort_keys=True).encode() + b"\n"
        self.subject.write_bytes(self.subject_bytes)
        self.digest = hashlib.sha256(self.subject_bytes).hexdigest()
        statement = {
            "subject": [
                {"name": self.subject.name, "digest": {"sha256": self.digest}}
            ]
        }
        self.bundle = Path("action-output.bundle.json")
        self.bundle_bytes = json.dumps(
            {
                "dsseEnvelope": {
                    "payload": base64.b64encode(json.dumps(statement).encode()).decode(),
                    "signatures": [{"sig": "SYNTHETIC_NOT_CRYPTOGRAPHIC_EVIDENCE"}],
                }
            },
            indent=2,
        ).encode() + b"\n"
        self.bundle.write_bytes(self.bundle_bytes)
        self.env = {
            "RUN_ID": "123",
            "RUN_ATTEMPT": "1",
            "HEAD_SHA": "a" * 40,
            "ATTESTATION_BUNDLE_PATH": str(self.bundle.resolve()),
            "ATTESTATION_ID": "456",
            "ATTESTATION_URL": "https://github.com/example/project/attestations/456",
            "REPOSITORY": "example/project",
            "WORKFLOW_NAME": "synthetic test",
            "WORKFLOW_REF": "example/project/" + WORKFLOW_PATH + "@refs/heads/main",
        }

    def execute(self):
        with patch.dict(os.environ, self.env, clear=True):
            exec(compile(PRESERVE_CODE, WORKFLOW_PATH, "exec"), {})

    def test_exact_bundle_and_factual_false_ceiling_are_preserved(self):
        self.execute()
        self.assertEqual(
            (self.root / "github_attestation.bundle.json").read_bytes(),
            self.bundle_bytes,
        )
        self.assertEqual(self.subject.read_bytes(), self.subject_bytes)
        metadata = json.loads(
            (self.root / "github_attestation_metadata.json").read_bytes()
        )
        self.assertEqual(metadata["subject_sha256"], self.digest)
        self.assertEqual(metadata["attestation_id"], "456")
        self.assertEqual(metadata["attestation_url"], self.env["ATTESTATION_URL"])
        self.assertIs(
            metadata["consistency_check_only_not_cryptographic_verification"], True
        )
        for field in FALSE_FIELDS:
            self.assertIs(metadata[field], False)

    def test_wrong_attestation_subject_or_upgraded_claim_fails(self):
        wrong_statement = {"subject": [{"digest": {"sha256": "0" * 64}}]}
        self.bundle.write_text(
            json.dumps(
                {
                    "dsseEnvelope": {
                        "payload": base64.b64encode(
                            json.dumps(wrong_statement).encode()
                        ).decode()
                    }
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "subject/manifest mismatch"):
            self.execute()

        self.bundle.write_bytes(self.bundle_bytes)
        self.manifest["lock_clock_authenticated"] = True
        changed = json.dumps(self.manifest, sort_keys=True).encode() + b"\n"
        self.subject.write_bytes(changed)
        changed_digest = hashlib.sha256(changed).hexdigest()
        statement = {"subject": [{"digest": {"sha256": changed_digest}}]}
        self.bundle.write_text(
            json.dumps(
                {
                    "dsseEnvelope": {
                        "payload": base64.b64encode(
                            json.dumps(statement).encode()
                        ).decode()
                    }
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "trust claim"):
            self.execute()


class StaticBoundaryTests(unittest.TestCase):
    def test_new_wrapper_has_no_network_process_or_production_locker_call(self):
        source = (ROOT / LOCK_WRAPPER).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertTrue(imports.isdisjoint({"subprocess", "socket", "urllib", "requests"}))
        self.assertNotIn("create_forecast_bundles_v1", source)
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(
            {"verify_receipt_chain", "verify_and_classify"}.isdisjoint(
                called_names | called_attributes
            )
        )

    def test_accepted_producer_and_production_locker_blobs_are_unchanged(self):
        expected = {
            ACCEPTED_WRAPPER: "1d3bfaf713807e799a6323875de670dc8d4e1a85",
            "scripts/forecasts/produce_actual_forecast_rows_v1.py": "af27586668c767de126af829c1131c6bae4634ad",
            "scripts/forecast_bundles/create_forecast_bundles_v1.py": "1cdba43d3b22a1abcfb65bbbd6b2bfebd4684018",
            "scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py": "064d93ee5ae30354590a3fb95be598c5fe8b3b9a",
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob(path), digest)

    def test_documented_checkpoint_is_exact_and_final(self):
        doc = (
            ROOT
            / "docs/DR002_PRE2B7H1_GITHUB_ATTESTED_LOCK_SHADOW_2026-10-05.md"
        ).read_text(encoding="utf-8")
        checkpoint = """lock_shadow_capability_installed: true
live_lock_run_executed: false
exact_forecast_payload_bound: true
gate2b4_lock_constructor_used: true
producer_receipt_externally_bound: false
lock_receipt_externally_bound: false
lock_clock_authenticated: false
durable_storage_proven: false
full_gate2b1_chain_verified: false
production_forecast_locked: false
dr002_activated: false
promotion_allowed: false"""
        self.assertTrue(doc.endswith("```text\n" + checkpoint + "\n```\n"))


if __name__ == "__main__":
    unittest.main()
