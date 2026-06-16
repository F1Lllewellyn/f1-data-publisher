import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_forecast_bundle_ledger_activation_contract_policy_v31e.json';
const DEFAULT_OUT = 'health/session_forecast_bundle_ledger_activation_contract_v31e_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    sandboxReflection: '',
    downstreamContract: '',
    sourceReview: '',
    sourceEvidence: '',
    mode: 'dry_run',
    execute: false,
    allowLedgerWrite: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--sandbox-reflection' && value) { args.sandboxReflection = value; i += 1; }
    else if (key === '--downstream-contract' && value) { args.downstreamContract = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--source-evidence' && value) { args.sourceEvidence = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--allow-ledger-write' && value) { args.allowLedgerWrite = value === 'true'; i += 1; }
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

function governanceIssues(policy, args, payloads) {
  const issues = [];
  if (policy.production_automation !== 'OFF') issues.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') issues.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) issues.push('policy_promotion_allowed_not_false');
  if (args.execute) issues.push('execute_true_not_supported_for_v31e_contract');
  if (args.allowLedgerWrite) issues.push('allow_ledger_write_true_not_supported_for_v31e_contract');
  for (const payload of payloads.filter(Boolean)) {
    if (payload.production_automation !== undefined && payload.production_automation !== 'OFF') issues.push('upstream_production_automation_not_off');
    if (payload.forecast_gate !== undefined && payload.forecast_gate !== 'OFF') issues.push('upstream_forecast_gate_not_off');
    if (payload.promotion_allowed !== undefined && payload.promotion_allowed !== false) issues.push('upstream_promotion_allowed_not_false');
    if (payload.stable_engine_modified === true) issues.push('stable_engine_modified_true');
    if (payload.canonical_workbook_overwrite === true) issues.push('canonical_workbook_overwrite_true');
    if (payload.workbook_write_performed === true) issues.push('upstream_workbook_write_performed_true');
    if (payload.canonical_workbook_write_performed === true) issues.push('upstream_canonical_workbook_write_performed_true');
    const gates = payload.consumer_gates || {};
    for (const [key, expected] of Object.entries(closedGates())) {
      if (gates[key] !== undefined && gates[key] !== expected) issues.push(`${key}_not_closed`);
    }
  }
  return Array.from(new Set(issues));
}

function deriveStatus(sandboxReflection, downstreamContract, sourceReview, sourceEvidence, issues) {
  if (issues.length > 0) {
    return {
      ledger_contract_status: 'forecast_bundle_ledger_contract_blocked',
      readiness_quality: 'governance_issue',
      action: 'hold_ledger_contract',
      severity: 'blocking'
    };
  }

  const reflection = text(sandboxReflection?.reflection_status || sandboxReflection?.status);
  const downstream = text(downstreamContract?.contract_status || downstreamContract?.status);
  const review = text(sourceReview?.review_status || sourceReview?.status);
  const evidence = text(sourceEvidence?.pull_status || sourceEvidence?.status);

  if ([reflection, downstream, review, evidence].some((s) => s.includes('blocked') || s.includes('failed'))) {
    return {
      ledger_contract_status: 'forecast_bundle_ledger_contract_blocked',
      readiness_quality: 'upstream_blocked',
      action: 'repair_upstream_before_ledger_contract',
      severity: 'blocking'
    };
  }

  if ([reflection, downstream, review].some((s) => s.includes('review_required') || s.includes('degraded'))) {
    return {
      ledger_contract_status: 'forecast_bundle_ledger_contract_review_required',
      readiness_quality: 'manual_review_required',
      action: 'review_before_ledger_write_activation',
      severity: 'review_required'
    };
  }

  if (reflection.includes('ready') && downstream.includes('ready') && review.includes('ready')) {
    return {
      ledger_contract_status: 'forecast_bundle_ledger_contract_ready',
      readiness_quality: 'ready_for_future_forecast_bundle_ledger_activation',
      action: 'eligible_for_future_ledger_writer_activation',
      severity: 'none'
    };
  }

  return {
    ledger_contract_status: 'forecast_bundle_ledger_contract_only',
    readiness_quality: 'contract_only_no_activation',
    action: 'continue_contract_build',
    severity: 'none'
  };
}

function buildLedgerContract(policy, sandboxReflection, downstreamContract, sourceReview, sourceEvidence) {
  const reflectionPacket = sandboxReflection?.reflection_packet || {};
  return {
    contract_type: 'forecast_bundle_ledger_activation_contract',
    ledger_write_performed: false,
    ledger_write_enabled: false,
    activation_required: 'explicit_future_approval',
    target_path_pattern: policy.target_path_pattern || 'forecast_bundle_ledger/snapshots/session_*.json',
    required_inputs: policy.required_inputs || [],
    event: sourceEvidence?.event || reflectionPacket.event || '',
    session: sourceEvidence?.session || reflectionPacket.session || '',
    source_review_status: sourceReview?.review_status || downstreamContract?.source_review_status || '',
    sandbox_reflection_status: sandboxReflection?.reflection_status || '',
    downstream_contract_status: downstreamContract?.contract_status || '',
    source_pull_status: sourceEvidence?.pull_status || '',
    source_count: num(sourceEvidence?.source_count ?? reflectionPacket.source_count),
    ready_source_count: num(sourceEvidence?.ready_source_count ?? reflectionPacket.ready_source_count),
    degraded_source_count: num(sourceEvidence?.degraded_source_count ?? reflectionPacket.degraded_source_count),
    failed_source_count: num(sourceEvidence?.failed_source_count ?? reflectionPacket.failed_source_count),
    row_count: num(sourceEvidence?.row_count ?? reflectionPacket.row_count),
    canonical_workbook_dependency: 'blocked',
    forecast_gate_dependency: 'blocked'
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const sandboxReflection = readJsonMaybe(args.sandboxReflection);
  const downstreamContract = readJsonMaybe(args.downstreamContract);
  const sourceReview = readJsonMaybe(args.sourceReview);
  const sourceEvidence = readJsonMaybe(args.sourceEvidence);
  const payloads = [sandboxReflection, downstreamContract, sourceReview, sourceEvidence];
  const issues = governanceIssues(policy, args, payloads);
  const derived = deriveStatus(sandboxReflection, downstreamContract, sourceReview, sourceEvidence, issues);
  const ledgerContract = buildLedgerContract(policy, sandboxReflection, downstreamContract, sourceReview, sourceEvidence);

  const status = {
    schema_version: 'f1_session_forecast_bundle_ledger_activation_contract_v31e_2026-06-16',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    forecast_bundle_ledger_write_performed: false,
    sandbox_reflection_supplied: Boolean(sandboxReflection),
    downstream_contract_supplied: Boolean(downstreamContract),
    source_review_supplied: Boolean(sourceReview),
    source_evidence_supplied: Boolean(sourceEvidence),
    ...derived,
    governance_issues: issues,
    ledger_contract: ledgerContract,
    consumer_gates: closedGates(),
    next_step: derived.ledger_contract_status === 'forecast_bundle_ledger_contract_ready'
      ? 'v31f_race_fantasy_readiness_metadata_contracts'
      : 'continue_review_or_repair_before_ledger_activation'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: status.ledger_contract_status !== 'forecast_bundle_ledger_contract_blocked', generated_utc: status.generated_utc, out: args.out, ledger_contract_status: status.ledger_contract_status });
  const ok = status.ledger_contract_status !== 'forecast_bundle_ledger_contract_blocked';
  console.log(JSON.stringify({ ok, out: args.out, ledger_contract_status: status.ledger_contract_status, readiness_quality: status.readiness_quality }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
