import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/maintenance/close_historical_scientific_validation_2026.py"
SPEC = importlib.util.spec_from_file_location("historical_closure", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HistoricalScientificClosureTests(unittest.TestCase):
    def test_official_grid_accepts_ordinal_grid_and_unranked_pit_lane(self):
        participants = [
            {"official_position": position, "driver_number": position, "start_status": "GRID"}
            for position in range(1, 22)
        ]
        participants.append(
            {"official_position": None, "driver_number": 99, "start_status": "PIT_LANE"}
        )
        MODULE.validate_official_participants(participants, "synthetic")

    def test_official_grid_rejects_fabricated_pit_lane_position(self):
        participants = [
            {"official_position": position, "driver_number": position, "start_status": "GRID"}
            for position in range(1, 22)
        ]
        participants.append(
            {"official_position": 22, "driver_number": 99, "start_status": "PIT_LANE"}
        )
        with self.assertRaisesRegex(RuntimeError, "FIA_PIT_LANE_POSITION_HOLD"):
            MODULE.validate_official_participants(participants, "synthetic")

    def test_exact_duplicate_is_removed_without_reordering(self):
        first = {
            "meeting_key": 1284,
            "session_key": 11270,
            "date": "2026-05-01T16:00:00+00:00",
            "driver_number": 1,
            "position": 2,
        }
        second = first | {"date": "2026-05-01T16:01:00+00:00", "position": 1}
        unique, duplicate_count = MODULE.exact_deduplicate(
            [first, first.copy(), second], 1284, 11270, "position"
        )
        self.assertEqual(unique, [first, second])
        self.assertEqual(duplicate_count, 1)

    def test_conflicting_observation_fails_closed(self):
        first = {
            "meeting_key": 1284,
            "session_key": 11270,
            "date": "2026-05-01T16:00:00+00:00",
            "driver_number": 1,
            "position": 2,
        }
        conflict = first | {"position": 1}
        with self.assertRaisesRegex(RuntimeError, "MIAMI_DUPLICATE_FORENSIC_HOLD"):
            MODULE.exact_deduplicate([first, conflict], 1284, 11270, "position")

    def test_wrong_source_identity_fails_closed(self):
        row = {
            "meeting_key": 1284,
            "session_key": 99999,
            "date": "2026-05-01T16:00:00+00:00",
            "driver_number": 1,
        }
        with self.assertRaisesRegex(RuntimeError, "MIAMI_ROW_IDENTITY_HOLD"):
            MODULE.exact_deduplicate([row], 1284, 11270, "weather")


if __name__ == "__main__":
    unittest.main()
