#!/usr/bin/env python3
"""Acceptance tests for F1 1B Output Contract v20 wiring fix."""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True)+"\n", encoding="utf-8")


def build_case(root: Path, source_status="clean", manual=False, laps=586, starting_grid=0, intervals=0, workbook_status="clean"):
    sp = root/"latest/session_data_processor/2026_1287_spain_barcelona_catalunya/practice_2_11301/source_readiness_manifest.json"
    wp = root/"latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json"
    counts = {"openf1_drivers":22,"openf1_intervals":intervals,"openf1_laps":laps,"openf1_pit":118,"openf1_position":424,"openf1_race_control":52,"openf1_session_result":22,"openf1_sessions":1,"openf1_starting_grid":starting_grid,"openf1_stints":118,"openf1_weather":85}
    statuses = {k:"clean" for k in counts}
    if starting_grid == 0: statuses["openf1_starting_grid"] = "expected_empty"
    if intervals == 0: statuses["openf1_intervals"] = "optional_empty"
    if laps == 0: statuses["openf1_laps"] = "late"
    write_json(sp, {"schema_version":"session_processor_result_v1","event_id":"2026_1287_spain_barcelona_catalunya","race_name":"Spain - Barcelona - Catalunya","session_name":"Practice 2","session_type":"Practice","session_key":11301,"run_id":"20260613T023457Z","overall_status":source_status,"source_status":source_status,"source_needs_manual_review":manual,"readiness_quality":"usable_with_optional_context_gaps" if not manual and source_status == "clean" else "blocked","source_counts":counts,"source_statuses":statuses,"promotion_allowed":False,"stable_engine_modified":False,"canonical_workbook_modified":False})
    write_json(wp, {"status":"refresh_applied" if workbook_status == "clean" else workbook_status,"source_status":workbook_status,"workbook_source_status":workbook_status,"sandbox_workbook":"latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_SAMPLE.xlsx","canonical_workbook_overwrite":False,"stable_engine_modified":False,"promotion_allowed":False})


def build_dashboard_override_case(root: Path, laps=586):
    build_case(root, source_status="needs_manual_review", manual=True, laps=laps, workbook_status="needs_manual_review")
    dash = root/"latest/readiness_dashboards/combined_readiness_dashboard.json"
    write_json(dash, {"generated_at_utc":"2026-06-13T02:35:10Z","status":"dashboard_refreshed","source_status":"clean","source_backed":True,"event_name":"Spain - Barcelona - Catalunya","session_name":{"gate":"post_fp2","meeting_key":1287,"session_key":11301,"session_name":"Practice 2","session_type":"Practice"},"workbook_artifact":"latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_SAMPLE.xlsx","workbook_manifest":"latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json","session_manifest":"latest/session_data_processor/2026_1287_spain_barcelona_catalunya/practice_2_11301/source_readiness_manifest.json","stable_engine_modified":False,"canonical_workbook_overwrite":False,"promotion_allowed":False})


