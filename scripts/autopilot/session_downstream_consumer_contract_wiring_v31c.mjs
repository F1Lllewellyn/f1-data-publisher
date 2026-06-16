import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_downstream_consumer_contract_wiring_policy_v31c.json';
const DEFAULT_OUT = 'health/session_downstream_consumer_contract_wiring_v31c_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    sourceReview: '',
    materialGate: '',
    replay: '',
    mode: 'dry_run',
    execute: false,
    allowLive: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--material-gate' && value) { args.materialGate = value; i += 1; }
    else if (key === '--replay' && value) { args.replay = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
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

function text(value) {
  return String(value ?? '').toLowerCase();
}

function gateClosedMap() {
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

function governanceIssues(policy, args, sourceReview) {
  const issues = [];
  if (policy.production_automation !== 'OFF') issues.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') issues.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) issues.push('policy_promotion_allowed_not_false');
  if (args.execute) issues.push('execute_true_not_supported_for_contract_wiring');
  if (args.allowLive) issues.push('allow_live_true_not_supported_for_contract_wiring');
  if (sourceReview?.production_automation !== undefined && sourceReview.production_automation !== 'OFF') issues.push('source_review_production_automation_not_off');
  if (sourceReview?.forecast_gate !== undefined && sourceReview.forecast_gate !== 'OFF') issues.push('source_review_forecast_gate_not_off');
  if (sourceReview?.promotion_allowed !== undefined && sourceReview.promotion_allowed !== false) issues.push('source_review_promotion_allowed_not_false');
  if (sourceReview?.stable_engine_modified === true) issues.push('stable_engine_modified_true');
  if (sourceReview?.canonical_workbook_overwrite === true) issues.push('canonical_workbook_overwrite_true');
  const gates = sourceReview?.consumer_gates || {};
  for (const [key, expected] of Object.entries(gateClosedMap())) {
    if (gates[key] !== undefined && gates[key] !== expected) issues.push(`${key}_not_closed`);
  }
  return Array.from(new Set(issues));
}

function sourceReviewStatus(sourceReview) {
  if (!sourceReview) return 'source_review_not_supplied_contract_only';
  return sourceReview.review_status || sourceReview.status || 'source_review_unknown';
}

function deriveEligibility(sourceReview, materialGate, replay, issues) {
  if (issues.length > 0) {
    return {
      contract_status: 'downstream_consumer_contract_blocked',
      readiness_quality: 'governance_issue',
      eligibility_level: 'blocked',
      reason: 'governance_or_closed_gate_violation'
    };
  }

  const review = text(sourceReviewStatus(sourceReview));
  const material = text(materialGate?.threshold_gate_status || materialGate?.status);
  const replayStatus = text(replay?.replay_status || replay?.status);

  if (review.includes('blocked') || material.includes('blocked') || replayStatus.includes('failed')) {
    return {
      contract_status: 'downstream_consumer_contract_blocked',
      readiness_quality: 'upstream_blocked',
      eligibility_level: 'blocked',
      reason: 'upstream_blocking_status'
    };
  }

  if (review.includes('degraded') || material.includes('material_change_detected')) {
    return {
      contract_status: 'downstream_consumer_contract_review_required',
      readiness_quality: 'manual_review_required_before_consumers',
      eligibility_level: 'review_required',
      reason: review.includes('degraded') ? 'source_review_degraded' : 'material_change_detected'
    };
  }

  if (review.includes('ready')) {
    return {
      contract_status: 'downstream_consumer_contract_ready',
      readiness_quality: 'source_review_ready_consumers_remain_closed',
      eligibility_level: 'eligible_after_manual_activation',
      reason: 'source_review_ready'
    };
  }

  return {
    contract_status: 'downstream_consumer_contract_contract_ready',
    readiness_quality: 'contract_only_no_activation',
    eligibility_level: 'contract_only',
    reason: 'source_review_absent_or_contract_only'
  };
}

function buildConsumerContracts(eligibility, policy) {
  const candidates = policy.consumer_contracts || [];
  return candidates.map((item) => ({
    consumer_id: item.consumer_id,
    consumer_type: item.consumer_type,
    intended_role: item.intended_role,
    current_enabled: false,
    candidate_eligible: eligibility.eligibility_level === 'eligible_after_manual_activation',
    activation_required: 'explicit_future_approval',
    writes_production_artifact: false,
    writes_canonical_workbook: false,
    sends_notification: false,
    blocked_until: item.blocked_until || 'manual_review_and_future_activation_patch'
  }));
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const sourceReview = readJsonMaybe(args.sourceReview);
  const materialGate = readJsonMaybe(args.materialGate);
  const replay = readJsonMaybe(args.replay);
  const issues = governanceIssues(policy, args, sourceReview);
  const eligibility = deriveEligibility(sourceReview, materialGate, replay, issues);
  const consumerContracts = buildConsumerContracts(eligibility, policy);

  const status = {
    schema_version: 'f1_session_downstream_consumer_contract_wiring_v31c_2026-06-16',
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
    source_review_supplied: Boolean(sourceReview),
    material_gate_supplied: Boolean(materialGate),
    replay_supplied: Boolean(replay),
    source_review_status: sourceReviewStatus(sourceReview),
    ...eligibility,
    governance_issues: issues,
    consumer_contract_count: consumerContracts.length,
    consumer_contracts: consumerContracts,
    consumer_gates: gateClosedMap(),
    next_step: eligibility.contract_status === 'downstream_consumer_contract_ready'
      ? 'v31d_sandbox_workbook_kpi_reflection_contract_after_review'
      : 'continue_contract_or_review_before_downstream_activation'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: status.contract_status !== 'downstream_consumer_contract_blocked', generated_utc: status.generated_utc, out: args.out, contract_status: status.contract_status });
  const ok = status.contract_status !== 'downstream_consumer_contract_blocked';
  console.log(JSON.stringify({ ok, out: args.out, contract_status: status.contract_status, readiness_quality: status.readiness_quality, consumer_contract_count: status.consumer_contract_count }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
