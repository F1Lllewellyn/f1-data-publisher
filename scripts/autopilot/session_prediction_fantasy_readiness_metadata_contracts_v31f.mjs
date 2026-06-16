import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_prediction_fantasy_readiness_metadata_contracts_policy_v31f.json';
const DEFAULT_OUT = 'health/session_prediction_fantasy_readiness_metadata_contracts_v31f_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    ledgerContract: '',
    sandboxReflection: '',
    sourceReview: '',
    sourceEvidence: '',
    mode: 'dry_run',
    execute: false,
    allowPredictionRefresh: false,
    allowFantasyRefresh: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--ledger-contract' && value) { args.ledgerContract = value; i += 1; }
    else if (key === '--sandbox-reflection' && value) { args.sandboxReflection = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--source-evidence' && value) { args.sourceEvidence = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--allow-prediction-refresh' && value) { args.allowPredictionRefresh = value === 'true'; i += 1; }
    else if (key === '--allow-fantasy-refresh' && value) { args.allowFantasyRefresh = value === 'true'; i += 1; }
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
  if (args.execute) issues.push('execute_true_not_supported_for_v31f_contract');
  if (args.allowPredictionRefresh) issues.push('allow_prediction_refresh_true_not_supported_for_v31f_contract');
  if (args.allowFantasyRefresh) issues.push('allow_fantasy_refresh_true_not_supported_for_v31f_contract');
  for (const payload of payloads.filter(Boolean)) {
    if (payload.production_automation !== undefined && payload.production_automation !== 'OFF') issues.push('upstream_production_automation_not_off');
    if (payload.forecast_gate !== undefined && payload.forecast_gate !== 'OFF') issues.push('upstream_forecast_gate_not_off');
    if (payload.promotion_allowed !== undefined && payload.promotion_allowed !== false) issues.push('upstream_promotion_allowed_not_false');
    if (payload.stable_engine_modified === true) issues.push('stable_engine_modified_true');
    if (payload.canonical_workbook_overwrite === true) issues.push('canonical_workbook_overwrite_true');
    if (payload.race_predictions_refresh_performed === true) issues.push('upstream_prediction_refresh_performed_true');
    if (payload.fantasy_refresh_performed === true) issues.push('upstream_fantasy_refresh_performed_true');
    const gates = payload.consumer_gates || {};
    for (const [key, expected] of Object.entries(closedGates())) {
      if (gates[key] !== undefined && gates[key] !== expected) issues.push(`${key}_not_closed`);
    }
  }
  return Array.from(new Set(issues));
}

function deriveStatus(ledgerContract, sandboxReflection, sourceReview, sourceEvidence, issues) {
  if (issues.length > 0) {
    return {
      readiness_contract_status: 'prediction_fantasy_readiness_contract_blocked',
      readiness_quality: 'governance_issue',
      action: 'hold_readiness_metadata_contract',
      severity: 'blocking'
    };
  }

  const ledger = text(ledgerContract?.ledger_contract_status || ledgerContract?.status);
  const reflection = text(sandboxReflection?.reflection_status || sandboxReflection?.status);
  const review = text(sourceReview?.review_status || sourceReview?.status);
  const evidence = text(sourceEvidence?.pull_status || sourceEvidence?.status);

  if ([ledger, reflection, review, evidence].some((s) => s.includes('blocked') || s.includes('failed'))) {
    return {
      readiness_contract_status: 'prediction_fantasy_readiness_contract_blocked',
      readiness_quality: 'upstream_blocked',
      action: 'repair_upstream_before_readiness_metadata',
      severity: 'blocking'
    };
  }

  if ([ledger, reflection, review].some((s) => s.includes('review_required') || s.includes('degraded'))) {
    return {
      readiness_contract_status: 'prediction_fantasy_readiness_contract_review_required',
      readiness_quality: 'manual_review_required',
      action: 'review_before_prediction_or_fantasy_readiness_activation',
      severity: 'review_required'
    };
  }

  if (ledger.includes('ready') && reflection.includes('ready') && review.includes('ready')) {
    return {
      readiness_contract_status: 'prediction_fantasy_readiness_contract_ready',
      readiness_quality: 'ready_for_future_metadata_refresh_activation',
      action: 'eligible_for_future_readiness_metadata_activation',
      severity: 'none'
    };
  }

  return {
    readiness_contract_status: 'prediction_fantasy_readiness_contract_only',
    readiness_quality: 'contract_only_no_activation',
    action: 'continue_contract_build',
    severity: 'none'
  };
}

