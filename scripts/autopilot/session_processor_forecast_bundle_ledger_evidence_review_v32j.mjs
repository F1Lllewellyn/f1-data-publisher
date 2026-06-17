import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_forecast_bundle_ledger_evidence_review_policy_v32j.json';
const DEFAULT_OUT = 'health/session_processor_forecast_bundle_ledger_evidence_review_v32j_status.json';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: '',
    status: '',
    artifact: '',
    mode: 'dry_run',
    execute: false,
    activate: false,
    allowLive: false,
    allowProductionLedgerWrite: false,
    allowCanonicalWorkbookWrite: false,
    allowNotificationSend: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--status' && value) { args.status = value; i += 1; }
    else if (key === '--artifact' && value) { args.artifact = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--activate' && value) { args.activate = value === 'true'; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--allow-production-ledger-write' && value) { args.allowProductionLedgerWrite = value === 'true'; i += 1; }
    else if (key === '--allow-canonical-workbook-write' && value) { args.allowCanonicalWorkbookWrite = value === 'true'; i += 1; }
    else if (key === '--allow-notification-send' && value) { args.allowNotificationSend = value === 'true'; i += 1; }
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
  return String(value ?? '').toLowerCase();
}

function isTrue(value) {
  return value === true;
}

function statusOf(payload) {
  if (!payload) return 'missing';
  return String(
    payload.sandbox_forecast_ledger_status ||
    payload.forecast_bundle_ledger_evidence_review_status ||
    payload.status ||
    payload.decision ||
    'present'
  );
}

function readyLike(status) {
  const value = lower(status);
  return value.includes('written_sandbox_only') ||
    value.includes('ready') ||
    value.includes('accepted') ||
    value.includes('passed');
}

function blockedLike(status) {
  const value = lower(status);
  return value.includes('blocked') ||
    value.includes('failed') ||
    value.includes('error') ||
    value.includes('rejected') ||
    value.includes('not_ready');
}

function ageMinutes(generatedUtc) {
  if (!generatedUtc) return Number.POSITIVE_INFINITY;
  const ts = Date.parse(generatedUtc);
  if (!Number.isFinite(ts)) return Number.POSITIVE_INFINITY;
  return (Date.now() - ts) / 60000;
}

function governanceIssues(name, payload) {
  const issues = [];
  if (!payload) return issues;
  if (payload.production_automation && payload.production_automation !== 'OFF') issues.push(`${name}:production_automation_not_off`);
  if (payload.forecast_gate && payload.forecast_gate !== 'OFF') issues.push(`${name}:forecast_gate_not_off`);
  if (isTrue(payload.promotion_allowed) || isTrue(payload.promotion) || isTrue(payload.model_promotion_allowed)) issues.push(`${name}:promotion_not_false`);
  if (isTrue(payload.live_fetch_performed) || isTrue(payload.live_fetch_enabled)) issues.push(`${name}:live_fetch_detected`);
  if (isTrue(payload.execute_performed)) issues.push(`${name}:execute_performed_detected`);
  if (isTrue(payload.activation_performed) || isTrue(payload.activate)) issues.push(`${name}:activation_detected`);
  if (isTrue(payload.forecast_bundle_ledger_write_performed) || isTrue(payload.forecast_bundle_ledger_written)) issues.push(`${name}:production_forecast_ledger_write_detected`);
  if (isTrue(payload.canonical_workbook_overwrite) || isTrue(payload.canonical_workbook_write_enabled) || isTrue(payload.canonical_workbook_written)) issues.push(`${name}:canonical_workbook_write_detected`);
  if (isTrue(payload.notification_sent) || isTrue(payload.notification_send_enabled)) issues.push(`${name}:notification_send_detected`);
  if (isTrue(payload.stable_engine_modified)) issues.push(`${name}:stable_engine_modified_detected`);
  for (const [gate, enabled] of Object.entries(payload.consumer_gates || {})) {
    if (enabled === true) issues.push(`${name}:consumer_gate_open:${gate}`);
  }
  return issues;
}

