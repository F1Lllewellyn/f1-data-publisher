"""Regression for post-PR364 workbook persistence / bounded output bridge.

The static guard must not require obsolete force-staging of unrelated upstream
workbooks, and it must reject reintroducing unsafe historical publication.
Uses isolated, synthetic copies of workflow YAML; no provider or git mutation.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts/ops/f1_workbook_persistence_handoff_guard_v1.py"
spec = importlib.util.spec_from_file_location("f1_persistence_guard_under_test", GUARD)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
PEAK = ".github/workflows/f1-peak-elite-control-room-one-click-v1.yml"
BRIDGE = ".github/workflows/f1-1b-output-contract-after-control-room-v22.yml"


class WorkbookBridgeGuardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for relative in (PEAK, BRIDGE):
            source = ROOT / relative
            self.assertTrue(source.exists(), relative)
            self.write(relative, source.read_text(encoding="utf-8"))

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def modify(self, func):
        path = self.root / BRIDGE
        self.write(BRIDGE, func(path.read_text(encoding="utf-8")))

    def result(self):
        return mod.static_checks(self.root)

    def bridge_result(self):
        return next(x for x in self.result()["checks"] if x["workflow"] == BRIDGE)

    def test_actual_deployed_bounded_bridge_passes(self):
        result = self.result()
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["issue_count"], 0)

    def test_old_oversized_history_staging_is_rejected(self):
        self.modify(lambda text: text.replace(
            "          if git diff --cached --quiet; then",
            '          git add -f history/session_data_processor\n'
            "          if git diff --cached --quiet; then",
        ))
        result = self.result()
        self.assertEqual(result["status"], "fail")
        self.assertTrue(self.bridge_result().get("unsafe_bridge_staging"))

    def test_loss_of_marker_guard_is_rejected(self):
        self.modify(lambda text: text.replace(
            'find "$root" -type f -newer "$MARKER" -print0',
            'find "$root" -type f -print0',
        ))
        result = self.result()
        self.assertEqual(result["status"], "fail")
        self.assertIn("unbounded_historical_staging", self.bridge_result().get("unsafe_bridge_staging", []))

    def test_protected_force_add_is_rejected(self):
        self.modify(lambda text: text.replace(
            "          if git diff --cached --quiet; then",
            "          git add -f Engine_2026-06-07_STABLE\n"
            "          if git diff --cached --quiet; then",
        ))
        result = self.result()
        self.assertEqual(result["status"], "fail")
        self.assertTrue(self.bridge_result().get("protected_force_add_violation"))

    def test_peak_contract_still_required(self):
        path = self.root / PEAK
        self.write(PEAK, path.read_text(encoding="utf-8").replace(
            "latest/workbook_kpi_refresh_applier/**",
            "removed_workbook_kpi_refresh_path",
        ))
        result = self.result()
        self.assertEqual(result["status"], "fail")
        check = next(x for x in result["checks"] if x["workflow"] == PEAK)
        self.assertIn("latest/workbook_kpi_refresh_applier/**", check["missing_tokens"])


if __name__ == "__main__":
    unittest.main()
