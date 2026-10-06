"""Focused offline tests for pre-2B-7I3 workflow-identity composability."""
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
import dr002_outcome_boundary_shadow_pilot_v1 as pilot

WORKFLOW_PATH = ".github/workflows/dr002-outcome-boundary-shadow-pilot.yml"
REVISION_WORKFLOW_PATH = ".github/workflows/dr002-revision-shadow-pilot.yml"
WORKFLOW = (ROOT / WORKFLOW_PATH).read_text(encoding="utf-8")
PRODUCER_WRAPPER = "scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py"
LOCK_WRAPPER = "scripts/forecast_bundles/dr002_forecast_lock_shadow_pilot_v1.py"
OUTCOME_WRAPPER = "scripts/forecast_bundles/dr002_outcome_boundary_shadow_pilot_v1.py"
SUBJECT = (
    "_runtime/dr002_pre2b7i_outcome_boundary_shadow/"
    "gha-${{ github.run_id }}-${{ github.run_attempt }}/outcome_boundary_execution_manifest.json"
)
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
    def test_manual_main_only_exact_permissions_and_hosted_runner(self):
        trigger = WORKFLOW.split("on:\n", 1)[1].split("permissions:", 1)[0]
        self.assertEqual(trigger, "  workflow_dispatch:\n")
        permissions = WORKFLOW.split("permissions:\n", 1)[1].split("jobs:", 1)[0]
        self.assertEqual(
            permissions,
            "  contents: read\n  id-token: write\n  attestations: write\n",
        )
        self.assertIn("if: github.ref == 'refs/heads/main'", WORKFLOW)
        self.assertIn("runs-on: ubuntu-latest", WORKFLOW)

    def test_each_wrapper_once_in_required_success_order(self):
        for wrapper in (PRODUCER_WRAPPER, LOCK_WRAPPER, OUTCOME_WRAPPER):
            self.assertEqual(WORKFLOW.count("python " + wrapper), 1)
        names = (
            "One accepted synthetic frozen producer shadow",
            "One accepted synthetic forecast lock shadow",
            "One Gate 2B-4 synthetic outcome boundary shadow",
            "Attest exact successful outcome boundary manifest",
            "Preserve attestation bundle and factual metadata",
            "uses: actions/upload-artifact@v4",
        )
        positions = [WORKFLOW.index(name) for name in names]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("continue-on-error", WORKFLOW)
        self.assertNotIn("|| true", WORKFLOW)

    def test_same_run_and_head_identity_passed_to_all_wrappers(self):
        self.assertEqual(
            WORKFLOW.count("SHADOW_RUN_ID: gha-${{ github.run_id }}-${{ github.run_attempt }}"),
            3,
        )
        self.assertEqual(WORKFLOW.count("IMPLEMENTATION_SHA: ${{ github.sha }}"), 3)
        self.assertEqual(WORKFLOW.count('--run-id "$SHADOW_RUN_ID"'), 3)
        self.assertEqual(WORKFLOW.count('--implementation-git-sha "$IMPLEMENTATION_SHA"'), 3)

    def test_lock_call_receives_actual_outcome_workflow_identity(self):
        lock_step = WORKFLOW.split(
            "      - name: One accepted synthetic forecast lock shadow\n", 1
        )[1].split(
            "      - name: One Gate 2B-4 synthetic outcome boundary shadow\n", 1
        )[0]
        self.assertIn("WORKFLOW_NAME: ${{ github.workflow }}", lock_step)
        self.assertIn("WORKFLOW_REF: ${{ github.workflow_ref }}", lock_step)
        self.assertIn("GIT_REF: ${{ github.ref }}", lock_step)
        self.assertNotIn(
            ".github/workflows/dr002-forecast-lock-shadow-pilot.yml", lock_step
        )

    def test_exact_attestation_pin_subject_and_outputs(self):
        self.assertIn(
            "uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2",
            WORKFLOW,
        )
        self.assertIn("subject-path: " + SUBJECT, WORKFLOW)
        self.assertIn("id: attest_outcome_boundary", WORKFLOW)
        for output in ("bundle-path", "attestation-id", "attestation-url"):
            self.assertIn("steps.attest_outcome_boundary.outputs." + output, WORKFLOW)
        for alternate in ("subject-digest:", "subject-checksums:", "predicate:", "sbom-path:"):
            self.assertNotIn(alternate, WORKFLOW)

    def test_runtime_only_and_no_production_network_or_repository_write(self):
        tail = WORKFLOW.split("      - uses: actions/upload-artifact@v4", 1)[1]
        for path in (
            "_runtime/dr002_pre2b7c_frozen_producer_shadow/**",
            "_runtime/dr002_pre2b7h_forecast_lock_shadow/**",
            "_runtime/dr002_pre2b7i_outcome_boundary_shadow/**",
        ):
            self.assertIn(path, tail)
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


class OutcomeBoundaryShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.fixture_temp.name)
        cls.producer_root = cls.fixture / "producer"
        cls.lock_root = cls.fixture / "lock"
        with patch.object(pilot.lock_shadow.producer_shadow, "RUNTIME_ROOT", cls.producer_root):
            pilot.lock_shadow.producer_shadow.run_pilot(
                run_id="gha-123-1", implementation_git_sha="a" * 40
            )
        producer_manifest = json.loads(
            (cls.producer_root / "gha-123-1/execution_manifest.json").read_bytes()
        )
        times = iter(
            (
                plus_seconds(producer_manifest["forecast_generation_utc"], 1),
                plus_seconds(producer_manifest["forecast_generation_utc"], 2),
            )
        )
        with patch.object(pilot.lock_shadow, "PRODUCER_RUNTIME_ROOT", cls.producer_root), patch.object(
            pilot.lock_shadow, "LOCK_RUNTIME_ROOT", cls.lock_root
        ):
            pilot.lock_shadow.run_lock_shadow(
                run_id="gha-123-1",
                implementation_git_sha="a" * 40,
                repository="example/project",
                workflow="DR-002 synthetic outcome boundary shadow pilot",
                workflow_ref="example/project/" + WORKFLOW_PATH + "@refs/heads/main",
                git_ref="refs/heads/main",
                github_run_id="123",
                github_run_attempt="1",
                clock=lambda: next(times),
            )

    @classmethod
    def tearDownClass(cls):
        cls.fixture_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.outcome_root = Path(self.temp.name) / "outcome"
        self.patches = (
            patch.object(pilot.lock_shadow, "PRODUCER_RUNTIME_ROOT", self.producer_root),
            patch.object(pilot, "LOCK_RUNTIME_ROOT", self.lock_root),
            patch.object(pilot, "OUTCOME_RUNTIME_ROOT", self.outcome_root),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def caller_lock_root(self, workflow_path, workflow_name):
        if workflow_path == WORKFLOW_PATH:
            return self.lock_root
        root = Path(self.temp.name) / ("lock-" + Path(workflow_path).stem)
        shutil.copytree(self.lock_root, root)
        target = root / "gha-123-1/lock_execution_manifest.json"
        manifest = json.loads(target.read_bytes())
        manifest.update(
            workflow_path=workflow_path,
            workflow_name=workflow_name,
            workflow_ref="example/project/" + workflow_path + "@refs/heads/main",
        )
        target.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return root

    def run_shadow(
        self,
        lock_root=None,
        *,
        workflow_path=WORKFLOW_PATH,
        workflow_name="DR-002 synthetic outcome boundary shadow pilot",
        workflow_ref=None,
        repository="example/project",
        git_ref="refs/heads/main",
        outcome_root=None,
    ):
        selected_lock_root = lock_root or self.lock_root
        selected_outcome_root = outcome_root or self.outcome_root
        workflow_ref = workflow_ref or (
            repository + "/" + workflow_path + "@" + git_ref
        )
        lock_manifest = json.loads(
            (selected_lock_root / "gha-123-1/lock_execution_manifest.json").read_bytes()
        )
        start = lock_manifest["lock_receipt_created_utc"]
        times = iter((plus_seconds(start, 1), plus_seconds(start, 2), plus_seconds(start, 3)))
        with patch.object(pilot, "LOCK_RUNTIME_ROOT", selected_lock_root), patch.object(
            pilot, "OUTCOME_RUNTIME_ROOT", selected_outcome_root
        ):
            result = pilot.run_outcome_boundary_shadow(
                run_id="gha-123-1",
                implementation_git_sha="a" * 40,
                repository=repository,
                workflow=workflow_name,
                workflow_ref=workflow_ref,
                git_ref=git_ref,
                github_run_id="123",
                github_run_attempt="1",
                clock=lambda: next(times),
            )
        return result, selected_outcome_root / "gha-123-1"

    def test_composed_lock_manifest_records_truthful_outer_identity(self):
        manifest, _ = self.run_shadow()
        lock_manifest = json.loads(
            (self.lock_root / "gha-123-1/lock_execution_manifest.json").read_bytes()
        )
        expected = {
            "repository": "example/project",
            "workflow_path": WORKFLOW_PATH,
            "workflow_name": "DR-002 synthetic outcome boundary shadow pilot",
            "workflow_ref": "example/project/" + WORKFLOW_PATH + "@refs/heads/main",
            "git_ref": "refs/heads/main",
            "implementation_git_sha": "a" * 40,
            "github_run_id": "123",
            "github_run_attempt": "1",
            "run_id": "gha-123-1",
        }
        for key, value in expected.items():
            self.assertEqual(lock_manifest[key], value)
            self.assertEqual(manifest[key], value)

    def test_future_revision_workflow_ref_accepted_and_recorded_truthfully(self):
        workflow_name = "DR-002 synthetic revision shadow pilot"
        lock_root = self.caller_lock_root(REVISION_WORKFLOW_PATH, workflow_name)
        manifest, _ = self.run_shadow(
            lock_root,
            workflow_path=REVISION_WORKFLOW_PATH,
            workflow_name=workflow_name,
        )
        expected = {
            "workflow_path": REVISION_WORKFLOW_PATH,
            "workflow_name": workflow_name,
            "workflow_ref": (
                "example/project/" + REVISION_WORKFLOW_PATH + "@refs/heads/main"
            ),
            "repository": "example/project",
            "git_ref": "refs/heads/main",
            "implementation_git_sha": "a" * 40,
            "github_run_id": "123",
            "github_run_attempt": "1",
        }
        for key, value in expected.items():
            self.assertEqual(manifest[key], value)

    def test_direct_and_composed_calls_preserve_exact_outcome_evidence(self):
        direct_root = Path(self.temp.name) / "direct-outcome"
        revision_root = Path(self.temp.name) / "revision-outcome"
        revision_name = "DR-002 synthetic revision shadow pilot"
        revision_lock = self.caller_lock_root(REVISION_WORKFLOW_PATH, revision_name)
        direct_manifest, direct = self.run_shadow(outcome_root=direct_root)
        revision_manifest, revision = self.run_shadow(
            revision_lock,
            workflow_path=REVISION_WORKFLOW_PATH,
            workflow_name=revision_name,
            outcome_root=revision_root,
        )
        evidence = (
            "synthetic_outcome_payload.json",
            "outcome_source_capture_receipt.json",
            "outcome_boundary_receipt.json",
            "outcome_boundary_report.md",
        )
        for name in evidence:
            self.assertEqual((direct / name).read_bytes(), (revision / name).read_bytes())
        self.assertEqual(direct_manifest["evidence_sha256"], revision_manifest["evidence_sha256"])
        self.assertEqual(
            direct_manifest["synthetic_outcome_payload_sha256"],
            revision_manifest["synthetic_outcome_payload_sha256"],
        )
        self.assertEqual(
            direct_manifest["outcome_capture_receipt_sha256"],
            revision_manifest["outcome_capture_receipt_sha256"],
        )
        self.assertEqual(
            direct_manifest["outcome_boundary_receipt_sha256"],
            revision_manifest["outcome_boundary_receipt_sha256"],
        )
        differences = {
            key
            for key in direct_manifest
            if direct_manifest[key] != revision_manifest[key]
        }
        self.assertEqual(
            differences,
            {
                "workflow_path",
                "workflow_name",
                "workflow_ref",
                "lock_execution_manifest_sha256",
            },
        )

    def test_exact_payload_receipt_hashes_and_required_package(self):
        manifest, output = self.run_shadow()
        payload = (output / "synthetic_outcome_payload.json").read_bytes()
        capture = json.loads((output / "outcome_source_capture_receipt.json").read_bytes())
        boundary = json.loads((output / "outcome_boundary_receipt.json").read_bytes())
        self.assertEqual(payload, pilot.SYNTHETIC_OUTCOME_BYTES)
        self.assertEqual(capture["payload"]["source_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(manifest["synthetic_outcome_payload_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(
            set(manifest["evidence_sha256"]),
            {
                "synthetic_outcome_payload.json",
                "outcome_source_capture_receipt.json",
                "outcome_boundary_receipt.json",
                "outcome_boundary_report.md",
            },
        )
        for name, digest in manifest["evidence_sha256"].items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
        self.assertTrue((output / "outcome_boundary_execution_manifest.json").is_file())
        self.assertEqual(boundary["payload"]["evidence_sha256"], hashlib.sha256(payload).hexdigest())

    def test_distinct_source_parent_boundary_and_exact_policy(self):
        manifest, output = self.run_shadow()
        capture = json.loads((output / "outcome_source_capture_receipt.json").read_bytes())
        boundary = json.loads((output / "outcome_boundary_receipt.json").read_bytes())
        lock_manifest = json.loads(
            (self.lock_root / "gha-123-1/lock_execution_manifest.json").read_bytes()
        )
        producer_root = self.producer_root / "gha-123-1"
        producer_manifest = json.loads((producer_root / "execution_manifest.json").read_bytes())
        forecast_sources = {item["source_id"] for item in producer_manifest["declared_sources"]}
        self.assertNotIn(capture["payload"]["source_id"], forecast_sources)
        self.assertEqual(capture["payload"]["source_id"], pilot.SOURCE_ID)
        self.assertEqual(boundary["parent_receipt_ids"], [capture["receipt_id"]])
        self.assertEqual(boundary["payload"]["boundary_policy_ref"], pilot.POLICY_REF)
        self.assertEqual(
            manifest["lock_execution_manifest_sha256"],
            hashlib.sha256(
                (self.lock_root / "gha-123-1/lock_execution_manifest.json").read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(lock_manifest["run_id"], manifest["run_id"])

    def test_constructor_called_once_and_boundary_is_only_first_observed(self):
        original = pilot.boundary_contract.build_outcome_boundary
        with patch.object(
            pilot.boundary_contract, "build_outcome_boundary", wraps=original
        ) as constructor:
            manifest, output = self.run_shadow()
        constructor.assert_called_once()
        capture = json.loads((output / "outcome_source_capture_receipt.json").read_bytes())
        boundary = json.loads((output / "outcome_boundary_receipt.json").read_bytes())
        self.assertEqual(
            boundary["payload"]["outcome_availability_boundary_utc"],
            capture["payload"]["first_observed_utc"],
        )
        self.assertEqual(manifest["outcome_availability_boundary_utc"], capture["payload"]["first_observed_utc"])
        self.assertIsNone(capture["payload"]["event_time_utc"])
        self.assertIsNone(capture["payload"]["publisher_time_utc"])
        self.assertNotIn("tlog", json.dumps(boundary).lower())
        self.assertNotEqual(capture["receipt_created_utc"], capture["payload"]["first_observed_utc"])
        self.assertNotEqual(boundary["receipt_created_utc"], capture["payload"]["first_observed_utc"])

    def test_no_revision_engine_or_fabricated_binding_and_all_claims_false(self):
        manifest, output = self.run_shadow()
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in output.iterdir()
            if path.is_file()
        )
        self.assertNotIn('"receipt_type":"revision"', combined)
        self.assertNotIn('"receipt_type":"engine_execution"', combined)
        self.assertNotIn("verified_receipt_bindings", combined)
        for field in pilot.FALSE_FLAGS:
            self.assertIs(manifest[field], False)
        self.assertIs(manifest["synthetic_outcome"], True)
        self.assertIs(manifest["separate_synthetic_outcome_capture_constructed"], True)
        self.assertIs(manifest["gate2b4_outcome_boundary_constructor_used"], True)
        self.assertIs(manifest["boundary_equals_outcome_first_observed"], True)

    def test_tampered_lock_evidence_fails_closed(self):
        work = Path(self.temp.name) / "lock-copy"
        shutil.copytree(self.lock_root, work)
        target = work / "gha-123-1/forecast_payload.csv"
        target.write_bytes(target.read_bytes() + b"tampered")
        with self.assertRaisesRegex(pilot.OutcomeBoundaryShadowError, "lock_evidence_hash_mismatch"):
            self.run_shadow(lock_root=work)
        self.assertFalse(
            (self.outcome_root / "gha-123-1/outcome_boundary_execution_manifest.json").exists()
        )

    def test_false_or_mismatched_lock_workflow_identity_fails_closed(self):
        mismatches = {
            "workflow_path": pilot.lock_shadow.WORKFLOW_PATH,
            "workflow_ref": (
                "example/project/"
                + pilot.lock_shadow.WORKFLOW_PATH
                + "@refs/heads/main"
            ),
            "workflow_name": "DR-002 synthetic forecast lock shadow pilot",
            "repository": "other/project",
            "git_ref": "refs/heads/topic",
            "implementation_git_sha": "b" * 40,
            "github_run_id": "999",
            "github_run_attempt": "2",
            "run_id": "gha-999-2",
        }
        for field, value in mismatches.items():
            with self.subTest(field=field):
                work = Path(self.temp.name) / ("lock-" + field)
                shutil.copytree(self.lock_root, work)
                target = work / "gha-123-1/lock_execution_manifest.json"
                lock_manifest = json.loads(target.read_bytes())
                lock_manifest[field] = value
                target.write_text(
                    json.dumps(lock_manifest, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    pilot.OutcomeBoundaryShadowError,
                    "lock_shadow_(?:run|head|identity)_mismatch",
                ):
                    self.run_shadow(lock_root=work)

    def test_direct_identity_cannot_replace_actual_revision_caller(self):
        with self.assertRaisesRegex(
            pilot.OutcomeBoundaryShadowError, "lock_shadow_identity_mismatch"
        ):
            self.run_shadow(
                self.lock_root,
                workflow_path=REVISION_WORKFLOW_PATH,
                workflow_name="DR-002 synthetic revision shadow pilot",
            )

    def test_revision_identity_cannot_replace_actual_direct_caller(self):
        revision_lock = self.caller_lock_root(
            REVISION_WORKFLOW_PATH, "DR-002 synthetic revision shadow pilot"
        )
        with self.assertRaisesRegex(
            pilot.OutcomeBoundaryShadowError, "lock_shadow_identity_mismatch"
        ):
            self.run_shadow(revision_lock)

    def test_invalid_caller_workflow_refs_fail_closed_before_output(self):
        invalid = {
            "repository_mismatch": (
                "other/project/" + WORKFLOW_PATH + "@refs/heads/main",
                "workflow_repository_mismatch",
            ),
            "ref_mismatch": (
                "example/project/" + WORKFLOW_PATH + "@refs/heads/topic",
                "workflow_ref_mismatch",
            ),
            "malformed": ("not-a-workflow-ref", "malformed_workflow_ref"),
            "traversal": (
                "example/project/.github/workflows/../evil.yml@refs/heads/main",
                "workflow_path_not_normalized",
            ),
            "outside_workflows": (
                "example/project/scripts/evil.yml@refs/heads/main",
                "workflow_path_not_normalized",
            ),
            "nested": (
                "example/project/.github/workflows/nested/evil.yml@refs/heads/main",
                "workflow_path_not_normalized",
            ),
            "empty": (
                "example/project/.github/workflows/@refs/heads/main",
                "workflow_path_not_normalized",
            ),
            "non_yaml": (
                "example/project/.github/workflows/evil.txt@refs/heads/main",
                "malformed_workflow_filename",
            ),
        }
        for name, (workflow_ref, reason) in invalid.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                pilot.lock_shadow.LockShadowError, reason
            ):
                self.run_shadow(workflow_ref=workflow_ref)
        self.assertFalse(self.outcome_root.exists())


class AttestationPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old_cwd = os.getcwd()
        self.addCleanup(os.chdir, self.old_cwd)
        os.chdir(self.temp.name)
        self.root = Path("_runtime/dr002_pre2b7i_outcome_boundary_shadow/gha-123-1")
        self.root.mkdir(parents=True)
        self.subject = self.root / "outcome_boundary_execution_manifest.json"
        self.manifest = {
            "status": pilot.STATUS,
            "repository": "example/project",
            "workflow_path": WORKFLOW_PATH,
            "workflow_name": "synthetic test",
            "workflow_ref": "example/project/" + WORKFLOW_PATH + "@refs/heads/main",
            "git_ref": "refs/heads/main",
            "implementation_git_sha": "a" * 40,
            "github_run_id": "123",
            "github_run_attempt": "1",
            "synthetic_outcome": True,
            "separate_synthetic_outcome_capture_constructed": True,
            "gate2b4_outcome_boundary_constructor_used": True,
            "boundary_equals_outcome_first_observed": True,
            **{field: False for field in pilot.FALSE_FLAGS},
        }
        self.subject_bytes = json.dumps(self.manifest, sort_keys=True).encode() + b"\n"
        self.subject.write_bytes(self.subject_bytes)
        self.digest = hashlib.sha256(self.subject_bytes).hexdigest()
        statement = {"subject": [{"digest": {"sha256": self.digest}}]}
        self.bundle = Path("action-output.bundle.json")
        self.bundle_bytes = json.dumps(
            {"dsseEnvelope": {"payload": base64.b64encode(json.dumps(statement).encode()).decode()}},
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

    def test_exact_bundle_subject_and_false_ceiling_preserved(self):
        self.execute()
        self.assertEqual((self.root / "github_attestation.bundle.json").read_bytes(), self.bundle_bytes)
        self.assertEqual(self.subject.read_bytes(), self.subject_bytes)
        metadata = json.loads((self.root / "github_attestation_metadata.json").read_bytes())
        self.assertEqual(metadata["subject_sha256"], self.digest)
        self.assertIs(metadata["consistency_check_only_not_cryptographic_verification"], True)
        self.assertIs(metadata["future_tlog_time_does_not_authenticate_internal_outcome_clock"], True)
        for field in pilot.FALSE_FLAGS:
            self.assertIs(metadata[field], False)

    def test_wrong_subject_or_upgraded_claim_fails(self):
        wrong = {"subject": [{"digest": {"sha256": "0" * 64}}]}
        self.bundle.write_text(
            json.dumps({"dsseEnvelope": {"payload": base64.b64encode(json.dumps(wrong).encode()).decode()}}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "subject/manifest mismatch"):
            self.execute()
        self.bundle.write_bytes(self.bundle_bytes)
        changed = dict(self.manifest, outcome_clock_authenticated=True)
        changed_bytes = json.dumps(changed, sort_keys=True).encode() + b"\n"
        self.subject.write_bytes(changed_bytes)
        changed_statement = {"subject": [{"digest": {"sha256": hashlib.sha256(changed_bytes).hexdigest()}}]}
        self.bundle.write_text(
            json.dumps({"dsseEnvelope": {"payload": base64.b64encode(json.dumps(changed_statement).encode()).decode()}}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "trust claim"):
            self.execute()


class StaticBoundaryTests(unittest.TestCase):
    def test_wrapper_has_no_network_process_verifier_or_production_locker(self):
        source = (ROOT / OUTCOME_WRAPPER).read_text(encoding="utf-8")
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
        self.assertNotIn("verify_receipt_chain", source)
        self.assertNotIn("verify_and_classify", source)

    def test_every_named_dependency_blob_is_unchanged(self):
        expected = {
            "scripts/forecasts/produce_actual_forecast_rows_v1.py": "af27586668c767de126af829c1131c6bae4634ad",
            PRODUCER_WRAPPER: "1d3bfaf713807e799a6323875de670dc8d4e1a85",
            LOCK_WRAPPER: "1ef04022041c7dcf625ae10c051c23b35ed72a9d",
            "tests/test_dr002_forecast_lock_shadow_pilot_v1.py": "7e6ba7d9837cacab99494b281aa5845eb3c91dfc",
            "scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py": "064d93ee5ae30354590a3fb95be598c5fe8b3b9a",
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py": "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
            "scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py": "b9b1f9acc1be30d5b7cdf42424853e3d652b9466",
            ".github/workflows/dr002-forecast-lock-shadow-pilot.yml": "4daa7c0ebb22f9b31dd35f5b0109c2eb227a976c",
            "docs/DR002_PRE2B7H2_LIVE_GITHUB_ATTESTED_LOCK_SHADOW_2026-10-05.md": "1e6177001a7e939cb18af6d8581748559d5bc859",
            "docs/DR002_PRE2B7H3_LOCK_SHADOW_WORKFLOW_IDENTITY_COMPOSABILITY_2026-10-06.md": "c48c6f80633c19232ef664c6724eb35342c974ac",
            ".github/workflows/dr002-outcome-boundary-shadow-pilot.yml": "5ebe0dcaed10583bacd56687bd92d971f561f680",
            "docs/DR002_PRE2B7I2_LIVE_GITHUB_ATTESTED_OUTCOME_BOUNDARY_SHADOW_2026-10-06.md": "df1b309b185e55300eedad7889971b1f8cc46d4f",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob(path), digest)

    def test_documented_checkpoint_is_exact_and_final(self):
        doc = (
            ROOT / "docs/DR002_PRE2B7I3_OUTCOME_BOUNDARY_WORKFLOW_IDENTITY_COMPOSABILITY_2026-10-06.md"
        ).read_text(encoding="utf-8")
        checkpoint = """outcome_boundary_workflow_identity_composable: true
direct_outcome_workflow_identity_preserved: true
future_revision_workflow_identity_truthful: true
historical_i2_evidence_rewritten: false
outcome_boundary_mechanics_modified: false
trust_ceiling_modified: false
live_workflow_run_executed: false
revision_proof_completed: false
observation_completeness_proven: false
dr002_activated: false
promotion_allowed: false"""
        self.assertTrue(doc.endswith("```text\n" + checkpoint + "\n```\n"))


if __name__ == "__main__":
    unittest.main()
