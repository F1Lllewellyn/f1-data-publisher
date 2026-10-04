"""Fixed synthetic frozen-input CLI mechanics, disposable producer writes only.

No source discovery, external source capture, scoring implementation or scientific
receipts. Pins identify reviewed bytes; they are not authenticated attestations.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCER_PATH = REPO_ROOT / 'scripts/forecasts/produce_actual_forecast_rows_v1.py'
PRODUCER_BLOB_SHA = 'af27586668c767de126af829c1131c6bae4634ad'
RUNTIME_ROOT = REPO_ROOT / '_runtime/dr002_pre2b7c_frozen_producer_shadow'
SCHEMA = 'dr002-frozen-producer-shadow-pilot-v1'
STATUS = 'SHADOW_EXECUTION_ONLY_NOT_A_PRODUCTION_FORECAST'
EVENT_ID = 'synthetic_dr002_frozen_producer_v1'
MEETING_ID = 'synthetic-meeting'
SESSION_ID = 'synthetic-session'
GATE = 'post_qualifying'
LANE = 'stable_baseline'
SOURCE_NAMES = ('drivers', 'starting_grid', 'intervals', 'stints', 'weather', 'race_control', 'pit', 'position', 'source_readiness')
SYNTHETIC_BYTES = {
    'drivers': b'driver_number,full_name,team_name,event_id,meeting_id,session_id\n10,Synthetic Ten,Ferrari,synthetic_dr002_frozen_producer_v1,synthetic-meeting,synthetic-session\n20,Synthetic Twenty,McLaren,synthetic_dr002_frozen_producer_v1,synthetic-meeting,synthetic-session\n',
    'starting_grid': b'driver_number,position,event_id,meeting_id,session_id\n20,1,synthetic_dr002_frozen_producer_v1,synthetic-meeting,synthetic-session\n10,2,synthetic_dr002_frozen_producer_v1,synthetic-meeting,synthetic-session\n',
    'weather': b'air_temperature,event_id,meeting_id,session_id\n25,synthetic_dr002_frozen_producer_v1,synthetic-meeting,synthetic-session\n',
}
FALSE_FLAGS = ('production_authenticated', 'historical_availability_proven', 'stable_engine_execution_proven', 'dr002_activated')


class PilotError(ValueError):
    """HOLD: no successful execution manifest."""


def require(condition, reason):
    if not condition:
        raise PilotError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def json_bytes(value):
    # Packaging JSON, not a new DR-002 receipt/forecast-manifest hash algorithm.
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def read_rows(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline='')))


def build_synthetic_inputs(root, include_weather=True):
    root.mkdir(parents=True)
    names = ['drivers', 'starting_grid'] + (['weather'] if include_weather else [])
    records = []
    for name in sorted(names):
        data = SYNTHETIC_BYTES[name]
        path = root / (name + '.csv')
        path.write_bytes(data)
        require(path.read_bytes() == data, 'synthetic_input_readback_failed')
        records.append(dict(source_name=name, source_id='synthetic:dr002:' + name,
                            relative_path=path.name, source_sha256=digest(data)))
    manifest = dict(schema_version='dr002-frozen-producer-input-v1', event_id=EVENT_ID,
                    meeting_id=MEETING_ID, session_id=SESSION_ID, sources=records)
    data = json_bytes(manifest)
    path = root / 'frozen_input_manifest.json'
    path.write_bytes(data)
    require(path.read_bytes() == data, 'synthetic_manifest_readback_failed')
    return path, manifest, data


def verify_outputs(audit, metadata, rows, snapshot, manifest, manifest_data):
    """Check the fixed synthetic ceiling, without implementing model scoring."""
    expected_sources = [dict(e, row_count=len(read_rows(SYNTHETIC_BYTES[e['source_name']])))
                        for e in manifest['sources']]
    expected_counts = {name: 0 for name in SOURCE_NAMES}
    expected_counts.update({e['source_name']: e['row_count'] for e in expected_sources})
    for record in (audit, metadata):
        require(record.get('input_mode') == 'frozen_manifest' and record.get('broad_discovery_used') is False,
                'unexpected_discovery_mode')
        require(record.get('schema_version') == manifest['schema_version'] and
                record.get('frozen_manifest_sha256') == digest(manifest_data), 'manifest_binding_mismatch')
        require(all(record.get(k) == v for k, v in (('event_id', EVENT_ID), ('meeting_id', MEETING_ID), ('session_id', SESSION_ID))),
                'output_scope_mismatch')
        require(record.get('sources') == expected_sources and record.get('source_counts') == expected_counts,
                'source_binding_or_count_mismatch')
        require(all(record.get(k) is False for k in FALSE_FLAGS) and
                record.get('promotion_allowed') is False and record.get('stable_output_overwrite_allowed') is False,
                'unsupported_trust_or_promotion_claim')
    require(audit.get('status') == 'forecast_rows_created' and audit.get('forecast_rows_created') == 2 and
            audit.get('gate_lane_files_created') == 1 and audit.get('driver_universe_count') == 2 and
            audit.get('gates') == [GATE] and audit.get('lanes') == [LANE], 'unexpected_execution_shape')
    require(metadata.get('gate') == GATE and metadata.get('engine_lane') == LANE and metadata.get('row_count') == 2,
            'metadata_product_mismatch')
    require(len(rows) == 2 and {r.get('driver_number') for r in rows} == {'10', '20'}, 'unexpected_driver_universe')
    readiness = .48 if 'weather' in expected_counts and expected_counts['weather'] else .38
    for row in rows:
        require(row.get('event_id') == EVENT_ID and row.get('gate') == GATE and row.get('engine_lane') == LANE,
                'row_scope_mismatch')
        require(float(row['source_readiness_score']) == readiness, 'unexpected_readiness')
        require(row.get('grid_position') == {'10': '2', '20': '1'}[row['driver_number']], 'unexpected_grid')
        require(row.get('driver_name') in ('Synthetic Ten', 'Synthetic Twenty'), 'unexpected_driver_name')
        timestamp = row.get('forecast_generation_utc', '')
        require(timestamp.endswith('Z'), 'missing_runtime_generation_time')
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    require(len({r['forecast_generation_utc'] for r in rows}) == 1, 'inconsistent_generation_time')
    require(len(snapshot) == len(SOURCE_NAMES) and {r['source_name'] for r in snapshot} == set(SOURCE_NAMES), 'snapshot_shape_mismatch')
    by_name = {e['source_name']: e for e in expected_sources}
    for record in snapshot:
        expected = by_name.get(record['source_name'])
        require(record['row_count'] == str(expected_counts[record['source_name']]) and
                record['found'] == ('True' if expected else 'False'), 'snapshot_count_mismatch')
        require(record.get('source_id') == (expected['source_id'] if expected else '') and
                record.get('source_sha256') == (expected['source_sha256'] if expected else '') and
                record.get('relative_path') == (expected['relative_path'] if expected else '') and
                record.get('path') == record.get('relative_path'), 'snapshot_binding_mismatch')
    return expected_sources, readiness


def persist_checked(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    require(path.read_bytes() == data, 'evidence_copy_readback_failed')
    return digest(data)


def run_pilot(*, run_id, implementation_git_sha, include_weather=True):
    require(isinstance(run_id, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', run_id), 'invalid_run_id')
    require(isinstance(implementation_git_sha, str) and re.fullmatch(r'[0-9a-f]{40}', implementation_git_sha), 'invalid_git_sha')
    require(isinstance(include_weather, bool), 'invalid_synthetic_selection')
    code = PRODUCER_PATH.read_bytes()
    require(git_blob_sha(code) == PRODUCER_BLOB_SHA, 'producer_fingerprint_changed')
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    require(not RUNTIME_ROOT.is_symlink(), 'ambiguous_runtime_root')
    output = RUNTIME_ROOT / run_id
    output.mkdir()  # Never overwrite a prior attempt.
    try:
        with tempfile.TemporaryDirectory(prefix='dr002-frozen-producer-pilot-') as directory:
            sandbox = Path(directory)
            input_path, manifest, manifest_data = build_synthetic_inputs(sandbox / 'inputs', include_weather)
            command = [sys.executable, str(PRODUCER_PATH), '--frozen-input-manifest', str(input_path),
                       '--event-id', EVENT_ID, '--meeting-id', MEETING_ID, '--session-id', SESSION_ID,
                       '--race-name', 'Synthetic DR-002 CLI mechanics only', '--gate', GATE, '--lane', LANE,
                       '--repo-root', str(sandbox), '--strict-source']
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            completed = subprocess.run(command, cwd=sandbox, env=environment,
                                       capture_output=True, text=True, timeout=120, check=True)
            require(PRODUCER_PATH.read_bytes() == code, 'producer_changed_during_execution')
            audit = json.loads(completed.stdout)
            producer_run_id = audit.get('run_id', '')
            require(isinstance(producer_run_id, str) and re.fullmatch(r'\d{8}T\d{6}Z', producer_run_id), 'invalid_producer_run_id')
            runtime = sandbox / '_runtime/actual_forecast_producer_v1' / producer_run_id
            latest = sandbox / 'latest/forecasts' / EVENT_ID / GATE / LANE
            history = sandbox / 'history/forecasts' / EVENT_ID / producer_run_id / GATE / LANE
            evidence = {
                'producer_audit.json': (runtime / 'actual_forecast_producer_audit.json').read_bytes(),
                'source_snapshot_manifest.csv': (runtime / 'source_snapshot_manifest.csv').read_bytes(),
                'forecast_rows.csv': (latest / 'forecast_rows.csv').read_bytes(),
                'forecast_metadata.json': (latest / 'forecast_metadata.json').read_bytes(),
            }
            require(json.loads(evidence['producer_audit.json']) == audit, 'stdout_audit_mismatch')
            metadata = json.loads(evidence['forecast_metadata.json'])
            rows = read_rows(evidence['forecast_rows.csv'])
            snapshot = read_rows(evidence['source_snapshot_manifest.csv'])
            sources, readiness = verify_outputs(audit, metadata, rows, snapshot, manifest, manifest_data)
            # Existing latest/history and compatibility mirrors must agree exactly.
            for base in (latest, history):
                for name in ('forecast_rows.csv', 'source_snapshot_manifest.csv', 'forecast_metadata.json'):
                    require((base / name).read_bytes() == evidence[name], 'sandbox_output_copy_mismatch')
            for base in (sandbox / 'latest/forecast_outputs' / EVENT_ID / GATE / LANE,
                         sandbox / 'history/forecast_outputs' / EVENT_ID / producer_run_id / GATE / LANE):
                for name in ('forecast_rows.csv', 'forecast_metadata.json'):
                    require((base / name).read_bytes() == evidence[name], 'sandbox_mirror_mismatch')
            evidence.update({'frozen_input_manifest.json': manifest_data, 'producer_code.py': code})
            evidence.update({e['relative_path']: SYNTHETIC_BYTES[e['source_name']] for e in manifest['sources']})
            hashes = {name: persist_checked(output / 'evidence' / name, data) for name, data in sorted(evidence.items())}
            producer_generation = rows[0]['forecast_generation_utc']
        require(not sandbox.exists(), 'sandbox_not_disposed')
        result = dict(schema_version=SCHEMA, status=STATUS, execution_mode='manual_github_synthetic_frozen_shadow',
                      run_id=run_id, implementation_git_sha=implementation_git_sha,
                      producer_implementation='scripts/forecasts/produce_actual_forecast_rows_v1.py',
                      producer_git_blob_sha=PRODUCER_BLOB_SHA, producer_code_sha256=digest(code),
                      frozen_manifest_sha256=digest(manifest_data), event_id=EVENT_ID, meeting_id=MEETING_ID,
                      session_id=SESSION_ID, gate=GATE, lane_name=LANE, declared_sources=sources,
                      generated_row_count=len(rows), source_readiness=readiness, producer_exit_code=completed.returncode,
                      producer_run_id=producer_run_id, forecast_generation_utc=producer_generation,
                      evidence_sha256=hashes, producer_audit_broad_discovery_used=False,
                      synthetic_inputs=True, producer_output_sandbox_disposed=True,
                      checkout_production_outputs_written=False, production_forecast_generated=False,
                      production_authenticated=False, historical_availability_proven=False,
                      stable_engine_execution_proven=False, blind_validation_eligible=False, dr002_activated=False,
                      claim_limit='Synthetic CLI mechanics only. Lane label is not engine execution proof; hashes are not authentication. Inner producer files remain unchanged historical-behavior evidence, not publishable production forecasts.')
        report = '# Synthetic frozen-producer shadow\n\n' + STATUS + '\n\n' + json.dumps(result, indent=2, sort_keys=True) + '\n'
        persist_checked(output / 'shadow_report.md', report.encode())
        # Success is published last, after every selected byte is verified/copied.
        persist_checked(output / 'execution_manifest.json', json_bytes(result))
        return result
    except Exception as exc:
        # Preserve diagnostics, never leave a success manifest after failure.
        final = output / 'execution_manifest.json'
        if final.exists():
            final.unlink()
        (output / 'hold_report.md').write_text('HOLD\n\n' + type(exc).__name__ + ': ' + str(exc) + '\n', encoding='utf-8')
        raise


def main():
    parser = argparse.ArgumentParser(description='Fixed synthetic frozen producer shadow; no production publication.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--implementation-git-sha', required=True)
    args = parser.parse_args()
    result = run_pilot(run_id=args.run_id, implementation_git_sha=args.implementation_git_sha)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
