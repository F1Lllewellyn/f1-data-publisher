#!/usr/bin/env python3
"""Offline acceptance checks for the sandbox processor's grid provenance."""
from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "session_data_processor"))
import session_data_processor_loop_v1 as processor


def session(name: str, key: int, meeting: int = 1294) -> dict:
    return {"session_name": name, "session_key": key, "meeting_key": meeting,
            "date_start": "2026-09-12T14:00:00Z" if "Qualifying" in name else "2026-09-13T13:00:00Z",
            "date_end": "2026-09-12T15:00:00Z" if "Qualifying" in name else "2026-09-13T15:00:00Z"}


def test_resolution() -> None:
    qualifying, sprint_qualifying = session("Qualifying", 11365), session("Sprint Qualifying", 11364)
    race, sprint = session("Race", 11369), session("Sprint", 11368)
    candidates = [qualifying, sprint_qualifying, race, sprint]
    assert processor.grid_source_for_target(candidates, race)[0] == qualifying
    assert processor.grid_source_for_target(candidates, sprint)[0] == sprint_qualifying
    assert processor.grid_source_for_target([sprint_qualifying, race], race)[0] is None
    assert processor.grid_source_for_target([session("Qualifying", 777, 1295), race], race)[0] is None
    assert processor.grid_source_for_target(candidates + [session("Qualifying", 888)], race)[1] == "qualifying_source_ambiguous"
    bad = dict(qualifying, date_end=None)
    assert processor.grid_source_for_target([bad, race], race)[1] == "qualifying_identity_or_schedule_invalid"
    late = dict(qualifying, date_end="2026-09-14T15:00:00Z")
    assert processor.grid_source_for_target([late, race], race)[0] is None
    grid = [{"session_key": 11365, "meeting_key": 1294, "driver_number": 1, "position": 2},
            {"session_key": 11365, "meeting_key": 1294, "driver_number": 2, "position": 1}]
    assert processor.grid_integrity_anomalies(grid, [{"driver_number": 1}, {"driver_number": 2}]) == []
    assert processor.analyze_rows("starting_grid", grid, qualifying, {"ok": True})["status"] == "clean"
    assert processor.analyze_rows("starting_grid", grid, race, {"ok": True})["status"] == "conflicting"
    assert "invalid_or_duplicate_grid_position" in processor.grid_integrity_anomalies(
        [dict(grid[0], position=1), grid[1]], [{"driver_number": 1}, {"driver_number": 2}])


def test_processor_fetch_and_revision() -> None:
    qualifying, race = session("Qualifying", 11365), session("Race", 11369)
    grid = [{"session_key": 11365, "meeting_key": 1294, "driver_number": n, "position": p}
            for n, p in [(1, 2), (2, 1)]]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        policy = root / "policy.json"
        policy.write_text(json.dumps({"recent_session_lookback_hours": 1000,
                                      "openf1_endpoints": ["sessions", "drivers", "starting_grid"]}))
        baseline = root / "latest/session_data_processor/test/qualifying_11365/validation/openf1_starting_grid_validation.json"
        baseline.parent.mkdir(parents=True)
        baseline_raw = root / "baseline.json"
        processor.write_json(baseline_raw, grid)
        baseline.write_text(json.dumps({"json_sha256": processor.sha256_file(baseline_raw)}))
        calls = []
        direct = {"rows": [], "meta": {"ok": False, "status_code": 404}}

        def fake_http(url: str, **kwargs):
            calls.append(url)
            if "/sessions?" in url:
                return [qualifying, race], {"ok": True}
            if "/drivers?" in url:
                return [{"driver_number": n, "session_key": 11369, "meeting_key": 1294} for n in [1, 2]], {"ok": True}
            if "starting_grid?session_key=11369" in url:
                return direct["rows"], direct["meta"]
            if "starting_grid?session_key=11365" in url:
                return grid, {"ok": True, "status_code": 200}
            raise AssertionError(url)

        argv = ["processor", "--event-id", "test", "--write-public-latest", "false"]
        with patch.object(processor, "ROOT", root), patch.object(processor, "RUNTIME", root / "_runtime"), \
             patch.object(processor, "POLICY_PATH", policy), patch.object(processor, "http_json", fake_http), \
             patch.object(sys, "argv", argv):
            assert processor.main() == 0
            out = root / "latest/session_data_processor/test/race_11369"
            report = json.loads((out / "validation/openf1_starting_grid_validation.json").read_text())
            assert report["status"] == "needs_manual_review", report
            assert report["provenance"]["openf1_row_status"] == "clean"
            assert "fia_final_grid_unverified" in report["anomalies"]
            assert report["provenance"]["source_session_key"] == 11365
            assert report["provenance"]["target_session_key"] == 11369
            assert report["provenance"]["direct_target_fetch"]["status_code"] == 404
            assert report["provenance"]["changed_since_qualifying_snapshot"] is False
            assert report["provenance"]["official_final_grid_verified"] is False
            assert report["provenance"]["forecast_as_of_eligible"] is False
            assert json.loads((out / "raw/openf1_starting_grid.json").read_text()) == grid
            assert any("starting_grid?session_key=11365" in url for url in calls)
            grid[0] = dict(grid[0], position=3)
            assert processor.main() == 0
            updated = json.loads((out / "validation/openf1_starting_grid_validation.json").read_text())
            assert updated["provenance"]["changed_since_qualifying_snapshot"] is True
            assert updated["provenance"]["changed_since_prior_target_snapshot"] is True
            assert updated["status"] == "needs_manual_review"
            assert "grid_revision_time_unestablished_after_start" in updated["anomalies"]
            direct["rows"] = [dict(row, session_key=11369, position=p) for row, p in zip(grid, [1, 2])]
            direct["meta"] = {"ok": True, "status_code": 200}
            before = len([url for url in calls if "starting_grid?session_key=11365" in url])
            assert processor.main() == 0
            published = json.loads((out / "validation/openf1_starting_grid_validation.json").read_text())
            assert published["status"] == "needs_manual_review"
            assert "fia_final_grid_unverified" in published["anomalies"]
            assert published["provenance"]["resolution"] == "direct_target_session"
            assert published["provenance"]["source_session_key"] == 11369
            assert len([url for url in calls if "starting_grid?session_key=11365" in url]) == before
            direct["rows"] = []
            direct["meta"] = {"ok": False, "status_code": 503, "error": "HTTPError 503"}
            assert processor.main() == 0
            failure = json.loads((out / "validation/openf1_starting_grid_validation.json").read_text())
            assert failure["status"] == "needs_manual_review"
            assert len([url for url in calls if "starting_grid?session_key=11365" in url]) == before


if __name__ == "__main__":
    test_resolution()
    test_processor_fetch_and_revision()
    print("grid provenance acceptance: pass")
