import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_activation_review_packet_policy_v31j.json';
const DEFAULT_OUT = 'health/session_processor_activation_review_packet_v31j_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    sourceEvidence: '',
    sourceReview: '',
    downstreamContract: '',
    sandboxReflection: '',
    ledgerContract: '',
    readinessMetadata: '',
    notificationPreview: '',
    rehearsalPacket: '',
    operatorReview: '',
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
    else if (key === '--source-evidence' && value) { args.sourceEvidence = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--downstream-contract' && value) { args.downstreamContract = value; i += 1; }
    else if (key === '--sandbox-reflection' && value) { args.sandboxReflection = value; i += 1; }
    else if (key === '--ledger-contract' && value) { args.ledgerContract = value; i += 1; }
    else if (key === '--readiness-metadata' && value) { args.readinessMetadata = value; i += 1; }
    else if (key === '--notification-preview' && value) { args.notificationPreview = value; i += 1; }
    else if (key === '--rehearsal-packet' && value) { args.rehearsalPacket = value; i += 1; }
    else if (key === '--operator-review' && value) { args.operatorReview = value; i += 1; }
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
    payload.status ||
    payload.pull_status ||
    payload.review_status ||
    payload.contract_status ||
    payload.reflection_status ||
    payload.ledger_contract_status ||
    payload.readiness_contract_status ||
    payload.notification_preview_status ||
    payload.rehearsal_status ||
    payload.activation_protocol_status ||
    payload.decision ||
    'present'
  );
}

function readyLike(status) {
  const value = lower(status);
  return value.includes('ready') || value.includes('accepted') || value.includes('passed') || value.includes('eligible') || value.includes('preview_ready');
}

function blockedLike(status) {
  const value = lower(status);
  return value.includes('blocked') || value.includes('failed') || value.includes('error') || value.includes('rejected') || value.includes('not_ready');
}

function governanceIssues(policy, args, namedPayloads) {
  const issues = [];
  if (policy.production_automation !== 'OFF') issues.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') issues.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) issues.push('policy_promotion_allowed_not_false');
  if (args.execute) issues.push('execute_true_not_supported_for_v31j_review_packet');
  if (args.activate) issues.push('activate_true_not_supported_for_v31j_review_packet');
  for (const item of namedPayloads) {
    const payload = item.payload;
    if (!payload) continue;
    if (payload.production_automation !== undefined && payload.production_automation !== 'OFF') issues.push(`${item.name}:production_automation_not_off`);
    if (payload.forecast_gate !== undefined && payload.forecast_gate !== 'OFF') issues.push(`${item.name}:forecast_gate_not_off`);
    if (payload.promotion_allowed !== undefined && payload.promotion_allowed !== false) issues.push(`${item.name}:promotion_allowed_not_false`);
    if (bool(payload.stable_engine_modified)) issues.push(`${item.name}:stable_engine_modified`);
    if (bool(payload.canonical_workbook_overwrite)) issues.push(`${item.name}:canonical_workbook_overwrite`);
    if (bool(payload.workbook_write_performed)) issues.push(`${item.name}:workbook_write_performed`);
    if (bool(payload.canonical_workbook_write_performed)) issues.push(`${item.name}:canonical_workbook_write_performed`);
    if (bool(payload.forecast_bundle_ledger_write_performed)) issues.push(`${item.name}:forecast_bundle_ledger_write_performed`);
    if (bool(payload.race_predictions_refresh_performed)) issues.push(`${item.name}:race_predictions_refresh_performed`);
    if (bool(payload.fantasy_refresh_performed)) issues.push(`${item.name}:fantasy_refresh_performed`);
    if (bool(payload.notification_sent)) issues.push(`${item.name}:notification_sent`);
    if (bool(payload.execute_performed)) issues.push(`${item.name}:execute_performed`);
    const gates = payload.consumer_gates || {};
    for (const [gate, expected] of Object.entries(closedGates())) {
      if (gates[gate] !== undefined && gates[gate] !== expected) issues.push(`${item.name}:consumer_gate_open:${gate}`);
    }
  }
  return Array.from(new Set(issues));
}

