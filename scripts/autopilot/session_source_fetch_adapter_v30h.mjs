#!/usr/bin/env node
/*
 * F1 v30H Session Source Fetch Adapter sandbox.
 *
 * Converts the v30G source-fetch contract into an executable request manifest.
 * Default mode is dry_run: no network fetches are performed.
 */
import fs from 'node:fs';
import path from 'node:path';

const OPENF1_BASE_URL = 'https://api.openf1.org/v1';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    allowLive: false,
    policy: 'scripts/autopilot/session_source_fetch_adapter_policy_v30h.json',
    contract: 'health/session_source_fetch_contract_v30g_status.json',
    out: 'health/session_source_fetch_adapter_v30h_status.json',
    cacheDir: 'cache/session_sources',
    logDir: 'logs/session_source_fetch_adapter'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--contract' && value) { args.contract = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--cache-dir' && value) { args.cacheDir = value; i += 1; }
    else if (key === '--log-dir' && value) { args.logDir = value; i += 1; }
  }

  return args;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

function queryUrl(endpoint, params) {
  const search = new URLSearchParams();
  Object.entries(params)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .forEach(([key, value]) => search.set(key, String(value)));
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return `${OPENF1_BASE_URL}/${endpoint}${suffix}`;
}

function sessionKeyFromContract(contract) {
  const raw = contract?.session?.session_id;
  if (typeof raw === 'number') return raw;
  if (typeof raw === 'string' && /^\d+$/.test(raw)) return Number(raw);
  return null;
}

function openF1Requests(contract) {
  const meetingKey = contract?.session?.meeting_key || null;
  const sessionKey = sessionKeyFromContract(contract);
  const year = contract?.session?.year || 2026;
  const sessionName = contract?.session?.session_type || null;
  const sessionParam = sessionKey || 'REQUIRES_SESSION_KEY';

  return [
    {
      request_id: 'openf1_resolve_session',
      endpoint: 'sessions',
      url: queryUrl('sessions', { meeting_key: meetingKey, year, session_name: sessionName }),
      required: true,
      purpose: 'resolve_or_confirm_session_key'
    },
    {
      request_id: 'openf1_drivers',
      endpoint: 'drivers',
      url: queryUrl('drivers', { session_key: sessionParam }),
      required: true,
      purpose: 'driver_identity_and_team_mapping'
    },
    {
      request_id: 'openf1_laps',
      endpoint: 'laps',
      url: queryUrl('laps', { session_key: sessionParam }),
      required: true,
      purpose: 'lap_timing_and_sector_foundation'
    },
    {
      request_id: 'openf1_stints',
      endpoint: 'stints',
      url: queryUrl('stints', { session_key: sessionParam }),
      required: true,
      purpose: 'tyre_compound_stint_and_age_foundation'
    },
    {
      request_id: 'openf1_intervals',
      endpoint: 'intervals',
      url: queryUrl('intervals', { session_key: sessionParam }),
      required: false,
      purpose: 'race_gap_and_traffic_context'
    },
    {
      request_id: 'openf1_position',
      endpoint: 'position',
      url: queryUrl('position', { session_key: sessionParam }),
      required: false,
      purpose: 'track_position_timeline'
    },
    {
      request_id: 'openf1_race_control',
      endpoint: 'race_control',
      url: queryUrl('race_control', { session_key: sessionParam }),
      required: false,
      purpose: 'safety_car_vsc_flags_incidents_and_penalties_context'
    },
    {
      request_id: 'openf1_weather',
      endpoint: 'weather',
      url: queryUrl('weather', { session_key: sessionParam }),
      required: false,
      purpose: 'weather_and_track_condition_context'
    },
    {
      request_id: 'openf1_session_result',
      endpoint: 'session_result',
      url: queryUrl('session_result', { session_key: sessionParam }),
      required: false,
      purpose: 'classification_crosscheck_when_available'
    }
  ];
}