def build_race_grid_case(root: Path):
    event = "2026_1294_spain_madrid_madring"
    race = root/f"latest/session_data_processor/{event}/race_11369/source_readiness_manifest.json"
    quali = root/f"latest/session_data_processor/{event}/qualifying_11365/source_readiness_manifest.json"
    write_json(race, {"event_id":event,"race_name":"Spain - Madrid - Madring","session":{"session_key":11369,"session_name":"Race","session_type":"Race","gate":"race_result"},"run_id":"20260915T012415Z","overall_status":"needs_manual_review","source_needs_manual_review":True,"readiness_quality":"blocked_manual_review_required_source","readiness_aggregation":{"overall_status":"needs_manual_review","needs_manual_review":True,"blocking_issues":[{"endpoint":"starting_grid","reason":"required_source_needs_manual_review","rows":0}],"critical_endpoints":["drivers","laps","position","race_control","session_result","starting_grid","weather"]},"sources":{"openf1_starting_grid":{"rows":0,"status":"needs_manual_review"}}})
    write_json(quali, {"event_id":event,"race_name":"Spain - Madrid - Madring","session":{"session_key":11365,"session_name":"Qualifying","session_type":"Qualifying","gate":"post_qualifying"},"run_id":"20260913T115906Z","overall_status":"clean","source_needs_manual_review":False,"readiness_quality":"usable_clean"})
    write_json(root/"latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json", {"source_status":"needs_manual_review","source_processor_root":str(race.parent.relative_to(root)),"sandbox_workbook":"latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_SAMPLE.xlsx"})
    dashboard = {"source_status":"needs_manual_review","source_backed":True,"event_name":"Spain - Madrid - Madring","session_name":{"session_key":11369,"session_name":"Race","session_type":"Race","gate":"race_result"},"session_manifest":str(race.relative_to(root)),"workbook_artifact":"latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_SAMPLE.xlsx"}
    write_json(root/"latest/readiness_dashboards/combined_readiness_dashboard.json", dashboard)
    return race, quali, dashboard



def build_stale_status_usable_quality_case(root: Path):
    sp = root/"latest/session_data_processor/2026_1287_spain_barcelona_catalunya/practice_2_11301/source_readiness_manifest.json"
    wp = root/"latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json"
    counts = {"openf1_drivers":22,"openf1_intervals":0,"openf1_laps":586,"openf1_pit":118,"openf1_position":424,"openf1_race_control":52,"openf1_session_result":22,"openf1_sessions":1,"openf1_starting_grid":0,"openf1_stints":118,"openf1_weather":85}
    statuses = {k:"clean" for k in counts}
    statuses["openf1_starting_grid"] = "expected_empty"
    statuses["openf1_intervals"] = "optional_empty"
    write_json(sp, {"schema_version":"session_processor_result_v1","event_id":"2026_1287_spain_barcelona_catalunya","race_name":"Spain - Barcelona - Catalunya","session_name":"Practice 2","session_type":"Practice","session_key":11301,"run_id":"20260613T023457Z","overall_status":"needs_manual_review","source_status":"needs_manual_review","source_needs_manual_review":True,"readiness_quality":"usable_with_optional_context_gaps","source_backed":True,"source_counts":counts,"source_statuses":statuses,"promotion_allowed":False,"stable_engine_modified":False,"canonical_workbook_modified":False})
    write_json(wp, {"status":"needs_manual_review","source_status":"needs_manual_review","workbook_source_status":"needs_manual_review","sandbox_workbook":"latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_SAMPLE.xlsx","canonical_workbook_overwrite":False,"stable_engine_modified":False,"promotion_allowed":False})

