"""Focused offline tests for the pre-2B-7J1 synthetic revision shadow."""
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
import dr002_revision_shadow_pilot_v1 as pilot

WORKFLOW_PATH = ".github/workflows/dr002-revision-shadow-pilot.yml"
WORKFLOW_NAME = "DR-002 synthetic post-cutoff revision shadow pilot"
WORKFLOW_REF = "example/project/" + WORKFLOW_PATH + "@refs/heads/main"
WORKFLOW = (ROOT / WORKFLOW_PATH).read_text(encoding="utf-8")
PRODUCER_WRAPPER = "scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py"
LOCK_WRAPPER = "scripts/forecast_bundles/dr002_forecast_lock_shadow_pilot_v1.py"
OUTCOME_WRAPPER = "scripts/forecast_bundles/dr002_outcome_boundary_shadow_pilot_v1.py"
REVISION_WRAPPER = "scripts/forecast_bundles/dr002_revision_shadow_pilot_v1.py"
SUBJECT = (
    "_runtime/dr002_pre2b7j_revision_shadow/"
    "gha-${{ github.run_id }}-${{ github.run_attempt }}/revision_execution_manifest.json"
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
    def test_manual_main_only_least_permissions_and_hosted_runner(self):
        trigger = WORKFLOW.split("on:\n", 1)[1].split("permissions:", 1)[0]
        self.assertEqual(trigger, "  workflow_dispatch:\n")
        permissions = WORKFLOW.split("permissions:\n", 1)[1].split("jobs:", 1)[0]
        self.assertEqual(
            permissions,
            "  contents: read\n  id-token: write\n  attestations: write\n",
        )
        self.assertIn("if: github.ref == 'refs/heads/main'", WORKFLOW)
        self.assertIn("runs-on: ubuntu-latest", WORKFLOW)

    def test_four_wrappers_called_once_in_required_success_order(self):
        wrappers = (PRODUCER_WRAPPER, LOCK_WRAPPER, OUTCOME_WRAPPER, REVISION_WRAPPER)
        for wrapper in wrappers:
            self.assertEqual(WORKFLOW.count("python " + wrapper), 1)
        names = (
            "One accepted synthetic frozen producer shadow",
            "One accepted synthetic forecast lock shadow",
            "One accepted synthetic outcome boundary shadow",
            "One Gate 2B-4 synthetic post-cutoff revision shadow",
            "Attest exact successful revision execution manifest",
            "Preserve attestation bundle and factual metadata",
            "uses: actions/upload-artifact@v4",
        )
        positions = [WORKFLOW.index(name) for name in names]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("continue-on-error", WORKFLOW)
        self.assertNotIn("|| true", WORKFLOW)

    def test_every_wrapper_receives_same_run_and_head(self):
        self.assertEqual(
            WORKFLOW.count("SHADOW_RUN_ID: gha-${{ github.run_id }}-${{ github.run_attempt }}"),
            4,
        )
        self.assertEqual(WORKFLOW.count("IMPLEMENTATION_SHA: ${{ github.sha }}"), 4)
        self.assertEqual(WORKFLOW.count('--run-id "$SHADOW_RUN_ID"'), 4)
        self.assertEqual(WORKFLOW.count('--implementation-git-sha "$IMPLEMENTATION_SHA"'), 4)

    def test_composed_wrappers_receive_actual_revision_workflow_identity(self):
        for start, end in (
            (
                "One accepted synthetic forecast lock shadow",
                "One accepted synthetic outcome boundary shadow",
            ),
            (
                "One accepted synthetic outcome boundary shadow",
                "One Gate 2B-4 synthetic post-cutoff revision shadow",
            ),
            (
                "One Gate 2B-4 synthetic post-cutoff revision shadow",
                "Attest exact successful revision execution manifest",
            ),
        ):
            step = WORKFLOW.split("      - name: " + start + "\n", 1)[1].split(
                "      - name: " + end + "\n", 1
            )[0]
            for value in (
                "WORKFLOW_NAME: ${{ github.workflow }}",
                "WORKFLOW_REF: ${{ github.workflow_ref }}",
                "REPOSITORY: ${{ github.repository }}",
                "GIT_REF: ${{ github.ref }}",
                "IMPLEMENTATION_SHA: ${{ github.sha }}",
                "RUN_ID: ${{ github.run_id }}",
                "RUN_ATTEMPT: ${{ github.run_attempt }}",
            ):
                self.assertIn(value, step)
            self.assertNotIn("dr002-forecast-lock-shadow-pilot.yml", step)
            self.assertNotIn("dr002-outcome-boundary-shadow-pilot.yml", step)

    def test_exact_attestation_pin_subject_and_action_outputs(self):
        self.assertIn(
            "uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2",
            WORKFLOW,
        )
        self.assertIn("subject-path: " + SUBJECT, WORKFLOW)
        for output in ("bundle-path", "attestation-id", "attestation-url"):
            self.assertIn("steps.attest_revision.outputs." + output, WORKFLOW)
        for alternate in ("subject-digest:", "subject-checksums:", "predicate:", "sbom-path:"):
            self.assertNotIn(alternate, WORKFLOW)

    def test_runtime_only_no_network_production_dispatch_or_repository_write(self):
        tail = WORKFLOW.split("      - uses: actions/upload-artifact@v4", 1)[1]
        for path in (
            "_runtime/dr002_pre2b7c_frozen_producer_shadow/**",
            "_runtime/dr002_pre2b7h_forecast_lock_shadow/**",
            "_runtime/dr002_pre2b7i_outcome_boundary_shadow/**",
            "_runtime/dr002_pre2b7j_revision_shadow/**",
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
        ):
            self.assertNotIn(forbidden, WORKFLOW.lower())


class RevisionShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.fixture_temp.name)
        cls.producer_root = cls.fixture / "producer"
        cls.lock_root = cls.fixture / "lock"
        cls.outcome_root = cls.fixture / "outcome"
        producer_module = pilot.outcome_shadow.lock_shadow.producer_shadow
        lock_module = pilot.outcome_shadow.lock_shadow
        with patch.object(producer_module, "RUNTIME_ROOT", cls.producer_root):
            producer_module.run_pilot(
                run_id="gha-123-1", implementation_git_sha="a" * 40
            )
        producer_manifest = json.loads(
            (cls.producer_root / "gha-123-1/execution_manifest.json").read_bytes()
        )
        lock_times = iter(
            (
                plus_seconds(producer_manifest["forecast_generation_utc"], 1),
                plus_seconds(producer_manifest["forecast_generation_utc"], 2),
            )
        )
        with patch.object(lock_module, "PRODUCER_RUNTIME_ROOT", cls.producer_root), patch.object(
            lock_module, "LOCK_RUNTIME_ROOT", cls.lock_root
        ):
            lock_module.run_lock_shadow(
                run_id="gha-123-1",
                implementation_git_sha="a" * 40,
                repository="example/project",
                workflow=WORKFLOW_NAME,
                workflow_ref=WORKFLOW_REF,
                git_ref="refs/heads/main",
                github_run_id="123",
                github_run_attempt="1",
                clock=lambda: next(lock_times),
            )
        lock_manifest = json.loads(
            (cls.lock_root / "gha-123-1/lock_execution_manifest.json").read_bytes()
        )
        outcome_times = iter(
            (
                plus_seconds(lock_manifest["lock_receipt_created_utc"], 1),
                plus_seconds(lock_manifest["lock_receipt_created_utc"], 2),
                plus_seconds(lock_manifest["lock_receipt_created_utc"], 3),
            )
        )
        outcome_module = pilot.outcome_shadow
        with patch.object(lock_module, "PRODUCER_RUNTIME_ROOT", cls.producer_root), patch.object(
            outcome_module, "LOCK_RUNTIME_ROOT", cls.lock_root
        ), patch.object(outcome_module, "OUTCOME_RUNTIME_ROOT", cls.outcome_root):
            outcome_module.run_outcome_boundary_shadow(
                run_id="gha-123-1",
                implementation_git_sha="a" * 40,
                repository="example/project",
                workflow=WORKFLOW_NAME,
                workflow_ref=WORKFLOW_REF,
                git_ref="refs/heads/main",
                github_run_id="123",
                github_run_attempt="1",
                clock=lambda: next(outcome_times),
            )

    @classmethod
    def tearDownClass(cls):
        cls.fixture_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.revision_root = Path(self.temp.name) / "revision"
        self.patches = (
            patch.object(
                pilot.outcome_shadow.lock_shadow,
                "PRODUCER_RUNTIME_ROOT",
                self.producer_root,
            ),
            patch.object(pilot.outcome_shadow, "LOCK_RUNTIME_ROOT", self.lock_root),
            patch.object(pilot, "LOCK_RUNTIME_ROOT", self.lock_root),
            patch.object(pilot, "OUTCOME_RUNTIME_ROOT", self.outcome_root),
            patch.object(pilot, "REVISION_RUNTIME_ROOT", self.revision_root),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def run_shadow(self, *, lock_root=None, outcome_root=None, revision_root=None):
        selected_lock = lock_root or self.lock_root
        selected_outcome = outcome_root or self.outcome_root
        selected_revision = revision_root or self.revision_root
        outcome_manifest = json.loads(
            (selected_outcome / "gha-123-1/outcome_boundary_execution_manifest.json").read_bytes()
        )
        start = outcome_manifest["outcome_boundary_receipt_created_utc"]
        times = iter(
            (plus_seconds(start, 1), plus_seconds(start, 2), plus_seconds(start, 3))
        )
        with patch.object(pilot.outcome_shadow, "LOCK_RUNTIME_ROOT", selected_lock), patch.object(
            pilot, "LOCK_RUNTIME_ROOT", selected_lock
        ), patch.object(pilot, "OUTCOME_RUNTIME_ROOT", selected_outcome), patch.object(
            pilot, "REVISION_RUNTIME_ROOT", selected_revision
        ):
            result = pilot.run_revision_shadow(
                run_id="gha-123-1",
                implementation_git_sha="a" * 40,
                repository="example/project",
                workflow=WORKFLOW_NAME,
                workflow_ref=WORKFLOW_REF,
                git_ref="refs/heads/main",
                github_run_id="123",
                github_run_attempt="1",
                clock=lambda: next(times),
            )
        return result, selected_revision / "gha-123-1"

    def test_exact_deterministic_source_revision_scope_and_payload(self):
        manifest, output = self.run_shadow()
        completed = json.loads((output / "completed_forecast_record.json").read_bytes())
        selected = min(completed["evidence"], key=lambda item: item["source_id"])
        payload = (output / "synthetic_revised_source_payload.json").read_bytes()
        capture = json.loads((output / "revised_source_capture_receipt.json").read_bytes())
        self.assertEqual(payload, pilot.SYNTHETIC_REVISED_SOURCE_BYTES)
        self.assertEqual(manifest["selected_original_source_id"], selected["source_id"])
        self.assertEqual(manifest["selected_original_source_uri"], selected["source_uri"])
        self.assertEqual(manifest["selected_original_source_sha256"], selected["source_sha256"])
        self.assertEqual(capture["payload"]["source_id"], selected["source_id"])
        self.assertEqual(capture["payload"]["source_uri"], selected["source_uri"])
        self.assertEqual(capture["scope"]["event_id"], selected["event_id"])
        self.assertEqual(capture["scope"]["meeting_id"], selected["meeting_id"])
        self.assertEqual(capture["scope"]["session_id"], selected["session_id"])
        self.assertNotEqual(capture["payload"]["source_sha256"], selected["source_sha256"])

    def test_post_cutoff_parentless_capture_and_revision_binding(self):
        manifest, output = self.run_shadow()
        capture = json.loads((output / "revised_source_capture_receipt.json").read_bytes())
        revision = json.loads((output / "revision_receipt.json").read_bytes())
        self.assertEqual(capture["parent_receipt_ids"], [])
        self.assertEqual(revision["parent_receipt_ids"], [capture["receipt_id"]])
        for field in ("source_id", "source_sha256", "first_observed_utc"):
            self.assertEqual(revision["payload"][field], capture["payload"][field])
        self.assertGreater(
            pilot.receipt_contract._time(capture["payload"]["first_observed_utc"]),
            pilot.receipt_contract._time(manifest["forecast_evidence_cutoff_utc"]),
        )
        self.assertGreaterEqual(
            pilot.receipt_contract._time(revision["receipt_created_utc"]),
            pilot.receipt_contract._time(capture["receipt_created_utc"]),
        )

    def test_gate2b4_constructors_each_called_exactly_once(self):
        original_revision = pilot.boundary_contract.build_revision
        original_complete = pilot.boundary_contract.complete_forecast_record
        with patch.object(
            pilot.boundary_contract, "build_revision", wraps=original_revision
        ) as build_revision, patch.object(
            pilot.boundary_contract,
            "complete_forecast_record",
            wraps=original_complete,
        ) as complete:
            self.run_shadow()
        build_revision.assert_called_once()
        complete.assert_called_once()

    def test_completed_record_preserves_base_and_has_one_exact_declaration(self):
        _, output = self.run_shadow()
        completed = json.loads((output / "completed_forecast_record.json").read_bytes())
        revision = json.loads((output / "revision_receipt.json").read_bytes())
        capture = json.loads((output / "revised_source_capture_receipt.json").read_bytes())
        lock_manifest = json.loads(
            (self.lock_root / "gha-123-1/lock_execution_manifest.json").read_bytes()
        )
        producer_root = self.producer_root / "gha-123-1"
        producer_manifest = json.loads((producer_root / "execution_manifest.json").read_bytes())
        forecast_bytes = (lock_manifest and producer_root / "evidence/forecast_rows.csv").read_bytes()
        base = pilot.outcome_shadow.lock_shadow.build_forecast_manifest(
            producer_manifest,
            lock_manifest["internal_lock_utc"],
            hashlib.sha256(forecast_bytes).hexdigest(),
        )
        producer = json.loads(
            (self.lock_root / "gha-123-1/producer_execution_receipt.json").read_bytes()
        )
        base["producer"] = {
            key: producer["payload"][key]
            for key in pilot.receipt_contract.PRODUCER_KEYS
        }
        for key, value in base.items():
            self.assertEqual(completed[key], value)
        self.assertEqual(len(completed["revisions"]), 1)
        declaration = completed["revisions"][0]
        self.assertEqual(declaration["revision_id"], revision["payload"]["revision_id"])
        self.assertEqual(declaration["capture_evidence_ref"], capture["receipt_id"])
        self.assertEqual(
            pilot.boundary_contract.input_manifest_sha256(completed),
            producer["payload"]["input_manifest_sha256"],
        )

    def test_exact_runtime_package_hashes_and_no_second_revision(self):
        manifest, output = self.run_shadow()
        expected = {
            "synthetic_revised_source_payload.json",
            "revised_source_capture_receipt.json",
            "revision_receipt.json",
            "completed_forecast_record.json",
            "revision_report.md",
        }
        self.assertEqual(set(manifest["evidence_sha256"]), expected)
        for name, digest in manifest["evidence_sha256"].items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
        self.assertTrue((output / "revision_execution_manifest.json").is_file())
        completed = json.loads((output / "completed_forecast_record.json").read_bytes())
        self.assertEqual(len(completed["revisions"]), 1)
        self.assertEqual(
            sum(
                '"receipt_type":"revision"' in path.read_text(encoding="utf-8")
                for path in output.iterdir()
                if path.is_file()
            ),
            1,
        )

    def test_truthful_predecessor_identity_and_manifest_bindings(self):
        manifest, _ = self.run_shadow()
        expected = {
            "repository": "example/project",
            "workflow_path": WORKFLOW_PATH,
            "workflow_name": WORKFLOW_NAME,
            "workflow_ref": WORKFLOW_REF,
            "git_ref": "refs/heads/main",
            "implementation_git_sha": "a" * 40,
            "github_run_id": "123",
            "github_run_attempt": "1",
            "run_id": "gha-123-1",
        }
        for root, name in (
            (self.lock_root, "lock_execution_manifest.json"),
            (self.outcome_root, "outcome_boundary_execution_manifest.json"),
        ):
            predecessor = json.loads((root / "gha-123-1" / name).read_bytes())
            for key, value in expected.items():
                self.assertEqual(predecessor[key], value)
                self.assertEqual(manifest[key], value)
        self.assertEqual(
            manifest["lock_execution_manifest_sha256"],
            hashlib.sha256(
                (self.lock_root / "gha-123-1/lock_execution_manifest.json").read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            manifest["outcome_execution_manifest_sha256"],
            hashlib.sha256(
                (self.outcome_root / "gha-123-1/outcome_boundary_execution_manifest.json").read_bytes()
            ).hexdigest(),
        )

    def test_direct_lock_or_outcome_identity_substitution_fails_closed(self):
        cases = (
            (self.lock_root, "lock_execution_manifest.json", pilot.outcome_shadow.lock_shadow.WORKFLOW_PATH),
            (
                self.outcome_root,
                "outcome_boundary_execution_manifest.json",
                ".github/workflows/dr002-outcome-boundary-shadow-pilot.yml",
            ),
        )
        for original_root, filename, direct_path in cases:
            with self.subTest(filename=filename):
                lock_root = self.lock_root
                outcome_root = self.outcome_root
                copied = Path(self.temp.name) / filename
                shutil.copytree(original_root, copied)
                target = copied / "gha-123-1" / filename
                data = json.loads(target.read_bytes())
                data["workflow_path"] = direct_path
                data["workflow_ref"] = "example/project/" + direct_path + "@refs/heads/main"
                target.write_text(
                    json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                if filename.startswith("lock"):
                    lock_root = copied
                else:
                    outcome_root = copied
                with self.assertRaisesRegex(
                    ValueError, "(?:lock|outcome)_shadow_identity_mismatch"
                ):
                    self.run_shadow(
                        lock_root=lock_root,
                        outcome_root=outcome_root,
                        revision_root=Path(self.temp.name) / (filename + "-result"),
                    )

    def test_tampered_outcome_evidence_fails_closed(self):
        work = Path(self.temp.name) / "outcome-copy"
        shutil.copytree(self.outcome_root, work)
        target = work / "gha-123-1/synthetic_outcome_payload.json"
        target.write_bytes(target.read_bytes() + b"tampered")
        with self.assertRaisesRegex(pilot.RevisionShadowError, "outcome_evidence_hash_mismatch"):
            self.run_shadow(outcome_root=work)
        self.assertFalse(
            (self.revision_root / "gha-123-1/revision_execution_manifest.json").exists()
        )

    def test_no_engine_verified_binding_or_trust_upgrade(self):
        manifest, output = self.run_shadow()
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in output.iterdir()
            if path.is_file()
        )
        self.assertNotIn('"receipt_type":"engine_execution"', combined)
        self.assertNotIn("verified_receipt_bindings", combined)
        for field in pilot.FALSE_FLAGS:
            self.assertIs(manifest[field], False)
        for field in (
            "revision_after_forecast_cutoff",
            "single_synthetic_revision_constructed",
            "gate2b4_revision_constructor_used",
            "completed_forecast_record_bound",
        ):
            self.assertIs(manifest[field], True)


class AttestationPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old_cwd = os.getcwd()
        self.addCleanup(os.chdir, self.old_cwd)
        os.chdir(self.temp.name)
        self.root = Path("_runtime/dr002_pre2b7j_revision_shadow/gha-123-1")
        self.root.mkdir(parents=True)
        self.subject = self.root / "revision_execution_manifest.json"
        self.manifest = {
            "status": pilot.STATUS,
            "repository": "example/project",
            "workflow_path": WORKFLOW_PATH,
            "workflow_name": WORKFLOW_NAME,
            "workflow_ref": WORKFLOW_REF,
            "git_ref": "refs/heads/main",
            "implementation_git_sha": "a" * 40,
            "github_run_id": "123",
            "github_run_attempt": "1",
            "revision_after_forecast_cutoff": True,
            "single_synthetic_revision_constructed": True,
            "gate2b4_revision_constructor_used": True,
            "completed_forecast_record_bound": True,
            **{field: False for field in pilot.FALSE_FLAGS},
        }
        self.subject_bytes = json.dumps(self.manifest, sort_keys=True).encode() + b"\n"
        self.subject.write_bytes(self.subject_bytes)
        self.digest = hashlib.sha256(self.subject_bytes).hexdigest()
        statement = {"subject": [{"digest": {"sha256": self.digest}}]}
        self.bundle = Path("action-output.bundle.json")
        self.bundle_bytes = json.dumps(
            {
                "dsseEnvelope": {
                    "payload": base64.b64encode(json.dumps(statement).encode()).decode()
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
            "WORKFLOW_NAME": WORKFLOW_NAME,
            "WORKFLOW_REF": WORKFLOW_REF,
        }

    def execute(self):
        with patch.dict(os.environ, self.env, clear=True):
            exec(compile(PRESERVE_CODE, WORKFLOW_PATH, "exec"), {})

    def test_exact_bundle_and_successful_manifest_subject_preserved(self):
        self.execute()
        self.assertEqual(
            (self.root / "github_attestation.bundle.json").read_bytes(),
            self.bundle_bytes,
        )
        self.assertEqual(self.subject.read_bytes(), self.subject_bytes)
        metadata = json.loads((self.root / "github_attestation_metadata.json").read_bytes())
        self.assertEqual(metadata["subject_sha256"], self.digest)
        self.assertIs(metadata["consistency_check_only_not_cryptographic_verification"], True)
        self.assertIs(
            metadata["future_tlog_time_does_not_authenticate_internal_revision_clock"],
            True,
        )
        for field in pilot.FALSE_FLAGS:
            self.assertIs(metadata[field], False)

    def test_wrong_subject_or_upgraded_claim_fails(self):
        wrong = {"subject": [{"digest": {"sha256": "0" * 64}}]}
        self.bundle.write_text(
            json.dumps(
                {
                    "dsseEnvelope": {
                        "payload": base64.b64encode(json.dumps(wrong).encode()).decode()
                    }
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "subject/manifest mismatch"):
            self.execute()
        self.bundle.write_bytes(self.bundle_bytes)
        changed = dict(self.manifest, revision_completeness_proven=True)
        changed_bytes = json.dumps(changed, sort_keys=True).encode() + b"\n"
        self.subject.write_bytes(changed_bytes)
        statement = {
            "subject": [
                {"digest": {"sha256": hashlib.sha256(changed_bytes).hexdigest()}}
            ]
        }
        self.bundle.write_text(
            json.dumps(
                {
                    "dsseEnvelope": {
                        "payload": base64.b64encode(json.dumps(statement).encode()).decode()
                    }
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "trust claim"):
            self.execute()


class StaticContractTests(unittest.TestCase):
    def test_wrapper_has_no_network_process_full_verifier_or_production_path(self):
        source = (ROOT / REVISION_WRAPPER).read_text(encoding="utf-8")
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
        for forbidden in (
            "create_forecast_bundles_v1",
            "verify_receipt_chain",
            "verify_and_classify",
            "api.openf1.org",
        ):
            self.assertNotIn(forbidden, source)

    def test_every_named_dependency_blob_is_unchanged(self):
        expected = {
            OUTCOME_WRAPPER: "adb69bab75758205e740f2d9a9c0e1a0f4fbb2f6",
            "tests/test_dr002_outcome_boundary_shadow_pilot_v1.py": "bdbf257d2448e2deffaa8adf80dacdd22ed48eb8",
            "docs/DR002_PRE2B7I3_OUTCOME_BOUNDARY_WORKFLOW_IDENTITY_COMPOSABILITY_2026-10-06.md": "d34f4363343c7ba11df6bc9379c3096d54eda16f",
            ".github/workflows/dr002-outcome-boundary-shadow-pilot.yml": "5ebe0dcaed10583bacd56687bd92d971f561f680",
            LOCK_WRAPPER: "1ef04022041c7dcf625ae10c051c23b35ed72a9d",
            PRODUCER_WRAPPER: "1d3bfaf713807e799a6323875de670dc8d4e1a85",
            "scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py": "064d93ee5ae30354590a3fb95be598c5fe8b3b9a",
            "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py": "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
            "docs/DR002_PRE2B7I2_LIVE_GITHUB_ATTESTED_OUTCOME_BOUNDARY_SHADOW_2026-10-06.md": "df1b309b185e55300eedad7889971b1f8cc46d4f",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob(path), digest)

    def test_documented_checkpoint_is_exact_and_final(self):
        doc = (
            ROOT
            / "docs/DR002_PRE2B7J1_GITHUB_ATTESTED_REVISION_SHADOW_2026-10-06.md"
        ).read_text(encoding="utf-8")
        checkpoint = """revision_shadow_capability_installed: true
truthful_composed_chain_identity: true
single_synthetic_post_cutoff_revision_constructed: true
gate2b4_revision_constructor_used: true
completed_forecast_record_bound: true
live_revision_run_executed: false
revision_capture_externally_bound: false
revision_receipt_externally_bound: false
revision_clock_authenticated: false
revision_source_publisher_authenticated: false
observation_completeness_proven: false
revision_completeness_proven: false
revision_proof_completed: false
production_revision_tracking_proven: false
dr002_activated: false
promotion_allowed: false"""
        self.assertTrue(doc.endswith("```text\n" + checkpoint + "\n```\n"))


if __name__ == "__main__":
    unittest.main()
