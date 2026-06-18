#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const VERSION = 'v33C';
const OPENF1_BASE_URL = 'https://api.openf1.org/v1';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_controlled_sandbox_live_source_pull_policy_v33c.json';
const DEFAULT_OUT = 'health/session_processor_controlled_sandbox_live_source_pull_v33c_status.json';
const DEFAULT_SANDBOX_DIR = 'sandbox/session_sources/v33c';
const REQUIRED_APPROVAL = 'APPROVE_V33C_CONTROLLED_SANDBOX_LIVE_SOURCE_PULL';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    allow_live: false,
    operator_approval: '',
    policy: DEFAULT_POLICY,
    event: '',
    fixture: '',
    out: DEFAULT_OUT,
    sandbox_dir: DEFAULT_SANDBOX_DIR,
    log_dir: '',
    timeout_seconds: 15,
    production_automation: false,
    workbook_write: false,
    ledger_write: false,
    race_predictions_refresh: false,
    fantasy_predictions_refresh: false,
    notification_send: false,
    model_promotion: false,
    activate: false
  };

  const aliases = new Map([
    ['allow-live', 'allow_live'],
    ['operator-approval', 'operator_approval'],
    ['sandbox-dir', 'sandbox_dir'],
    ['log-dir', 'log_dir'],
    ['timeout-seconds', 'timeout_seconds'],
    ['production-automation', 'production_automation'],
    ['workbook-write', 'workbook_write'],
    ['ledger-write', 'ledger_write'],
    ['race-predictions-refresh', 'race_predictions_refresh'],
    ['fantasy-predictions-refresh', 'fantasy_predictions_refresh'],
    ['notification-send', 'notification_send'],
    ['model-promotion', 'model_promotion']
  ]);

  const booleans = new Set([
    'allow_live',
    'production_automation',
    'workbook_write',
    'ledger_write',
    'race_predictions_refresh',
    'fantasy_predictions_refresh',
    'notification_send',
    'model_promotion',
    'activate'
  ]);

  for (let i = 2; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith('--')) continue;
    const raw = item.slice(2);
    const key = aliases.get(raw) || raw.replaceAll('-', '_');
    if (!(key in args)) throw new Error(`Unknown argument: --${raw}`);
    const next = argv[i + 1];
    if (booleans.has(key)) {
      if (next === 'true' || next === 'false') {
        args[key] = next === 'true';
        i += 1;
      } else {
        args[key] = true;
      }
    } else if (key === 'timeout_seconds') {
      if (!next || next.startsWith('--')) throw new Error(`Missing value for --${raw}`);
      args[key] = Number(next);
      i += 1;
    } else {
      if (!next || next.startsWith('--')) throw new Error(`Missing value for --${raw}`);
      args[key] = next;
      i += 1;
    }
  }

  return args;
}

function readJsonMaybe(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function lower(value) {
  return String(value || '').toLowerCase();
}

function classifySessionEvent(event) {
  if (!event) {
    return {
      gate_detected: false,
      reason: 'missing_event_payload',
      event_name: 'unknown_event',
      session_name: 'unknown_session',
      session_key: null,
      meeting_key: null,
      year: 2026
    };
  }

  const eventType = lower(event.event_type || event.type || event.kind || event.signal || '');
  const status = lower(event.session_status || event.status || event.state || '');
  const explicit = event.gate_detected === true
    || event.session_end_detected === true
    || event.session_complete === true
    || event.session_completed === true;
  const terminalTypes = new Set([
    'session_end',
    'session_complete',
    'session_completed',
    'race_session_complete',
    'chequered_flag',
    'post_session',
    'classification_posted'
  ]);
  const terminalStatuses = new Set([
    'ended',
    'complete',
    'completed',
    'final',
    'official',
    'classified',
    'session_complete'
  ]);

  const rawSessionKey = event.session_key ?? event.session_id ?? null;
  const sessionKey = typeof rawSessionKey === 'number'
    ? rawSessionKey
    : (/^\d+$/.test(String(rawSessionKey || '')) ? Number(rawSessionKey) : null);

  return {
    gate_detected: explicit || terminalTypes.has(eventType) || terminalStatuses.has(status),
    reason: explicit || terminalTypes.has(eventType) || terminalStatuses.has(status)
      ? 'session_end_signal_detected'
      : 'no_session_end_signal',
    event_type: eventType || null,
    session_status: status || null,
    event_name: event.event || event.grand_prix || event.race || event.meeting || 'unknown_event',
    session_name: event.session || event.session_name || event.session_type || 'unknown_session',
    session_key: sessionKey,
    meeting_key: event.meeting_key ?? null,
    year: event.year || 2026,
    source_timestamp_utc: event.source_timestamp_utc || event.timestamp_utc || event.generated_utc || null
  };
}

function queryUrl(endpoint, params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value));
  }
  return `${OPENF1_BASE_URL}/${endpoint}${search.toString() ? `?${search.toString()}` : ''}`;
}

