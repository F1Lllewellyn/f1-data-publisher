#!/usr/bin/env node
/*
 * F1 v30J OpenF1 Sandbox Probe.
 *
 * Probes OpenF1 source availability for a session without touching the stable
 * engine, workbook, forecast gate, model promotion, or notification path.
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
    policy: 'scripts/autopilot/session_openf1_sandbox_probe_policy_v30j.json',
    adapter: 'health/session_source_fetch_adapter_v30h_status.json',
    fixture: '',
    out: 'health/session_openf1_sandbox_probe_v30j_status.json',
    cacheDir: 'cache/session_sources/openf1',
    logDir: 'logs/session_openf1_sandbox_probe'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--adapter' && value) { args.adapter = value; i += 1; }
    else if (key === '--fixture' && value) { args.fixture = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--cache-dir' && value) { args.cacheDir = value; i += 1; }
    else if (key === '--log-dir' && value) { args.logDir = value; i += 1; }
  }

  return args;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function readJsonMaybe(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return readJson(filePath);
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

function normalizeEndpointName(endpoint) {
  if (endpoint === 'race_control') return 'race_control';
  if (endpoint === 'session_result') return 'session_result';
  return endpoint;
}

function openF1Requests(adapter) {
  const groups = Array.isArray(adapter?.request_manifest) ? adapter.request_manifest : [];
  const openF1Group = groups.find(group => group.source_id === 'openf1_session_data');
  const planned = Array.isArray(openF1Group?.planned_requests) ? openF1Group.planned_requests : [];
  return planned
    .filter(request => request.url && request.url.startsWith(OPENF1_BASE_URL))
    .map(request => ({
      request_id: request.request_id,
      endpoint: normalizeEndpointName(request.endpoint),
      url: request.url,
      required: Boolean(request.required),
      purpose: request.purpose || null
    }));
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

async function collectResults(args, policy, requests) {
  if (args.mode === 'fixture') {
    const fixture = readJson(args.fixture);
    return Array.isArray(fixture.fetch_results) ? fixture.fetch_results : [];
  }

  const liveAllowed = args.mode === 'sandbox_live' && args.allowLive === true && policy.sandbox_live_probe_allowed === true;
  if (!liveAllowed) return [];

  const results = [];
  for (const request of requests.filter(item => !item.url.includes('REQUIRES_SESSION_KEY'))) {
    const result = await fetchJson(request.url, policy.default_timeout_seconds * 1000);
    results.push({
      request_id: request.request_id,
      endpoint: request.endpoint,
      url: request.url,
      ...result
    });
  }
  return results;
}

function validateResults(requests, fetchResults, policy, liveFetchEnabled) {
  const byId = new Map(fetchResults.map(result => [result.request_id, result]));
  const requiredRequests = requests.filter(request => policy.required_openf1_request_ids.includes(request.request_id));
  const requiredFailures = [];

  if (liveFetchEnabled) {
    for (const request of requiredRequests.filter(item => !item.url.includes('REQUIRES_SESSION_KEY'))) {
      const result = byId.get(request.request_id);
      if (!result) requiredFailures.push({ request_id: request.request_id, issue: 'missing_fetch_result' });
      else if (result.ok !== true) requiredFailures.push({ request_id: request.request_id, issue: 'http_not_ok', status: result.status });
      else if (policy.require_nonempty_required_results && !(result.row_count > 0)) {
        requiredFailures.push({ request_id: request.request_id, issue: 'empty_required_result', row_count: result.row_count });
      }
    }
  }

  return {
    required_openf1_request_count: requiredRequests.length,
    fetch_result_count: fetchResults.length,
    required_failures: requiredFailures
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const policy = readJson(args.policy);
  const adapter = readJson(args.adapter);

  if (!['dry_run', 'fixture', 'sandbox_live'].includes(args.mode)) {
    console.error(JSON.stringify({ ok: false, error: 'invalid_mode', mode: args.mode }, null, 2));
    process.exit(1);
  }
  if (args.mode === 'fixture' && !readJsonMaybe(args.fixture)) {
    console.error(JSON.stringify({ ok: false, error: 'missing_fixture', fixture: args.fixture }, null, 2));
    process.exit(1);
  }

  const requests = openF1Requests(adapter);
  const liveFetchEnabled = args.mode === 'sandbox_live' && args.allowLive === true && policy.sandbox_live_probe_allowed === true;
  const fixtureMode = args.mode === 'fixture';
  const fetchResults = await collectResults(args, policy, requests);
  const validation = validateResults(requests, fetchResults, policy, liveFetchEnabled || fixtureMode);
  const requestIds = new Set(requests.map(request => request.request_id));
  const missingRequests = policy.required_openf1_request_ids.filter(id => !requestIds.has(id));
  const manifestReady = requests.length >= policy.minimum_openf1_request_count && missingRequests.length === 0;
  const dataReady = (liveFetchEnabled || fixtureMode) && manifestReady && validation.required_failures.length === 0 && fetchResults.length > 0;
  const generatedUtc = nowIso();

  const status = {
    ok: manifestReady && (args.mode === 'dry_run' || dataReady),
    schema_version: 'f1_session_openf1_sandbox_probe_status_v30j_2026-06-16',
    generated_utc: generatedUtc,
    mode: args.mode,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    workbook_write_allowed: false,
    notification_sending_enabled: false,
    live_fetch_enabled: liveFetchEnabled,
    policy_schema_version: policy.schema_version,
    adapter_schema_version: adapter.schema_version,
    session: adapter.session || null,
    validation_status: dataReady ? 'data_ready' : (manifestReady ? 'probe_manifest_ready' : 'blocked'),
    manifest_ready: manifestReady,
    data_ready: dataReady,
    openf1_request_count: requests.length,
    required_missing_requests: missingRequests,
    openf1_requests: requests,
    fetch_results: fetchResults,
    validation,
    cache_dir: args.cacheDir,
    consumer_gates: {
      workbook_refresh_allowed: false,
      forecast_bundle_refresh_allowed: dataReady,
      race_predictions_refresh_allowed: dataReady,
      fantasy_readiness_refresh_allowed: dataReady,
      reason: dataReady ? 'openf1_probe_validated_required_rows' : 'openf1_probe_not_data_ready'
    },
    next_step: 'v30K_source_cache_artifact_writer_or_control_room_validation_wiring_after_review'
  };

  writeJson(args.out, status);
  const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
  writeJson(path.join(args.logDir, `v30j_run_${stamp}.json`), status);

  console.log(JSON.stringify({
    ok: status.ok,
    out: args.out,
    validation_status: status.validation_status,
    manifest_ready: status.manifest_ready,
    data_ready: status.data_ready,
    live_fetch_enabled: status.live_fetch_enabled,
    openf1_request_count: status.openf1_request_count,
    required_missing_requests: status.required_missing_requests
  }, null, 2));

  process.exit(status.ok ? 0 : 1);
}

main().catch(error => {
  console.error(JSON.stringify({ ok: false, error: String(error), stack: String(error?.stack || '') }, null, 2));
  process.exit(1);
});
