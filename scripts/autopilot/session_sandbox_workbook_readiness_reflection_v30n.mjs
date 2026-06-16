#!/usr/bin/env node
/*
 * F1 v30N Sandbox Workbook Readiness Reflection.
 *
 * Converts v30L/v30M Control Room source-cache readiness into a workbook-
 * compatible sandbox JSON artifact. This does not write the canonical workbook,
 * refresh forecasts, refresh race/fantasy consumers, send notifications, or
 * promote model logic.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_sandbox_workbook_readiness_reflection_policy_v30n.json',
    sourceSummary: 'health/session_control_room_source_cache_summary_v30l_status.json',
    snapshotDiff: 'health/session_control_room_snapshot_diff_v30m_status.json',
    out: 'health/session_sandbox_workbook_readiness_reflection_v30n_status.json',
    artifactDir: 'artifacts/sandbox_workbook_readiness',
    logDir: 'logs/session_sandbox_workbook_readiness_reflection'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--source-summary' && value) { args.sourceSummary = value; i += 1; }
    else if (key === '--snapshot-diff' && value) { args.snapshotDiff = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--artifact-dir' && value) { args.artifactDir = value; i += 1; }
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

function validateGovernance(sourceSummary, snapshotDiff) {
  const issues = [];
  for (const [label, artifact] of [['source_summary', sourceSummary], ['snapshot_diff', snapshotDiff]]) {
    if (!artifact) {
      issues.push({ label, issue: 'missing_artifact' });
      continue;
    }
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

function artifactPath(artifactDir, generatedUtc) {
  const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
  return path.join(artifactDir, `sandbox_workbook_readiness_${stamp}.json`);
}

function readinessRows(sourceSummary, snapshotDiff) {
  const artifactRows = Array.isArray(sourceSummary.artifacts)
    ? sourceSummary.artifacts.map(artifact => ({
      section: 'source_artifact',
      key: artifact.label,
      status: artifact.validation_status || 'unknown',
      present: artifact.present === true,
      ok: artifact.ok === true,
      manifest_ready: artifact.manifest_ready === true,
      data_ready: artifact.data_ready === true,
      cache_ready: artifact.cache_ready === true,
      row_count_total: Number.isFinite(artifact.row_count_total) ? artifact.row_count_total : null
    }))
    : [];

  return [
    {
      section: 'control_room',
      key: 'summary_status',
      status: sourceSummary.summary_status || 'unknown',
      present: true,
      ok: sourceSummary.ok === true,
      manifest_ready: sourceSummary.source_validation_ready === true && sourceSummary.openf1_probe_ready === true,
      data_ready: sourceSummary.cache_data_ready === true,
      cache_ready: sourceSummary.cache_contract_ready === true,
      row_count_total: null
    },
    {
      section: 'control_room',
      key: 'material_change',
      status: snapshotDiff.material_change_detected === true ? 'material_change_detected' : 'no_material_change',
      present: true,
      ok: snapshotDiff.ok === true,
      manifest_ready: true,
      data_ready: sourceSummary.cache_data_ready === true,
      cache_ready: sourceSummary.cache_contract_ready === true,
      row_count_total: null
    },
    ...artifactRows
  ];
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30N only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJson(args.policy);
const sourceSummary = readJson(args.sourceSummary);
const snapshotDiff = readJson(args.snapshotDiff);
const generatedUtc = nowIso();
const governanceIssues = validateGovernance(sourceSummary, snapshotDiff);
const sourceReady = sourceSummary.ok === true && ['source_cache_contract_ready_dry_run', 'source_cache_data_ready_dry_run'].includes(sourceSummary.summary_status);
const diffReady = snapshotDiff.ok === true;
const sandboxReady = sourceReady && diffReady && governanceIssues.length === 0;
const rows = readinessRows(sourceSummary, snapshotDiff);
const workbookArtifactPath = artifactPath(args.artifactDir, generatedUtc);

const workbookCompatibleArtifact = {
  schema_version: 'f1_sandbox_workbook_readiness_artifact_v30n_2026-06-16',
  generated_utc: generatedUtc,
  source_summary_schema_version: sourceSummary.schema_version,
  snapshot_diff_schema_version: snapshotDiff.schema_version,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  canonical_workbook_path: null,
  workbook_write_allowed: false,
  notification_sending_enabled: false,
  workbook_target: 'sandbox_json_artifact_only',
  readiness_status: sourceSummary.cache_data_ready === true ? 'data_ready_for_review' : 'contract_ready_for_review',
  material_change_detected: snapshotDiff.material_change_detected === true,
  material_change_count: snapshotDiff.material_change_count || 0,
  source_cache_summary_status: sourceSummary.summary_status,
  rows,
  consumer_gates: {
    workbook_refresh_allowed: false,
    forecast_bundle_refresh_allowed: false,
    race_predictions_refresh_allowed: false,
    fantasy_readiness_refresh_allowed: false,
    notification_sending_allowed: false,
    reason: 'v30n_sandbox_artifact_only_no_canonical_workbook_write'
  }
};

if (sandboxReady) {
  writeJson(workbookArtifactPath, workbookCompatibleArtifact);
}

const status = {
  ok: sandboxReady,
  schema_version: 'f1_session_sandbox_workbook_readiness_reflection_status_v30n_2026-06-16',
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
  source_summary_schema_version: sourceSummary.schema_version,
  snapshot_diff_schema_version: snapshotDiff.schema_version,
  sandbox_readiness_status: workbookCompatibleArtifact.readiness_status,
  sandbox_artifact_written: sandboxReady,
  sandbox_artifact_path: sandboxReady ? workbookArtifactPath : null,
  readiness_row_count: rows.length,
  material_change_detected: snapshotDiff.material_change_detected === true,
  governance_issues: governanceIssues,
  consumer_gates: workbookCompatibleArtifact.consumer_gates,
  next_step: 'v30O_material_change_notifier_dry_run_after_review'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, `v30n_run_${stamp}.json`), status);

console.log(JSON.stringify({
  ok: status.ok,
  out: args.out,
  sandbox_readiness_status: status.sandbox_readiness_status,
  sandbox_artifact_written: status.sandbox_artifact_written,
  sandbox_artifact_path: status.sandbox_artifact_path,
  readiness_row_count: status.readiness_row_count
}, null, 2));

process.exit(status.ok ? 0 : 1);