function artifactIssues(artifact, policy) {
  const issues = [];
  if (!artifact) return ['missing_sandbox_ledger_artifact'];
  if (artifact.artifact_type !== policy.required_artifact_type) issues.push(`artifact_type_mismatch:${artifact.artifact_type || 'missing'}`);
  if (artifact.target !== policy.required_target) issues.push(`artifact_target_mismatch:${artifact.target || 'missing'}`);
  if (artifact.write_scope !== policy.required_write_scope) issues.push(`artifact_write_scope_mismatch:${artifact.write_scope || 'missing'}`);
  if (artifact.production_ledger_target !== 'blocked') issues.push('artifact_production_ledger_target_not_blocked');
  if (artifact.canonical_workbook_target !== 'blocked') issues.push('artifact_canonical_workbook_target_not_blocked');
  if (Number(artifact.row_count ?? 0) < 1) issues.push('artifact_row_count_missing');
  if (Number(artifact.source_count ?? 0) < 1) issues.push('artifact_source_count_missing');
  if (ageMinutes(artifact.generated_utc) > Number(policy.max_artifact_age_minutes ?? 1440)) issues.push('artifact_stale');
  issues.push(...governanceIssues('artifact', artifact));
  return issues;
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const status = readJsonMaybe(args.status);
  const artifact = readJsonMaybe(args.artifact || status?.sandbox_artifact);

  const blockers = [];
  const statusValue = statusOf(status);

  if (!status) blockers.push('missing_v32i_status');
  else if (statusValue !== policy.required_status) blockers.push(`status_mismatch:${statusValue}`);
  else if (!readyLike(statusValue) || blockedLike(statusValue)) blockers.push(`status_not_ready:${statusValue}`);

  if (status && status.sandbox_forecast_ledger_write_performed !== true) blockers.push('sandbox_write_not_performed');
  if (status && status.forecast_bundle_ledger_write_performed !== false) blockers.push('production_ledger_write_not_false');
  if (status && status.canonical_workbook_overwrite !== false) blockers.push('canonical_workbook_overwrite_not_false');

  blockers.push(...artifactIssues(artifact, policy));
  blockers.push(...governanceIssues('status', status));

  if (args.execute) blockers.push('execute_true_not_supported_in_v32j_review');
  if (args.activate) blockers.push('activate_true_not_supported_in_v32j_review');
  if (args.allowLive) blockers.push('allow_live_true_not_supported_in_v32j_review');
  if (args.allowProductionLedgerWrite) blockers.push('production_ledger_write_request_rejected');
  if (args.allowCanonicalWorkbookWrite) blockers.push('canonical_workbook_write_request_rejected');
  if (args.allowNotificationSend) blockers.push('notification_send_request_rejected');
  if (args.mode !== 'dry_run' && args.mode !== 'review') blockers.push(`unsupported_mode:${args.mode}`);

  const ok = blockers.length === 0;
  const output = {
    schema_version: 'f1_session_processor_forecast_bundle_ledger_evidence_review_v32j_2026-06-17',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    live_fetch_performed: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    forecast_bundle_ledger_write_performed: false,
    notification_sent: false,
    forecast_bundle_ledger_evidence_review_status: ok ? 'forecast_bundle_ledger_evidence_review_ready' : 'forecast_bundle_ledger_evidence_review_blocked',
    readiness_quality: ok ? 'sandbox_ledger_artifact_verified' : 'blocked_or_missing_sandbox_ledger_evidence',
    v32i_status: statusValue,
    artifact_type: artifact?.artifact_type || null,
    artifact_target: artifact?.target || null,
    artifact_write_scope: artifact?.write_scope || null,
    artifact_row_count: Number(artifact?.row_count ?? 0),
    artifact_source_count: Number(artifact?.source_count ?? 0),
    artifact_age_minutes: Number.isFinite(ageMinutes(artifact?.generated_utc)) ? Math.round(ageMinutes(artifact?.generated_utc)) : null,
    blockers,
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: ok ? (policy.next_layer || 'v32k_race_predictions_readiness_refresh_preflight_after_review') : 'resolve_v32j_evidence_review_blockers_before_v32k'
  };

  writeJson(args.out, output);
  if (args.log) writeJson(args.log, { ok, generated_utc: output.generated_utc, out: args.out, blocker_count: blockers.length });
  console.log(JSON.stringify({
    ok,
    out: args.out,
    forecast_bundle_ledger_evidence_review_status: output.forecast_bundle_ledger_evidence_review_status,
    readiness_quality: output.readiness_quality,
    blocker_count: blockers.length
  }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
