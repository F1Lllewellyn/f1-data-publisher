#!/usr/bin/env python3
"""
F1 Cross-Car Microdelta Forensics + Pattern Discovery Layer v0
Hardened source-discovery guard version.

If no suitable input CSV exists, this script now exits successfully with a
no-action report instead of failing the workflow. This is intentional: the
microdelta layer is experimental and should not break production workflows when
its source artifact is absent or not yet generated.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np

METRIC_MAP = {
    'interval_mean': ('interval/gap','mean interval profile vs field'),
    'gap_mean': ('interval/gap','gap to leader/field spacing pressure'),
    'pressure_records': ('traffic','pressure/close-running exposure'),
    'train_records': ('traffic','traffic/energy train exposure'),
    'traffic_pressure_score': ('traffic','normalized pressure exposure'),
    'energy_train_score': ('traffic_energy','traffic/energy management proxy'),
    'position_volatility': ('race_state','position instability'),
    'pit_time_loss': ('pit_strategy','pit/lane time cost'),
    'pit_efficiency_score': ('pit_strategy','pit efficiency signal'),
    'stint_degradation_pressure': ('stint_degradation','stint/tyre-pressure proxy'),
    'strategy_degradation_specialist_score': ('strategy_degradation','strategy/degradation specialist score'),
    'rc_risk_score': ('race_control','race-control incident/flag risk'),
    'reliability_eol_risk_score': ('reliability_eol','Reliability/EOL risk'),
    'sim_dnf_probability': ('reliability_eol','recalibrated DNF probability'),
    'source_completeness_score': ('source_readiness','input completeness gate'),
    'proof_loop_confidence_score': ('method_e','Method E proof-loop confidence'),
    'grid_track_position_specialist_score': ('grid_track_position','grid/track-position score'),
    'forecast_artifact_ensemble_score': ('forecast_artifact','forecast artifact ensemble'),
    'stable_challenger_delta_score': ('forecast_delta','stable vs challenger disagreement'),
    'fantasy_proxy_expected_score': ('fantasy_proxy','fantasy proxy expected score'),
}

REQUIRED_COLUMNS = {'session_key', 'team_name', 'driver_name'}

PREFERRED_NAMES = [
    'reliability_eol_recalibration_driver_summary.csv',
    'integrated_specialist_feature_matrix.csv',
    'integrated_specialist_replay_driver_summary.csv',
    'driver_session_summary.csv',
    'session_driver_summary.csv',
    'microdelta_driver_source_summary.csv',
    'refreshed_workbook_kpi_readiness.csv',
    'workbook_kpi_readiness.csv',
]

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def write_no_action(output_dir: Path, reason: str, searched_root: str, candidates: list[str] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'results').mkdir(exist_ok=True)
    (output_dir / 'manifests').mkdir(exist_ok=True)

    status = {
        'status': 'no_action',
        'reason': reason,
        'searched_root': searched_root,
        'candidate_count': len(candidates or []),
        'candidate_examples': (candidates or [])[:20],
        'stable_engine_modified': False,
        'canonical_workbook_overwrite': False,
        'promotion_allowed': False,
        'created_utc': utc_now(),
    }
    (output_dir / 'manifests' / 'governance_status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    (output_dir / 'NO_ACTION_REPORT.md').write_text(
        '# Cross-Car Microdelta No-Action Report\n\n'
        f'- Status: no_action\n'
        f'- Reason: {reason}\n'
        f'- Searched root: `{searched_root}`\n'
        f'- Candidate count: {len(candidates or [])}\n'
        '- Stable engine modified: false\n'
        '- Canonical workbook overwrite: false\n'
        '- Promotion allowed: false\n',
        encoding='utf-8'
    )
    # Empty but schema-present outputs keep artifact consumers stable.
    pd.DataFrame().to_csv(output_dir / 'results' / 'microdelta_driver_signal_matrix.csv', index=False)
    pd.DataFrame().to_csv(output_dir / 'results' / 'teammate_divergence_map.csv', index=False)
    pd.DataFrame().to_csv(output_dir / 'results' / 'team_pair_platform_fingerprint_map.csv', index=False)
    pd.DataFrame().to_csv(output_dir / 'results' / 'race_engineer_findings_ranked.csv', index=False)
    print(json.dumps(status, indent=2))

def csv_has_required_columns(path: Path) -> bool:
    try:
        head = pd.read_csv(path, nrows=5)
        return REQUIRED_COLUMNS.issubset(set(head.columns))
    except Exception:
        return False

def find_input_csv(input_dir: Path, explicit: str|None=None) -> tuple[Path|None, str, list[str]]:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            return None, f'explicit_input_not_found:{p}', []
        if not csv_has_required_columns(p):
            return None, f'explicit_input_invalid_schema:{p}', [str(p)]
        return p, 'explicit_input', [str(p)]

    files = list(input_dir.rglob('*.csv'))
    candidates = [str(f) for f in files if f.name in PREFERRED_NAMES]

    # First pass: exact preferred names with required columns.
    for pref in PREFERRED_NAMES:
        for f in files:
            if f.name == pref and csv_has_required_columns(f):
                return f, f'preferred:{pref}', candidates

    # Second pass: any CSV with the required driver/session schema, excluding known output/history loops.
    excluded_tokens = {'cross_car_microdelta_forensics', 'readiness_dashboards'}
    for f in files:
        parts = set(f.parts)
        if parts.intersection(excluded_tokens):
            continue
        if csv_has_required_columns(f):
            return f, 'schema_discovery', candidates

    return None, 'no_driver_session_summary_csv_with_required_schema', candidates

def z_by_session(df: pd.DataFrame, col: str) -> pd.Series:
    def f(s):
        s = pd.to_numeric(s, errors='coerce')
        sd = s.std(ddof=0)
        if pd.isna(sd) or sd == 0:
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - s.mean()) / sd
    return df.groupby('session_key')[col].transform(f)

def run(input_csv: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/'results').mkdir(exist_ok=True)
    (output_dir/'manifests').mkdir(exist_ok=True)
    df = pd.read_csv(input_csv)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        write_no_action(output_dir, 'input_csv_missing_required_columns:' + ','.join(sorted(missing)), str(input_csv), [str(input_csv)])
        return

    metrics = [m for m in METRIC_MAP if m in df.columns]
    if not metrics:
        write_no_action(output_dir, 'input_csv_has_no_supported_microdelta_metric_columns', str(input_csv), [str(input_csv)])
        return

    for m in metrics:
        df[m+'_z'] = z_by_session(df, m)
        df[m+'_session_rank_desc'] = df.groupby('session_key')[m].rank(ascending=False, method='min')

    z_cols = [m+'_z' for m in metrics]
    rel = [c for c in ['sim_dnf_probability_z','reliability_eol_risk_score_z','rc_risk_score_z','stable_challenger_delta_score_z'] if c in df]
    traf = [c for c in ['traffic_pressure_score_z','energy_train_score_z','train_records_z','pressure_records_z'] if c in df]
    strat = [c for c in ['strategy_degradation_specialist_score_z','stint_degradation_pressure_z','pit_time_loss_z'] if c in df]
    source = [c for c in ['source_completeness_score_z','proof_loop_confidence_score_z'] if c in df]

    df['microdelta_anomaly_breadth'] = (df[z_cols].abs() > 1.25).sum(axis=1)
    df['reliability_pressure_combo_z'] = df[rel].mean(axis=1) if rel else 0
    df['traffic_energy_combo_z'] = df[traf].mean(axis=1) if traf else 0
    df['strategy_degradation_combo_z'] = df[strat].mean(axis=1) if strat else 0
    df['source_confidence_combo_z'] = df[source].mean(axis=1) if source else 0
    df['false_degradation_challenge_flag'] = ((df['traffic_energy_combo_z'] > 0.75) & (df['strategy_degradation_combo_z'] > 0.25)).astype(int)
    df['reliability_watch_flag'] = ((df['reliability_pressure_combo_z'] > 1.0) | (df.get('dnf', False) == True)).astype(int)

    matrix_cols = [c for c in ['country_name','session_name','session_key','driver_number','driver_name','team_name','position','dnf','microdelta_anomaly_breadth','reliability_watch_flag','false_degradation_challenge_flag','reliability_pressure_combo_z','traffic_energy_combo_z','strategy_degradation_combo_z','source_confidence_combo_z'] if c in df]
    for m in metrics:
        matrix_cols += [m, m+'_z', m+'_session_rank_desc']
    df[matrix_cols].to_csv(output_dir/'results/microdelta_driver_signal_matrix.csv', index=False)

    rows = []
    for (sk, team), g in df.groupby(['session_key','team_name']):
        if len(g) < 2:
            continue
        g = g.sort_values('driver_name')
        a, b = g.iloc[0], g.iloc[1]
        diffs = {m: abs(float(a.get(m+'_z',0)) - float(b.get(m+'_z',0))) for m in metrics}
        primary = max(diffs, key=diffs.get) if diffs else ''
        rows.append({
            'session_key': sk, 'team_name': team,
            'driver_a': a.driver_name, 'driver_b': b.driver_name,
            'primary_divergence_metric': primary,
            'primary_divergence_family': METRIC_MAP.get(primary,('',))[0] if primary else '',
            'primary_z_diff': diffs.get(primary,0),
            'total_abs_z_diff': sum(diffs.values()),
            'high_divergence_metric_count': sum(v > 1.5 for v in diffs.values()),
        })
    pd.DataFrame(rows).sort_values(['primary_z_diff','total_abs_z_diff'], ascending=False).to_csv(output_dir/'results/teammate_divergence_map.csv', index=False)

    team_rows = []
    for (sk, team), g in df.groupby(['session_key','team_name']):
        rec = {'session_key': sk, 'team_name': team, 'drivers': ' / '.join(g.driver_name.astype(str)), 'cars_count': len(g)}
        rec['team_reliability_pair_risk_z'] = g['reliability_pressure_combo_z'].mean()
        rec['team_traffic_energy_pair_z'] = g['traffic_energy_combo_z'].mean()
        rec['team_strategy_degradation_pair_z'] = g['strategy_degradation_combo_z'].mean()
        rec['team_anomaly_breadth_sum'] = int(g['microdelta_anomaly_breadth'].sum())
        team_rows.append(rec)
    team_df = pd.DataFrame(team_rows)
    team_df.to_csv(output_dir/'results/team_pair_platform_fingerprint_map.csv', index=False)

    findings = []
    if not team_df.empty:
        for _, r in team_df.sort_values('team_reliability_pair_risk_z', ascending=False).head(10).iterrows():
            findings.append({
                'finding_rank_basis': 'team_pair_reliability_risk',
                'entity_type': 'team_pair',
                'entity': r.team_name,
                'drivers': r.drivers,
                'primary_signal': 'Two-car reliability/operational risk fingerprint above session field',
                'supporting_metrics': f"team_reliability_pair_risk_z={r.team_reliability_pair_risk_z:.2f}; anomaly_breadth_sum={r.team_anomaly_breadth_sum}",
                'prediction_treatment': 'Reliability/EOL watchlist; not stable until repeat proof',
                'confidence_class': 'medium',
            })
    findings_df = pd.DataFrame(findings)
    if not findings_df.empty:
        findings_df.insert(0, 'rank', range(1, len(findings_df)+1))
    findings_df.to_csv(output_dir/'results/race_engineer_findings_ranked.csv', index=False)

    lattice = [
        ['car_vs_teammate','active','team/session paired comparison'],
        ['car_vs_constructor_pair','active','team/session paired platform map'],
        ['car_vs_field','active','session z-score and rank'],
        ['car_vs_corner_type','gated','needs car_data/telemetry'],
        ['car_vs_straight_line','gated','needs speed/RPM/gear/throttle'],
        ['car_vs_braking_zone','gated','needs brake/speed decel trace'],
    ]
    pd.DataFrame(lattice, columns=['comparison_family','current_status','input_basis']).to_csv(output_dir/'manifests/comparison_lattice_activation_register.csv', index=False)

    status = {
        'status': 'Pass with warnings',
        'input_csv': str(input_csv),
        'rows': int(len(df)),
        'sessions': int(df.session_key.nunique()),
        'stable_engine_modified': False,
        'canonical_workbook_overwrite': False,
        'promotion_allowed': False,
        'created_utc': utc_now(),
    }
    (output_dir/'manifests/governance_status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    print(json.dumps(status, indent=2))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', default='.', help='Directory to search for preferred input CSV')
    ap.add_argument('--input-csv', default=None, help='Explicit driver/session summary CSV')
    ap.add_argument('--output-dir', default='outputs/cross_car_microdelta_forensics_v0')
    args = ap.parse_args()

    input_csv, reason, candidates = find_input_csv(Path(args.input_dir), args.input_csv)
    if input_csv is None:
        write_no_action(Path(args.output_dir), reason, str(Path(args.input_dir)), candidates)
        return
    run(input_csv, Path(args.output_dir))

if __name__ == '__main__':
    main()