function requestManifest(gate, policy) {
  const sessionParam = gate.session_key || 'REQUIRES_SESSION_KEY';
  const base = [
    {
      request_id: 'openf1_resolve_session',
      endpoint: 'sessions',
      required: true,
      url: queryUrl('sessions', {
        year: gate.year,
        meeting_key: gate.meeting_key,
        session_name: gate.session_name
      })
    },
    {
      request_id: 'openf1_drivers',
      endpoint: 'drivers',
      required: true,
      url: queryUrl('drivers', { session_key: sessionParam })
    },
    {
      request_id: 'openf1_laps',
      endpoint: 'laps',
      required: true,
      url: queryUrl('laps', { session_key: sessionParam })
    },
    {
      request_id: 'openf1_stints',
      endpoint: 'stints',
      required: true,
      url: queryUrl('stints', { session_key: sessionParam })
    },
    {
      request_id: 'openf1_position',
      endpoint: 'position',
      required: false,
      url: queryUrl('position', { session_key: sessionParam })
    },
    {
      request_id: 'openf1_intervals',
      endpoint: 'intervals',
      required: false,
      url: queryUrl('intervals', { session_key: sessionParam })
    },
    {
      request_id: 'openf1_race_control',
      endpoint: 'race_control',
      required: false,
      url: queryUrl('race_control', { session_key: sessionParam })
    },
    {
      request_id: 'openf1_weather',
      endpoint: 'weather',
      required: false,
      url: queryUrl('weather', { session_key: sessionParam })
    }
  ];

  const allowedIds = new Set(policy.allowed_openf1_request_ids || base.map((item) => item.request_id));
  return base.filter((item) => allowedIds.has(item.request_id));
}

async function fetchJson(url, timeoutSeconds) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), Math.max(1, timeoutSeconds) * 1000);
  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: { accept: 'application/json' }
    });
    const text = await response.text();
    let json = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = null;
    }
    return {
      ok: response.ok,
      http_status: response.status,
      row_count: Array.isArray(json) ? json.length : null,
      bytes: Buffer.byteLength(text, 'utf8'),
      first_row_keys: Array.isArray(json) && json[0] && typeof json[0] === 'object'
        ? Object.keys(json[0]).sort()
        : []
    };
  } catch (error) {
    return {
      ok: false,
      http_status: null,
      row_count: null,
      bytes: 0,
      error: String(error?.name || error)
    };
  } finally {
    clearTimeout(timeout);
  }
}

function runtimeSafetyIssues(args, policy) {
  const issues = [];
  if (!policy || policy.production_automation !== 'OFF') issues.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') issues.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) issues.push('policy_promotion_allowed_not_false');
  if (policy.stable_engine_protected !== true) issues.push('policy_stable_engine_not_protected');
  if (policy.canonical_workbook_protected !== true) issues.push('policy_canonical_workbook_not_protected');

  for (const flag of policy.required_false_flags || []) {
    if (args[flag] !== false) issues.push(`runtime_flag_${flag}_must_remain_false`);
  }

  if (!policy.allowed_modes.includes(args.mode)) issues.push(`mode_not_allowed:${args.mode}`);
  if (args.mode !== 'sandbox_live' && args.allow_live === true) issues.push('allow_live_true_only_valid_in_sandbox_live_mode');
  if (args.mode === 'sandbox_live') {
    if (args.allow_live !== true) issues.push('sandbox_live_requires_allow_live_true');
    if (policy.sandbox_live_fetch_allowed !== true) issues.push('sandbox_live_not_allowed_by_policy');
    if (policy.sandbox_live_requires_operator_approval === true && args.operator_approval !== REQUIRED_APPROVAL) {
      issues.push('sandbox_live_requires_exact_operator_approval');
    }
  }

  return issues;
}

