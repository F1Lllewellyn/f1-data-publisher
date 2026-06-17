import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_execution_preflight_harness_policy_v32b.json';
const DEFAULT_OUT = 'health/session_processor_execution_preflight_harness_v32b_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    activationPreflight: '',
    activationReview: '',
    sourceEvidence: '',
    sourceReview: '',
    downstreamContract: '',
    sandboxReflection: '',
    forecastLedgerContract: '',
    readinessMetadata: '',
    notificationPreview: '',
    endToEndRehearsal: '',
    sandboxLiveOperatorReview: '',
    mode: 'dry_run',
    execute: false,
    activate: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--activation-preflight' && value) { args.activationPreflight = value; i += 1; }
    else if (key === '--activation-review' && value) { args.activationReview = value; i += 1; }
    else if (key === '--source-evidence' && value) { args.sourceEvidence = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--downstream-contract' && value) { args.downstreamContract = value; i += 1; }
    else if (key === '--sandbox-reflection' && value) { args.sandboxReflection = value; i += 1; }
    else if (key === '--forecast-ledger-contract' && value) { args.forecastLedgerContract = value; i += 1; }
    else if (key === '--readiness-metadata' && value) { args.readinessMetadata = value; i += 1; }
    else if (key === '--notification-preview' && value) { args.notificationPreview = value; i += 1; }
    else if (key === '--end-to-end-rehearsal' && value) { args.endToEndRehearsal = value; i += 1; }
    else if (key === '--sandbox-live-operator-review' && value) { args.sandboxLiveOperatorReview = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--activate' && value) { args.activate = value === 'true'; i += 1; }
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

function statusOf(payload) {
  if (!payload) return 'missing';
  return String(
    payload.status ||
    payload.authorization_preflight_status ||
    payload.activation_review_status ||
    payload.rehearsal_status ||
    payload.review_status ||
    payload.readiness_status ||
    payload.threshold_gate_status ||
    payload.notification_preview_status ||
    payload.decision ||
    'present'
  );
}

function readyLike(status) {
  const value = lower(status);
  return value.includes('ready') || value.includes('eligible') || value.includes('accepted') || value.includes('passed') || value.includes('preview');
}

function blockedLike(status) {
  const value = lower(status);
  return value.includes('blocked') || value.includes('failed') || value.includes('error') || value.includes('rejected') || value.includes('not_ready');
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

function payloadGovernanceIssues(name, payload) {
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

function inputRecord(name, filePath, payload, required) {
  const status = statusOf(payload);
  const present = payload !== null;
  return {
    name,
    path: filePath || '',
    present,
    required,
    status,
    ready: present && readyLike(status) && !blockedLike(status),
    blocked: present && blockedLike(status)
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const inputs = [
    inputRecord('activation_authorization_preflight', args.activationPreflight, readJsonMaybe(args.activationPreflight), true),
    inputRecord('activation_review_packet', args.activationReview, readJsonMaybe(args.activationReview), true),
    inputRecord('source_evidence', args.sourceEvidence, readJsonMaybe(args.sourceEvidence), false),
    inputRecord('source_review', args.sourceReview, readJsonMaybe(args.sourceReview), false),
    inputRecord('downstream_contract', args.downstreamContract, readJsonMaybe(args.downstreamContract), false),
    inputRecord('sandbox_reflection', args.sandboxReflection, readJsonMaybe(args.sandboxReflection), false),
    inputRecord('forecast_ledger_contract', args.forecastLedgerContract, readJsonMaybe(args.forecastLedgerContract), false),
    inputRecord('readiness_metadata', args.readinessMetadata, readJsonMaybe(args.readinessMetadata), false),
    inputRecord('notification_preview', args.notificationPreview, readJsonMaybe(args.notificationPreview), false),
    inputRecord('end_to_end_rehearsal', args.endToEndRehearsal, readJsonMaybe(args.endToEndRehearsal), false),
    inputRecord('sandbox_live_operator_review', args.sandboxLiveOperatorReview, readJsonMaybe(args.sandboxLiveOperatorReview), false)
  ];

  const payloads = inputs.map(input => ({ name: input.name, payload: readJsonMaybe(input.path) }));
  const blockers = [];
  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.execution_allowed !== false) blockers.push('policy_execution_allowed_not_false');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');
  if (args.mode !== 'dry_run' && args.mode !== 'preflight') blockers.push(`unsupported_mode:${args.mode}`);
  if (args.execute) blockers.push('execute_true_rejected_by_v32b_preflight');
  if (args.activate) blockers.push('activate_true_rejected_by_v32b_preflight');
  for (const input of inputs) {
    if (input.required && !input.present) blockers.push(`missing_required_input:${input.name}`);
    if (input.required && input.blocked) blockers.push(`blocked_required_input:${input.name}:${input.status}`);
    if (input.required && input.present && !input.ready && !input.blocked) blockers.push(`required_input_not_ready:${input.name}:${input.status}`);
  }
  for (const item of payloads) blockers.push(...payloadGovernanceIssues(item.name, item.payload));
  const uniqueBlockers = Array.from(new Set(blockers));
  const requiredInputs = inputs.filter(input => input.required);
  const readyRequiredInputs = requiredInputs.filter(input => input.ready);
  const status = {
    schema_version: 'f1_session_processor_execution_preflight_harness_v32b_2026-06-17',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    activate_requested: args.activate,
    activation_performed: false,
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
    preflight_status: uniqueBlockers.length === 0 ? 'sandbox_processor_execution_preflight_ready' : 'sandbox_processor_execution_preflight_blocked',
    readiness_quality: uniqueBlockers.length === 0 ? 'required_activation_evidence_ready_all_gates_closed' : 'preflight_blockers_present',
    execution_decision: uniqueBlockers.length === 0 ? 'eligible_to_prepare_separate_sandbox_execution_patch_after_explicit_instruction' : 'do_not_prepare_execution_patch',
    required_input_count: requiredInputs.length,
    ready_required_input_count: readyRequiredInputs.length,
    input_count: inputs.length,
    inputs,
    blockers: uniqueBlockers,
    consumer_gates: closedGates(),
    activation_boundary: {
      this_patch_executes_processor: false,
      this_patch_activates_anything: false,
      future_execution_must_be_separate_patch: true,
      future_activation_must_be_separate_patch: true
    },
    next_step: uniqueBlockers.length === 0 ? 'prepare_v32c_controlled_sandbox_processor_execution_patch_after_explicit_instruction' : 'resolve_v32b_preflight_blockers'
  };
  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: uniqueBlockers.length === 0, generated_utc: status.generated_utc, out: args.out, preflight_status: status.preflight_status });
  console.log(JSON.stringify({
    ok: uniqueBlockers.length === 0,
    out: args.out,
    preflight_status: status.preflight_status,
    readiness_quality: status.readiness_quality,
    blocker_count: uniqueBlockers.length
  }, null, 2));
  process.exit(uniqueBlockers.length === 0 ? 0 : 1);
}

main();
