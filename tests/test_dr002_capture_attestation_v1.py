"""Offline workflow and packaging tests; mock bundles are NOT signed evidence."""
import ast
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import textwrap
import unittest
from unittest.mock import Mock, patch

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / '.github/workflows/dr002-capture-provenance-pilot.yml'
TEXT = WORKFLOW.read_text()
CODE = textwrap.dedent(TEXT.split("          python - <<'PY'\n", 1)[1].split('\n          PY', 1)[0])
spec = importlib.util.spec_from_file_location('capture_attestation_pilot', REPO / 'scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
SHA = 'a' * 40
ROOT = Path('_runtime/dr002_gate2b2_capture_pilot/gha-123-1')
BODY = b'[ {"session_key":11371,"meeting_key":1295,"date":"2026-09-18T13:00:00Z","air_temperature":27.1} ]\n'
TIMES = ['2026-10-04T10:00:00Z', '2026-10-04T10:00:01Z', '2026-10-04T10:00:02Z', '2026-10-04T10:00:03Z']
REPOSITORY = 'F1Lllewellyn/f1-data-publisher'
WORKFLOW_PATH = '.github/workflows/dr002-capture-provenance-pilot.yml'


class WorkflowTests(unittest.TestCase):
    def test_manual_main_only(self):
        self.assertEqual(TEXT.split('on:\n')[1].split('permissions:')[0], '  workflow_dispatch:\n')
        self.assertIn("    if: github.ref == 'refs/heads/main'\n", TEXT)
        self.assertEqual(TEXT.count('    runs-on:'), 1)

    def test_permissions_exact(self):
        self.assertEqual(TEXT.split('permissions:\n')[1].split('jobs:')[0],
                         '  contents: read\n  id-token: write\n  attestations: write\n')
        self.assertEqual(TEXT.count('permissions:'), 1)
        self.assertNotIn('write-all', TEXT)
        self.assertNotIn('artifact-metadata:', TEXT)

    def test_checkout_exact(self):
        self.assertIn('uses: actions/checkout@v4\n        with:\n          ref: ${{ github.sha }}\n          persist-credentials: false', TEXT)

    def test_capture_invocation_unchanged_once(self):
        command = ('python scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py\n'
                   '          --run-id gha-${{ github.run_id }}-${{ github.run_attempt }}\n'
                   '          --implementation-git-sha ${{ github.sha }}\n')
        self.assertEqual(TEXT.count(command), 1)
        self.assertEqual(TEXT.count('python scripts/'), 1)
        self.assertEqual(TEXT.count('        run:'), 2)

    def test_attestation_order_pin_subject_and_mode(self):
        section = TEXT.split('      - name: Attest exact successful source capture receipt\n')[1].split('      - name: Preserve')[0]
        self.assertIn('id: attest_capture', section)
        self.assertIn('actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6', section)
        self.assertIn('subject-path: _runtime/dr002_gate2b2_capture_pilot/gha-${{ github.run_id }}-${{ github.run_attempt }}/source_capture_receipt.json', section)
        self.assertIn('push-to-registry: false', section)
        self.assertIn('create-storage-record: false', section)
        self.assertNotIn('if:', section)  # implicit success() after capture
        self.assertLess(TEXT.index('--implementation-git-sha'), TEXT.index('id: attest_capture'))
        self.assertLess(TEXT.index('id: attest_capture'), TEXT.index('      - name: Preserve'))

    def test_failure_remains_failure(self):
        self.assertNotIn('continue-on-error', TEXT)
        self.assertNotIn('|| true', TEXT)
        self.assertEqual(TEXT.count('if: always()'), 1)
        upload = TEXT.split('      - name: Upload runtime-only evidence and HOLD diagnostics')[1]
        self.assertIn('if: always()', upload)
        self.assertIn('path: _runtime/dr002_gate2b2_capture_pilot/**', upload)
        self.assertNotIn('run:', upload)
        self.assertNotIn('except', CODE)

    def test_packaging_imports_and_calls_have_no_network_or_retry(self):
        tree = ast.parse(CODE)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        self.assertEqual(imports, {'base64', 'hashlib', 'json', 'os', 'pathlib', 're', 'sys', 'verify_forecast_integrity_receipts_v1'})
        self.assertFalse(any(isinstance(n, (ast.While, ast.Try)) for n in ast.walk(tree)))
        for forbidden in ('urlopen(', 'requests.', 'subprocess', 'os.system', 'sleep(', 'retry', 'git push', 'git commit', 'workflow_call', 'verified_receipt_bindings'):
            self.assertNotIn(forbidden, TEXT)

    def test_no_downstream_or_token_persistence(self):
        for forbidden in ('produce_actual_forecast', 'orchestrate_forecast', 'Engine_2026', 'GITHUB_TOKEN',
                          'ACTIONS_ID_TOKEN', 'secrets.', 'os.environ.items', 'dict(os.environ)', 'print('):
            self.assertNotIn(forbidden, TEXT)
        self.assertIn('${{ steps.attest_capture.outputs.bundle-path }}', TEXT)
        self.assertIn('${{ steps.attest_capture.outputs.attestation-id }}', TEXT)
        self.assertIn('${{ steps.attest_capture.outputs.attestation-url }}', TEXT)

    def test_accepted_dependencies_unchanged(self):
        expected = {
            'scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py': 'b9b1f9acc1be30d5b7cdf42424853e3d652b9466',
            'tests/test_dr002_capture_provenance_pilot_v1.py': 'fa11b27c7e32638985944f404815a1a7fe04e4a2',
            'scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py': 'ccd17a28744f0e7c6706c3be9562d57b7dcea0ae',
            'docs/DR002_GATE2B2A_CAPTURE_PROVENANCE_PILOT_2026-10-03.md': '675f6884b631dbc5cd158195ea41005b3252e741',
            'docs/DR002_GATE2B2B_LIVE_CAPTURE_CHECKPOINT_2026-10-03.md': 'ba08ea34754af1a3d09c2a1751618474bbf7a954',
            'docs/DR002_PRE2B7D2_LIVE_GITHUB_ATTESTED_SHADOW_2026-10-03.md': 'd07a0ff228227378af863313a487e6d64c21fd50',
            'docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md': '91dfffd80635f643a2f605f75422c6311e93a9c6',
        }
        for name, sha in expected.items():
            with self.subTest(path=name):
                data = (REPO / name).read_bytes()
                self.assertEqual(hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest(), sha)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.previous_cwd = Path.cwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, self.previous_cwd)
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Network prohibited'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.transport = Mock(return_value=(200, BODY))
        pilot.capture(ROOT.name, request=self.transport, clock=Mock(side_effect=TIMES), git_commit=SHA)
        self.transport.assert_called_once_with()
        self.subject = ROOT / 'source_capture_receipt.json'
        self.original = self.subject.read_bytes()
        self.receipt = json.loads(self.original)
        self.manifest = json.loads((ROOT / 'capture_manifest.json').read_bytes())
        self.bundle = Path('runner-temp/attestation.json')
        self.bundle.parent.mkdir()
        self.statement = {'subject': [{'name': 'source_capture_receipt.json', 'digest': {'sha256': hashlib.sha256(self.original).hexdigest()}}]}
        self.save_bundle()
        self.environment = dict(ATTESTATION_BUNDLE_PATH=str(self.bundle), ATTESTATION_ID='456',
            ATTESTATION_URL='https://github.com/' + REPOSITORY + '/attestations/456',
            REPOSITORY=REPOSITORY, HEAD_SHA=SHA, RUN_ID='123', RUN_ATTEMPT='1',
            WORKFLOW_NAME='DR-002 isolated capture provenance pilot',
            WORKFLOW_REF=REPOSITORY + '/' + WORKFLOW_PATH + '@refs/heads/main',
            GITHUB_TOKEN='TOKEN_SENTINEL_MUST_NOT_ESCAPE', ACTIONS_ID_TOKEN_REQUEST_TOKEN='OIDC_SENTINEL_MUST_NOT_ESCAPE')

    def save_bundle(self):
        # Deliberately unsigned fixture: only decoding/packaging is under test.
        bundle = {'dsseEnvelope': {'payload': base64.b64encode(json.dumps(self.statement).encode()).decode(), 'signatures': []}}
        self.bundle.write_bytes((json.dumps(bundle, indent=2) + '\n').encode())

    def save_manifest(self):
        (ROOT / 'capture_manifest.json').write_bytes(pilot.canonical_json_bytes(self.manifest))

    def save_receipt(self):
        self.subject.write_bytes(pilot.canonical_json_bytes(self.receipt))
        self.manifest['receipt_sha256'] = pilot.receipt_sha256(self.receipt)
        self.save_manifest()
        self.statement['subject'][0]['digest']['sha256'] = hashlib.sha256(self.subject.read_bytes()).hexdigest()
        self.save_bundle()

    def execute(self):
        with patch.dict(os.environ, self.environment, clear=True):
            exec(compile(CODE, str(WORKFLOW) + ':packaging', 'exec'), {'__name__': '__main__'})

    def fails(self):
        before = self.subject.read_bytes() if self.subject.exists() else None
        with self.assertRaises((ValueError, KeyError, OSError, TypeError)):
            self.execute()
        self.assertFalse((ROOT / 'github_attestation_metadata.json').exists())
        if before is not None:
            self.assertEqual(self.subject.read_bytes(), before)

    def test_success_exact_bytes_metadata_and_ceiling(self):
        before = {p: p.read_bytes() for p in ROOT.rglob('*') if p.is_file()}
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self.execute()
        self.assertEqual(out.getvalue(), '')
        self.assertEqual((ROOT / 'github_attestation.bundle.json').read_bytes(), self.bundle.read_bytes())
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)
        meta = json.loads((ROOT / 'github_attestation_metadata.json').read_bytes())
        expected = dict(schema_version='dr002-github-source-capture-attestation-metadata-v1', attestation_id='456',
            attestation_url=self.environment['ATTESTATION_URL'], subject_relative_path=self.subject.as_posix(),
            subject_sha256=hashlib.sha256(self.original).hexdigest(), repository=REPOSITORY,
            workflow_path=WORKFLOW_PATH, workflow_name=self.environment['WORKFLOW_NAME'],
            workflow_ref=self.environment['WORKFLOW_REF'], git_head_sha=SHA, run_id='123', run_attempt='1',
            receipt_id=self.receipt['receipt_id'], source_uri=pilot.URI, source_sha256=hashlib.sha256(BODY).hexdigest(),
            scope=pilot.SCOPE, capture_ref=(ROOT / 'raw/openf1_weather.response.json').as_posix(),
            first_observed_utc=TIMES[1], ingested_utc=TIMES[2], binding_status='UNBOUND',
            production_authenticated=False, historical_availability_proven=False, dr002_activated=False)
        self.assertEqual(meta, expected)
        added = {p.name for p in ROOT.rglob('*') if p.is_file() and p not in before}
        self.assertEqual(added, {'github_attestation.bundle.json', 'github_attestation_metadata.json'})
        for p in ROOT.rglob('*'):
            if p.is_file():
                self.assertNotIn(b'TOKEN_SENTINEL', p.read_bytes())
                self.assertNotIn(b'OIDC_SENTINEL', p.read_bytes())

    def test_canonical_hash_distinct_from_exact_attestation_bytes(self):
        self.subject.write_bytes((json.dumps(self.receipt, indent=2) + '\n').encode())
        exact = self.subject.read_bytes()
        self.assertNotEqual(hashlib.sha256(exact).hexdigest(), self.manifest['receipt_sha256'])
        self.statement['subject'][0]['digest']['sha256'] = hashlib.sha256(exact).hexdigest()
        self.save_bundle()
        self.execute()
        self.assertEqual(self.subject.read_bytes(), exact)
        self.assertEqual(json.loads((ROOT / 'github_attestation_metadata.json').read_bytes())['subject_sha256'], hashlib.sha256(exact).hexdigest())

    def test_missing_receipt(self):
        self.subject.unlink()
        self.fails()

    def test_hold_manifest(self):
        self.manifest['validation_status'] = 'HOLD'
        self.save_manifest()
        self.fails()

    def test_wrong_run_head(self):
        self.manifest['implementation_git_sha'] = 'b' * 40
        self.save_manifest()
        self.fails()

    def test_wrong_canonical_receipt_hash(self):
        self.manifest['receipt_sha256'] = '0' * 64
        self.save_manifest()
        self.fails()

    def test_tampered_raw_bytes(self):
        (ROOT / 'raw/openf1_weather.response.json').write_bytes(BODY + b' ')
        self.fails()

    def test_wrong_receipt_source_hash(self):
        self.receipt['payload']['source_sha256'] = '0' * 64
        self.save_receipt()
        self.fails()

    def test_wrong_manifest_source_hash(self):
        self.manifest['source_sha256'] = '0' * 64
        self.save_manifest()
        self.fails()

    def test_wrong_scope(self):
        self.receipt['scope']['session_id'] = '11372'
        self.save_receipt()
        self.fails()

    def test_wrong_uri(self):
        self.receipt['payload']['source_uri'] = 'https://example.invalid/weather'
        self.save_receipt()
        self.fails()

    def test_wrong_capture_ref(self):
        self.receipt['payload']['capture_ref'] = '../raw.json'
        self.save_receipt()
        self.fails()

    def test_wrong_observation_time(self):
        self.manifest['first_observed_utc'] = TIMES[0]
        self.save_manifest()
        self.fails()

    def test_inconsistent_receipt_times(self):
        self.receipt['payload']['ingested_utc'] = TIMES[0]
        self.save_receipt()
        self.fails()

    def test_wrong_receipt_identity(self):
        self.receipt['receipt_id'] = 'source_capture:' + '0' * 64
        self.save_receipt()
        self.fails()

    def test_bundle_wrong_digest(self):
        self.statement['subject'][0]['digest']['sha256'] = '0' * 64
        self.save_bundle()
        self.fails()

    def test_bundle_wrong_name(self):
        self.statement['subject'][0]['name'] = 'capture_manifest.json'
        self.save_bundle()
        self.fails()

    def test_bundle_extra_subject(self):
        self.statement['subject'].append(self.statement['subject'][0].copy())
        self.save_bundle()
        self.fails()

    def test_invalid_bundle(self):
        self.bundle.write_text('{bad')
        self.fails()

    def test_missing_bundle(self):
        self.bundle.unlink()
        self.fails()

    def test_wrong_binding(self):
        self.manifest['binding_status'] = 'BOUND'
        self.save_manifest()
        self.fails()

    def test_false_flags_required_exactly(self):
        for flag in ('production_authenticated', 'historical_availability_proven', 'dr002_activated'):
            for value in (True, 0, 'false', None):
                with self.subTest(flag=flag, value=value):
                    self.manifest[flag] = value
                    self.save_manifest()
                    self.fails()
            self.manifest[flag] = False

    def test_wrong_workflow_ref(self):
        self.environment['WORKFLOW_REF'] = REPOSITORY + '/' + WORKFLOW_PATH + '@refs/heads/other'
        self.fails()

    def test_invalid_run_identity(self):
        self.environment['RUN_ID'] = '../123'
        self.fails()

    def test_missing_attestation_output(self):
        self.environment['ATTESTATION_ID'] = ''
        self.fails()

    def test_wrong_attestation_url(self):
        self.environment['ATTESTATION_URL'] += '7'
        self.fails()

    def test_bundle_write_failure_propagates(self):
        original_open = Path.open
        def fail(path, *args, **kwargs):
            if path.name == 'github_attestation.bundle.json' and args == ('xb',):
                raise OSError('injected bundle failure')
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', fail):
            self.fails()

    def test_metadata_write_failure_propagates(self):
        original_open = Path.open
        def fail(path, *args, **kwargs):
            if path.name == 'github_attestation_metadata.json' and args == ('xb',):
                raise OSError('injected metadata failure')
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', fail):
            self.fails()

    def test_existing_evidence_not_overwritten(self):
        self.execute()
        originals = {p: p.read_bytes() for p in ROOT.rglob('*') if p.is_file()}
        with self.assertRaises(FileExistsError):
            self.execute()
        for p, data in originals.items():
            self.assertEqual(p.read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