async function collectResults(args, policy, manifest) {
  if (args.mode === 'fixture') {
    const fixture = readJsonMaybe(args.fixture);
    if (!fixture) return { results: [], error: 'missing_fixture' };
    return {
      results: Array.isArray(fixture.fetch_results) ? fixture.fetch_results : [],
      error: null
    };
  }

  if (!(args.mode === 'sandbox_live' && args.allow_live === true && policy.sandbox_live_fetch_allowed === true)) {
    return { results: [], error: null };
  }

  const results = [];
  for (const request of manifest.filter((item) => item.url && !item.url.includes('REQUIRES_SESSION_KEY'))) {
    const result = await fetchJson(request.url, args.timeout_seconds);
    results.push({
      request_id: request.request_id,
      endpoint: request.endpoint,
      required: request.required === true,
      url: request.url,
      ...result
    });
  }
  return { results, error: null };
}

function validateResults(policy, manifest, results, shouldHaveData) {
  const requiredIds = Array.isArray(policy.required_openf1_request_ids) ? policy.required_openf1_request_ids : [];
  const manifestIds = new Set(manifest.map((item) => item.request_id));
  const resultById = new Map(results.map((item) => [item.request_id, item]));
  const missingManifestRequests = requiredIds.filter((id) => !manifestIds.has(id));
  const requiredFailures = [];
  const degradedSources = [];

  if (shouldHaveData) {
    for (const id of requiredIds) {
      const result = resultById.get(id);
      if (!result) {
        requiredFailures.push({ request_id: id, issue: 'missing_fetch_result' });
      } else if (result.ok !== true) {
        requiredFailures.push({
          request_id: id,
          issue: 'fetch_not_ok',
          http_status: result.http_status ?? null,
          error: result.error || null
        });
      } else if (policy.require_nonempty_required_results === true && !(Number(result.row_count) > 0)) {
        requiredFailures.push({
          request_id: id,
          issue: 'empty_required_result',
          row_count: result.row_count ?? null
        });
      }
    }

    for (const result of results.filter((item) => item.required !== true)) {
      if (result.ok !== true || !(Number(result.row_count) > 0)) {
        degradedSources.push({
          request_id: result.request_id,
          issue: result.ok === true ? 'optional_source_empty' : 'optional_source_fetch_not_ok',
          http_status: result.http_status ?? null,
          row_count: result.row_count ?? null
        });
      }
    }
  }

  const rowCountTotal = results.reduce((sum, item) => sum + (Number(item.row_count) || 0), 0);
  return {
    missing_manifest_requests: missingManifestRequests,
    required_failures: requiredFailures,
    degraded_sources: degradedSources,
    row_count_total: rowCountTotal,
    required_result_count: requiredIds.length,
    fetch_result_count: results.length
  };
}

function derivePullStatus({ safetyIssues, gate, collection, validation, args, liveFetchPerformed }) {
  if (safetyIssues.length > 0) return { status: 'BLOCKED', reason: 'governance_or_runtime_safety_issue' };
  if (!gate.gate_detected) return { status: 'NO_SESSION_GATE', reason: gate.reason };
  if (collection.error) return { status: 'BLOCKED', reason: collection.error };
  if (validation.missing_manifest_requests.length > 0) return { status: 'BLOCKED', reason: 'missing_required_manifest_requests' };
  if ((args.mode === 'fixture' || liveFetchPerformed) && validation.required_failures.length > 0) {
    return { status: 'BLOCKED', reason: 'required_source_fetch_failed' };
  }
  if ((args.mode === 'fixture' || liveFetchPerformed) && collection.results.length > 0) {
    return {
      status: validation.degraded_sources.length > 0 ? 'SANDBOX_SOURCE_EVIDENCE_DEGRADED' : 'SANDBOX_SOURCE_EVIDENCE_READY',
      reason: validation.degraded_sources.length > 0
        ? 'required_sources_ready_optional_sources_degraded'
        : 'required_sources_ready'
    };
  }
  return { status: 'PULL_MANIFEST_READY_NO_LIVE_FETCH', reason: 'dry_run_manifest_ready' };
}

