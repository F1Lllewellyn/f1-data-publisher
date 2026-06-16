#!/usr/bin/env node
/*
 * F1 v30K Session Source Cache Artifact Writer.
 *
 * Converts a validated v30J OpenF1 sandbox probe status into a durable
 * cache-artifact manifest. This is still sandbox/dry-run infrastructure:
 * no workbook writes, forecast refresh, prediction refresh, notifications,
 * production automation, or model promotion are enabled here.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_source_cache_artifact_policy_v30k.json',
    probe: 'health/session_openf1_sandbox_probe_v30j_status.json',
    out: 'health/session_source_cache_artifact_v30k_status.json',
    cacheDir: 'cache/session_sources',
    logDir: 'logs/session_source_cache_artifact_writer'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--probe' && value) { args.probe = value; i += 1; }
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

function validateGovernance(probe) {
  const issues = [];
  if (probe.production_automation !== 'OFF') issues.push({ field: 'production_automation', actual: probe.production_automation, expected: 'OFF' });
  if (probe.forecast_gate !== 'OFF') issues.push({ field: 'forecast_gate', actual: probe.forecast_gate, expected: 'OFF' });
  if (probe.promotion_allowed !== false) issues.push({ field: 'promotion_allowed', actual: probe.promotion_allowed, expected: false });
  if (probe.stable_engine_modified !== false) issues.push({ field: 'stable_engine_modified', actual: probe.stable_engine_modified, expected: false });
  if (probe.canonical_workbook_overwrite !== false) issues.push({ field: 'canonical_workbook_overwrite', actual: probe.canonical_workbook_overwrite, expected: false });
  if (probe.workbook_write_allowed !== false) issues.push({ field: 'workbook_write_allowed', actual: probe.workbook_write_allowed, expected: false });
  if (probe.notification_sending_enabled !== false) issues.push({ field: 'notification_sending_enabled', actual: probe.notification_sending_enabled, expected: false });
  return issues;
}

function sessionKey(session) {
  if (!session || typeof session !== 'object') return 'unknown_session';
  const year = session.year ?? 'unknown_year';
  const round = session.round ?? 'unknown_round';
  const type = session.session_type ?? 'unknown_type';
  const sessionId = session.session_id ?? 'unknown_session_id';
  return `${year}_round_${round}_${type}_${sessionId}`;
}

function summarizeFetchResults(fetchResults) {
  const results = Array.isArray(fetchResults) ? fetchResults : [];
  return results.map(result => ({
    request_id: result.request_id,
    endpoint: result.endpoint || null,
    ok: result.ok === true,
    status: result.status ?? null,
    row_count: Number.isFinite(result.row_count) ? result.row_count : null,
    bytes: Number.isFinite(result.bytes) ? result.bytes : null
  }));
}

function requiredResultSummary(probe, requiredIds) {
  const results = new Map((Array.isArray(probe.fetch_results) ? probe.fetch_results : []).map(result => [result.request_id, result]));
  return requiredIds.map(requestId => {
    const result = results.get(requestId);
    return {
      request_id: requestId,
      present: Boolean(result),
      ok: result?.ok === true,
      row_count: Number.isFinite(result?.row_count) ? result.row_count : null,
      status: result?.status ?? null
    };
  });
}

function cacheArtifactPath(cacheDir, sourceFamily, sessionIdentity, generatedUtc) {
  const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
  return path.join(cacheDir, sourceFamily, sessionIdentity, `cache_artifact_${stamp}.json`);
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30K only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJson(args.policy);
const probe = readJson(args.probe);
const generatedUtc = nowIso();
const governanceIssues = validateGovernance(probe);
const manifestReady = probe.ok === true && probe.manifest_ready === true && Array.isArray(probe.openf1_requests);
const dataReady = manifestReady && probe.data_ready === true && Array.isArray(probe.fetch_results) && probe.fetch_results.length > 0;
const requiredIds = Array.isArray(policy.required_openf1_request_ids) ? policy.required_openf1_request_ids : [];
const requiredResults = requiredResultSummary(probe, requiredIds);
const requiredFailures = requiredResults.filter(result => !result.present || !result.ok || !(result.row_count > 0));
const cacheReady = dataReady && governanceIssues.length === 0 && requiredFailures.length === 0;
const sourceFamily = 'openf1';
const sessionIdentity = sessionKey(probe.session);
const artifactPath = cacheArtifactPath(args.cacheDir, sourceFamily, sessionIdentity, generatedUtc);
const fetchSummary = summarizeFetchResults(probe.fetch_results);

const cacheArtifact = {
  schema_version: 'f1_session_source_cache_artifact_v30k_2026-06-16',
  generated_utc: generatedUtc,
  source_family: sourceFamily,
  source_id: 'openf1_session_data',
  session_identity: sessionIdentity,
  session: probe.session || null,
  source_probe_schema_version: probe.schema_version || null,
  source_probe_generated_utc: probe.generated_utc || null,
  validation_status: cacheReady ? 'cache_artifact_ready' : (manifestReady ? 'cache_contract_ready' : 'blocked'),
  manifest_ready: Boolean(manifestReady),
  data_ready: Boolean(dataReady),
  cache_ready: Boolean(cacheReady),
  required_result_summary: requiredResults,
  fetch_result_summary: fetchSummary,
  row_count_total: fetchSummary.reduce((sum, result) => sum + (result.row_count || 0), 0),
  bytes_total: fetchSummary.reduce((sum, result) => sum + (result.bytes || 0), 0),
  downstream_refresh_allowed: false,
  downstream_refresh_reason: cacheReady
    ? 'source_cache_ready_requires_control_room_wiring_and_review'
    : 'source_cache_not_data_ready'
};

if (cacheReady) {
  writeJson(artifactPath, cacheArtifact);
}

const status = {
  ok: manifestReady && governanceIssues.length === 0,
  schema_version: 'f1_session_source_cache_artifact_writer_status_v30k_2026-06-16',
  generated_utc: generatedUtc,
  mode: args.mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  workbook_write_allowed: false,
  notification_sending_enabled: false,
  source_family: sourceFamily,
  session_identity: sessionIdentity,
  policy_schema_version: policy.schema_version,
  probe_schema_version: probe.schema_version || null,
  manifest_ready: Boolean(manifestReady),
  data_ready: Boolean(dataReady),
  cache_ready: Boolean(cacheReady),
  cache_status: cacheReady ? 'cache_artifact_ready' : (manifestReady ? 'cache_contract_ready' : 'blocked'),
  cache_artifact_path: cacheReady ? artifactPath : null,
  cache_artifact_written: Boolean(cacheReady),
  governance_issues: governanceIssues,
  required_result_summary: requiredResults,
  required_failures: requiredFailures,
  fetch_result_count: fetchSummary.length,
  row_count_total: cacheArtifact.row_count_total,
  consumer_gates: {
    workbook_refresh_allowed: false,
    forecast_bundle_refresh_allowed: false,
    race_predictions_refresh_allowed: false,
    fantasy_readiness_refresh_allowed: false,
    notification_sending_allowed: false,
    reason: cacheReady
      ? 'source_cache_ready_but_control_room_wiring_not_reviewed'
      : 'source_cache_not_data_ready'
  },
  next_step: 'v30L_control_room_source_cache_summary_dry_run_after_review'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, `v30k_run_${stamp}.json`), status);

console.log(JSON.stringify({
  ok: status.ok,
  out: args.out,
  cache_status: status.cache_status,
  cache_artifact_written: status.cache_artifact_written,
  cache_artifact_path: status.cache_artifact_path,
  data_ready: status.data_ready,
  row_count_total: status.row_count_total
}, null, 2));

process.exit(status.ok ? 0 : 1);
