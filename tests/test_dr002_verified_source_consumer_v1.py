"""Synthetic interface composition, not signature verification or live capture."""
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_dr002_github_attestation_binding_v1 as f1_fixture
from scripts.forecast_bundles import dr002_verified_source_consumer_v1 as consumer

gate = consumer.receipts
frozen = consumer.frozen


def fixture():
    # Use the accepted bridge itself with its synthetic external-verifier fixture.
    # These are consistency fixtures; no signature authenticity is asserted.
    source = b'explicit synthetic weather bytes\n'
    receipt, _, _, verified, identity, ref = f1_fixture.fixture()
    receipt['payload']['source_sha256'] = gate.sha256(source)
    raw = gate.canonical_json_bytes(receipt)
    statement = verified['result']['statement']
    statement['subject'][0]['digest']['sha256'] = gate.sha256(raw)
    bundle = verified['result']['bundle']
    bundle['dsseEnvelope']['payload'] = base64.b64encode(gate.canonical_json_bytes(statement)).decode()
    result = consumer.bridge.build_verified_github_receipt_binding(
        raw, gate.canonical_json_bytes(bundle), verified, identity, ref)
    assert result['status'] == 'VERIFIED_GITHUB_PROVENANCE_BINDING'
    return dict(receipt_bytes=raw, source_bytes=source,
                request_scope=dict(event_id='event', meeting_id='meeting',
                                   allowed_session_ids=['session', 'other']),
                bridge_result=result)


