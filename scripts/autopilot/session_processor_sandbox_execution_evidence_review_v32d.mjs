import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_sandbox_execution_evidence_review_policy_v32d.json';
const DEFAULT_OUT = 'health/session_processor_sandbox_execution_evidence_review_v32d_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    sandboxExecution: '',
    mode: 'dry_run',
    execute: false,
    activate: false,
    allowLive: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--sandbox-execution' && value) { args.sandboxExecution = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--activate' && value) { args.activate = value === 'true'; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
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

function lower(value) {
  return String(value ?? '').toLowerCase();
}

function bool(value) {
  return value === true;
}

function closedGates() {
  return {
    workbook_write_enabled: false,
    canonical_workbook_write_enabled: false,
    forecast_bundle_write_enabled: false,
    race_predictions_refresh_enabled: false,
    fantasy_refresh_enabled: false,
    notification_send_enabled: false,
    production_automation_enabled: false
  };
}

function statusOf(payload) {
  if (!payload) return 'missing';
  return String(payload.sandbox_execution_status || payload.status || payload.decision || 'present');
}

function blockedLike(status) {
  const value = lower(status);
  return value.includes('blocked') || value.includes('failed') || value.includes('error') || value.includes('rejected') || value.includes('not_ready');
}

function governanceIssues(name, payload) {
  const issues = [];
  if (!payload) return issues;
  if (payload.production_automation !== undefined && payload.production_automation !== 'OFF') issues.push(`${name}:production_automation_not_off`);
  if (payload.forecast_gate !== undefined && payload.forecast_gate !== 'OFF') issues.push(`${name}:forecast_gate_not_off`);
  if (bool(payload.promotion_allowed) || bool(payload.promotion) || bool(payload.model_promotion_allowed)) issues.push(`${name}:promotion_not_false`);
  if (bool(payload.live_fetch_performed)) issues.push(`${name}:live_fetch_performed`);
  if (bool(payload.activation_performed)) issues.push(`${name}:activation_performed`);
  if (bool(payload.stable_engine_modified)) issues.push(`${name}:stable_engine_modified`);
  if (bool(payload.canonical_workbook_overwrite)) issues.push(`${name}:canonical_workbook_overwrite`);
  if (bool(payload.workbook_write_performed)) issues.push(`${name}:workbook_write_performed`);
  if (bool(payload.canonical_workbook_write_performed)) issues.push(`${name}:canonical_workbook_write_performed`);
  if (bool(payload.forecast_bundle_ledger_write_performed)) issues.push(`${name}:forecast_bundle_ledger_write_performed`);
  if (bool(payload.race_predictions_refresh_performed)) issues.push(`${name}:race_predictions_refresh_performed`);
  if (bool(payload.fantasy_refresh_performed)) issues.push(`${name}:fantasy_refresh_performed`);
  if (bool(payload.notification_sent)) issues.push(`${name}:notification_sent`);
  const gates = payload.consumer_gates || {};
  for (const [gate, expected] of Object.entries(closedGates())) {
    if (gates[gate] !== undefined && gates[gate] !== expected) issues.push(`${name}:consumer_gate_open:${gate}`);
  }
  return issues;
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const sandboxExecution = readJsonMaybe(args.sandboxExecution);
  const executionStatus = statusOf(sandboxExecution);
  const blockers = [];

  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');
  if (policy.execution_allowed !== false) blockers.push('policy_execution_allowed_not_false');
  if (args.mode !== 'dry_run' && args.mode !== 'review') blockers.push(`unsupported_mode:${args.mode}`);
  if (args.execute) blockers.push('execute_true_rejected_by_v32d_review_gate');
  if (args.activate) blockers.push('activate_true_rejected_by_v32d_review_gate');
  if (args.allowLive) blockers.push('allow_live_true_rejected_by_v32d_review_gate');
  if (!sandboxExecution) blockers.push('missing_required_input:sandbox_execution_status');
  if (sandboxExecution && blockedLike(executionStatus)) blockers.push(`blocked_sandbox_execution_status:${executionStatus}`);
  if (sandboxExecution && executionStatus !== policy.required_execution_status) blockers.push(`sandbox_execution_status_not_required:${executionStatus}`);
  if (sandboxExecution && sandboxExecution.execute_performed !== policy.required_execution_performed) blockers.push('sandbox_execution_not_performed');
  blockers.push(...governanceIssues('sandbox_execution', sandboxExecution));

  const uniqueBlockers = Array.from(new Set(blockers));
  const passed = uniqueBlockers.length === 0;
  const status = {
    schema_version: 'f1_session_processor_sandbox_execution_evidence_review_v32d_2026-06-17',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    activate_requested: args.activate,
    activation_performed: false,
    live_fetch_requested: args.allowLive,
    live_fetch_performed: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    workbook_write_performed: false,
    canonical_workbook_write_performed: false,
    forecast_bundle_ledger_write_performed: false,
    race_predictions_refresh_performed: false,
    fantasy_refresh_performed: false,
    notification_sent: false,
    sandbox_execution_evidence_supplied: Boolean(sandboxExecution),
    sandbox_execution_status: executionStatus,
    sandbox_execution_evidence_review_status: passed ? 'sandbox_execution_evidence_review_ready' : 'sandbox_execution_evidence_review_blocked',
    readiness_quality: passed ? 'health_only_sandbox_execution_verified_all_consumer_gates_closed' : 'sandbox_execution_evidence_blockers_present',
    blockers: uniqueBlockers,
    reviewed_evidence: sandboxExecution ? {
      execute_performed: sandboxExecution.execute_performed,
      activation_performed: sandboxExecution.activation_performed,
      live_fetch_performed: sandboxExecution.live_fetch_performed,
      sandbox_artifact_present: Boolean(sandboxExecution.sandbox_artifact),
      consumer_gates: sandboxExecution.consumer_gates || {}
    } : null,
    consumer_gates: closedGates(),
    next_step: passed ? policy.next_allowed_layer : 'resolve_v32d_sandbox_execution_evidence_blockers'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: passed, generated_utc: status.generated_utc, out: args.out, review_status: status.sandbox_execution_evidence_review_status });
  console.log(JSON.stringify({
    ok: passed,
    out: args.out,
    sandbox_execution_evidence_review_status: status.sandbox_execution_evidence_review_status,
    readiness_quality: status.readiness_quality,
    blocker_count: uniqueBlockers.length
  }, null, 2));
  process.exit(passed ? 0 : 1);
}

main();
