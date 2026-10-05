"""Offline validator regression tests; no workflow or shell payload execution."""
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / 'scripts/ops'
sys.path.insert(0, str(OPS))
scan = importlib.import_module('f1_workflow_shell_scan_v1')
static = importlib.import_module('f1_workflow_static_validator_v2')


def workflow(script):
    return 'name: Test\non: workflow_dispatch\njobs:\n  test:\n    steps:\n      - name: Test\n        run: |\n' + ''.join(
        '          ' + line + '\n' for line in script.splitlines())


class HeredocTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'.github/workflows').mkdir(parents=True)
        (self.root/'scripts/ops').mkdir(parents=True)
        (self.root/'scripts/ops/safe_git_push_rebase_retry.sh').write_text('# fixture only\n')
        (self.root/'.github/workflows/f1-workbook-kpi-refresh-scheduled.yml').write_text(
            'name: Required fixture\non: workflow_dispatch\njobs: {}\n')
        self.path = self.root/'.github/workflows/test.yml'

    def results(self, text):
        self.path.write_text(text)
        with patch.object(static, 'ROOT', self.root):
            result = static.validate_workflow(self.path)
        env = dict(os.environ, GITHUB_WORKSPACE=str(self.root), PYTHONDONTWRITEBYTECODE='1')
        proc = subprocess.run([sys.executable, str(OPS/'f1_workflow_meta_health_check_v1.py')],
                              cwd=self.root, env=env, capture_output=True, text=True)
        meta = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, int(meta['status'] == 'Fail'), proc.stderr)
        return result, meta

    def assert_pass(self, script):
        for result in self.results(workflow(script)):
            self.assertFalse([i for i in result['issues'] if i['severity'] == 'fail'], result)

    def assert_fail(self, script):
        for result in self.results(workflow(script)):
            self.assertTrue([i for i in result['issues'] if i['severity'] == 'fail'], result)

    def test_current_dr002_workflows(self):
        for name, old_count in [('dr002-capture-provenance-pilot.yml', 25),
                                ('dr002-frozen-producer-shadow-pilot.yml', 8)]:
            with self.subTest(name=name):
                text = (ROOT/'.github/workflows'/name).read_text()
                scripts = [b[3] for b in static.extract_run_blocks(text.splitlines())]
                self.assertEqual(sum(len(re.findall(r'(?m)^\s*if\b', s)) for s in scripts), old_count)
                for s in scripts:
                    self.assertEqual(static.bash_validate(s), '')
                    self.assertEqual(len(re.findall(r'(?m)^\s*if\b', scan.shell_visible_text(s))), 0)
                for result in self.results(text):
                    self.assertFalse([i for i in result['issues'] if i['severity'] == 'fail'], result)

    def test_python_body_not_shell(self):
        self.assert_pass("python - <<'PY'\nif True:\n    if False:\n        pass\nfi\nfor arbitrary text\nPY\n")

    def test_real_bash_around_and_beside_heredoc(self):
        self.assert_pass("if true; then\n  cat <<'END'\nif\nfi\nEND\nfi\nif false; then\n  :\nfi\n")

    def test_unmatched_bash_if_still_fails(self):
        self.assert_fail("cat <<EOF\nif python:\nEOF\nif true; then\n  :\n")

    def test_body_fi_cannot_close_real_if(self):
        self.assert_fail("if true; then\ncat <<EOF\nfi\nEOF\n")

    def test_delimiter_forms(self):
        for opener, end in [('EOF', 'EOF'), ("'EOF'", 'EOF'), ('"EOF"', 'EOF'),
                            ('-EOF', '\tEOF'), ("-'EOF'", '\tEOF'), ('\\EOF', 'EOF'),
                            ("E'O'F", 'EOF'), ("'END MARK'", 'END MARK'), ("''", '')]:
            with self.subTest(opener=opener):
                self.assert_pass('cat <<'+opener+'\nif arbitrary:\n'+end+'\necho done\n')

    def test_multiple_heredocs_consumed_in_order(self):
        self.assert_pass("cat <<A <<'B'\nif\nA\nfi\nif\nB\n")

    def test_unterminated_and_malformed_fail_closed(self):
        for script in ["cat <<EOF\nif\n", 'cat <<\n', "cat <<'EOF\n", 'cat <<-EOF\n EOF\n',
                       'cat <<EOF\nEOF \n', 'cat <<A <<B\nA\n']:
            with self.subTest(script=script):
                with self.assertRaises(scan.ShellScanError):
                    scan.shell_visible_text(script)
                self.assert_fail(script)

    def test_cr_in_terminator_is_not_stripped_by_helper(self):
        with self.assertRaises(scan.ShellScanError):
            scan.shell_visible_text('cat <<EOF\nEOF\r\n')

    def test_literals_comments_here_strings_arithmetic_not_heredocs(self):
        self.assert_pass('echo "<<EOF"\necho \'<<EOF\'\n# <<EOF\ncat <<< "if"\n'
                         'echo $((1 << 2))\n(( x = 1 << 2 ))\n')

    def test_continued_header(self):
        self.assert_pass("cat <<EOF \\\n  | cat\nif\nEOF\n")

    def test_unquoted_body_backslash_newline(self):
        self.assert_pass('cat <<EOF\nif\\\nEOF\nEOF\n')
        with self.assertRaises(scan.ShellScanError):
            scan.shell_visible_text('cat <<EOF\nif\\\nEOF\n')

    def test_scanner_retains_shell_and_line_positions(self):
        script = "if true; then\ncat <<'EOF'\nif python\nEOF\nfi\n"
        expected = "if true; then\ncat <<'EOF'\n\n\nfi\n"
        self.assertEqual(scan.shell_visible_text(script), expected)
        self.assertEqual(scan.shell_visible_text(script), scan.shell_visible_text(script))

    def test_bash_n_receives_original_script(self):
        text = workflow("cat <<EOF\nif python\nEOF\n")
        original = static.extract_run_blocks(text.splitlines())[0][3]
        self.path.write_text(text)
        with patch.object(static, 'ROOT', self.root), patch.object(static, 'bash_validate', return_value='') as check:
            static.validate_workflow(self.path)
        check.assert_called_once_with(original)
        self.assertNotEqual(original, scan.shell_visible_text(original))
        with patch.object(static.shutil, 'which', return_value='/bin/bash'), \
             patch.object(static.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            static.bash_validate(original)
        self.assertEqual(run.call_args.args[0][:2], ['/bin/bash', '-n'])

    def test_raw_and_force_push_checks_remain(self):
        # These legacy checks deliberately still inspect original text, including bodies.
        text = workflow("cat <<EOF\ngit push --force\nEOF\ngit push origin main\n")
        result, meta = self.results(text)
        messages = [i['message'] for i in result['issues']]
        self.assertEqual(messages.count('raw_git_push_detected_prefer_safe_push_retry'), 2)
        self.assertIn('force_push_detected', messages)
        self.assertEqual(sum(i['severity'] == 'warn' for i in meta['issues']), 2)

    def test_bom_and_missing_required_keys(self):
        self.path.write_bytes(b'\xef\xbb\xbf'+workflow('echo ok').encode())
        with patch.object(static, 'ROOT', self.root):
            result = static.validate_workflow(self.path)
        self.assertIn('utf8_bom_present', [i['message'] for i in result['issues']])
        self.path.write_text('run: |\n  echo ok\n')
        with patch.object(static, 'ROOT', self.root):
            result = static.validate_workflow(self.path)
        self.assertEqual({i['message'] for i in result['issues']},
                         {'missing_required_key_name', 'missing_required_key_on', 'missing_required_key_jobs'})

    def test_protected_asset_detection_unchanged(self):
        paths = ['Engine_2026-06-07_STABLE/code.py', 'F1_2026_Prediction_Model_Data_Workbook.xlsx',
                 'F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated.xlsx']
        proc = subprocess.CompletedProcess([], 0, '\n'.join(' M '+p for p in paths), '')
        with patch.object(static.shutil, 'which', return_value='/usr/bin/git'), \
             patch.object(static.subprocess, 'run', return_value=proc):
            self.assertEqual(static.protected_modified(self.root), paths)

    def test_shared_pure_helper_used_by_both(self):
        self.assertIs(static.shell_visible_text, scan.shell_visible_text)
        for name in ['f1_workflow_meta_health_check_v1.py', 'f1_workflow_static_validator_v2.py']:
            tree = ast.parse((OPS/name).read_text())
            self.assertTrue(any(isinstance(n, ast.ImportFrom) and n.module == 'f1_workflow_shell_scan_v1'
                                for n in ast.walk(tree)))
            self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                                and n.func.id == 'shell_visible_text' for n in ast.walk(tree)))
        tree = ast.parse(Path(scan.__file__).read_text())
        self.assertFalse(any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree)))

    def test_unchanged_dependency_blobs(self):
        expected = {
            '.github/workflows/dr002-capture-provenance-pilot.yml': '883fcbc1a00ec9ae1dd6dd40423a03af05ae1fe3',
            '.github/workflows/dr002-frozen-producer-shadow-pilot.yml': '850e96cbea815c3dec3f14c3a731f2f65cce2944',
            '.github/workflows/f1-peak-elite-control-room-one-click-v1.yml': '42c107142e076ac4d056f2e33e93dab4163f3b72',
            'scripts/ops/f1_peak_elite_health_v1.py': '7e27e30a12649cf36eaaa19c0862d468579c314a',
            'scripts/ops/safe_git_push_rebase_retry.sh': '85f85bb540cf8442827a1586d5ccf0c5602d7a75',
            'docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md': '85ce44807ef159b5ba5d3bfd543ea1f945097f77',
        }
        for path, sha in expected.items():
            with self.subTest(path=path):
                data = (ROOT/path).read_bytes()
                self.assertEqual(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(), sha)


if __name__ == '__main__':
    unittest.main()
