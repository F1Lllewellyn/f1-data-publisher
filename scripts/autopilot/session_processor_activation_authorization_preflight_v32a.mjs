import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_activation_authorization_preflight_policy_v32a.json';
const DEFAULT_OUT = 'health/session_processor_activation_authorization_preflight_v32a_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    activationReview: '',
    mode: 'dry_run',
    execute: false,
    activate: false,
    operatorApproval: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--activation-review' && value) { args.activationReview = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--activate' && value) { args.activate = value === 'true'; i += 1; }
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

function activationReviewStatus(review) {
  if (!review) return 'missing';
  return String(review.activation_review_status || review.status || review.decision || 'present');
}

function reviewReady(review) {
  const status = lower(activationReviewStatus(review));
  return status.includes('ready') || status.includes('eligible');
}

function governanceIssues(policy, args, review) {
  const issues = [];
  if (policy.production_automation !== 'OFF') issues.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') issues.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) issues.push('policy_promotion_allowed_not_false');
  if (policy.activation_allowed !== false) issues.push('policy_activation_allowed_not_false');
  if (args.execute) issues.push('execute_true_not_supported_for_v32a_preflight');
  if (args.activate) issues.push('activate_true_not_supported_for_v32a_preflight');
  if (review) {
    if (review.production_automation !== undefined && review.production_automation !== 'OFF') issues.push('activation_review_production_automation_not_off');
    if (review.forecast_gate !== undefined && review.forecast_gate !== 'OFF') issues.push('activation_review_forecast_gate_not_off');
    if (review.promotion_allowed !== undefined && review.promotion_allowed !== false) issues.push('activation_review_promotion_allowed_not_false');
    if (bool(review.stable_engine_modified)) issues.push('stable_engine_modified_true');
    if (bool(review.canonical_workbook_overwrite)) issues.push('canonical_workbook_overwrite_true');
    if (bool(review.workbook_write_performed)) issues.push('workbook_write_performed_true');
    if (bool(review.canonical_workbook_write_performed)) issues.push('canonical_workbook_write_performed_true');
    if (bool(review.forecast_bundle_ledger_write_performed)) issues.push('forecast_bundle_ledger_write_performed_true');
    if (bool(review.race_predictions_refresh_performed)) issues.push('race_predictions_refresh_performed_true');
    if (bool(review.fantasy_refresh_performed)) issues.push('fantasy_refresh_performed_true');
    if (bool(review.notification_sent)) issues.push('notification_sent_true');
    const gates = review.consumer_gates || {};
    for (const [gate, expected] of Object.entries(closedGates())) {
      if (gates[gate] !== undefined && gates[gate] !== expected) issues.push(`consumer_gate_open:${gate}`);
    }
  }
  return Array.from(new Set(issues));
}

function deriveStatus(review, issues, args) {
  if (!review) {
    return {
      authorization_preflight_status: 'activation_authorization_preflight_blocked',
      readiness_quality: 'missing_activation_review_packet',
      authorization_decision: 'do_not_prepare_activation',
      blockers: ['missing_activation_review_packet']
    };
  }
  if (issues.length > 0) {
    return {
      authorization_preflight_status: 'activation_authorization_preflight_blocked',
      readiness_quality: 'governance_issue',
      authorization_decision: 'do_not_prepare_activation',
      blockers: issues
    };
  }
  if (!reviewReady(review)) {
    return {
      authorization_preflight_status: 'activation_authorization_preflight_blocked',
      readiness_quality: 'activation_review_not_ready',
      authorization_decision: 'do_not_prepare_activation',
      blockers: [`activation_review_not_ready:${activationReviewStatus(review)}`]
    };
  }
  return {
    authorization_preflight_status: args.operatorApproval
      ? 'activation_authorization_operator_acknowledged_preflight_only'
      : 'activation_authorization_preflight_ready',
    readiness_quality: 'activation_review_ready_all_gates_still_closed',
    authorization_decision: 'eligible_to_prepare_separate_activation_patch_after_explicit_instruction',
    blockers: []
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const review = readJsonMaybe(args.activationReview);
  const issues = governanceIssues(policy, args, review);
  const derived = deriveStatus(review, issues, args);
  const status = {
    schema_version: 'f1_session_processor_activation_authorization_preflight_v32a_2026-06-17',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    activate_requested: args.activate,
    activation_performed: false,
    operator_approval_recorded: args.operatorApproval,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    activation_allowed: false,
    activation_review_supplied: Boolean(review),
    activation_review_status: activationReviewStatus(review),
    ...derived,
    required_future_explicit_approvals: [
      'enable_sandbox_processor_execution',
      'enable_forecast_bundle_ledger_write',
      'enable_sandbox_workbook_reflection',
      'enable_race_predictions_readiness_refresh',
      'enable_fantasy_readiness_refresh',
      'enable_notification_send',
      'enable_production_automation'
    ],
    activation_boundary: {
      this_patch_activates_anything: false,
      future_activation_must_be_separate_patch: true,
      current_authorization_is_preflight_only: true
    },
    consumer_gates: closedGates(),
    next_step: derived.authorization_preflight_status === 'activation_authorization_preflight_ready' || derived.authorization_preflight_status === 'activation_authorization_operator_acknowledged_preflight_only'
      ? 'operator_explicit_instruction_required_before_v32b_sandbox_processor_execution_patch'
      : 'resolve_authorization_preflight_blockers'
  };
  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: status.authorization_preflight_status !== 'activation_authorization_preflight_blocked', generated_utc: status.generated_utc, out: args.out, authorization_preflight_status: status.authorization_preflight_status });
  const ok = status.authorization_preflight_status !== 'activation_authorization_preflight_blocked';
  console.log(JSON.stringify({ ok, out: args.out, authorization_preflight_status: status.authorization_preflight_status, readiness_quality: status.readiness_quality, blocker_count: status.blockers.length }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
