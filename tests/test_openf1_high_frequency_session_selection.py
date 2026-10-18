import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/openf1/openf1_high_frequency_auto_ingest.py"
SPEC = importlib.util.spec_from_file_location("openf1_high_frequency_auto_ingest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeClient:
    def __init__(self, rows):
        self.rows = rows

    def get(self, endpoint, params):
        self.assert_request = (endpoint, params)
        return self.rows, {"status_code": 200, "note": "offline_fixture"}


def session(session_key, meeting_key, country="Australia"):
    return {
        "session_key": session_key,
        "meeting_key": meeting_key,
        "country_name": country,
        "meeting_name": "Grand Prix",
        "location": "Circuit",
        "session_type": "Practice",
        "session_name": "Practice 1",
        "date_start": "2026-01-01T09:00:00+00:00",
        "date_end": "2026-01-01T10:00:00+00:00",
    }


class SessionSelectionTests(unittest.TestCase):
    def test_identity_exclusions_preserve_october_meeting(self):
        rows = []
        championship = [1279, 1280, 1281, 1284, 1285, 1286, 1287, 1288, 1289,
                        1290, 1291, 1292, 1293, 1294, 1295, 1308, 1296]
        for meeting_index, meeting_key in enumerate(championship):
            for offset in range(5):
                rows.append(session(20000 + meeting_index * 5 + offset, meeting_key,
                                    country="Bahrain" if meeting_key == 1308 else "Australia"))
        for meeting_key in [1282, 1283, 1304, 1305]:
            rows.append(session(30000 + meeting_key, meeting_key, country="Bahrain"))

        selected = MODULE.discover_sessions(FakeClient(rows), 2026, "all")

        self.assertEqual(len(selected), 85)
        self.assertEqual(len(selected.loc[selected.meeting_key == 1308]), 5)
        self.assertFalse(set(selected.meeting_key) & {1282, 1283, 1304, 1305})

    def test_exact_five_session_allowlist(self):
        keys = frozenset({11727, 11728, 11729, 11730, 11731})
        rows = [session(key, 1308, country="Bahrain") for key in sorted(keys)]
        rows.append(session(99999, 1296))
        selected = MODULE.discover_sessions(FakeClient(rows), 2026, "all", session_keys=keys)
        self.assertEqual(set(selected.session_key), keys)

    def test_allowlist_fails_closed_when_key_missing(self):
        rows = [session(11727, 1308, country="Bahrain")]
        with self.assertRaisesRegex(RuntimeError, "11728"):
            MODULE.discover_sessions(
                FakeClient(rows), 2026, "all", session_keys=frozenset({11727, 11728})
            )

    def test_parser_rejects_noninteger(self):
        with self.assertRaisesRegex(Exception, "comma-separated integers"):
            MODULE.parse_session_keys("11727,nope")


class FeatureGenerationTests(unittest.TestCase):
    def write_chunks(self, root, car_rows, location_rows):
        for endpoint, rows in (("car_data", car_rows), ("location", location_rows)):
            folder = root / "raw" / endpoint / "session_key=11353" / "driver_number=1"
            folder.mkdir(parents=True)
            pd.DataFrame(rows).to_parquet(folder / "chunk_0000.parquet", index=False)

    def test_zero_rpm_and_gear_zero_ratios_remain_missing_without_false_flags(self):
        dates = pd.date_range("2026-08-23T13:00:00Z", periods=4, freq="1s")
        car_rows = [
            {
                "session_key": 11353,
                "driver_number": 1,
                "date": date,
                "rpm": 0,
                "speed": speed,
                "n_gear": 0,
                "throttle": 100,
                "brake": 0,
            }
            for date, speed in zip(dates, (0, 10, 20, 30))
        ]
        location_rows = [
            {"date": date, "x": i, "y": i, "z": 0}
            for i, date in enumerate(dates)
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_chunks(root, car_rows, location_rows)
            features = MODULE.build_driver_features(root, 11353, 1)

        self.assertEqual(len(features), 1)
        self.assertTrue(np.isnan(features.loc[0, "efficiency_ratio_norm_mean"]))
        self.assertTrue(np.isnan(features.loc[0, "efficiency_ratio_norm_min"]))
        self.assertEqual(features.loc[0, "efficiency_loss_count"], 0)
        self.assertEqual(features.loc[0, "samples"], 4)

    def test_valid_nonzero_efficiency_calculation_is_preserved(self):
        dates = pd.date_range("2026-08-23T13:00:00Z", periods=4, freq="1s")
        rpms = (1000, 2000, 3000, 4000)
        car_rows = [
            {
                "session_key": 11353,
                "driver_number": 1,
                "date": date,
                "rpm": rpm,
                "speed": rpm / 100,
                "n_gear": 1,
                "throttle": 90,
                "brake": 0,
            }
            for date, rpm in zip(dates, rpms)
        ]
        location_rows = [
            {"date": date, "x": i, "y": i, "z": 0}
            for i, date in enumerate(dates)
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_chunks(root, car_rows, location_rows)
            features = MODULE.build_driver_features(root, 11353, 1)

        self.assertEqual(len(features), 1)
        self.assertAlmostEqual(features.loc[0, "efficiency_ratio_norm_mean"], 1.0)
        self.assertAlmostEqual(features.loc[0, "efficiency_ratio_norm_min"], 1.0)
        self.assertEqual(features.loc[0, "efficiency_loss_count"], 0)


if __name__ == "__main__":
    unittest.main()