function buildMetadataContracts(policy, ledgerContract, sandboxReflection, sourceReview, sourceEvidence) {
  const common = {
    event: sourceEvidence?.event || sandboxReflection?.reflection_packet?.event || ledgerContract?.ledger_contract?.event || '',
    session: sourceEvidence?.session || sandboxReflection?.reflection_packet?.session || ledgerContract?.ledger_contract?.session || '',
    source_pull_status: sourceEvidence?.pull_status || ledgerContract?.ledger_contract?.source_pull_status || '',
    source_review_status: sourceReview?.review_status || ledgerContract?.ledger_contract?.source_review_status || '',
    source_count: num(sourceEvidence?.source_count ?? ledgerContract?.ledger_contract?.source_count),
    ready_source_count: num(sourceEvidence?.ready_source_count ?? ledgerContract?.ledger_contract?.ready_source_count),
    degraded_source_count: num(sourceEvidence?.degraded_source_count ?? ledgerContract?.ledger_contract?.degraded_source_count),
    failed_source_count: num(sourceEvidence?.failed_source_count ?? ledgerContract?.ledger_contract?.failed_source_count),
    row_count: num(sourceEvidence?.row_count ?? ledgerContract?.ledger_contract?.row_count)
  };
  return (policy.metadata_contracts || []).map((contract) => ({
    contract_id: contract.contract_id,
    surface: contract.surface,
    metadata_only: true,
    refresh_enabled: false,
    refresh_performed: false,
    produces_prediction: false,
    produces_fantasy_pick: false,
    activation_required: 'explicit_future_approval',
    required_fields: contract.required_fields || [],
    ...common
  }));
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const ledgerContract = readJsonMaybe(args.ledgerContract);
  const sandboxReflection = readJsonMaybe(args.sandboxReflection);
  const sourceReview = readJsonMaybe(args.sourceReview);
  const sourceEvidence = readJsonMaybe(args.sourceEvidence);
  const payloads = [ledgerContract, sandboxReflection, sourceReview, sourceEvidence];
  const issues = governanceIssues(policy, args, payloads);
  const derived = deriveStatus(ledgerContract, sandboxReflection, sourceReview, sourceEvidence, issues);
  const metadataContracts = buildMetadataContracts(policy, ledgerContract, sandboxReflection, sourceReview, sourceEvidence);

  const status = {
    schema_version: 'f1_session_prediction_fantasy_readiness_metadata_contracts_v31f_2026-06-16',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    race_predictions_refresh_performed: false,
    fantasy_refresh_performed: false,
    ledger_contract_supplied: Boolean(ledgerContract),
    sandbox_reflection_supplied: Boolean(sandboxReflection),
    source_review_supplied: Boolean(sourceReview),
    source_evidence_supplied: Boolean(sourceEvidence),
    ...derived,
    governance_issues: issues,
    metadata_contract_count: metadataContracts.length,
    metadata_contracts: metadataContracts,
    consumer_gates: closedGates(),
    next_step: derived.readiness_contract_status === 'prediction_fantasy_readiness_contract_ready'
      ? 'v31g_material_notification_preview_gate'
      : 'continue_review_or_repair_before_readiness_metadata_activation'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: status.readiness_contract_status !== 'prediction_fantasy_readiness_contract_blocked', generated_utc: status.generated_utc, out: args.out, readiness_contract_status: status.readiness_contract_status });
  const ok = status.readiness_contract_status !== 'prediction_fantasy_readiness_contract_blocked';
  console.log(JSON.stringify({ ok, out: args.out, readiness_contract_status: status.readiness_contract_status, readiness_quality: status.readiness_quality, metadata_contract_count: status.metadata_contract_count }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