function plannedRequestsForSource(source, contract) {
  if (source.source_id === 'openf1_session_data') {
    return openF1Requests(contract);
  }
  if (source.source_id === 'fastf1_session_cache') {
    return [
      {
        request_id: 'fastf1_cache_manifest',
        endpoint: 'local_or_python_fastf1_cache',
        url: null,
        required: false,
        purpose: 'prepare_fastf1_cache_lookup_for_lap_sector_tyre_crosscheck'
      }
    ];
  }
  if (source.source_id === 'fia_documents_index') {
    return [
      {
        request_id: 'fia_documents_manual_public_index',
        endpoint: 'fia_public_documents',
        url: null,
        required: false,
        purpose: 'record_official_classification_penalty_and_stewards_document_lookup'
      }
    ];
  }
  if (source.source_id === 'formula1_official_event_context') {
    return [
      {
        request_id: 'formula1_public_event_context',
        endpoint: 'formula1_public_site',
        url: null,
        required: false,
        purpose: 'record_public_schedule_context_and_event_identity_lookup'
      }
    ];
  }
  return [];
}

async function fetchJson(url, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal, headers: { accept: 'application/json' } });
    const text = await response.text();
    let json = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = null;
    }
    return {
      ok: response.ok,
      status: response.status,
      row_count: Array.isArray(json) ? json.length : null,
      bytes: Buffer.byteLength(text, 'utf8')
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const policy = readJson(args.policy);
  const contract = readJson(args.contract);

  if (!['dry_run', 'sandbox_live'].includes(args.mode)) {
    console.error(JSON.stringify({ ok: false, error: 'invalid_mode', mode: args.mode }, null, 2));
    process.exit(1);
  }

  const liveFetchEnabled = args.mode === 'sandbox_live' && args.allowLive === true && policy.sandbox_live_fetch_allowed === true;
  const generatedUtc = nowIso();
  const sourcePlan = Array.isArray(contract.source_plan) ? contract.source_plan : [];
  const requestManifest = sourcePlan.map(source => ({
    source_id: source.source_id,
    source_family: source.source_family,
    role: source.role,
    blocking_if_missing: Boolean(source.blocking_if_missing),
    fetch_mode: liveFetchEnabled && source.source_id === 'openf1_session_data' ? 'sandbox_live' : 'manifest_only',
    planned_requests: plannedRequestsForSource(source, contract)
  }));

  const fetchResults = [];
  if (liveFetchEnabled) {
    for (const group of requestManifest.filter(item => item.source_id === 'openf1_session_data')) {
      for (const request of group.planned_requests.filter(item => item.url && !item.url.includes('REQUIRES_SESSION_KEY'))) {
        const result = await fetchJson(request.url, policy.default_timeout_seconds * 1000);
        fetchResults.push({ request_id: request.request_id, url: request.url, ...result });
      }
    }
  }

  const status = {
    ok: contract.ok === true && requestManifest.length > 0,
    schema_version: 'f1_session_source_fetch_adapter_status_v30h_2026-06-16',
    generated_utc: generatedUtc,
    mode: args.mode,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    live_fetch_enabled: liveFetchEnabled,
    workbook_write_allowed: false,
    notification_sending_enabled: false,
    policy_schema_version: policy.schema_version,
    contract_schema_version: contract.schema_version,
    session: contract.session,
    source_count: requestManifest.length,
    request_count: requestManifest.reduce((count, group) => count + group.planned_requests.length, 0),
    request_manifest: requestManifest,
    fetch_results: fetchResults,
    cache_dir: args.cacheDir,
    next_step: 'v30I_source_validation_summary_after_review'
  };

  writeJson(args.out, status);
  const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
  writeJson(path.join(args.logDir, `v30h_run_${stamp}.json`), status);

  console.log(JSON.stringify({
    ok: status.ok,
    out: args.out,
    mode: args.mode,
    live_fetch_enabled: status.live_fetch_enabled,
    source_count: status.source_count,
    request_count: status.request_count
  }, null, 2));

  process.exit(status.ok ? 0 : 1);
}

main().catch(error => {
  console.error(JSON.stringify({ ok: false, error: String(error), stack: String(error?.stack || '') }, null, 2));
  process.exit(1);
});
