"""Execute the deployed bridge publication shell against isolated Git remotes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/f1-1b-output-contract-after-control-room-v22.yml'


class BridgePublicationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'checkout'
        self.remote = Path(tmp.name) / 'remote.git'
        self.root.mkdir()
        self.git('init', '--bare', str(self.remote))
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Sandbox Test')
        self.git('config', 'user.email', 'sandbox@example.invalid')
        self.git('remote', 'add', 'origin', str(self.remote))
        self.write('README.md', 'isolated publication test\n')
        self.write('Engine_2026-06-07_STABLE', 'protected sentinel\n')
        self.write('.gitignore', '_runtime/\nlatest/readiness_handoff/ignored.json\n')
        self.write('scripts/ops/safe_git_push_rebase_retry.sh',
                   (ROOT / 'scripts/ops/safe_git_push_rebase_retry.sh').read_text())
        self.git('add', '.')
        self.git('commit', '-m', 'sandbox base')
        self.git('push', '-u', 'origin', 'main')
        self.base = self.git('rev-parse', 'HEAD').stdout.strip()
        self.write('_runtime/1b_output_contract/start.marker', '', 20)
        self.write('latest/readiness_handoff/current.json', '{"state":"HOLD"}\n', 30)
        self.write('latest/readiness_handoff/ignored.json', '{}\n', 30)
        self.write('history/readiness_handoff/not_owned.json', '{}\n', 30)
        self.write('history/downstream_consumers/old.json', '{}\n', 10)
        self.write('history/downstream_consumers/new.json', '{}\n', 30)
        self.write('history/session_data_processor/upstream.json', '{}\n', 30)
        self.write('latest/workbook_kpi_refresh_applier/upstream.xlsx', 'upstream\n', 30)

    def git(self, *args, check=True):
        return subprocess.run(['git', *args], cwd=self.root, text=True,
                              capture_output=True, check=check)

    def write(self, rel, content, mtime=None):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        if mtime is not None:
            os.utime(p, (mtime, mtime))

    def publish(self):
        script = textwrap.dedent(WORKFLOW.read_text().split(
            '- name: Commit v25 output-contract bridge', 1)[1].split('run: |', 1)[1])
        env = dict(os.environ, GITHUB_REF_NAME='main', F1_SAFE_PUSH_SLEEP_SECONDS='0')
        return subprocess.run(['bash', '-c', script], cwd=self.root, env=env,
                              capture_output=True, text=True, timeout=15)

    def remote_head(self):
        return self.git('--git-dir=' + str(self.remote), 'rev-parse', 'main').stdout.strip()

    def test_real_shell_publishes_only_owned_new_outputs_and_restart_is_noop(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        changed = self.git('diff', '--name-only', self.base, 'HEAD').stdout.splitlines()
        self.assertEqual(set(changed), {'latest/readiness_handoff/current.json',
                                       'history/downstream_consumers/new.json'})
        first = self.remote_head()
        self.assertEqual(first, self.git('rev-parse', 'HEAD').stdout.strip())
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.remote_head(), first)
        self.assertEqual((self.root / 'Engine_2026-06-07_STABLE').read_text(), 'protected sentinel\n')

    def test_missing_marker_refuses_publication(self):
        (self.root / '_runtime/1b_output_contract/start.marker').unlink()
        self.assertNotEqual(self.publish().returncode, 0)
        self.assertEqual(self.remote_head(), self.base)

    def test_modified_protected_asset_refuses_publication(self):
        self.write('Engine_2026-06-07_STABLE', 'mutation must not publish\n')
        self.assertNotEqual(self.publish().returncode, 0)
        self.assertEqual(self.remote_head(), self.base)

    def test_remote_rejection_retains_commit_without_publishing(self):
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.remote_head(), self.base)
        self.assertNotEqual(self.git('rev-parse', 'HEAD').stdout.strip(), self.base)


if __name__ == '__main__':
    unittest.main()
