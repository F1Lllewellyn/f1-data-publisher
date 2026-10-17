import importlib.util
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
