#!/usr/bin/env node
/*
 * F1 v30M Control Room Snapshot Diff.
 *
 * Compares the current v30L source-cache summary with the previous snapshot
 * and records whether the readiness state materially changed. This is still
 * dry-run control-plane infrastructure: no notifications, workbook writes,
 * forecast refreshes, prediction refreshes, model promotion, or production
 * automation are enabled.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_control_room_snapshot_diff_policy_v30m.json',
    current: 'health/session_control_room_source_cache_summary_v30l_status.json',
    previous: 'health/session_control_room_source_cache_summary_previous.json',
    snapshotOut: 'health/session_control_room_source_cache_summary_previous.json',
    out: 'health/session_control_room_snapshot_diff_v30m_status.json',
    logDir: 'logs/session_control_room_snapshot_diff',
    writeSnapshot: true
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--current' && value) { args.current = value; i += 1; }
    else if (key === '--previous' && value) { args.previous = value; i += 1; }
    else if (key === '--snapshot-out' && value) { args.snapshotOut = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log-dir' && value) { args.logDir = value; i += 1; }
    else if (key === '--write-snapshot' && value) { args.writeSnapshot = value === 'true'; i += 1; }
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

function sortedJson(value) {
  if (Array.isArray(value)) return value.map(sortedJson);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, sortedJson(value[key])]));
  }
  return value;
}

function stableString(value) {
  return JSON.stringify(sortedJson(value));
}

function pickComparable(summary) {
  if (!summary) return null;
  if (summary.schema_version === 'f1_session_control_room_source_cache_snapshot_v30m_2026-06-16' && summary.comparable) {
    return summary.comparable;
  }
  return {
    summary_status: summary.summary_status || null,
    ok: summary.ok === true,
    source_validation_ready: summary.source_validation_ready === true,
    openf1_probe_ready: summary.openf1_probe_ready === true,
    cache_contract_ready: summary.cache_contract_ready === true,
    cache_data_ready: summary.cache_data_ready === true,
    missing_artifacts: Array.isArray(summary.missing_artifacts) ? [...summary.missing_artifacts].sort() : [],
    governance_issue_count: Array.isArray(summary.governance_issues) ? summary.governance_issues.length : null,
    consumer_gates: summary.consumer_gates || null,
    artifacts: Array.isArray(summary.artifacts)
      ? summary.artifacts.map(artifact => ({
        label: artifact.label,
        present: artifact.present === true,
        ok: artifact.ok === true,
        validation_status: artifact.validation_status || null,
        manifest_ready: artifact.manifest_ready === true,
        data_ready: artifact.data_ready === true,
        cache_ready: artifact.cache_ready === true,
        source_family: artifact.source_family || null,
        session_identity: artifact.session_identity || null,
        row_count_total: Number.isFinite(artifact.row_count_total) ? artifact.row_count_total : null
      })).sort((a, b) => String(a.label).localeCompare(String(b.label)))
      : []
  };
}

function diffComparable(previous, current) {
  const changes = [];
  const keys = new Set([...Object.keys(previous || {}), ...Object.keys(current || {})]);
  for (const key of [...keys].sort()) {
    const before = previous ? previous[key] : undefined;
    const after = current ? current[key] : undefined;
    if (stableString(before) !== stableString(after)) {
      changes.push({ field: key, before: before ?? null, after: after ?? null });
    }
  }
  return changes;
}

function validateGovernance(summary) {
  const issues = [];
  if (!summary) return [{ field: 'current_summary', issue: 'missing' }];
  if (summary.production_automation !== 'OFF') issues.push({ field: 'production_automation', actual: summary.production_automation, expected: 'OFF' });
  if (summary.forecast_gate !== 'OFF') issues.push({ field: 'forecast_gate', actual: summary.forecast_gate, expected: 'OFF' });
  if (summary.promotion_allowed !== false) issues.push({ field: 'promotion_allowed', actual: summary.promotion_allowed, expected: false });
  if (summary.stable_engine_modified !== false) issues.push({ field: 'stable_engine_modified', actual: summary.stable_engine_modified, expected: false });
  if (summary.canonical_workbook_overwrite !== false) issues.push({ field: 'canonical_workbook_overwrite', actual: summary.canonical_workbook_overwrite, expected: false });
  if (summary.workbook_write_allowed !== false) issues.push({ field: 'workbook_write_allowed', actual: summary.workbook_write_allowed, expected: false });
  if (summary.notification_sending_enabled !== false) issues.push({ field: 'notification_sending_enabled', actual: summary.notification_sending_enabled, expected: false });
  return issues;
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30M only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJsonMaybe(args.policy);
const current = readJsonMaybe(args.current);
const previous = readJsonMaybe(args.previous);
const generatedUtc = nowIso();
const governanceIssues = validateGovernance(current);
const currentComparable = pickComparable(current);
const previousComparable = pickComparable(previous);
const firstSnapshot = previousComparable === null;
const changes = firstSnapshot ? [] : diffComparable(previousComparable, currentComparable);
const materialChange = !firstSnapshot && changes.length > 0;
const snapshot = {
  schema_version: 'f1_session_control_room_source_cache_snapshot_v30m_2026-06-16',
  generated_utc: generatedUtc,
  source_summary_schema_version: current?.schema_version || null,
  source_summary_generated_utc: current?.generated_utc || null,
  comparable: currentComparable
};

if (args.writeSnapshot && currentComparable && governanceIssues.length === 0) {
  writeJson(args.snapshotOut, snapshot);
}

const status = {
  ok: Boolean(policy) && Boolean(currentComparable) && governanceIssues.length === 0,
  schema_version: 'f1_session_control_room_snapshot_diff_status_v30m_2026-06-16',
  generated_utc: generatedUtc,
  mode: args.mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  workbook_write_allowed: false,
  notification_sending_enabled: false,
  policy_schema_version: policy?.schema_version || null,
  current_summary_schema_version: current?.schema_version || null,
  previous_snapshot_schema_version: previous?.schema_version || null,
  first_snapshot: firstSnapshot,
  material_change_detected: materialChange,
  material_change_count: changes.length,
  material_changes: changes,
  snapshot_written: Boolean(args.writeSnapshot && currentComparable && governanceIssues.length === 0),
  snapshot_path: args.writeSnapshot ? args.snapshotOut : null,
  governance_issues: governanceIssues,
  notification_decision: {
    send_notification: false,
    reason: materialChange
      ? 'material_change_detected_but_notification_sending_not_enabled_in_v30m'
      : (firstSnapshot ? 'initial_baseline_snapshot_no_notification' : 'no_material_change')
  },
  consumer_gates: {
    workbook_refresh_allowed: false,
    forecast_bundle_refresh_allowed: false,
    race_predictions_refresh_allowed: false,
    fantasy_readiness_refresh_allowed: false,
    notification_sending_allowed: false,
    reason: 'v30m_diff_only_no_consumer_wiring'
  },
  next_step: 'v30N_sandbox_workbook_readiness_reflection_or_material_change_notifier_after_review'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, `v30m_run_${stamp}.json`), status);

console.log(JSON.stringify({
  ok: status.ok,
  out: args.out,
  first_snapshot: status.first_snapshot,
  material_change_detected: status.material_change_detected,
  material_change_count: status.material_change_count,
  snapshot_written: status.snapshot_written
}, null, 2));

process.exit(status.ok ? 0 : 1);
