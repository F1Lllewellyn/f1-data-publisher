#!/usr/bin/env node
/*
 * F1 v30I Session Source Validation Summary.
 *
 * Validates v30H source-fetch adapter output before any workbook, KPI,
 * forecast bundle, race prediction, or fantasy readiness consumer can use it.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_source_validation_policy_v30i.json',
    adapter: 'health/session_source_fetch_adapter_v30h_status.json',
    out: 'health/session_source_validation_summary_v30i_status.json',
    logDir: 'logs/session_source_validation_summary'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--adapter' && value) { args.adapter = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
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

function flattenRequests(adapter) {
  const groups = Array.isArray(adapter.request_manifest) ? adapter.request_manifest : [];
  return groups.flatMap(group => {
    const planned = Array.isArray(group.planned_requests) ? group.planned_requests : [];
    return planned.map(request => ({
      source_id: group.source_id,
      source_family: group.source_family,
      request_id: request.request_id,
      endpoint: request.endpoint,
      required: Boolean(request.required),
      url: request.url || null,
      purpose: request.purpose || null
    }));
  });
}

function requiredMissing(requiredIds, actualIds) {
  return requiredIds.filter(id => !actualIds.has(id));
}

function validateGovernance(adapter) {
  const issues = [];
  if (adapter.production_automation !== 'OFF') issues.push({ field: 'production_automation', actual: adapter.production_automation, expected: 'OFF' });
  if (adapter.forecast_gate !== 'OFF') issues.push({ field: 'forecast_gate', actual: adapter.forecast_gate, expected: 'OFF' });
  if (adapter.promotion_allowed !== false) issues.push({ field: 'promotion_allowed', actual: adapter.promotion_allowed, expected: false });
  if (adapter.stable_engine_modified !== false) issues.push({ field: 'stable_engine_modified', actual: adapter.stable_engine_modified, expected: false });
  if (adapter.canonical_workbook_overwrite !== false) issues.push({ field: 'canonical_workbook_overwrite', actual: adapter.canonical_workbook_overwrite, expected: false });
  if (adapter.workbook_write_allowed !== false) issues.push({ field: 'workbook_write_allowed', actual: adapter.workbook_write_allowed, expected: false });
  if (adapter.notification_sending_enabled !== false) issues.push({ field: 'notification_sending_enabled', actual: adapter.notification_sending_enabled, expected: false });
  return issues;
}

function validateFetchResults(adapter, requests, policy) {
  const results = Array.isArray(adapter.fetch_results) ? adapter.fetch_results : [];
  const resultById = new Map(results.map(result => [result.request_id, result]));
  const requiredLive = requests.filter(request => request.required && request.url && !request.url.includes('REQUIRES_SESSION_KEY'));
  const requiredLiveFailures = [];

  if (adapter.live_fetch_enabled === true) {
    for (const request of requiredLive) {
      const result = resultById.get(request.request_id);
      if (!result) {
        requiredLiveFailures.push({ request_id: request.request_id, issue: 'missing_fetch_result' });
      } else if (result.ok !== true) {
        requiredLiveFailures.push({ request_id: request.request_id, issue: 'http_not_ok', status: result.status });
      } else if (policy.require_nonempty_required_results && !(result.row_count > 0)) {
        requiredLiveFailures.push({ request_id: request.request_id, issue: 'empty_required_result', row_count: result.row_count });
      }
    }
  }

  return {
    fetch_result_count: results.length,
    required_live_request_count: requiredLive.length,
    required_live_failures: requiredLiveFailures
  };
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30I only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJson(args.policy);
const adapter = readJson(args.adapter);
const requests = flattenRequests(adapter);
const actualRequestIds = new Set(requests.map(request => request.request_id));
const missingRequiredRequests = requiredMissing(policy.required_request_ids, actualRequestIds);
const governanceIssues = validateGovernance(adapter);
const fetchValidation = validateFetchResults(adapter, requests, policy);
const manifestReady = adapter.ok === true && requests.length >= policy.minimum_request_count && missingRequiredRequests.length === 0 && governanceIssues.length === 0;
const dataReady = manifestReady && adapter.live_fetch_enabled === true && fetchValidation.required_live_failures.length === 0 && fetchValidation.fetch_result_count > 0;

const generatedUtc = nowIso();
const status = {
  ok: manifestReady,
  schema_version: 'f1_session_source_validation_summary_status_v30i_2026-06-16',
  generated_utc: generatedUtc,
  mode: args.mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  workbook_write_allowed: false,
  notification_sending_enabled: false,
  policy_schema_version: policy.schema_version,
  adapter_schema_version: adapter.schema_version,
  session: adapter.session || null,
  validation_status: dataReady ? 'data_ready' : (manifestReady ? 'contract_ready' : 'blocked'),
  manifest_ready: manifestReady,
  data_ready: dataReady,
  live_fetch_enabled: adapter.live_fetch_enabled === true,
  source_count: adapter.source_count || 0,
  request_count: requests.length,
  required_request_ids: policy.required_request_ids,
  missing_required_requests: missingRequiredRequests,
  governance_issues: governanceIssues,
  fetch_validation: fetchValidation,
  source_family_coverage: [...new Set(requests.map(request => request.source_family).filter(Boolean))],
  source_ids: [...new Set(requests.map(request => request.source_id).filter(Boolean))],
  consumer_gates: {
    workbook_refresh_allowed: false,
    forecast_bundle_refresh_allowed: dataReady,
    race_predictions_refresh_allowed: dataReady,
    fantasy_readiness_refresh_allowed: dataReady,
    reason: dataReady ? 'source_artifacts_validated' : 'dry_run_contract_ready_but_no_live_source_artifacts'
  },
  next_step: 'v30J_control_room_source_validation_wiring_or_sandbox_live_openf1_probe_after_review'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, `v30i_run_${stamp}.json`), status);

console.log(JSON.stringify({
  ok: status.ok,
  out: args.out,
  validation_status: status.validation_status,
  manifest_ready: status.manifest_ready,
  data_ready: status.data_ready,
  request_count: status.request_count,
  missing_required_requests: status.missing_required_requests
}, null, 2));

process.exit(status.ok ? 0 : 1);
