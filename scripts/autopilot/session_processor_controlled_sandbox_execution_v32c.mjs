import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_controlled_sandbox_execution_policy_v32c.json';
const DEFAULT_OUT = 'health/session_processor_controlled_sandbox_execution_v32c_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    executionPreflight: '',
    activationReview: '',
    sourceEvidence: '',
    sourceReview: '',
    sessionId: 'unknown_session',
    eventId: 'unknown_event',
    mode: 'dry_run',
    execute: false,
    activate: false,
    allowLive: false,
    operatorApproval: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--execution-preflight' && value) { args.executionPreflight = value; i += 1; }
    else if (key === '--activation-review' && value) { args.activationReview = value; i += 1; }
    else if (key === '--source-evidence' && value) { args.sourceEvidence = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--session-id' && value) { args.sessionId = value; i += 1; }
    else if (key === '--event-id' && value) { args.eventId = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--activate' && value) { args.activate = value === 'true'; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--operator-approval' && value) { args.operatorApproval = value === 'true'; i += 1; }
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
    payload.preflight_status ||
    payload.activation_review_status ||
    payload.authorization_preflight_status ||
    payload.review_status ||
    payload.readiness_status ||
    payload.decision ||
    'present'
  );
}

function readyLike(status) {
  const value = lower(status);
  return value.includes('ready') || value.includes('eligible') || value.includes('accepted') || value.includes('passed');
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

function buildSandboxArtifact(args, inputs) {
  return {
    artifact_type: 'controlled_sandbox_processor_execution_v32c',
    session_id: args.sessionId,
    event_id: args.eventId,
    generated_utc: nowIso(),
    execution_scope: 'sandbox_health_and_log_only',
    source_inputs_present: inputs.filter(input => input.present).map(input => input.name),
    simulated_processor_steps: [
      'freeze_ready_evidence',
      'verify_governance_gates_closed',
      'compose_sandbox_execution_status',
      'emit_health_status_only'
    ],
    blocked_consumers: [
      'canonical_workbook',
      'forecast_bundle_ledger',
      'race_predictions',
      'fantasy_outputs',
      'notification_send',
      'production_automation'
    ]
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const preflight = readJsonMaybe(args.executionPreflight);
  const activationReview = readJsonMaybe(args.activationReview);
  const sourceEvidence = readJsonMaybe(args.sourceEvidence);
  const sourceReview = readJsonMaybe(args.sourceReview);
  const inputs = [
    inputRecord('execution_preflight', args.executionPreflight, preflight, true),
    inputRecord('activation_review_packet', args.activationReview, activationReview, true),
    inputRecord('source_evidence', args.sourceEvidence, sourceEvidence, false),
    inputRecord('source_review', args.sourceReview, sourceReview, false)
  ];

  const blockers = [];
  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.sandbox_execution_allowed !== true) blockers.push('policy_sandbox_execution_not_allowed');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');
  if (policy.live_fetch_allowed !== false) blockers.push('policy_live_fetch_allowed_not_false');
  if (args.mode !== 'dry_run' && args.mode !== 'sandbox_execution') blockers.push(`unsupported_mode:${args.mode}`);
  if (args.activate) blockers.push('activate_true_rejected_by_v32c');
  if (args.allowLive) blockers.push('allow_live_true_rejected_by_v32c');
  if (args.execute && args.mode !== 'sandbox_execution') blockers.push('execute_true_requires_mode_sandbox_execution');
  if (args.execute && !args.operatorApproval) blockers.push('execute_true_requires_operator_approval');
  for (const input of inputs) {
    if (input.required && !input.present) blockers.push(`missing_required_input:${input.name}`);
    if (input.required && input.blocked) blockers.push(`blocked_required_input:${input.name}:${input.status}`);
    if (input.required && input.present && !input.ready && !input.blocked) blockers.push(`required_input_not_ready:${input.name}:${input.status}`);
  }
  blockers.push(...payloadGovernanceIssues('execution_preflight', preflight));
  blockers.push(...payloadGovernanceIssues('activation_review_packet', activationReview));
  blockers.push(...payloadGovernanceIssues('source_evidence', sourceEvidence));
  blockers.push(...payloadGovernanceIssues('source_review', sourceReview));

  const uniqueBlockers = Array.from(new Set(blockers));
  const executePerformed = args.execute && uniqueBlockers.length === 0;
  const sandboxArtifact = executePerformed ? buildSandboxArtifact(args, inputs) : null;
  const status = {
    schema_version: 'f1_session_processor_controlled_sandbox_execution_v32c_2026-06-17',
    generated_utc: nowIso(),
    mode: args.mode,
    session_id: args.sessionId,
    event_id: args.eventId,
    execute_requested: args.execute,
    execute_performed: executePerformed,
    activate_requested: args.activate,
    activation_performed: false,
    operator_approval_recorded: args.operatorApproval,
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
    sandbox_execution_status: uniqueBlockers.length > 0
      ? 'controlled_sandbox_execution_blocked'
      : (executePerformed ? 'controlled_sandbox_execution_performed_health_only' : 'controlled_sandbox_execution_ready_not_performed'),
    readiness_quality: uniqueBlockers.length > 0
      ? 'sandbox_execution_blockers_present'
      : (executePerformed ? 'sandbox_execution_health_only_artifact_emitted' : 'sandbox_execution_ready_for_operator_approved_run'),
    inputs,
    blockers: uniqueBlockers,
    sandbox_artifact: sandboxArtifact,
    consumer_gates: closedGates(),
    activation_boundary: {
      this_patch_allows_sandbox_health_only_execution: true,
      this_patch_activates_production: false,
      future_consumer_gate_opening_must_be_separate_patch: true,
      future_production_activation_must_be_separate_patch: true
    },
    next_step: uniqueBlockers.length > 0
      ? 'resolve_v32c_sandbox_execution_blockers'
      : (executePerformed ? 'v32d_sandbox_execution_evidence_review_gate' : 'run_v32c_with_operator_approval_or_prepare_v32d_review_gate')
  };
  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: uniqueBlockers.length === 0, generated_utc: status.generated_utc, out: args.out, sandbox_execution_status: status.sandbox_execution_status, execute_performed: executePerformed });
  console.log(JSON.stringify({
    ok: uniqueBlockers.length === 0,
    out: args.out,
    sandbox_execution_status: status.sandbox_execution_status,
    execute_performed: executePerformed,
    blocker_count: uniqueBlockers.length
  }, null, 2));
  process.exit(uniqueBlockers.length === 0 ? 0 : 1);
}

main();