class ConsumerTests(unittest.TestCase):
    def hold(self, args):
        before = copy.deepcopy(args)
        out = consumer.consume_verified_source(**args)
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['verified_receipt_bindings'], {})
        self.assertNotIn('frozen_evidence_manifest', out)
        self.assertTrue(all(out[k] is False for k in consumer.bridge.HOLD_TRUST))
        self.assertEqual(args, before)

    def test_success_composes_actual_bridge_and_unchanged_builder(self):
        args = fixture()
        out = consumer.consume_verified_source(**args)
        receipt = json.loads(args['receipt_bytes'])
        digest = gate.receipt_sha256(receipt)
        expected_manifest = frozen.build_frozen_evidence_manifest(
            {**args['request_scope'], 'captures': [{'receipt_path': 'r', 'content_path': 'c'}]},
            read_bytes={'r': args['receipt_bytes'], 'c': args['source_bytes']}.__getitem__)
        self.assertEqual(out, dict(
            status='OFFLINE_VERIFIED_SOURCE_CONSUMER_VALIDATED',
            frozen_evidence_manifest=expected_manifest,
            verified_receipt_bindings=args['bridge_result']['verified_receipt_bindings'],
            receipt_id=receipt['receipt_id'], canonical_receipt_sha256=digest,
            exact_receipt_sha256=gate.sha256(args['receipt_bytes']),
            source_sha256=gate.sha256(args['source_bytes']),
            binding_trust_scope='GITHUB_EXECUTION_PROVENANCE_ONLY',
            attested_receipt_existed_by_utc='2026-10-04T19:42:36Z',
            internal_first_observed_utc=receipt['payload']['first_observed_utc'],
            frozen_manifest_binding_status='UNBOUND', **consumer.bridge.HOLD_TRUST))
        gate._external_binding(receipt, out['verified_receipt_bindings'])
        self.assertTrue(frozen.validate_frozen_evidence_manifest(out['frozen_evidence_manifest']))

    def test_manifest_stays_unbound_and_companion_stays_separate(self):
        out = consumer.consume_verified_source(**fixture())
        self.assertEqual(out['frozen_evidence_manifest']['manifest']['trust'], dict(
            binding_status='UNBOUND', production_authenticated=False, historical_availability_proven=False))
        self.assertNotIn('verified_receipt_bindings', out['frozen_evidence_manifest']['manifest'])
        self.assertNotEqual(out['source_sha256'], out['exact_receipt_sha256'])

    def test_noncanonical_bytes_hold(self):
        args = fixture()
        args['receipt_bytes'] = json.dumps(json.loads(args['receipt_bytes']), indent=2).encode()
        self.hold(args)

    def test_malformed_receipts_hold(self):
        for value in [b'{', b'null', b'[]', b'NaN', b'\xff', b'{"a":1,"a":2}', {}, None]:
            with self.subTest(value=value):
                args = fixture(); args['receipt_bytes'] = value; self.hold(args)

    def test_parented_and_valid_wrong_type_receipts_hold(self):
        args = fixture(); receipt = json.loads(args['receipt_bytes'])
        receipt['parent_receipt_ids'] = ['parent']
        args['receipt_bytes'] = gate.canonical_json_bytes(receipt); self.hold(args)
        receipt['receipt_type'] = 'revision'
        receipt['scope'].update(product_id='p', forecast_id='f', gate='post_event', lane_name='test')
        receipt['payload'] = dict(revision_id='rev', source_id='s', source_sha256='a'*64,
                                  first_observed_utc='2026-10-04T19:42:34Z')
        gate.validate_receipt_envelope(receipt)
        args['receipt_bytes'] = gate.canonical_json_bytes(receipt); self.hold(args)

    def test_source_bytes_must_match(self):
        for value in [b'changed', '', None, bytearray(b'x')]:
            args = fixture(); args['source_bytes'] = value; self.hold(args)

    def test_scope_mismatches_hold(self):
        for field, value in [('event_id', 'wrong'), ('meeting_id', 'wrong'),
                             ('allowed_session_ids', ['wrong'])]:
            args = fixture(); args['request_scope'][field] = value; self.hold(args)

    def test_malformed_request_scope_holds(self):
        for value in [None, [], {}, {'event_id': 'event'},
                      dict(event_id='event', meeting_id='meeting', allowed_session_ids=[]),
                      dict(event_id='event', meeting_id='meeting', allowed_session_ids=['session', 'session']),
                      dict(event_id='event', meeting_id='meeting', allowed_session_ids='session'),
                      dict(event_id='event', meeting_id='meeting', allowed_session_ids=[None])]:
            args = fixture(); args['request_scope'] = value; self.hold(args)
        args = fixture(); args['request_scope']['captures'] = []; self.hold(args)

    def test_bridge_status_scope_and_schema_hold(self):
        for field, value in [('status', 'HOLD'), ('trust_scope', 'AUTHENTICATED'),
                             ('schema_version', 'unknown')]:
            args = fixture(); args['bridge_result'][field] = value; self.hold(args)

    def test_ambiguous_envelope_holds(self):
        args = fixture()
        for field in list(args['bridge_result']):
            with self.subTest(missing=field):
                changed = copy.deepcopy(args); del changed['bridge_result'][field]; self.hold(changed)
        args['bridge_result']['extra_claim'] = True; self.hold(args)
        args['bridge_result'] = None; self.hold(args)

    def test_missing_extra_wrong_binding_holds(self):
        for value in [{}, {'wrong': {}}, None]:
            args = fixture(); args['bridge_result']['verified_receipt_bindings'] = value; self.hold(args)
        args = fixture(); args['bridge_result']['verified_receipt_bindings']['extra'] = {}; self.hold(args)

    def test_binding_entry_validated_by_gate2b1(self):
        for field, value in [('receipt_sha256', '0'*64), ('verification_ref', ''), ('extra', True)]:
            args = fixture(); rid = args['bridge_result']['receipt_id']
            args['bridge_result']['verified_receipt_bindings'][rid][field] = value; self.hold(args)

    def test_bridge_receipt_hash_fields_hold(self):
        for field in ['receipt_id', 'canonical_receipt_sha256', 'exact_receipt_sha256']:
            args = fixture(); args['bridge_result'][field] = 'wrong'; self.hold(args)

    def test_every_ceiling_requires_false_boolean(self):
        for field in consumer.bridge.HOLD_TRUST:
            for value in [True, 0, None, 'false']:
                with self.subTest(field=field, value=value):
                    args = fixture(); args['bridge_result'][field] = value; self.hold(args)

    def test_temporal_projection_must_match_receipt(self):
        for field, value in [('internal_first_observed_utc', '2026-10-04T19:42:35Z'),
                             ('attested_receipt_existed_by_utc', '2026-10-04T19:42:34Z'),
                             ('attested_receipt_existed_by_utc', 'not-a-time'),
                             ('attested_receipt_existed_by_utc', None)]:
            args = fixture(); args['bridge_result'][field] = value; self.hold(args)

    def test_invalid_builder_output_holds_without_repair(self):
        args = fixture()
        manifest = consumer.consume_verified_source(**args)['frozen_evidence_manifest']
        for field, value in [('binding_status', 'BOUND'), ('production_authenticated', True),
                             ('historical_availability_proven', True)]:
            changed = copy.deepcopy(manifest); changed['manifest']['trust'][field] = value
            before = copy.deepcopy(changed)
            with patch.object(frozen, 'build_frozen_evidence_manifest', return_value=changed):
                self.hold(args)
            self.assertEqual(changed, before)
        changed = copy.deepcopy(manifest); changed['frozen_evidence_manifest_sha256'] = '0'*64
        with patch.object(frozen, 'build_frozen_evidence_manifest', return_value=changed):
            self.hold(args)

    def test_no_mutation_deterministic_and_no_output_aliases(self):
        args = fixture(); before = copy.deepcopy(args)
        first = consumer.consume_verified_source(**args)
        self.assertEqual(first, consumer.consume_verified_source(**args))
        self.assertEqual(args, before)
        first['verified_receipt_bindings'][first['receipt_id']]['verification_ref'] = 'changed'
        first['frozen_evidence_manifest']['manifest']['scope']['allowed_session_ids'].append('changed')
        self.assertEqual(args, before)

    def test_offline_closed_reader_and_no_io_dependencies(self):
        args = fixture()
        with patch('builtins.open', side_effect=AssertionError('file I/O')), \
             patch.object(Path, 'read_bytes', side_effect=AssertionError('path I/O')), \
             patch('socket.socket', side_effect=AssertionError('network')):
            self.assertEqual(consumer.consume_verified_source(**args)['status'],
                             'OFFLINE_VERIFIED_SOURCE_CONSUMER_VALIDATED')
        def probe(request, *, read_bytes):
            self.assertEqual(read_bytes('receipt'), args['receipt_bytes'])
            self.assertEqual(read_bytes('source'), args['source_bytes'])
            with self.assertRaises(KeyError):
                read_bytes('/arbitrary/path')
            return real_builder(request, read_bytes=read_bytes)
        real_builder = frozen.build_frozen_evidence_manifest
        with patch.object(frozen, 'build_frozen_evidence_manifest', side_effect=probe):
            self.assertEqual(consumer.consume_verified_source(**args)['status'],
                             'OFFLINE_VERIFIED_SOURCE_CONSUMER_VALIDATED')
        tree = ast.parse(Path(consumer.__file__).read_text())
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual(len(imports), 3)
        self.assertTrue(all(isinstance(n, ast.ImportFrom) and n.level == 1 for n in imports))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, 'attr', getattr(node.func, 'id', ''))
                self.assertNotIn(name, {'open', 'read_bytes', 'write_bytes', 'getenv', 'now',
                                        'utcnow', 'today', 'system', 'exec', 'eval'})

    def test_declared_dependency_blobs_unchanged(self):
        expected = {
            'scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py': 'ccd17a28744f0e7c6706c3be9562d57b7dcea0ae',
            'scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py': '8dfd855184b172ce88235ee7de3ea33a68031b2e',
            'scripts/forecast_bundles/dr002_github_attestation_binding_v1.py': '215f012b79aa9e6f33aff6ad62ca7efba53a9627',
            'tests/test_dr002_github_attestation_binding_v1.py': '1d764c840202463e091110132521f23f34853ad0',
            'docs/DR002_PRE2B7F1_GITHUB_ATTESTATION_BINDING_BRIDGE_2026-10-04.md': '0ebbfe417cc460ad87ad5efcfd8535d282d2419b',
            'docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md': '85ce44807ef159b5ba5d3bfd543ea1f945097f77',
        }
        root = Path(__file__).resolve().parents[1]
        for path, sha in expected.items():
            with self.subTest(path=path):
                raw = (root/path).read_bytes()
                self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(), sha)


if __name__ == '__main__':
    unittest.main()
