"""Fixed OpenF1 weather observation pilot. UNBOUND; no forecast consumption.

One request only. Complete-response time is observation of these exact bytes,
not historical publication/availability. Clock and observer are unauthenticated.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'forecast_bundles'))
from verify_forecast_integrity_receipts_v1 import (
    VERSION, canonical_json_bytes, sha256, receipt_sha256,
    validate_receipt_envelope, verify_temporal_bindings,
)

URI = 'https://api.openf1.org/v1/weather?session_key=11371'
SCOPE = dict(event_id='2026_1295_azerbaijan_baku_baku', meeting_id='1295', session_id='11371')
IMPLEMENTATION = 'scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py'
ROOT = Path('_runtime/dr002_gate2b2_capture_pilot')


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def transport():
    # No retries; read() completes before the caller samples response completion.
    with urlopen(Request(URI, method='GET', headers={'Accept': 'application/json',
                 'Accept-Encoding': 'identity'}), timeout=30) as response:
        return response.status, response.read()


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(data)


def parse_utc(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value):
        raise ValueError('invalid_utc')
    return datetime.fromisoformat(value[:-1] + '+00:00')


def validate_weather(body):
    rows = json.loads(body, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite_json')))
    if not isinstance(rows, list) or not rows:
        raise ValueError('expected_nonempty_weather_list')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid_weather_row')
        # Same required scope/date columns as SDP, strengthened to every row.
        for key, expected in [('session_key', '11371'), ('meeting_key', '1295')]:
            if key not in row or str(row[key]) != expected:
                raise ValueError('missing_or_wrong_' + key)
        date = row.get('date')
        if not isinstance(date, str) or datetime.fromisoformat(date.replace('Z', '+00:00')).tzinfo is None:
            raise ValueError('invalid_weather_date')
        if not any(isinstance(row.get(k), (int, float)) and not isinstance(row.get(k), bool)
                   and math.isfinite(row[k]) for k in ('air_temperature', 'track_temperature',
                   'humidity', 'pressure', 'rainfall', 'wind_direction', 'wind_speed')):
            raise ValueError('no_usable_weather_measurement')
        key = canonical_json_bytes(row)
        if key in seen:
            raise ValueError('duplicate_weather_row')
        seen.add(key)
    return rows


def capture(run_id, *, request=transport, clock=utc_now, writer=write_bytes,
            reader=lambda p: p.read_bytes(), validator=validate_receipt_envelope,
            runtime_root=ROOT, git_commit=None):
    """Injected transport/clock/filesystem support offline tests; returns manifest.

