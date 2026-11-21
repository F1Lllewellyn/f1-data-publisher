"""Reproduce the existing readiness workflow's exact sparse import surface."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SparseHarnessTests(unittest.TestCase):
    def test_readiness_suite_imports_with_only_declared_checkout_paths(self):
        workflow = (ROOT / ".github/workflows/f1-session-readiness-recovery-pr-tests.yml").read_text()
        paths = workflow.split("          sparse-checkout: |\n", 1)[1].split("          sparse-checkout-cone-mode:", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            sparse = Path(directory)
            for relative in (line.strip() for line in paths.splitlines()):
                if not relative or relative.startswith("history/"):
                    continue  # no historical data needed by the first suite
                source = ROOT / relative
                destination = sparse / relative
                if source.is_dir():
                    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
            self.assertFalse((sparse / "tests/test_f1_1b_integrated_recovery_byte_custody.py").exists())
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_sp2026_integrated_recovery_guard_v1.py", "-v"],
                cwd=sparse, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Ran 12 tests", result.stderr)


if __name__ == "__main__":
    unittest.main()
