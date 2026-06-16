import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_sandbox_workbook_kpi_reflection_contract_policy_v31d.json';
const DEFAULT_OUT = 'health/session_sandbox_workbook_kpi_reflection_contract_v31d_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    downstreamContract: '',
    sourceReview: '',
    sourceEvidence: '',
    mode: 'dry_run',
    execute: false,
    allowWorkbookWrite: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--downstream-contract' && value) { args.downstreamContract = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--source-evidence' && value) { args.sourceEvidence = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--allow-workbook-write' && value) { args.allowWorkbookWrite = value === 'true'; i += 1; }
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

function num(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function closedConsumerGates() {
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

function governanceIssues(policy, args, downstreamContract, sourceReview, sourceEvidence) {
  const issues = [];
  if (policy.production_automation !== 'OFF') issues.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') issues.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) issues.push('policy_promotion_allowed_not_false');
  if (args.execute) issues.push('execute_true_not_supported_for_v31d_contract');
  if (args.allowWorkbookWrite) issues.push('allow_workbook_write_true_not_supported_for_v31d_contract');
  for (const payload of [downstreamContract, sourceReview, sourceEvidence].filter(Boolean)) {
    if (payload.production_automation !== undefined && payload.production_automation !== 'OFF') issues.push('upstream_production_automation_not_off');
    if (payload.forecast_gate !== undefined && payload.forecast_gate !== 'OFF') issues.push('upstream_forecast_gate_not_off');
    if (payload.promotion_allowed !== undefined && payload.promotion_allowed !== false) issues.push('upstream_promotion_allowed_not_false');
    if (payload.stable_engine_modified === true) issues.push('stable_engine_modified_true');
    if (payload.canonical_workbook_overwrite === true) issues.push('canonical_workbook_overwrite_true');
    const gates = payload.consumer_gates || {};
    for (const [key, expected] of Object.entries(closedConsumerGates())) {
      if (gates[key] !== undefined && gates[key] !== expected) issues.push(`${key}_not_closed`);
    }
  }
  return Array.from(new Set(issues));
}

function deriveStatus(downstreamContract, sourceReview, sourceEvidence, issues) {
  if (issues.length > 0) {
    return {
      reflection_status: 'sandbox_kpi_reflection_contract_blocked',
      readiness_quality: 'governance_issue',
      action: 'hold_reflection_contract',
      severity: 'blocking'
    };
  }

  const downstreamStatus = text(downstreamContract?.contract_status || downstreamContract?.status);
  const reviewStatus = text(sourceReview?.review_status || sourceReview?.status);
  const evidenceStatus = text(sourceEvidence?.pull_status || sourceEvidence?.status);

  if (downstreamStatus.includes('blocked') || reviewStatus.includes('blocked') || evidenceStatus.includes('blocked') || evidenceStatus.includes('failed')) {
    return {
      reflection_status: 'sandbox_kpi_reflection_contract_blocked',
      readiness_quality: 'upstream_blocked',
      action: 'repair_upstream_before_reflection',
      severity: 'blocking'
    };
  }

  if (downstreamStatus.includes('review_required') || reviewStatus.includes('degraded')) {
    return {
      reflection_status: 'sandbox_kpi_reflection_review_required',
      readiness_quality: 'manual_review_required',
      action: 'review_before_sandbox_reflection_activation',
      severity: 'review_required'
    };
  }

  if (downstreamStatus.includes('ready') || reviewStatus.includes('ready')) {
    return {
      reflection_status: 'sandbox_kpi_reflection_contract_ready',
      readiness_quality: 'ready_for_sandbox_workbook_reflection_contract',
      action: 'eligible_for_future_sandbox_reflection_activation',
      severity: 'none'
    };
  }

  return {
    reflection_status: 'sandbox_kpi_reflection_contract_only',
    readiness_quality: 'contract_only_no_activation',
    action: 'continue_contract_build',
    severity: 'none'
  };
}

function buildReflectionPacket(downstreamContract, sourceReview, sourceEvidence) {
  return {
    packet_type: 'sandbox_workbook_kpi_reflection_contract',
    event: sourceEvidence?.event || sourceReview?.source_evidence?.event || '',
    session: sourceEvidence?.session || sourceReview?.source_evidence?.session || '',
    source_review_status: sourceReview?.review_status || downstreamContract?.source_review_status || '',
    downstream_contract_status: downstreamContract?.contract_status || '',
    source_pull_status: sourceEvidence?.pull_status || '',
    source_count: num(sourceEvidence?.source_count ?? sourceReview?.source_evidence?.source_count),
    ready_source_count: num(sourceEvidence?.ready_source_count ?? sourceReview?.source_evidence?.ready_source_count),
    degraded_source_count: num(sourceEvidence?.degraded_source_count ?? sourceReview?.source_evidence?.degraded_source_count),
    failed_source_count: num(sourceEvidence?.failed_source_count ?? sourceReview?.source_evidence?.failed_source_count),
    row_count: num(sourceEvidence?.row_count ?? sourceReview?.source_evidence?.row_count),
    workbook_target: 'sandbox_only_future_activation',
    canonical_workbook_target: 'blocked',
    write_performed: false
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const downstreamContract = readJsonMaybe(args.downstreamContract);
  const sourceReview = readJsonMaybe(args.sourceReview);
  const sourceEvidence = readJsonMaybe(args.sourceEvidence);
  const issues = governanceIssues(policy, args, downstreamContract, sourceReview, sourceEvidence);
  const derived = deriveStatus(downstreamContract, sourceReview, sourceEvidence, issues);
  const reflectionPacket = buildReflectionPacket(downstreamContract, sourceReview, sourceEvidence);

  const status = {
    schema_version: 'f1_session_sandbox_workbook_kpi_reflection_contract_v31d_2026-06-16',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    workbook_write_performed: false,
    canonical_workbook_write_performed: false,
    downstream_contract_supplied: Boolean(downstreamContract),
    source_review_supplied: Boolean(sourceReview),
    source_evidence_supplied: Boolean(sourceEvidence),
    ...derived,
    governance_issues: issues,
    reflection_packet: reflectionPacket,
    consumer_gates: closedConsumerGates(),
    next_step: derived.reflection_status === 'sandbox_kpi_reflection_contract_ready'
      ? 'v31e_forecast_bundle_ledger_activation_contract'
      : 'continue_review_or_repair_before_sandbox_reflection_activation'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: status.reflection_status !== 'sandbox_kpi_reflection_contract_blocked', generated_utc: status.generated_utc, out: args.out, reflection_status: status.reflection_status });
  const ok = status.reflection_status !== 'sandbox_kpi_reflection_contract_blocked';
  console.log(JSON.stringify({ ok, out: args.out, reflection_status: status.reflection_status, readiness_quality: status.readiness_quality }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
