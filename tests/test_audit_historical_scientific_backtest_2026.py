import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/maintenance/audit_historical_scientific_backtest_2026.py"
SPEC = importlib.util.spec_from_file_location("historical_backtest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HistoricalBacktestGateTests(unittest.TestCase):
    def test_unhashed_season_manifest_fails_event_scope(self):
        rows = [{"source_name": "drivers", "path": "latest/openf1/data/drivers.csv", "row_count": "22"}]
        self.assertEqual(
            MODULE.event_scoped_input_manifest(rows, "2026_1290_belgium"),
            (False, "producer_inputs_not_hash_bound"),
        )

    def test_hash_bound_cross_event_manifest_fails_scope(self):
        rows = [{
            "source_name": "drivers",
            "source_id": "run-1",
            "source_sha256": "a" * 64,
            "relative_path": "2026_1291_hungary/drivers.csv",
        }]
        self.assertEqual(
            MODULE.event_scoped_input_manifest(rows, "2026_1290_belgium"),
            (False, "producer_inputs_not_event_scoped"),
        )

    def test_hash_bound_event_manifest_passes_scope(self):
        rows = [{
            "source_name": "drivers",
            "source_id": "run-1",
            "source_sha256": "a" * 64,
            "relative_path": "2026_1290_belgium/drivers.csv",
        }]
        self.assertEqual(
            MODULE.event_scoped_input_manifest(rows, "2026_1290_belgium"),
            (True, "event_scoped_hash_bound_inputs"),
        )

    def test_rank_metrics_are_exact_for_perfect_order(self):
        actual = {driver: driver for driver in range(1, 23)}
        metrics = MODULE.rank_metrics(actual.copy(), actual)
        self.assertEqual(metrics["mae"], 0)
        self.assertEqual(metrics["rmse"], 0)
        self.assertEqual(metrics["spearman_rho"], 1)
        self.assertEqual(metrics["podium_overlap"], 1)
        self.assertEqual(metrics["top10_overlap"], 1)
        self.assertTrue(metrics["winner_hit"])


if __name__ == "__main__":
    unittest.main()
