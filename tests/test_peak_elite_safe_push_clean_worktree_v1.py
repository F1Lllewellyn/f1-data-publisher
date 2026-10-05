"""Offline staging regression; the synthetic helper records status, never pushes."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = '.github/workflows/f1-peak-elite-control-room-one-click-v1.yml'
READINESS = ('latest/latest_manifest.json', 'latest/data_readiness.json',
             'latest/combined_source_manifest.json')
ADDED_LINES = ''.join('            "'+p+'"\n' for p in READINESS)


def candidates(text):
    blocks = re.findall(r'(?m)^\s*candidates=\(\n(.*?)^\s*\)', text, re.S)
    assert len(blocks) == 1
    return re.findall(r'^\s*"([^"]+)"\s*$', blocks[0], re.M)


def commit_script(text):
    marker = '      - name: Commit safe repaired workflows, status outputs, and refreshed workbook handoff artifacts\n'
    block = text.split(marker, 1)[1].split('        run: |\n', 1)[1]
    return '\n'.join(line[10:] if line.startswith('          ') else line
                     for line in block.splitlines())+'\n'


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True, text=True,
                          capture_output=True).stdout


class CleanWorktreeTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT/WORKFLOW).read_text()

    def test_exact_three_additions_and_no_other_workflow_change(self):
        self.assertEqual(self.text.count(ADDED_LINES), 1)
        baseline = self.text.replace(ADDED_LINES, '', 1).encode()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(baseline)).encode()+b'\0'+baseline).hexdigest(),
                         '42c107142e076ac4d056f2e33e93dab4163f3b72')
        old = candidates(baseline.decode()); new = candidates(self.text)
        for path in READINESS:
            self.assertEqual(new.count(path), 1)
            self.assertNotIn(path, old)
        self.assertEqual([p for p in new if p not in READINESS], old)
        # Reconstructing the exact baseline proves all guards/cache/roots/force-add,
        # commit message/concurrency/input behavior and other workflow bytes unchanged.

    def test_established_session_workflow_candidate_outputs(self):
        for path in ['.github/workflows/f1-session-data-processor-loop-v1.yml',
                     '.github/workflows/f1-session-autorepair-integrated-loop-v1.yml']:
            listed = candidates((ROOT/path).read_text(encoding='utf-8-sig'))
            for output in READINESS:
                self.assertEqual(listed.count(output), 1, (path, output))

    def test_synthetic_commit_leaves_no_tracked_dirt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, 'init', '-b', 'main')
            git(root, 'config', 'user.name', 'Offline Test')
            git(root, 'config', 'user.email', 'offline@example.invalid')
            changed_paths = list(READINESS)+['latest/session_data_processor/synthetic.json']
            for path in changed_paths:
                f = root/path; f.parent.mkdir(parents=True, exist_ok=True); f.write_text('{"version":1}\n')
            # Substitute only the helper's implementation in this disposable fixture.
            # The exact workflow call executes, but no remote or real push is used.
            helper = root/'scripts/ops/safe_git_push_rebase_retry.sh'
            helper.parent.mkdir(parents=True)
            status = root/'_runtime/status_at_safe_push.txt'
            helper.write_text('set -euo pipefail\nmkdir -p _runtime\n'
                              'git status --porcelain=v1 --untracked-files=no > _runtime/status_at_safe_push.txt\n')
            git(root, 'add', '.'); git(root, 'commit', '-m', 'synthetic baseline')
            for path in changed_paths:
                (root/path).write_text('{"version":2}\n')
            original = git(root, 'rev-parse', 'HEAD')
            script = commit_script(self.text).replace('${{ inputs.commit_outputs }}', 'true')
            proc = subprocess.run(['bash', '-c', script], cwd=root, capture_output=True,
                                  text=True, env=dict(os.environ, GITHUB_WORKSPACE=str(root)))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotEqual(git(root, 'rev-parse', 'HEAD'), original)
            self.assertEqual(git(root, 'show', '--pretty=', '--name-only').splitlines(), sorted(changed_paths))
            self.assertEqual(status.read_text(), '')
            self.assertEqual(git(root, 'status', '--porcelain=v1', '--untracked-files=no'), '')
            for path in READINESS:
                self.assertEqual(git(root, 'show', 'HEAD:'+path), '{"version":2}\n')

    def test_protected_guards_surround_staging(self):
        script = commit_script(self.text)
        first = script.index('if git status --porcelain | grep -E "$PROTECTED_PATTERN"; then')
        staging = script.index('git add "$p"')
        second = script.index('if git diff --cached --name-only | grep -E "$PROTECTED_PATTERN"; then')
        self.assertLess(first, staging)
        self.assertLess(staging, second)
        self.assertLess(second, script.index('git commit -m'))
        for pattern in ['Engine_2026-06-07_STABLE', 'F1_2026_Prediction_Model_Data_Workbook\\.xlsx',
                        'F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated\\.xlsx']:
            self.assertIn(pattern, script)

    def test_safe_push_call_exact_and_no_dangerous_additions(self):
        script = commit_script(self.text)
        self.assertEqual(script.count('bash scripts/ops/safe_git_push_rebase_retry.sh'), 1)
        self.assertTrue(script.endswith('  bash scripts/ops/safe_git_push_rebase_retry.sh\nfi\n'))
        for pattern in [r'git push.*--force', r'git stash', r'--autostash',
                        r'git reset\s+--hard', r'git clean']:
            self.assertNotRegex(script, pattern)
        self.assertNotRegex(ADDED_LINES, r'\b(push|stash|reset|clean|concurrency)\b')

    def test_original_commit_block_bash_syntax(self):
        script = commit_script(self.text).replace('${{ inputs.commit_outputs }}', 'true')
        proc = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_unchanged_dependency_blobs(self):
        expected = {
            'scripts/ops/safe_git_push_rebase_retry.sh': '85f85bb540cf8442827a1586d5ccf0c5602d7a75',
            '.github/workflows/f1-session-data-processor-loop-v1.yml': 'cfbed6cbedac9c7e601802c38c6eb5770d09004d',
            '.github/workflows/f1-session-autorepair-integrated-loop-v1.yml': '3392539856cda53cb29652f5ada4988ce74fb779',
            'docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md': '85ce44807ef159b5ba5d3bfd543ea1f945097f77',
        }
        for path, sha in expected.items():
            with self.subTest(path=path):
                raw = (ROOT/path).read_bytes()
                self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(), sha)


if __name__ == '__main__':
    unittest.main()
