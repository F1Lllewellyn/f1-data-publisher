"""Bounded outages and authenticated digest checks supplement accepted PR358."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from test_f1_1b_integrated_recovery_artifact import MODULE, artifact, REPO, TOKEN


class ArtifactRecoveryTests(unittest.TestCase):
    def test_transient_statuses_have_finite_budget_and_can_recover(self):
        for code in (429, 500, 502, 503, 504):
            for recover in (True, False):
                with self.subTest(code=code, recover=recover), patch.object(MODULE.time, 'sleep') as sleep:
                    failures = [HTTPError('https://api.github.com/test', code, 'failure', {}, None)] * 3
                    if recover:
                        failures[2] = {'ok': True}
                    with patch.object(MODULE, 'gh_get_json', side_effect=failures) as request:
                        if recover:
                            self.assertEqual(MODULE.bounded_request(lambda: request('url', TOKEN)), {'ok': True})
                        else:
                            with self.assertRaises(MODULE.ArtifactHold):
                                MODULE.bounded_request(lambda: request('url', TOKEN))
                    self.assertEqual(request.call_count, 3)
                    self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])

    def test_authentication_missing_and_unbounded_retry_after_do_not_retry(self):
        for code, headers in ((401, {}), (403, {}), (404, {}), (429, {'Retry-After': '61'})):
            with self.subTest(code=code), patch.object(MODULE.time, 'sleep') as sleep:
                with patch.object(MODULE, 'gh_get_json', side_effect=HTTPError('https://api.github.com/test', code, 'failure', headers, None)) as request:
                    with self.assertRaises((MODULE.ArtifactHold, HTTPError)):
                        MODULE.bounded_request(lambda: request('url', TOKEN))
                self.assertEqual(request.call_count, 1)
                sleep.assert_not_called()

    def test_expired_artifact_and_malformed_digest_fail_closed(self):
        for changes in ({'expires_at': '2000-01-01T00:00:00Z'}, {'digest': 'md5:wrong'}):
            with self.subTest(changes=changes), self.assertRaises(MODULE.ArtifactHold):
                MODULE.validate_artifact(artifact(**changes), REPO, MODULE.PROFILES['pre_race'])

    def test_authenticated_digest_rejects_same_size_corruption(self):
        target = artifact(digest='sha256:' + 'a' * 64)
        MODULE.verify_archive_digest(target, 'a' * 64)
        with self.assertRaisesRegex(MODULE.ArtifactHold, 'authenticated digest'):
            MODULE.verify_archive_digest(target, 'b' * 64)

    def test_listing_outage_retains_actionable_manifest(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(MODULE, 'list_artifacts', side_effect=MODULE.ArtifactHold('HTTP 503; HOLD')), patch.dict(os.environ, GITHUB_REPOSITORY=REPO, GITHUB_TOKEN=TOKEN), patch('sys.argv', ['downloader', '--output-dir', tmp]):
            with self.assertRaises(MODULE.ArtifactHold):
                MODULE.main()
            receipt = json.loads((Path(tmp) / 'manifests/elite_artifact_source_manifest.json').read_text())
            self.assertTrue(receipt['hold'])
            self.assertIn('listing failed', receipt['error'])
            self.assertFalse(receipt['source_ready'])
            self.assertFalse((Path(tmp) / 'inputs').exists())
