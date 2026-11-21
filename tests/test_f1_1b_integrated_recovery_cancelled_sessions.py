"""Issue #367: provider-confirmed cancelled sessions are not completed evidence.

These offline tests never call OpenF1 and do not authorize a forecast or publication.
"""
import datetime as dt
import unittest
from unittest.mock import patch

import pandas as pd

from scripts.openf1 import publish_openf1_lightweight_source_closure as collector


def session(key, *, cancelled=False, status=None, end="2026-04-10T12:30:00Z"):
    record = {
        "session_key": key,
        "meeting_key": 1282,
        "year": 2026,
        "country_name": "Bahrain",
        "location": "Sakhir",
        "circuit_short_name": "Sakhir",
        "session_name": "Practice 1",
        "session_type": "Practice",
        "date_start": "2026-04-10T11:30:00Z",
        "date_end": end,
        "is_cancelled": cancelled,
    }
    if status is not None:
        record["session_status"] = status
    return record


class CancelledSessionDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.rows = pd.DataFrame([
            session(11253),
            session(11254, cancelled=True),
            session(11255, cancelled=True),
            session(11256, status="Cancelled"),
            session(11257, cancelled=True),
            session(11261, cancelled=True),
            session(11262, cancelled=True),
            session(11263, cancelled=True),
            session(11264, cancelled=True),
            session(11265, cancelled=True),
            session(11269, cancelled=True),
        ])
        self.now = dt.datetime(2026, 11, 21, 22, 30, tzinfo=dt.timezone.utc)

    def discover(self, completed_only):
        log = []
        with patch.object(collector, "openf1_get", return_value=self.rows), patch.object(
            collector, "utc_now", return_value=self.now
        ):
            actual = collector.get_sessions(2026, completed_only, log)
        return actual

    def test_provider_cancelled_rows_are_not_completed(self):
        actual = self.discover(True)
        self.assertEqual(list(actual["session_key"]), [11253])
        self.assertEqual(
            set(actual.attrs["provider_confirmed_cancelled_session_keys"]),
            {str(k) for k in [11254, 11255, 11256, 11257, 11261,
                              11262, 11263, 11264, 11265, 11269]},
        )
        self.assertEqual(actual["_completed_session"].tolist(), [True])

    def test_full_catalog_retains_cancellations_without_claiming_completion(self):
        actual = self.discover(False)
        self.assertEqual(len(actual), 11)
        self.assertEqual(actual["_completed_session"].sum(), 1)
        self.assertFalse(actual.loc[actual["session_key"] == 11254, "_completed_session"].iloc[0])

    def test_documented_cancellations_do_not_trigger_historical_coverage_regression(self):
        current = {"11253", "11416"}
        old = {"11253", "11254", "11255", "11256", "11416"}
        cancelled = {"11254", "11255", "11256"}
        self.assertEqual(
            collector._unexplained_missing_session_keys(old, current, cancelled), []
        )

    def test_unexplained_missing_session_remains_a_blocking_regression(self):
        current = {"11253"}
        old = {"11253", "11254", "11255"}
        self.assertEqual(
            collector._unexplained_missing_session_keys(old, current, {"11254"}),
            ["11255"],
        )

    def test_future_and_unknown_end_do_not_qualify(self):
        with patch.object(collector, "utc_now", return_value=self.now):
            self.assertFalse(collector.is_completed_session(pd.Series(
                session(11417, end="2026-11-22T05:00:00Z"))))
            self.assertFalse(collector.is_completed_session(pd.Series(
                session(11417, end=None))))

    def test_status_cancellation_never_becomes_completed(self):
        with patch.object(collector, "utc_now", return_value=self.now):
            self.assertFalse(collector.is_completed_session(pd.Series(
                session(11254, status="canceled"))))


if __name__ == "__main__":
    unittest.main()