function evaluateInputs(policy, namedPayloads) {
  const required = new Set(policy.required_inputs || []);
  return namedPayloads.map((item) => {
    const status = statusOf(item.payload);
    const present = item.payload !== null;
    const blocked = present && blockedLike(status);
    const ready = present && readyLike(status) && !blocked;
    return {
      name: item.name,
      present,
      required: required.has(item.name),
      status,
      ready,
      blocked
    };
  });
}

function deriveDecision(inputs, issues) {
  const blockers = [];
  for (const input of inputs) {
    if (input.required && !input.present) blockers.push(`missing_required_input:${input.name}`);
    if (input.required && input.blocked) blockers.push(`blocked_required_input:${input.name}:${input.status}`);
    if (input.required && input.present && !input.ready && !input.blocked) blockers.push(`not_ready_required_input:${input.name}:${input.status}`);
  }
  blockers.push(...issues);

  if (blockers.length > 0) {
    return {
      activation_review_status: 'activation_review_blocked',
      readiness_quality: 'blocked_or_missing_required_evidence',
      activation_decision: 'do_not_activate',
      operator_action: 'repair_or_review_blockers_before_activation',
      blockers
    };
  }

  return {
    activation_review_status: 'activation_review_ready_for_explicit_decision',
    readiness_quality: 'all_required_dry_run_gates_ready',
    activation_decision: 'eligible_for_separate_explicit_activation_review',
    operator_action: 'review_packet_then_decide_whether_to_authorize_future_activation_patch',
    blockers: []
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const namedPayloads = [
    { name: 'source_evidence', payload: readJsonMaybe(args.sourceEvidence) },
    { name: 'source_review', payload: readJsonMaybe(args.sourceReview) },
    { name: 'downstream_contract', payload: readJsonMaybe(args.downstreamContract) },
    { name: 'sandbox_reflection', payload: readJsonMaybe(args.sandboxReflection) },
    { name: 'ledger_contract', payload: readJsonMaybe(args.ledgerContract) },
    { name: 'readiness_metadata', payload: readJsonMaybe(args.readinessMetadata) },
    { name: 'notification_preview', payload: readJsonMaybe(args.notificationPreview) },
    { name: 'end_to_end_rehearsal_packet', payload: readJsonMaybe(args.rehearsalPacket) },
    { name: 'sandbox_live_operator_review', payload: readJsonMaybe(args.operatorReview) }
  ];
  const issues = governanceIssues(policy, args, namedPayloads);
  const inputs = evaluateInputs(policy, namedPayloads);
  const decision = deriveDecision(inputs, issues);

  const status = {
    schema_version: 'f1_session_processor_activation_review_packet_v31j_2026-06-17',
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
    ...decision,
    input_count: inputs.length,
    ready_required_input_count: inputs.filter((input) => input.required && input.ready).length,
    required_input_count: inputs.filter((input) => input.required).length,
    inputs,
    governance_issues: issues,
    activation_review_packet: {
      activation_type: 'future_separate_explicit_activation_patch_only',
      current_patch_activates_anything: false,
      approval_required: true,
      recommended_next_step: decision.activation_review_status === 'activation_review_ready_for_explicit_decision'
        ? 'operator_decision_on_whether_to_prepare_v32_activation_patch'
        : 'repair_blockers_before_activation_review'
    },
    consumer_gates: closedGates(),
    next_step: decision.activation_review_status === 'activation_review_ready_for_explicit_decision'
      ? 'operator_decision_required_before_any_v32_activation_patch'
      : 'resolve_activation_review_blockers'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: status.activation_review_status !== 'activation_review_blocked', generated_utc: status.generated_utc, out: args.out, activation_review_status: status.activation_review_status });
  const ok = status.activation_review_status !== 'activation_review_blocked';
  console.log(JSON.stringify({ ok, out: args.out, activation_review_status: status.activation_review_status, readiness_quality: status.readiness_quality, blocker_count: status.blockers.length }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
