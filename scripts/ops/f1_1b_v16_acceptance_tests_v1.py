#!/usr/bin/env python3
"""Acceptance tests for F1 1B Output Contract v16."""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True)+"\n", encoding="utf-8")


def build_case(root: Path, name: str, source_status="clean", manual=False, laps=586, starting_grid=0, intervals=0, workbook_status="clean"):
    sp = root/"latest/session_data_processor/2026_1287_spain_barcelona_catalunya/practice_2_11301/source_readiness_manifest.json"
    wp = root/"latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json"
    counts = {
        "openf1_drivers": 22,
        "openf1_intervals": intervals,
        "openf1_laps": laps,
        "openf1_pit": 118,
        "openf1_position": 424,
        "openf1_race_control": 52,
        "openf1_session_result": 22,
        "openf1_sessions": 1,
        "openf1_starting_grid": starting_grid,
        "openf1_stints": 118,
        "openf1_weather": 85,
    }
    statuses = {k: "clean" for k in counts}
    if starting_grid == 0: statuses["openf1_starting_grid"] = "expected_empty"
    if intervals == 0: statuses["openf1_intervals"] = "optional_empty"
    if laps == 0: statuses["openf1_laps"] = "late"
    write_json(sp, {
        "schema_version": "session_processor_result_v1",
        "event_id": "2026_1287_spain_barcelona_catalunya",
        "race_name": "Spain - Barcelona - Catalunya",
        "session_name": "Practice 2",
        "session_type": "Practice",
        "session_key": 11301,
        "overall_status": source_status,
        "source_status": source_status,
        "source_needs_manual_review": manual,
        "readiness_quality": "usable_with_optional_context_gaps" if not manual and source_status == "clean" else "blocked",
        "source_counts": counts,
        "source_statuses": statuses,
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_modified": False,
    })
    write_json(wp, {
        "status": "refresh_applied" if workbook_status == "clean" else workbook_status,
        "source_status": workbook_status,
        "workbook_source_status": workbook_status,
        "sandbox_workbook": "latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_SAMPLE.xlsx",
        "canonical_workbook_overwrite": False,
        "stable_engine_modified": False,
        "promotion_allowed": False,
    })


def run_script(script: Path, repo: Path):
    cp = subprocess.run([sys.executable, str(script), "--repo-root", str(repo), "--mode", "run_now"], text=True, capture_output=True)
    if cp.returncode != 0:
        raise AssertionError(f"script failed rc={cp.returncode}\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}")
    return json.loads(cp.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    args = ap.parse_args()
    repo_root = Path(args.repo_root).resolve()
    script = repo_root/"scripts/session_data_processor/f1_1b_output_contract_v16.py"
    if not script.exists():
        raise SystemExit(f"missing script: {script}")
    results = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        # Case 1: clean practice with optional gaps should pass and update last-good.
        case1 = base/"case1"
        build_case(case1, "clean_optional")
        r1 = run_script(script, case1)
        snap = json.loads((case1/"latest/forecast_bundle_ledger/latest_bundle_snapshot.json").read_text(encoding="utf-8"))
        assert r1["status"] == "pass", r1
        assert r1["last_good_state_updated"] is True, r1
        assert snap["status"] == "usable_with_optional_context_gaps", snap
        assert (case1/"latest/last_good_state.json").exists()
        assert json.loads((case1/"latest/readiness_handoff/race_predictions_readiness.json").read_text())["ready_for_use"] is True
        results.append({"case":"clean_practice_optional_gaps", "status":"pass"})
        # Case 2: no material change on second run with same inputs.
        r1b = run_script(script, case1)
        assert r1b["material_change_detected"] is False, r1b
        results.append({"case":"no_change_second_run", "status":"pass"})
        # Case 3: missing critical laps should not update last-good.
        case2 = base/"case2"
        build_case(case2, "needs_manual_review", manual=True, laps=0)
        r2 = run_script(script, case2)
        assert r2["status"] == "blocked", r2
        assert r2["last_good_state_updated"] is False, r2
        assert not (case2/"latest/last_good_state.json").exists()
        results.append({"case":"missing_critical_source_blocked", "status":"pass"})
        # Case 4: workbook source not clean should block last-good.
        case3 = base/"case3"
        build_case(case3, "clean", workbook_status="needs_manual_review")
        r3 = run_script(script, case3)
        assert r3["last_good_state_updated"] is False, r3
        results.append({"case":"workbook_not_clean_blocks_last_good", "status":"pass"})
    out = {"schema_version":"f1_1b_v16_acceptance_tests", "status":"pass", "results":results}
    latest = repo_root/"latest/1b_validation"
    latest.mkdir(parents=True, exist_ok=True)
    (latest/"v16_acceptance_tests.json").write_text(json.dumps(out, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
