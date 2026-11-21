"""No-provider regressions for historical source observation date gate."""
from __future__ import annotations
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts/ops"))
spec=importlib.util.spec_from_file_location("historical",ROOT/"scripts/ops/f1_las_vegas_2026_post_session_custody_v1.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
UTC=dt.timezone.utc


class HistoricalCustodyTests(unittest.TestCase):
    def test_only_post_live_exact_2026_windows(self):
        cases=[
            ((2026,11,21,0,45),None),((2026,11,21,1,59),None),
            ((2026,11,21,2,0),(11415,"FP3")),
            ((2026,11,21,2,45),(11415,"FP3")),
            ((2026,11,21,4,0),None),
            ((2026,11,21,5,59),None),
            ((2026,11,21,6,15),(11416,"QUALIFYING")),
            ((2026,11,21,7,45),(11416,"QUALIFYING")),
            ((2026,11,21,8,0),None),
            ((2026,11,22,4,15),None),
            ((2026,11,22,7,15),(11420,"RACE")),
            ((2026,11,22,8,45),(11420,"RACE")),
            ((2026,11,22,9,0),None),
            ((2027,11,21,2,45),None),
        ]
        for parts,expected in cases:
            with self.subTest(parts=parts):
                self.assertEqual(mod.select_window(dt.datetime(*parts,tzinfo=UTC)),expected)

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            mod.select_window(dt.datetime(2026,11,21,2,15))

    def test_outside_window_no_provider_or_writes(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(mod.dt,"datetime",wraps=dt.datetime) as datetime_mock:
                datetime_mock.now.return_value=dt.datetime(2026,11,20,19,55,tzinfo=UTC)
                with patch.object(mod,"capture_session") as provider:
                    result=mod.main()
                    self.assertEqual(result,0)
                    provider.assert_not_called()

    def test_in_window_retains_original_context_only(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td)
            with patch("os.getcwd",return_value=str(temp)), patch("os.chdir") as changer:
                pass
            import os
            before=Path.cwd()
            try:
                os.chdir(temp)
                with patch.object(mod.dt,"datetime",wraps=dt.datetime) as datetime_mock:
                    datetime_mock.now.return_value=dt.datetime(2026,11,21,2,15,tzinfo=UTC)
                    def fake(meeting,session,out):
                        self.assertEqual((meeting,session),(1300,11415))
                        Path(out).mkdir(parents=True,exist_ok=True)
                        (Path(out)/"original_source_canary_manifest.json").write_text('{"synthetic":true}')
                        return {"result":"VERIFIED_LIVE_PROVIDER_SNAPSHOT_CONTEXT_ONLY","verified_row_counts":{"sessions":1,"drivers":22,"laps":340}}
                    with patch.object(mod,"capture_session",side_effect=fake):
                        result=mod.main()
                        self.assertEqual(result,0)
                    decisions=list(temp.glob("_runtime/las_vegas_2026_post_session_custody/fp3_11415/post_session_custody_decision.json"))
                    self.assertEqual(len(decisions),1)
                    obj=json.loads(decisions[0].read_text())
                    for k in ("forecast_eligible","stable_engine_executed","historical_source_complete","prediction_locked","source_publication"):
                        self.assertIs(obj[k],False)
                    self.assertFalse((temp/"latest").exists())
                    self.assertFalse((temp/"history").exists())
            finally:
                os.chdir(before)

    def test_failed_historical_provider_preserves_hold_without_forecast(self):
        import os
        with tempfile.TemporaryDirectory() as td:
            before=Path.cwd()
            try:
                os.chdir(td)
                with patch.object(mod.dt,"datetime",wraps=dt.datetime) as datetime_mock:
                    datetime_mock.now.return_value=dt.datetime(2026,11,21,6,45,tzinfo=UTC)
                    def fake(meeting,session,out):
                        self.assertEqual(session,11416)
                        Path(out).mkdir(parents=True,exist_ok=True)
                        return {"result":"HOLD_LIVE_SOURCE_SNAPSHOT_INCOMPLETE","verified_row_counts":{}}
                    with patch.object(mod,"capture_session",side_effect=fake):
                        self.assertEqual(mod.main(),2)
                data=json.loads(Path("_runtime/las_vegas_2026_post_session_custody/qualifying_11416/post_session_custody_decision.json").read_text())
                self.assertFalse(data["forecast_eligible"])
                self.assertFalse(data["historical_source_complete"])
            finally:
                os.chdir(before)


if __name__=="__main__":
    unittest.main()
