#!/usr/bin/env python3
"""
Elite Weekend Engine v2 artifact consumer.

Consumes latest OpenF1 autopilot artifacts and produces control-room outputs,
workbook bridge exports, GitHub run summary, and locked ledger snapshot.

Guardrails:
- Public/proxy OpenF1 data only.
- Risk/fantasy/reporting only.
- No automatic qualifying P1-P5 reorder.
- No automatic stable race P1-P20 reorder.
- DNF_ALL broad precursor policy preserved.
- 2026 no-DRS rule preserved.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import zipfile
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


def load_verifier(name, relative):
    path = Path(__file__).resolve().parents[1] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def current_identity(repo, now):
    dashboard = load_verifier('elite_current_authority', 'dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py')
    state = dashboard.discover_state(repo, reference_time=now)
    if state.get('downstream_eligible') is not True:
        raise RuntimeError('HOLD_ELITE_CURRENT_SOURCE:' + ','.join(state.get('readiness_reasons', [])))
    return {key: state[key] for key in ('event_id', 'meeting_key', 'session_key')}


def verify_profile_custody(profile, profile_dir, artifact_row, expected, now):
    """Authenticate the archive independently; a local found/verified flag is no proof.

    Legacy high-frequency archives lack original response/observation custody.
    They remain quarantined. This consumes an original source_custody.json only
    when it is itself inside the authenticated archive; it never creates one.
    """
    intake = load_verifier('elite_transfer_verifier', 'elite/download_latest_openf1_artifacts.py')
    if not expected:
        raise RuntimeError('HOLD_ELITE_CURRENT_IDENTITY_UNVERIFIED')
    if artifact_row.get('quarantined_to') or artifact_row.get('event_session_provenance_verified') is not True:
        raise RuntimeError('HOLD_ELITE_SOURCE_PROVENANCE_UNVERIFIED')
    repo, token = os.environ.get('GITHUB_REPOSITORY', ''), os.environ.get('GITHUB_TOKEN', '')
    if not repo or not token:
        raise RuntimeError('HOLD_ELITE_AUTHENTICATED_INTAKE_UNAVAILABLE')
    artifact_id = artifact_row.get('artifact_id')
    if not str(artifact_id).isdigit() or int(artifact_id) <= 0:
        raise RuntimeError('HOLD_ELITE_ARTIFACT_IDENTITY')
    metadata = intake.gh_get_json(f'https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}', token)
    intake.validate_artifact(metadata, repo, intake.PROFILES[profile])
    origin = intake.verify_originating_workflow_run(metadata, profile, repo, token)
    if (str(metadata['id']) != str(artifact_id) or metadata['name'] != artifact_row.get('artifact_name')
            or str(origin['id']) != str(artifact_row.get('workflow_run_id'))
            or str(origin['run_attempt']) != str(artifact_row.get('workflow_run_attempt'))
            or origin['head_sha'] != artifact_row.get('workflow_run_head_sha')
            or origin['path'] != artifact_row.get('workflow_path')):
        raise RuntimeError('HOLD_ELITE_ORIGINAL_RUN_MISMATCH')
    root = profile_dir.parent.parent.resolve()
    archive_path = root / 'downloads' / f'{profile}_{artifact_id}.zip'
    for path in (archive_path, profile_dir):
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.resolve().is_relative_to(root):
            raise RuntimeError('HOLD_ELITE_INPUT_PATH')
    if not archive_path.is_file() or archive_path.stat().st_size != metadata['size_in_bytes']:
        raise RuntimeError('HOLD_ELITE_ARCHIVE_MISSING_OR_INCOMPLETE')
    archive_sha = intake._file_sha256(archive_path)
    if metadata.get('digest') != 'sha256:' + archive_sha:
        raise RuntimeError('HOLD_ELITE_AUTHENTICATED_ARCHIVE_DIGEST')
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos if not i.is_dir()]
        if (len(infos) > intake.MAX_ZIP_MEMBERS or len(names) != len(set(names))
                or sum(i.file_size for i in infos) > intake.MAX_EXTRACTED_BYTES or archive.testzip()):
            raise RuntimeError('HOLD_ELITE_ARCHIVE_INTEGRITY')
        # Verify every extracted byte, including feature/checkpoint summaries.
        for name in names:
            path = profile_dir / name
            if ('\\' in name or '..' in Path(name).parts or Path(name).is_absolute()
                    or not path.resolve().is_relative_to(profile_dir.resolve())
                    or any(p.is_symlink() for p in (path, *path.parents))
                    or not path.is_file() or path.read_bytes() != archive.read(name)):
                raise RuntimeError('HOLD_ELITE_EXTRACTED_BYTES')
        if set(names) != {p.relative_to(profile_dir).as_posix() for p in profile_dir.rglob('*') if p.is_file()}:
            raise RuntimeError('HOLD_ELITE_UNBOUND_EXTRACTED_FILES')
        if 'source_custody.json' not in names:
            raise RuntimeError('HOLD_ELITE_ORIGINAL_SOURCE_CUSTODY_NOT_RETAINED')
        custody = json.loads(archive.read('source_custody.json'))
        if (custody.get('schema') != 'elite-source-custody-v1' or custody.get('profile') != profile
                or custody.get('capture_origin') != origin
                or any(custody.get(k) != v for k, v in expected.items())):
            raise RuntimeError('HOLD_ELITE_EVENT_SESSION_OR_ORIGIN')
        sources = custody.get('sources')
        if not isinstance(sources, list) or not sources:
            raise RuntimeError('HOLD_ELITE_ORIGINAL_SOURCE_CUSTODY_NOT_RETAINED')
        endpoints, hashes, clocks, driver_rows, observed_rows = set(), {}, {}, [], []
        for source in sources:
            endpoint, name = source.get('endpoint'), source.get('path')
            if endpoint not in {'drivers', 'laps', 'position', 'weather', 'car_data', 'location', 'stints', 'pit', 'race_control', 'team_radio', 'intervals'} or name not in names or name in hashes:
                raise RuntimeError('HOLD_ELITE_SOURCE_ENDPOINT')
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != source.get('sha256') or source.get('http_status') != 200:
                raise RuntimeError('HOLD_ELITE_SOURCE_BYTES')
            from urllib.parse import urlparse, parse_qs
            request = urlparse(source.get('request_url', ''))
            if (request.scheme != 'https' or request.netloc != 'api.openf1.org'
                    or request.path != '/v1/' + endpoint or request.fragment
                    or parse_qs(request.query).get('session_key') != [str(expected['session_key'])]):
                raise RuntimeError('HOLD_ELITE_SOURCE_REQUEST_IDENTITY')
            observed = intake._parse_utc(source.get('observed_at_utc'), 'source observation')
            if not observed <= intake._parse_utc(metadata['created_at'], 'created_at') <= now:
                raise RuntimeError('HOLD_ELITE_SOURCE_AVAILABILITY')
            rows = json.loads(raw)
            if not isinstance(rows, list) or not rows or len(rows) != source.get('rows'):
                raise RuntimeError('HOLD_ELITE_SOURCE_COVERAGE')
            for row in rows:
                if not isinstance(row, dict) or row.get('meeting_key') != expected['meeting_key'] or row.get('session_key') != expected['session_key']:
                    raise RuntimeError('HOLD_ELITE_SOURCE_ROW_IDENTITY')
                if row.get('date') and intake._parse_utc(row['date'], 'source row') > observed:
                    raise RuntimeError('HOLD_ELITE_SOURCE_AVAILABILITY')
            if endpoint == 'drivers':
                driver_rows.extend(rows)
            observed_rows.extend(rows)
            endpoints.add(endpoint); hashes[name] = source['sha256']; clocks[name] = source['observed_at_utc']
        if not {'drivers', 'laps', 'position', 'weather'}.issubset(endpoints):
            raise RuntimeError('HOLD_ELITE_REQUIRED_SOURCE_COVERAGE')
        drivers = [r.get('driver_number') for r in driver_rows]
        if not drivers or len(drivers) != len(set(drivers)) or any(type(d) is not int or d <= 0 for d in drivers):
            raise RuntimeError('HOLD_ELITE_DRIVER_ROSTER')
        if any(r.get('driver_number') is not None and r['driver_number'] not in drivers for r in observed_rows):
            raise RuntimeError('HOLD_ELITE_DRIVER_MEMBERSHIP')
    return dict(expected, archive_sha256=archive_sha, capture_origin=origin,
                source_hashes=hashes, source_availability=clocks,
                context_verified=True, forecast_eligible=False, prediction_locked=False)


def find_first(root: Path, pattern: str):
    hits = list(root.rglob(pattern))
    if not hits:
        return None
    hits.sort(key=lambda p: len(str(p)))
    return hits[0]


def read_json(path: Path) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def read_csv(path: Path) -> pd.DataFrame:
    if path and path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def profile_summary(profile: str, profile_dir: Path, artifact_row: dict, expected=None, now=None) -> dict:
    custody, hold_reason = {}, ''
    found = artifact_row.get('found') is True
    if found:
        try:
            custody = verify_profile_custody(profile, profile_dir, artifact_row, expected, now or datetime.now(timezone.utc))
        except Exception as exc:
            # Exception text can contain signed URLs/credentials from transport.
            hold_reason = str(exc) if str(exc).startswith('HOLD_ELITE_') else 'HOLD_ELITE_INTAKE_' + type(exc).__name__
    else:
        hold_reason = 'HOLD_ELITE_SOURCE_PROVENANCE_UNVERIFIED' if artifact_row.get('quarantined_to') else 'HOLD_ELITE_ARTIFACT_MISSING'
    if not custody:
        return dict(profile=profile, artifact_found=False, artifact_name=artifact_row.get('artifact_name',''),
                    artifact_id=artifact_row.get('artifact_id',''), updated_at=artifact_row.get('updated_at',''),
                    checkpoint_status='', selected_sessions=0, high_frequency_rows=0, normal_feature_rows=0,
                    fallback_feature_builder_used=False, feature_rows=0, status='HOLD' if found else 'MISSING',
                    hold_reason=hold_reason, custody={}, forecast_eligible=False)
    checkpoint = read_json(find_first(profile_dir, "extraction_checkpoint_summary.json") or Path(""))
    manifest = read_csv(find_first(profile_dir, "high_frequency_extraction_manifest.csv") or Path(""))
    feature_manifest = read_csv(find_first(profile_dir, "feature_manifest.csv") or Path(""))
    sessions = read_csv(find_first(profile_dir, "completed_sessions_selected.csv") or Path(""))

    high_freq_rows = 0
    if not manifest.empty and "rows" in manifest.columns:
        high_freq_rows = int(pd.to_numeric(manifest["rows"], errors="coerce").fillna(0).sum())

    feature_rows = checkpoint.get("feature_rows", 0)
    if not feature_rows and not feature_manifest.empty and "rows_30s" in feature_manifest.columns:
        feature_rows = int(pd.to_numeric(feature_manifest["rows_30s"], errors="coerce").fillna(0).sum())

    status = "MISSING"
    if found and high_freq_rows > 0 and feature_rows > 0:
        status = "PASS"
    elif found and high_freq_rows > 0 and feature_rows == 0:
        status = "PASS_WITH_WARNINGS"
    elif found:
        status = "FOUND_BUT_UNUSABLE"

    return {
        "profile": profile,
        "artifact_found": found,
        "artifact_name": artifact_row.get("artifact_name", ""),
        "artifact_id": artifact_row.get("artifact_id", ""),
        "updated_at": artifact_row.get("updated_at", ""),
        "checkpoint_status": checkpoint.get("status", ""),
        "selected_sessions": int(checkpoint.get("selected_session_count", len(sessions) if not sessions.empty else 0) or 0),
        "high_frequency_rows": high_freq_rows,
        "normal_feature_rows": int(checkpoint.get("normal_feature_rows", feature_rows) or 0),
        "fallback_feature_builder_used": bool(checkpoint.get("fallback_feature_builder_used", False)),
        "feature_rows": int(feature_rows or 0),
        "status": status,
        "hold_reason": hold_reason,
        "custody": custody,
        "forecast_eligible": False,
    }


def write_df(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def copy_for_workbook(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        dst.write_bytes(src.read_bytes())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--repo-root", default=".")
    args = p.parse_args()

    input_root = Path(args.input_dir)
    out = Path(args.output_dir)
    for sub in ["reports", "metrics", "ledgers", "manifests", "validation", "workbook_exports"]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    manifest_json = read_json(input_root / "manifests" / "elite_artifact_source_manifest.json")
    profile_rows = manifest_json.get("profiles", [])
    profile_by_name = {r.get("profile"): r for r in profile_rows}

    profiles = ["pre_race", "full_historical", "post_race"]
    now = datetime.now(timezone.utc)
    try:
        expected = current_identity(Path(args.repo_root).resolve(), now)
        current_hold = ''
    except Exception:
        expected, current_hold = None, 'HOLD_ELITE_CURRENT_IDENTITY_UNVERIFIED'
    summaries = [
        profile_summary(profile, input_root / "inputs" / profile, profile_by_name.get(profile, {}), expected, now)
        for profile in profiles
    ]

    readiness = pd.DataFrame(summaries)
    source_readiness_path = out / "metrics" / "source_readiness_board.csv"
    write_df(readiness, source_readiness_path)

    pre = next((s for s in summaries if s["profile"] == "pre_race"), {})
    full = next((s for s in summaries if s["profile"] == "full_historical"), {})
    post = next((s for s in summaries if s["profile"] == "post_race"), {})

    if pre.get("status") == "PASS" and full.get("status") == "PASS":
        if post.get("status") == "PASS_WITH_WARNINGS":
            elite_status = "READY_WITH_POSTRACE_SIGNAL_WARNING"
        elif post.get("status") == "PASS":
            elite_status = "READY"
        else:
            elite_status = "READY_WITH_POSTRACE_ARTIFACT_MISSING"
    elif full.get("status") == "PASS":
        elite_status = "PARTIAL_READY_FULL_HISTORICAL_ONLY"
    elif pre.get("status") == "PASS":
        elite_status = "PARTIAL_READY_PRERACE_ONLY"
    else:
        elite_status = "NOT_READY"
    # Source context is not an executed stable engine or an eligible forecast.
    if elite_status != 'NOT_READY':
        elite_status = 'CONTEXT_ONLY'

    reliability_rows = []
    for s in summaries:
        reliability_rows.append({
            "source_profile": s["profile"],
            "artifact_status": s["status"],
            "selected_sessions": s["selected_sessions"],
            "high_frequency_rows": s["high_frequency_rows"],
            "normal_feature_rows": s["normal_feature_rows"],
            "fallback_feature_builder_used": s["fallback_feature_builder_used"],
            "feature_rows": s["feature_rows"],
            "reliability_signal_available": bool(s.get('custody', {}).get('context_verified') and s["feature_rows"] > 0),
            "usage": "risk/fantasy/reporting only",
            "stable_rank_change_allowed": False,
        })
    reliability_board = pd.DataFrame(reliability_rows)
    reliability_path = out / "metrics" / "reliability_warning_board.csv"
    write_df(reliability_board, reliability_path)

    dnf_board = reliability_board.copy()
    dnf_board["target_policy"] = "DNF_ALL"
    dnf_board["visible_outcome_labels_are_metadata_only"] = True
    dnf_board["do_not_exclude_crash_contact_damage_without_searching_precursors"] = True
    dnf_path = out / "metrics" / "dnf_all_precursor_board.csv"
    write_df(dnf_board, dnf_path)

    fantasy_board = reliability_board[[
        "source_profile", "artifact_status", "feature_rows",
        "fallback_feature_builder_used", "reliability_signal_available"
    ]].copy()
    fantasy_board["fantasy_usage"] = fantasy_board["reliability_signal_available"].map(
        lambda x: "eligible_for_risk_flag_review" if x else "no_signal_available"
    )
    fantasy_board["automatic_transfer_recommendation_allowed"] = False
    fantasy_path = out / "metrics" / "fantasy_risk_board.csv"
    write_df(fantasy_board, fantasy_path)

    disagreement = pd.DataFrame([{
        "model_family": "OpenF1 public/proxy reliability layer",
        "pre_race_status": pre.get("status", "MISSING"),
        "full_historical_status": full.get("status", "MISSING"),
        "post_race_status": post.get("status", "MISSING"),
        "post_race_fallback_used": post.get("fallback_feature_builder_used", False),
        "disagreement_state": "postrace_zero_feature_warning" if post.get("status") == "PASS_WITH_WARNINGS" else "normal",
        "action": "review_before_consumption" if post.get("status") == "PASS_WITH_WARNINGS" else "available_for_control_room",
    }])
    disagreement_path = out / "metrics" / "model_disagreement_board.csv"
    write_df(disagreement, disagreement_path)

    if elite_status == "READY":
        promotion_action = "NO_PROMOTION_AUTOMATIC__AVAILABLE_FOR_REVIEW"
    elif elite_status == "READY_WITH_POSTRACE_SIGNAL_WARNING":
        promotion_action = "NO_PROMOTION__POSTRACE_SIGNAL_WARNING"
    else:
        promotion_action = "NO_PROMOTION_HOLD_STABLE"

    promotion = pd.DataFrame([{
        "gate": "automatic_promotion_demotion_controller",
        "elite_status": elite_status,
        "prediction_locked": False,
        "stable_engine_executed": False,
        "forecast_eligible": False,
        "promotion_action": promotion_action,
        "stable_race_p1_p20_change_allowed": False,
        "qualifying_p1_p5_change_allowed": False,
        "requires_human_review_for_forecast_consumption": True,
    }])
    promotion_path = out / "metrics" / "promotion_demotion_gate.csv"
    write_df(promotion, promotion_path)

    ledger = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "engine_layer": "Elite Weekend Engine v2 Artifact Consumer",
        "elite_status": elite_status,
        "artifact_profiles": summaries,
        "guardrails": {
            "public_proxy_only": True,
            "stable_race_p1_p20_change_allowed": False,
            "qualifying_p1_p5_change_allowed": False,
            "dnf_all_broad_precursor_policy": True,
            "no_drs_2026_rule_preserved": True,
        },
        "next_forecast_cycle_state": {
            "pre_race_auto_ingest": pre.get("status", "MISSING"),
            "full_historical_auto_ingest": full.get("status", "MISSING"),
            "post_race_auto_reliability": post.get("status", "MISSING"),
            "recommended_action": "use_elite_outputs_for_control_room_review" if elite_status.startswith("READY") else "repair_sources_before_forecast_use",
        },
    }
    ledger_path = out / "ledgers" / "locked_forecast_ledger_snapshot.json"
    ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    write_df(pd.DataFrame(summaries), out / "manifests" / "elite_artifact_source_manifest.csv")

    # Workbook/control-room bridge exports
    workbook_dir = out / "workbook_exports"
    workbook_map = [
        (source_readiness_path, "F1_Source_Readiness_Board.csv", "Workbook source readiness import"),
        (reliability_path, "F1_Reliability_Warnings.csv", "Workbook reliability warnings import"),
        (dnf_path, "F1_DNF_ALL_Precursor_Board.csv", "Workbook DNF_ALL precursor import"),
        (fantasy_path, "F1_Fantasy_Risk_Board.csv", "Workbook fantasy risk import"),
        (disagreement_path, "F1_Model_Disagreement_Board.csv", "Workbook model disagreement import"),
        (promotion_path, "F1_Promotion_Gate.csv", "Workbook promotion/demotion gate import"),
        (ledger_path, "F1_Locked_Forecast_Ledger_Snapshot.json", "Workbook locked ledger sidecar"),
    ]
    bridge_rows = []
    for src, name, purpose in workbook_map:
        dst = workbook_dir / name
        copy_for_workbook(src, dst)
        bridge_rows.append({
            "workbook_export": name,
            "source_path": str(src.relative_to(out)),
            "export_path": str(dst.relative_to(out)),
            "purpose": purpose,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
        })
    write_df(pd.DataFrame(bridge_rows), workbook_dir / "workbook_bridge_manifest.csv")

    report_lines = [
        "# Elite Weekend Engine v2 Report",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Elite status: **{elite_status}**",
        "",
        "## Artifact source readiness",
        "",
        "| Profile | Artifact | Status | Sessions | High-frequency rows | Feature rows | Fallback used |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for s in summaries:
        report_lines.append(
            f"| {s['profile']} | {s['artifact_name']} | {s['status']} | {s['selected_sessions']} | {s['high_frequency_rows']} | {s['feature_rows']} | {s['fallback_feature_builder_used']} |"
        )
    report_lines += [
        "",
        "## Output boards generated",
        "",
        "- source_readiness_board.csv",
        "- reliability_warning_board.csv",
        "- dnf_all_precursor_board.csv",
        "- fantasy_risk_board.csv",
        "- model_disagreement_board.csv",
        "- promotion_demotion_gate.csv",
        "- locked_forecast_ledger_snapshot.json",
        "- workbook_exports/workbook_bridge_manifest.csv",
        "",
        "## Next forecast cycle",
        "",
        "Use Elite outputs for control-room review once the latest scheduled pre-race run completes. Do not manually rerun large OpenF1 extraction unless a workflow fails or a fresh full-history rebuild is explicitly needed.",
        "",
        "## Guardrails",
        "",
        "- This run consumes public/proxy OpenF1 artifacts only.",
        "- It does not automatically reorder stable race P1-P20 predictions.",
        "- It does not automatically reorder qualifying P1-P5 predictions.",
        "- Reliability outputs are risk/fantasy/reporting inputs only unless separately promoted.",
        "- DNF_ALL remains broad precursor search; visible DNF labels are metadata only.",
        "- 2026 no-DRS rule preserved.",
        "",
    ]
    report_path = out / "reports" / "elite_weekend_engine_v2_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    validation = {
        "validation_status": "PASS" if elite_status != "NOT_READY" else "FAIL",
        "elite_status": elite_status,
        "current_identity": expected,
        "current_identity_hold": current_hold,
        "forecast_eligible": False,
        "stable_engine_executed": False,
        "prediction_locked": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "required_profiles": profiles,
        "profiles": summaries,
        "workbook_bridge_exports": bridge_rows,
    }
    (out / "validation" / "elite_validation_summary.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")

    summary_lines = [
        "## Elite Weekend Engine v2 summary",
        "",
        f"**Elite status:** `{elite_status}`",
        "",
        "| Source | Status | Sessions | Rows | Features | Fallback |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in summaries:
        summary_lines.append(
            f"| {s['profile']} | {s['status']} | {s['selected_sessions']} | {s['high_frequency_rows']} | {s['feature_rows']} | {s['fallback_feature_builder_used']} |"
        )
    summary_lines += [
        "",
        f"**Promotion gate:** `{promotion_action}`",
        "",
        "- Stable race P1-P20 changes: disabled",
        "- Qualifying P1-P5 changes: disabled",
        "- Workbook bridge exports: generated",
        "",
        "### Next action",
        "",
        "Use the workbook bridge outputs for control-room review. Do not rerun the large OpenF1 full historical workflow unless explicitly needed.",
        "",
    ]
    (out / "reports" / "github_step_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print(json.dumps(validation, indent=2))
    if elite_status == "NOT_READY":
        raise SystemExit("Elite Weekend Engine v2 could not find enough validated OpenF1 artifacts.")


if __name__ == "__main__":
    main()
