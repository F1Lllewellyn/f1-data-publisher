#!/usr/bin/env python3
"""Offline regressions for peak health's Auto-Repair preflight and safe push."""

from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTOREPAIR = ROOT / "scripts/autorepair/f1_autorepair_orchestrator_v1.py"
SAFE_PUSH = ROOT / "scripts/ops/safe_git_push_rebase_retry.sh"
PEAK_HEALTH = ROOT / "scripts/ops/f1_peak_elite_health_v1.py"
LATEST = Path("latest/autorepair/session_workbook_recovery")
SNAPSHOT = ("autorepair_status.json", "autorepair_report.md", "autorepair_manifest.json")


def run(cwd: Path, *command: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)


def checked(cwd: Path, *command: str) -> str:
    result = run(cwd, *command)
    if result.returncode:
        raise AssertionError(f"{command}: {result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def identity(repo: Path) -> None:
    checked(repo, "git", "config", "user.name", "Offline Test")
    checked(repo, "git", "config", "user.email", "offline@example.invalid")


class PeakWorktreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def fixture(self) -> Path:
        repo = self.base / "fixture"
        checked(self.base, "git", "init", "-q", "--initial-branch=main", str(repo))
        identity(repo)
        (repo / ".gitignore").write_text("_runtime/\n", encoding="utf-8")
        for rel in ("scripts/session_data_processor/session_data_processor_loop_v1.py",
                    "scripts/workbook_kpi_refresh/apply_workbook_kpi_refresh_v1.py"):
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# discovery fixture\n", encoding="utf-8")
        for name in SNAPSHOT:
            path = repo / LATEST / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("original owner snapshot\n", encoding="utf-8")
        checked(repo, "git", "add", ".")
        checked(repo, "git", "commit", "-qm", "seed tracked Auto-Repair snapshot")
        return repo

    def test_legacy_safe_test_reproduces_three_dirty_tracked_paths(self) -> None:
        repo = self.fixture()
        result = run(repo, sys.executable, str(AUTOREPAIR), "--mode", "safe_test", "--repo-root", str(repo))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            set(checked(repo, "git", "diff", "--name-only").splitlines()),
            {str(LATEST / name) for name in SNAPSHOT},
        )
        self.assertTrue((repo / "history/autorepair/session_workbook_recovery").exists())

    def test_peak_preflight_preserves_latest_and_history(self) -> None:
        repo = self.fixture()
        result = run(repo, sys.executable, str(AUTOREPAIR), "--mode", "safe_test",
                     "--runtime-only", "--repo-root", str(repo))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(checked(repo, "git", "status", "--porcelain"), "")
        self.assertFalse((repo / "history/autorepair").exists())
        for name in SNAPSHOT:
            self.assertEqual((repo / LATEST / name).read_text(encoding="utf-8"), "original owner snapshot\n")
        runtime = repo / "_runtime/autorepair/session_workbook_recovery"
        self.assertTrue((runtime / "autorepair_status.json").exists())
        self.assertTrue((runtime / "autorepair_report.md").exists())
        self.assertEqual((runtime / "commit_allowed.txt").read_text(encoding="utf-8"), "false")

    def test_runtime_only_refuses_live_repair(self) -> None:
        repo = self.fixture()
        result = run(repo, sys.executable, str(AUTOREPAIR), "--mode", "run_now",
                     "--runtime-only", "--repo-root", str(repo))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("only with --mode safe_test", result.stderr)
        self.assertEqual(checked(repo, "git", "status", "--porcelain"), "")

    def test_peak_health_invokes_nonmutating_preflight(self) -> None:
        repo = self.fixture()
        for source, relative in ((AUTOREPAIR, "scripts/autorepair/f1_autorepair_orchestrator_v1.py"),
                                 (PEAK_HEALTH, "scripts/ops/f1_peak_elite_health_v1.py")):
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        run(repo, sys.executable, str(repo / "scripts/ops/f1_peak_elite_health_v1.py"),
            "--repo-root", str(repo), "--run-safe-tests", "true")
        health = json.loads((repo / "_runtime/peak_elite/health/peak_elite_health.json").read_text(encoding="utf-8"))
        auto = next(step for step in health["steps"] if step["label"] == "autorepair_safe_test")
        self.assertTrue(auto["ok"], auto)
        self.assertIn("--runtime-only", auto["cmd"])
        for name in SNAPSHOT:
            self.assertEqual((repo / LATEST / name).read_text(encoding="utf-8"), "original owner snapshot\n")

    def push_fixture(self) -> tuple[Path, Path, Path]:
        remote = self.base / "remote.git"
        a, b = self.base / "writer-a", self.base / "writer-b"
        checked(self.base, "git", "init", "-q", "--bare", "--initial-branch=main", str(remote))
        checked(self.base, "git", "clone", "-q", str(remote), str(a))
        identity(a)
        tracked = a / LATEST / "autorepair_status.json"
        tracked.parent.mkdir(parents=True, exist_ok=True)
        tracked.write_text("base\n", encoding="utf-8")
        checked(a, "git", "add", ".")
        checked(a, "git", "commit", "-qm", "seed")
        checked(a, "git", "push", "-q", "origin", "main")
        checked(self.base, "git", "clone", "-q", str(remote), str(b))
        identity(b)
        return remote, a, b

    def safe_push(self, repo: Path) -> subprocess.CompletedProcess[str]:
        return run(repo, "bash", str(SAFE_PUSH), env={**os.environ,
                   "GITHUB_REF_NAME": "main", "F1_SAFE_PUSH_SLEEP_SECONDS": "0",
                   "F1_SAFE_PUSH_MAX_ATTEMPTS": "2"})

    def test_collision_reports_dirty_path_without_discard_or_push(self) -> None:
        remote, a, b = self.push_fixture()
        (a / "other.txt").write_text("remote change\n", encoding="utf-8")
        checked(a, "git", "add", "other.txt")
        checked(a, "git", "commit", "-qm", "parallel writer")
        checked(a, "git", "push", "-q", "origin", "main")
        before = checked(remote, "git", "rev-parse", "refs/heads/main")
        (b / "own.txt").write_text("local committed change\n", encoding="utf-8")
        checked(b, "git", "add", "own.txt")
        checked(b, "git", "commit", "-qm", "peak writer")
        dirty = b / LATEST / "autorepair_status.json"
        dirty.write_text("unsaved snapshot\n", encoding="utf-8")
        result = self.safe_push(b)
        self.assertEqual(result.returncode, 20, result.stdout + result.stderr)
        self.assertIn("tracked worktree changes before rebase", result.stdout)
        self.assertIn(str(LATEST / "autorepair_status.json"), result.stdout)
        self.assertEqual(dirty.read_text(encoding="utf-8"), "unsaved snapshot\n")
        self.assertEqual(checked(remote, "git", "rev-parse", "refs/heads/main"), before)

    def test_clean_collision_rebases_and_conflict_still_holds(self) -> None:
        remote, a, b = self.push_fixture()
        (a / "other.txt").write_text("remote change\n", encoding="utf-8")
        checked(a, "git", "add", "other.txt")
        checked(a, "git", "commit", "-qm", "parallel writer")
        checked(a, "git", "push", "-q", "origin", "main")
        (b / "own.txt").write_text("local change\n", encoding="utf-8")
        checked(b, "git", "add", "own.txt")
        checked(b, "git", "commit", "-qm", "peak writer")
        result = self.safe_push(b)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(set(checked(remote, "git", "ls-tree", "-r", "--name-only", "main").splitlines()),
                         {"other.txt", "own.txt", str(LATEST / "autorepair_status.json")})

        c = self.base / "writer-c"
        checked(self.base, "git", "clone", "-q", str(remote), str(c))
        identity(c)
        (b / "own.txt").write_text("another remote value\n", encoding="utf-8")
        checked(b, "git", "add", "own.txt")
        checked(b, "git", "commit", "-qm", "remote update")
        checked(b, "git", "push", "-q", "origin", "main")
        (c / "own.txt").write_text("conflicting local value\n", encoding="utf-8")
        checked(c, "git", "add", "own.txt")
        checked(c, "git", "commit", "-qm", "conflicting local update")
        before = checked(remote, "git", "rev-parse", "refs/heads/main")
        conflict = self.safe_push(c)
        self.assertEqual(conflict.returncode, 20, conflict.stdout + conflict.stderr)
        self.assertIn("rebase conflict", conflict.stdout)
        self.assertEqual(checked(remote, "git", "rev-parse", "refs/heads/main"), before)
        self.assertEqual(checked(c, "git", "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