A new run directory is mandatory. Existing attempts are never overwritten.
Only the CLI's fixed runtime root is exposed to real executions.
"""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', run_id):
        raise ValueError('invalid_run_id')
    root = Path(runtime_root) / run_id
    root.mkdir(parents=True, exist_ok=False)
    raw = root / 'raw/openf1_weather.response.json'
    normalized = root / 'normalized/openf1_weather.normalized.json'
    receipt_path = root / 'source_capture_receipt.json'
    manifest = dict(schema_version='dr002-capture-pilot-v1', run_id=run_id, endpoint='weather',
        request_uri=URI, http_method='GET', **SCOPE, request_started_utc=None,
        response_completed_utc=None, first_observed_utc=None, ingested_utc=None,
        receipt_created_utc=None, http_status=None, byte_count=0, source_sha256=None,
        readback_sha256=None, readback_verified=False, normalized_sha256=None,
        row_count=0, validation_status='HOLD', implementation=IMPLEMENTATION,
        implementation_git_sha=git_commit, raw_artifact_path=str(raw), receipt_path=None,
        receipt_sha256=None, binding_status='UNBOUND', production_authenticated=False,
        historical_availability_proven=False, dr002_activated=False, reason=None)
    try:
        manifest['request_started_utc'] = clock()
        status, body = request()
        completed = clock()  # ONLY after COMPLETE body read.
        manifest.update(http_status=status, response_completed_utc=completed, first_observed_utc=completed)
        if status != 200:
            raise ValueError('http_status_not_200')
        if not isinstance(body, bytes) or not body:
            raise ValueError('empty_or_invalid_response_bytes')
        manifest.update(byte_count=len(body), source_sha256=sha256(body))
        writer(raw, body)
        digest = sha256(reader(raw))
        manifest['readback_sha256'] = digest
        if digest != manifest['source_sha256']:
            raise ValueError('raw_readback_hash_mismatch')
        manifest['readback_verified'] = True
        manifest['ingested_utc'] = clock()
        rows = validate_weather(body)
        manifest['row_count'] = len(rows)
        canonical = canonical_json_bytes(rows)
        writer(normalized, canonical)
        if reader(normalized) != canonical:
            raise ValueError('normalized_readback_mismatch')
        manifest['normalized_sha256'] = sha256(canonical)
        created = clock()
        manifest['receipt_created_utc'] = created
        times = [parse_utc(manifest[k]) for k in ('request_started_utc', 'first_observed_utc', 'ingested_utc', 'receipt_created_utc')]
        if times != sorted(times):
            raise ValueError('invalid_time_order')
        receipt = dict(schema_version=VERSION,
            receipt_id='source_capture:' + sha256(canonical_json_bytes({
                'source_id': 'openf1:weather:1295:11371', **SCOPE,
                'source_sha256': manifest['source_sha256'], 'first_observed_utc': completed})),
            receipt_type='source_capture', receipt_created_utc=created, scope=dict(SCOPE),
            parent_receipt_ids=[], payload=dict(source_id='openf1:weather:1295:11371',
                source_uri=URI, source_sha256=manifest['source_sha256'], event_time_utc=None,
                publisher_time_utc=None, first_observed_utc=completed,
                ingested_utc=manifest['ingested_utc'], capture_ref=str(raw), implementation=IMPLEMENTATION))
        if validator(receipt) is not True:
            raise ValueError('receipt_structural_validation_failed')
        verify_temporal_bindings(receipt)
        encoded = canonical_json_bytes(receipt)
        # Verify a diagnostic candidate before publishing the receipt filename.
        candidate = root / 'receipt_candidate.diagnostic.json'
        writer(candidate, encoded)
        if reader(candidate) != encoded:
            raise ValueError('receipt_readback_mismatch')
        manifest.update(validation_status='CAPTURED_UNBOUND', receipt_path=str(receipt_path),
                        receipt_sha256=receipt_sha256(receipt))
    except Exception as exc:
        manifest['reason'] = type(exc).__name__ + ': ' + str(exc)
    # If report persistence fails, propagate failure; never advertise success.
    writer(root / 'capture_manifest.json', canonical_json_bytes(manifest))
    writer(root / 'pilot_report.md', (
        '# DR-002 isolated capture pilot\n\nStatus: ' + manifest['validation_status'] +
        '\n\nUNBOUND: no production authentication or historical availability proof.\n'
        'DR-002 remains PROPOSED — NOT ACTIVATED. No forecast consumes this capture.\n'
        '\nReason: ' + str(manifest['reason']) + '\n').encode())
    # Publish LAST. Diagnostic persistence and rename errors propagate.
    if manifest['validation_status'] == 'CAPTURED_UNBOUND':
        candidate.rename(receipt_path)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--implementation-git-sha')
    args = parser.parse_args()
    if args.implementation_git_sha and not re.fullmatch('[0-9a-f]{40}', args.implementation_git_sha):
        parser.error('implementation Git SHA must be 40 lowercase hex characters')
    result = capture(args.run_id, git_commit=args.implementation_git_sha)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['validation_status'] == 'CAPTURED_UNBOUND' else 1


if __name__ == '__main__':
    raise SystemExit(main())
