import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_sandbox_workbook_reflection_preflight_policy_v32e.json';
const DEFAULT_OUT = 'health/session_processor_sandbox_workbook_reflection_preflight_v32e_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    sandboxExecutionReview: '',
    sandboxReflectionContract: '',
    mode: 'dry_run',
    execute: false,
    activate: false,
    allowSandboxWorkbookWrite: false,
    allowCanonicalWorkbookWrite: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--sandbox-execution-review' && value) { args.sandboxExecutionReview = value; i += 1; }
    else if (key === '--sandbox-reflection-contract' && value) { args.sandboxReflectionContract = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--activate' && value) { args.activate = value === 'true'; i += 1; }
    else if (key === '--allow-sandbox-workbook-write' && value) { args.allowSandboxWorkbookWrite = value === 'true'; i += 1; }
    else if (key === '--allow-canonical-workbook-write' && value) { args.allowCanonicalWorkbookWrite = value === 'true'; i += 1; }
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
  return String(
    payload.sandbox_workbook_reflection_preflight_status ||
    payload.sandbox_execution_evidence_review_status ||
    payload.status ||
    payload.readiness_status ||
    payload.decision ||
    'present'
  );
}

function reflectionStatusOf(payload) {
  if (!payload) return 'missing';
  return String(
    payload.sandbox_kpi_reflection_status ||
    payload.reflection_status ||
    payload.status ||
    payload.readiness_status ||
    payload.decision ||
    'present'
  );
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
  if (bool(payload.execute_performed)) issues.push(`${name}:execute_performed`);
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
  const sandboxExecutionReview = readJsonMaybe(args.sandboxExecutionReview);
  const sandboxReflectionContract = readJsonMaybe(args.sandboxReflectionContract);
  const reviewStatus = statusOf(sandboxExecutionReview);
  const reflectionStatus = reflectionStatusOf(sandboxReflectionContract);
  const blockers = [];

  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');
  if (policy.execution_allowed !== false) blockers.push('policy_execution_allowed_not_false');
  if (policy.sandbox_workbook_write_allowed !== false) blockers.push('policy_sandbox_workbook_write_allowed_not_false');
  if (policy.canonical_workbook_write_allowed !== false) blockers.push('policy_canonical_workbook_write_allowed_not_false');
  if (args.mode !== 'dry_run' && args.mode !== 'preflight') blockers.push(`unsupported_mode:${args.mode}`);
  if (args.execute) blockers.push('execute_true_rejected_by_v32e_preflight');
  if (args.activate) blockers.push('activate_true_rejected_by_v32e_preflight');
  if (args.allowSandboxWorkbookWrite) blockers.push('sandbox_workbook_write_true_rejected_by_v32e_preflight');
  if (args.allowCanonicalWorkbookWrite) blockers.push('canonical_workbook_write_true_rejected_by_v32e_preflight');
  if (!sandboxExecutionReview) blockers.push('missing_required_input:sandbox_execution_evidence_review');
  if (!sandboxReflectionContract) blockers.push('missing_required_input:sandbox_reflection_contract');
  if (sandboxExecutionReview && blockedLike(reviewStatus)) blockers.push(`blocked_sandbox_execution_review:${reviewStatus}`);
  if (sandboxReflectionContract && blockedLike(reflectionStatus)) blockers.push(`blocked_sandbox_reflection_contract:${reflectionStatus}`);
  if (sandboxExecutionReview && reviewStatus !== policy.required_review_status) blockers.push(`sandbox_execution_review_status_not_required:${reviewStatus}`);
  if (sandboxReflectionContract && reflectionStatus !== policy.required_reflection_status) blockers.push(`sandbox_reflection_status_not_required:${reflectionStatus}`);
  blockers.push(...governanceIssues('sandbox_execution_review', sandboxExecutionReview));
  blockers.push(...governanceIssues('sandbox_reflection_contract', sandboxReflectionContract));

  const uniqueBlockers = Array.from(new Set(blockers));
  const passed = uniqueBlockers.length === 0;
  const status = {
    schema_version: 'f1_session_processor_sandbox_workbook_reflection_preflight_v32e_2026-06-17',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    activate_requested: args.activate,
    activation_performed: false,
    sandbox_workbook_write_requested: args.allowSandboxWorkbookWrite,
    sandbox_workbook_write_performed: false,
    canonical_workbook_write_requested: args.allowCanonicalWorkbookWrite,
    canonical_workbook_write_performed: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    workbook_write_performed: false,
    forecast_bundle_ledger_write_performed: false,
    race_predictions_refresh_performed: false,
    fantasy_refresh_performed: false,
    notification_sent: false,
    sandbox_execution_review_status: reviewStatus,
    sandbox_reflection_contract_status: reflectionStatus,
    sandbox_workbook_reflection_preflight_status: passed ? 'sandbox_workbook_reflection_preflight_ready' : 'sandbox_workbook_reflection_preflight_blocked',
    readiness_quality: passed ? 'sandbox_reflection_contract_ready_after_health_only_execution_review' : 'sandbox_workbook_reflection_preflight_blockers_present',
    candidate_sandbox_targets: policy.candidate_sandbox_targets || [],
    blocked_write_targets: policy.blocked_write_targets || [],
    blockers: uniqueBlockers,
    consumer_gates: closedGates(),
    activation_boundary: {
      this_patch_writes_any_workbook: false,
      future_sandbox_workbook_write_must_be_separate_patch: true,
      future_canonical_workbook_write_must_be_separate_explicit_approval: true,
      future_production_activation_must_be_separate_patch: true
    },
    next_step: passed ? policy.next_allowed_layer : 'resolve_v32e_sandbox_workbook_reflection_preflight_blockers'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: passed, generated_utc: status.generated_utc, out: args.out, preflight_status: status.sandbox_workbook_reflection_preflight_status });
  console.log(JSON.stringify({
    ok: passed,
    out: args.out,
    sandbox_workbook_reflection_preflight_status: status.sandbox_workbook_reflection_preflight_status,
    readiness_quality: status.readiness_quality,
    blocker_count: uniqueBlockers.length
  }, null, 2));
  process.exit(passed ? 0 : 1);
}

main();
