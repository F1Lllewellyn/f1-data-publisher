import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_source_pull_evidence_policy_v31a.json';
const DEFAULT_OUT = 'health/session_source_pull_evidence_v31a_status.json';
const DEFAULT_CACHE_DIR = 'logs/source_cache/v31a';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: '',
    cacheDir: DEFAULT_CACHE_DIR,
    event: 'unknown_event',
    session: 'unknown_session',
    mode: 'dry_run',
    allowLive: false,
    timeoutMs: 8000,
    maxBytes: 600000
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--cache-dir' && value) { args.cacheDir = value; i += 1; }
    else if (key === '--event' && value) { args.event = value; i += 1; }
    else if (key === '--session' && value) { args.session = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--timeout-ms' && value) { args.timeoutMs = Number(value); i += 1; }
    else if (key === '--max-bytes' && value) { args.maxBytes = Number(value); i += 1; }
  }
  return args;
}

function readJsonMaybe(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

function sanitizeName(value) {
  return String(value || 'unknown').replace(/[^a-zA-Z0-9._-]+/g, '_').slice(0, 80);
}

function isLiveAllowed(args, policy) {
  return args.mode === 'sandbox_live' && args.allowLive === true && policy.live_fetch_allowed === true;
}

function buildRequests(policy, args) {
  const configured = Array.isArray(policy.sources) ? policy.sources : [];
  return configured.map((source) => {
    const query = Object.entries(source.query || {}).map(([key, value]) => {
      const resolved = String(value)
        .replaceAll('{event}', args.event)
        .replaceAll('{session}', args.session);
      return `${encodeURIComponent(key)}=${encodeURIComponent(resolved)}`;
    }).join('&');
    const url = query ? `${source.url}?${query}` : source.url;
    return {
      source_id: source.source_id,
      provider: source.provider,
      source_type: source.source_type,
      url,
      required_fields: source.required_fields || [],
      expected_min_rows: Number(source.expected_min_rows || 0),
      enabled: source.enabled !== false
    };
  });
}

function detectRows(payload) {
  if (Array.isArray(payload)) return payload.length;
  if (payload && Array.isArray(payload.results)) return payload.results.length;
  if (payload && Array.isArray(payload.data)) return payload.data.length;
  if (payload && Array.isArray(payload.rows)) return payload.rows.length;
  return payload ? 1 : 0;
}

function validateFields(payload, requiredFields) {
  if (!requiredFields.length) return [];
  const sample = Array.isArray(payload) ? payload[0] : (payload?.results?.[0] ?? payload?.data?.[0] ?? payload?.rows?.[0] ?? payload);
  if (!sample || typeof sample !== 'object') return requiredFields;
  return requiredFields.filter((field) => !(field in sample));
}

async function fetchWithTimeout(url, timeoutMs, maxBytes) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal, headers: { accept: 'application/json,text/plain;q=0.8,*/*;q=0.5' } });
    const text = await response.text();
    const truncated = Buffer.byteLength(text, 'utf8') > maxBytes;
    const clipped = truncated ? text.slice(0, maxBytes) : text;
    let json = null;
    try { json = JSON.parse(clipped); } catch {}
    return {
      ok: response.ok,
      http_status: response.status,
      content_type: response.headers.get('content-type') || '',
      byte_count: Buffer.byteLength(text, 'utf8'),
      truncated,
      payload: json ?? clipped
    };
  } finally {
    clearTimeout(timer);
  }
}

