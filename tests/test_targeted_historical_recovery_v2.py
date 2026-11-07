from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/maintenance/targeted_historical_recovery_v2.py"
SPEC = importlib.util.spec_from_file_location("targeted_historical_recovery_v2", MODULE_PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class TargetedHistoricalRecoveryV2Tests(unittest.TestCase):
    def test_exact_openf1_allowlist(self):
        self.assertEqual(
            recovery.approved_source_request(
                "https://api.openf1.org/v1/laps?session_key=11227", {11227}
            ),
            ("laps", 11227),
        )
        rejected = (
            "http://api.openf1.org/v1/laps?session_key=11227",
            "https://evil.example/v1/laps?session_key=11227",
            "https://api.openf1.org/v2/laps?session_key=11227",
            "https://api.openf1.org/v1/laps?session_key=99999",
            "https://api.openf1.org/v1/laps?session_key=11227&extra=1",
            "https://api.openf1.org/v1/laps?session_key=11227#fragment",
        )
        for url in rejected:
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                recovery.approved_source_request(url, {11227})

    def test_integral_decimal_typing_is_exact(self):
        self.assertEqual(recovery.parse_cell("position", "14.0"), 14)
        self.assertEqual(recovery.parse_cell("driver_number", "0"), 0)
        for value in ("14.5", "NaN", "Infinity", "not-a-number"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                recovery.parse_cell("position", value)

    def test_required_fetches_match_accepted_session_policy(self):
        practice = recovery.required_endpoints_for_session(
            {"session_name": "Practice 2", "session_type": "Practice"}
        )
        qualifying = recovery.required_endpoints_for_session(
            {"session_name": "Sprint Qualifying", "session_type": "Qualifying"}
        )
        race = recovery.required_endpoints_for_session(
            {"session_name": "Race", "session_type": "Race"}
        )
        self.assertEqual(practice, {"drivers", "laps", "position", "weather"})
        self.assertEqual(
            qualifying, {"drivers", "laps", "position", "session_result", "weather"}
        )
        self.assertEqual(
            race,
            {"drivers", "laps", "position", "race_control", "session_result", "starting_grid", "weather"},
        )

    def test_recovered_rows_are_reused_without_a_provider_request(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            raw = out / "latest/session_data_processor/event/practice_1_11227/raw/openf1_laps.json"
            raw.parent.mkdir(parents=True)
            rows = [{"session_key": 11227, "driver_number": 1, "lap_number": 1}]
            raw.write_text(json.dumps(rows), encoding="utf-8")
            cache = {name: {} for name in recovery.SOURCE_LANES}
            recovery.merge_recovery_cache(out, {11227}, cache)
            self.assertEqual(cache["laps"][11227], rows)


if __name__ == "__main__":
    unittest.main()