function buildSourceSummary(decision, validation, collection, gate) {
  return {
    source_readiness: decision.status,
    source_reason: decision.reason,
    event_name: gate.event_name,
    session_name: gate.session_name,
    session_key: gate.session_key,
    meeting_key: gate.meeting_key,
    source_timestamp_utc: gate.source_timestamp_utc,
    fetch_result_count: validation.fetch_result_count,
    row_count_total: validation.row_count_total,
    required_failures: validation.required_failures,
    degraded_sources: validation.degraded_sources,
    source_ids: collection.results.map((item) => ({
      request_id: item.request_id,
      endpoint: item.endpoint,
      required: item.required === true,
      ok: item.ok === true,
      row_count: item.row_count ?? null,
      http_status: item.http_status ?? null
    }))
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const event = readJsonMaybe(args.event);
  const gate = classifySessionEvent(event);
  const safetyIssues = runtimeSafetyIssues(args, policy);
  const manifest = gate.gate_detected ? requestManifest(gate, policy) : [];
  const liveFetchPerformed = safetyIssues.length === 0
    && gate.gate_detected
    && args.mode === 'sandbox_live'
    && args.allow_live === true
    && policy.sandbox_live_fetch_allowed === true;
  const collection = safetyIssues.length === 0 && gate.gate_detected
    ? await collectResults(args, policy, manifest)
    : { results: [], error: null };
  const validation = validateResults(policy, manifest, collection.results, args.mode === 'fixture' || liveFetchPerformed);
  const decision = derivePullStatus({ safetyIssues, gate, collection, validation, args, liveFetchPerformed });
  const generatedUtc = nowIso();
  const stamp = generatedUtc.replaceAll(':', '').replaceAll('-', '').replaceAll('.', '');
  const sandboxArtifactPath = ['SANDBOX_SOURCE_EVIDENCE_READY', 'SANDBOX_SOURCE_EVIDENCE_DEGRADED'].includes(decision.status)
    ? path.join(args.sandbox_dir, `source_evidence_${stamp}.json`)
    : null;
  const sourceSummary = buildSourceSummary(decision, validation, collection, gate);
  const ok = !['BLOCKED'].includes(decision.status);

  const status = {
    schema_version: 'f1_session_processor_controlled_sandbox_live_source_pull_v33c_2026-06-17',
    generated_utc: generatedUtc,
    version: VERSION,
    ok,
    mode: args.mode,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    workbook_write_allowed: false,
    ledger_write_allowed: false,
    prediction_refresh_enabled: false,
    fantasy_refresh_enabled: false,
    notification_send_enabled: false,
    live_fetch_performed: liveFetchPerformed,
    sandbox_artifact_written: Boolean(sandboxArtifactPath),
    sandbox_artifact_path: sandboxArtifactPath,
    pull_status: decision.status,
    pull_reason: decision.reason,
    gate,
    runtime_safety_issues: safetyIssues,
    request_manifest: manifest,
    fetch_results: collection.results,
    validation,
    source_summary: sourceSummary,
    side_effects: {
      activation_performed: false,
      production_automation: false,
      workbook_write: false,
      canonical_workbook_write: false,
      production_ledger_write: false,
      race_predictions_refresh: false,
      fantasy_predictions_refresh: false,
      notification_send: false,
      model_promotion: false,
      stable_engine_modified: false
    },
    consumer_gates: {
      quality_review_enabled: decision.status === 'SANDBOX_SOURCE_EVIDENCE_READY' || decision.status === 'SANDBOX_SOURCE_EVIDENCE_DEGRADED',
      forecast_bundle_publish_enabled: false,
      canonical_workbook_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: decision.status === 'SANDBOX_SOURCE_EVIDENCE_READY' || decision.status === 'SANDBOX_SOURCE_EVIDENCE_DEGRADED'
      ? 'v33D_sandbox_live_source_quality_review'
      : 'resolve_v33c_source_pull_before_v33d'
  };

  writeJson(args.out, status);
  if (sandboxArtifactPath) writeJson(sandboxArtifactPath, status);
  if (args.log_dir) writeJson(path.join(args.log_dir, `v33c_run_${stamp}.json`), status);

  console.log(JSON.stringify({
    ok: status.ok,
    mode: status.mode,
    pull_status: status.pull_status,
    pull_reason: status.pull_reason,
    gate_detected: gate.gate_detected,
    live_fetch_performed: liveFetchPerformed,
    sandbox_artifact_written: status.sandbox_artifact_written,
    fetch_result_count: validation.fetch_result_count,
    row_count_total: validation.row_count_total,
    next_step: status.next_step
  }, null, 2));

  process.exit(ok ? 0 : 1);
}

main().catch((error) => {
  console.error(JSON.stringify({
    ok: false,
    error: String(error),
    stack: String(error?.stack || '')
  }, null, 2));
  process.exit(1);
});