async function evaluateRequest(request, args, policy, liveAllowed) {
  const base = {
    source_id: request.source_id,
    provider: request.provider,
    source_type: request.source_type,
    enabled: request.enabled,
    live_fetch_attempted: false,
    live_fetch_performed: false,
    status: 'not_run',
    row_count: 0,
    cache_path: null,
    failures: [],
    warnings: []
  };
  if (!request.enabled) return { ...base, status: 'disabled_by_policy' };
  if (!liveAllowed) {
    return { ...base, status: 'dry_run_not_fetched', warnings: ['live_fetch_disabled_by_policy_or_cli'] };
  }
  const result = { ...base, live_fetch_attempted: true };
  try {
    const fetched = await fetchWithTimeout(request.url, args.timeoutMs, args.maxBytes);
    result.live_fetch_performed = true;
    result.http_status = fetched.http_status;
    result.content_type = fetched.content_type;
    result.byte_count = fetched.byte_count;
    result.truncated = fetched.truncated;
    const rows = detectRows(fetched.payload);
    result.row_count = rows;
    const missingFields = validateFields(fetched.payload, request.required_fields);
    if (!fetched.ok) result.failures.push(`provider_http_${fetched.http_status}`);
    if (rows < request.expected_min_rows) result.failures.push('row_count_below_expected_minimum');
    if (missingFields.length) result.failures.push(`missing_fields:${missingFields.join(',')}`);
    result.status = result.failures.length ? 'source_evidence_degraded' : 'source_evidence_ready';
    const cachePath = path.join(args.cacheDir, `${sanitizeName(request.source_id)}_${Date.now()}.json`);
    writeJson(cachePath, {
      schema_version: 'f1_session_source_pull_evidence_cache_v31a_2026-06-16',
      generated_utc: nowIso(),
      source_id: request.source_id,
      provider: request.provider,
      url: request.url,
      http_status: fetched.http_status,
      content_type: fetched.content_type,
      byte_count: fetched.byte_count,
      truncated: fetched.truncated,
      row_count: rows,
      payload: fetched.payload
    });
    result.cache_path = cachePath;
  } catch (error) {
    result.status = 'source_evidence_failed';
    result.failures.push(String(error?.name || 'fetch_error'));
    result.error = String(error?.message || error);
  }
  return result;
}

function deriveOverall(results, liveAllowed) {
  const enabled = results.filter((item) => item.enabled);
  const failures = results.flatMap((item) => item.failures || []);
  const ready = results.filter((item) => item.status === 'source_evidence_ready');
  const degraded = results.filter((item) => item.status === 'source_evidence_degraded');
  if (!liveAllowed) return { pull_status: 'source_evidence_contract_ready', readiness_quality: 'dry_run_no_live_fetch' };
  if (failures.length) return { pull_status: degraded.length ? 'source_evidence_degraded' : 'source_evidence_failed', readiness_quality: 'source_failures_observed' };
  if (enabled.length && ready.length === enabled.length) return { pull_status: 'source_evidence_ready', readiness_quality: 'sandbox_live_evidence_collected' };
  return { pull_status: 'source_evidence_partial', readiness_quality: 'partial_source_evidence' };
}

async function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const liveAllowed = isLiveAllowed(args, policy);
  const requests = buildRequests(policy, args);
  const results = [];
  for (const request of requests) {
    results.push(await evaluateRequest(request, args, policy, liveAllowed));
  }
  const overall = deriveOverall(results, liveAllowed);
  const status = {
    schema_version: 'f1_session_source_pull_evidence_collector_v31a_2026-06-16',
    generated_utc: nowIso(),
    mode: args.mode,
    event: args.event,
    session: args.session,
    live_fetch_allowed_by_policy: policy.live_fetch_allowed === true,
    live_fetch_requested: args.allowLive,
    live_fetch_performed: results.some((item) => item.live_fetch_performed),
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    workbook_write_enabled: false,
    prediction_refresh_enabled: false,
    fantasy_refresh_enabled: false,
    notification_sending_enabled: false,
    pull_status: overall.pull_status,
    readiness_quality: overall.readiness_quality,
    source_count: results.length,
    ready_source_count: results.filter((item) => item.status === 'source_evidence_ready').length,
    degraded_source_count: results.filter((item) => item.status === 'source_evidence_degraded').length,
    failed_source_count: results.filter((item) => item.status === 'source_evidence_failed').length,
    row_count: results.reduce((sum, item) => sum + Number(item.row_count || 0), 0),
    results,
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: liveAllowed ? 'operator_review_source_evidence_before_any_downstream_consumer' : 'run_with_sandbox_live_flags_after_manual_approval'
  };
  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: status.failed_source_count === 0, generated_utc: status.generated_utc, out: args.out, pull_status: status.pull_status });
  console.log(JSON.stringify({ ok: status.failed_source_count === 0, out: args.out, pull_status: status.pull_status, readiness_quality: status.readiness_quality, row_count: status.row_count }, null, 2));
  process.exit(status.failed_source_count === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
