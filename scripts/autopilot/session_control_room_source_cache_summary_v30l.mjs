#!/usr/bin/env node
/*
 * F1 v30L Control Room Source Cache Summary.
 *
 * Aggregates v30I/v30J/v30K readiness artifacts into a Control Room style
 * dry-run status. This does not mutate workbook, forecast, prediction,
 * fantasy, notification, stable-engine, or canonical workbook paths.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_control_room_source_cache_summary_policy_v30l.json',
    sourceValidation: 'health/session_source_validation_summary_v30i_status.json',
    openf1Probe: 'health/session_openf1_sandbox_probe_v30j_status.json',
    cacheStatus: 'health/session_source_cache_artifact_v30k_status.json',
    out: 'health/session_control_room_source_cache_summary_v30l_status.json',
    logDir: 'logs/session_control_room_source_cache_summary'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--source-validation' && value) { args.sourceValidation = value; i += 1; }
    else if (key === '--openf1-probe' && value) { args.openf1Probe = value; i += 1; }
    else if (key === '--cache-status' && value) { args.cacheStatus = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log-dir' && value) { args.logDir = value; i += 1; }
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

function artifactStatus(label, artifact) {
  if (!artifact) return { label, present: false, ok: false, status: 'missing' };
  return {
    label,
    present: true,
    ok: artifact.ok === true,
    schema_version: artifact.schema_version || null,
    generated_utc: artifact.generated_utc || null,
    validation_status: artifact.validation_status || artifact.cache_status || null,
    manifest_ready: artifact.manifest_ready === true,
    data_ready: artifact.data_ready === true,
    cache_ready: artifact.cache_ready === true,
    source_family: artifact.source_family || null,
    session_identity: artifact.session_identity || null,
    row_count_total: Number.isFinite(artifact.row_count_total) ? artifact.row_count_total : null
  };
}

function governanceIssues(artifacts) {
  const issues = [];
  for (const [label, artifact] of artifacts) {
    if (!artifact) continue;
    if (artifact.production_automation !== 'OFF') issues.push({ label, field: 'production_automation', actual: artifact.production_automation, expected: 'OFF' });
    if (artifact.forecast_gate !== 'OFF') issues.push({ label, field: 'forecast_gate', actual: artifact.forecast_gate, expected: 'OFF' });
    if (artifact.promotion_allowed !== false) issues.push({ label, field: 'promotion_allowed', actual: artifact.promotion_allowed, expected: false });
    if (artifact.stable_engine_modified !== false) issues.push({ label, field: 'stable_engine_modified', actual: artifact.stable_engine_modified, expected: false });
    if (artifact.canonical_workbook_overwrite !== false) issues.push({ label, field: 'canonical_workbook_overwrite', actual: artifact.canonical_workbook_overwrite, expected: false });
    if (artifact.workbook_write_allowed !== false) issues.push({ label, field: 'workbook_write_allowed', actual: artifact.workbook_write_allowed, expected: false });
    if (artifact.notification_sending_enabled !== false) issues.push({ label, field: 'notification_sending_enabled', actual: artifact.notification_sending_enabled, expected: false });
  }
  return issues;
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30L only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJsonMaybe(args.policy);
if (!policy) {
  console.error(JSON.stringify({ ok: false, error: 'missing_policy', path: args.policy }, null, 2));
  process.exit(1);
}

const sourceValidation = readJsonMaybe(args.sourceValidation);
const openf1Probe = readJsonMaybe(args.openf1Probe);
const cacheStatus = readJsonMaybe(args.cacheStatus);
const artifacts = [
  ['v30i_source_validation', sourceValidation],
  ['v30j_openf1_probe', openf1Probe],
  ['v30k_cache_status', cacheStatus]
];
const generatedUtc = nowIso();
const artifactSummaries = artifacts.map(([label, artifact]) => artifactStatus(label, artifact));
const missingArtifacts = artifactSummaries.filter(item => !item.present).map(item => item.label);
const governance = governanceIssues(artifacts);
const sourceValidationReady = sourceValidation?.ok === true && sourceValidation?.manifest_ready === true;
const probeReady = openf1Probe?.ok === true && openf1Probe?.manifest_ready === true;
const cacheContractReady = cacheStatus?.ok === true && ['cache_contract_ready', 'cache_artifact_ready'].includes(cacheStatus.cache_status);
const cacheDataReady = cacheStatus?.cache_ready === true && cacheStatus?.cache_status === 'cache_artifact_ready';
const controlRoomReady = missingArtifacts.length === 0 && governance.length === 0 && sourceValidationReady && probeReady && cacheContractReady;
const downstreamDataReady = controlRoomReady && cacheDataReady;

const status = {
  ok: controlRoomReady,
  schema_version: 'f1_session_control_room_source_cache_summary_status_v30l_2026-06-16',
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
  summary_status: downstreamDataReady ? 'source_cache_data_ready_dry_run' : (controlRoomReady ? 'source_cache_contract_ready_dry_run' : 'blocked'),
  source_validation_ready: Boolean(sourceValidationReady),
  openf1_probe_ready: Boolean(probeReady),
  cache_contract_ready: Boolean(cacheContractReady),
  cache_data_ready: Boolean(cacheDataReady),
  missing_artifacts: missingArtifacts,
  governance_issues: governance,
  artifacts: artifactSummaries,
  material_readiness: {
    changed_since_previous: null,
    reason: 'v30L_dry_run_does_not_compare_previous_control_room_snapshot'
  },
  consumer_gates: {
    workbook_refresh_allowed: false,
    forecast_bundle_refresh_allowed: false,
    race_predictions_refresh_allowed: false,
    fantasy_readiness_refresh_allowed: false,
    notification_sending_allowed: false,
    reason: downstreamDataReady
      ? 'source_cache_data_ready_but_consumer_wiring_not_reviewed'
      : 'source_cache_not_data_ready_or_contract_only'
  },
  next_step: 'v30M_control_room_previous_snapshot_diff_or_sandbox_workbook_readiness_after_review'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, `v30l_run_${stamp}.json`), status);

console.log(JSON.stringify({
  ok: status.ok,
  out: args.out,
  summary_status: status.summary_status,
  cache_data_ready: status.cache_data_ready,
  missing_artifacts: status.missing_artifacts,
  governance_issue_count: status.governance_issues.length
}, null, 2));

process.exit(status.ok ? 0 : 1);
