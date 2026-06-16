#!/usr/bin/env node
/*
 * F1 v30O Material Change Notifier Dry-Run.
 *
 * Builds a notification preview from v30M/v30N readiness changes. It never
 * sends email or external notifications; it only records whether a notification
 * would be warranted after review.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_material_change_notifier_policy_v30o.json',
    snapshotDiff: 'health/session_control_room_snapshot_diff_v30m_status.json',
    sandboxReadiness: 'health/session_sandbox_workbook_readiness_reflection_v30n_status.json',
    out: 'health/session_material_change_notifier_v30o_status.json',
    previewDir: 'artifacts/session_material_change_notifications',
    logDir: 'logs/session_material_change_notifier'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--snapshot-diff' && value) { args.snapshotDiff = value; i += 1; }
    else if (key === '--sandbox-readiness' && value) { args.sandboxReadiness = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--preview-dir' && value) { args.previewDir = value; i += 1; }
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

function validateGovernance(snapshotDiff, sandboxReadiness) {
  const issues = [];
  for (const [label, artifact] of [['snapshot_diff', snapshotDiff], ['sandbox_readiness', sandboxReadiness]]) {
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

function changeSeverity(change) {
  if (change.field === 'summary_status') return 'high';
  if (change.field === 'cache_data_ready') return 'high';
  if (change.field === 'missing_artifacts') return 'high';
  if (change.field === 'governance_issue_count') return 'high';
  if (change.field === 'artifacts') return 'medium';
  if (change.field === 'consumer_gates') return 'low';
  return 'low';
}

function summarizeChanges(changes) {
  return changes.map(change => ({
    field: change.field,
    severity: changeSeverity(change),
    before: change.before ?? null,
    after: change.after ?? null
  }));
}

function highestSeverity(changeSummary) {
  if (changeSummary.some(change => change.severity === 'high')) return 'high';
  if (changeSummary.some(change => change.severity === 'medium')) return 'medium';
  if (changeSummary.length) return 'low';
  return 'none';
}

function previewPath(previewDir, generatedUtc) {
  const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
  return path.join(previewDir, `material_change_notification_preview_${stamp}.json`);
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30O only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJson(args.policy);
const snapshotDiff = readJson(args.snapshotDiff);
const sandboxReadiness = readJson(args.sandboxReadiness);
const generatedUtc = nowIso();
const governanceIssues = validateGovernance(snapshotDiff, sandboxReadiness);
const changes = Array.isArray(snapshotDiff.material_changes) ? snapshotDiff.material_changes : [];
const changeSummary = summarizeChanges(changes);
const severity = highestSeverity(changeSummary);
const materialChange = snapshotDiff.material_change_detected === true && changes.length > 0;
const sandboxReady = sandboxReadiness.ok === true;
const wouldNotify = materialChange && sandboxReady && governanceIssues.length === 0;
const notificationSendingEnabled = false;
const preview = {
  schema_version: 'f1_material_change_notification_preview_v30o_2026-06-16',
  generated_utc: generatedUtc,
  notification_type: 'session_readiness_material_change',
  would_notify: wouldNotify,
  sent: false,
  send_blocked_reason: notificationSendingEnabled
    ? null
    : 'notification_sending_disabled_in_v30o_dry_run',
  severity,
  subject: wouldNotify
    ? `F1 Source Readiness Material Change: ${sandboxReadiness.sandbox_readiness_status}`
    : 'F1 Source Readiness: no notification',
  summary: {
    sandbox_readiness_status: sandboxReadiness.sandbox_readiness_status,
    material_change_detected: materialChange,
    material_change_count: changes.length,
    sandbox_artifact_path: sandboxReadiness.sandbox_artifact_path || null
  },
  changes: changeSummary,
  consumer_gates: {
    workbook_refresh_allowed: false,
    forecast_bundle_refresh_allowed: false,
    race_predictions_refresh_allowed: false,
    fantasy_readiness_refresh_allowed: false,
    notification_sending_allowed: false,
    reason: 'v30o_preview_only_no_notification_send'
  }
};

let previewFilePath = null;
if (wouldNotify || policy.write_preview_when_no_change === true) {
  previewFilePath = previewPath(args.previewDir, generatedUtc);
  writeJson(previewFilePath, preview);
}

const status = {
  ok: snapshotDiff.ok === true && sandboxReadiness.ok === true && governanceIssues.length === 0,
  schema_version: 'f1_session_material_change_notifier_status_v30o_2026-06-16',
  generated_utc: generatedUtc,
  mode: args.mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  workbook_write_allowed: false,
  notification_sending_enabled: notificationSendingEnabled,
  policy_schema_version: policy.schema_version,
  snapshot_diff_schema_version: snapshotDiff.schema_version,
  sandbox_readiness_schema_version: sandboxReadiness.schema_version,
  material_change_detected: materialChange,
  material_change_count: changes.length,
  material_change_severity: severity,
  notification_would_send: wouldNotify,
  notification_sent: false,
  preview_written: Boolean(previewFilePath),
  preview_path: previewFilePath,
  governance_issues: governanceIssues,
  notification_decision: {
    send_notification: false,
    would_send_if_enabled: wouldNotify,
    reason: wouldNotify
      ? 'material_change_detected_but_v30o_is_dry_run'
      : 'no_material_change_or_readiness_not_valid'
  },
  consumer_gates: preview.consumer_gates,
  next_step: 'v30P_end_to_end_control_room_orchestrator_dry_run_after_review'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, `v30o_run_${stamp}.json`), status);

console.log(JSON.stringify({
  ok: status.ok,
  out: args.out,
  material_change_detected: status.material_change_detected,
  notification_would_send: status.notification_would_send,
  notification_sent: status.notification_sent,
  preview_written: status.preview_written,
  preview_path: status.preview_path
}, null, 2));

process.exit(status.ok ? 0 : 1);