def run_script(script: Path, repo: Path):
    cp = subprocess.run([sys.executable, str(script), "--repo-root", str(repo), "--mode", "run_now"], text=True, capture_output=True)
    if cp.returncode != 0:
        raise AssertionError(f"script failed rc={cp.returncode}\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}")
    return json.loads(cp.stdout)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--repo-root", default="."); args = ap.parse_args()
    repo_root = Path(args.repo_root).resolve()
    script = repo_root/"scripts/session_data_processor/f1_1b_output_contract_v16.py"
    if not script.exists(): raise SystemExit(f"missing script: {script}")
    results=[]
    with tempfile.TemporaryDirectory() as td:
        base=Path(td)
        case1=base/"case1"; build_case(case1)
        r1=run_script(script, case1)
        snap=json.loads((case1/"latest/forecast_bundle_ledger/latest_bundle_snapshot.json").read_text())
        assert r1["status"] == "pass", r1
        assert r1["last_good_state_updated"] is True, r1
        assert snap["status"] == "usable_with_optional_context_gaps", snap
        assert (case1/"latest/last_good_state.json").exists()
        results.append({"case":"clean_practice_optional_gaps", "status":"pass"})
        r1b=run_script(script, case1)
        assert r1b["material_change_detected"] is False, r1b
        results.append({"case":"no_change_second_run", "status":"pass"})
        case2=base/"case2"; build_case(case2, source_status="needs_manual_review", manual=True, laps=0)
        r2=run_script(script, case2)
        assert r2["status"] == "blocked", r2
        assert r2["last_good_state_updated"] is False, r2
        results.append({"case":"missing_critical_source_blocked", "status":"pass"})
        case3=base/"case3"; build_case(case3, source_status="clean", workbook_status="needs_manual_review")
        r3=run_script(script, case3)
        assert r3["last_good_state_updated"] is False, r3
        results.append({"case":"workbook_not_clean_blocks_last_good", "status":"pass"})
        case4=base/"case4"; build_dashboard_override_case(case4)
        r4=run_script(script, case4)
        assert r4["status"] == "pass", r4
        assert r4["source_status"] == "clean", r4
        assert r4["workbook_source_status"] == "clean", r4
        assert r4["last_good_state_updated"] is True, r4
        results.append({"case":"dashboard_clean_state_overrides_stale_blocked_manifest", "status":"pass"})
        case5=base/"case5"; build_stale_status_usable_quality_case(case5)
        r5=run_script(script, case5)
        assert r5["status"] == "pass", r5
        assert r5["source_status"] == "clean", r5
        assert r5["workbook_source_status"] == "clean", r5
        assert r5["last_good_state_updated"] is True, r5
        results.append({"case":"usable_quality_normalizes_stale_manual_review_status", "status":"pass"})
        case6=base/"case6"; build_dashboard_override_case(case6, laps=0)
        r6=run_script(script, case6)
        assert r6["status"] == "blocked" and r6["last_good_state_updated"] is False, r6
        results.append({"case":"clean_dashboard_cannot_override_missing_laps", "status":"pass"})
        case7=base/"case7"; race, _, dashboard=build_race_grid_case(case7)
        r7=run_script(script, case7)
        assert r7["status"] == "blocked" and r7["notification_recommended"] is False, r7
        snap7=json.loads((case7/"latest/forecast_bundle_ledger/latest_bundle_snapshot.json").read_text())
        assert snap7["source"]["manifest_path"] == str(race.relative_to(case7)), snap7
        assert snap7["event"]["session_key"] == 11369 and not snap7["handoffs"]["race_reports"]["ready_for_full_report"], snap7
        assert not (case7/"latest/last_good_state.json").exists()
        results.append({"case":"blocked_race_grid_cannot_borrow_clean_qualifying", "status":"pass"})
        case8=base/"case8"; _, quali, dashboard=build_race_grid_case(case8)
        dashboard["source_status"]="clean"; dashboard["session_manifest"]=str(quali.relative_to(case8))
        write_json(case8/"latest/readiness_dashboards/combined_readiness_dashboard.json", dashboard)
        r8=run_script(script, case8)
        assert r8["status"] == "blocked" and r8["last_good_state_updated"] is False, r8
        results.append({"case":"explicit_session_reference_mismatch_blocks", "status":"pass"})
        case9=base/"case9"; _, _, dashboard=build_race_grid_case(case9)
        dashboard["source_status"]="clean"
        write_json(case9/"latest/readiness_dashboards/combined_readiness_dashboard.json", dashboard)
        r9=run_script(script, case9)
        assert r9["status"] == "blocked" and r9["last_good_state_updated"] is False, r9
        results.append({"case":"clean_dashboard_cannot_override_blocked_race_aggregation", "status":"pass"})
    out={"schema_version":"f1_1b_v20_acceptance_tests", "status":"pass", "results":results}
    latest=repo_root/"latest/1b_validation"; latest.mkdir(parents=True, exist_ok=True)
    (latest/"v20_acceptance_tests.json").write_text(json.dumps(out, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
