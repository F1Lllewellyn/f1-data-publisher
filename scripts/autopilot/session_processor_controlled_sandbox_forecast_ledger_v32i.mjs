import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_controlled_sandbox_forecast_ledger_policy_v32i.json';
const DEFAULT_OUT = 'health/session_processor_controlled_sandbox_forecast_ledger_v32i_status.json';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: '',
    sandboxArtifact: '',
    preflight: '',
    ledgerContract: '',
    eventId: 'unknown_event',
    sessionId: 'unknown_session',
    mode: 'dry_run',
    execute: false,
    activate: false,
    allowLive: false,
    allowSandboxLedgerWrite: false,
    allowProductionLedgerWrite: false,
    allowCanonicalWorkbookWrite: false,
    operatorApproval: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--sandbox-artifact' && value) { args.sandboxArtifact = value; i += 1; }
    else if (key === '--preflight' && value) { args.preflight = value; i += 1; }
    else if (key === '--ledger-contract' && value) { args.ledgerContract = value; i += 1; }
    else if (key === '--event-id' && value) { args.eventId = value; i += 1; }
    else if (key === '--session-id' && value) { args.sessionId = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--activate' && value) { args.activate = value === 'true'; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--allow-sandbox-ledger-write' && value) { args.allowSandboxLedgerWrite = value === 'true'; i += 1; }
    else if (key === '--allow-production-ledger-write' && value) { args.allowProductionLedgerWrite = value === 'true'; i += 1; }
    else if (key === '--allow-canonical-workbook-write' && value) { args.allowCanonicalWorkbookWrite = value === 'true'; i += 1; }
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

function preflightStatusOf(payload) {
  if (!payload) return 'missing';
  return String(payload.forecast_bundle_ledger_write_preflight_status || payload.status || payload.decision || 'present');
}

function contractStatusOf(payload) {
  if (!payload) return 'missing';
  return String(payload.ledger_contract_status || payload.status || payload.readiness_status || payload.decision || 'present');
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
  if (bool(payload.canonical_workbook_write_performed)) issues.push(`${name}:canonical_workbook_write_performed`);
  if (bool(payload.forecast_bundle_ledger_write_performed) || bool(payload.forecast_bundle_ledger_written)) issues.push(`${name}:forecast_bundle_ledger_write_performed`);
  if (bool(payload.race_predictions_refresh_performed)) issues.push(`${name}:race_predictions_refresh_performed`);
  if (bool(payload.fantasy_refresh_performed)) issues.push(`${name}:fantasy_refresh_performed`);
  if (bool(payload.notification_sent)) issues.push(`${name}:notification_sent`);
  const gates = payload.consumer_gates || {};
  for (const [gate, expected] of Object.entries(closedGates())) {
    if (gates[gate] !== undefined && gates[gate] !== expected) issues.push(`${name}:consumer_gate_open:${gate}`);
  }
  return issues;
}

function buildSandboxLedgerSnapshot(args, ledgerContract) {
  const contract = ledgerContract?.ledger_contract || {};
  return {
    artifact_type: 'sandbox_forecast_bundle_ledger_snapshot_v32i',
    generated_utc: nowIso(),
    event_id: args.eventId,
    session_id: args.sessionId,
    target: 'sandbox_only',
    production_ledger_target: 'blocked',
    canonical_workbook_target: 'blocked',
    write_scope: 'sandbox_artifact_only',
    event: contract.event || args.eventId,
    session: contract.session || args.sessionId,
    source_review_status: contract.source_review_status || 'unknown',
    sandbox_reflection_status: contract.sandbox_reflection_status || 'unknown',
    downstream_contract_status: contract.downstream_contract_status || 'unknown',
    source_pull_status: contract.source_pull_status || 'unknown',
    source_count: contract.source_count ?? null,
    ready_source_count: contract.ready_source_count ?? null,
    degraded_source_count: contract.degraded_source_count ?? null,
    failed_source_count: contract.failed_source_count ?? null,
    row_count: contract.row_count ?? null,
    forecast_gate_dependency: 'blocked',
    consumer_gates: closedGates()
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const preflight = readJsonMaybe(args.preflight);
  const ledgerContract = readJsonMaybe(args.ledgerContract);
  const preflightStatus = preflightStatusOf(preflight);
  const contractStatus = contractStatusOf(ledgerContract);
  const sandboxArtifactPath = args.sandboxArtifact || policy.sandbox_artifact_default || 'sandbox/session_processor/forecast_bundle_ledger_snapshot_v32i.json';
  const blockers = [];

  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.sandbox_forecast_ledger_write_allowed !== true) blockers.push('policy_sandbox_forecast_ledger_write_allowed_not_true');
  if (policy.production_forecast_ledger_write_allowed !== false) blockers.push('policy_production_forecast_ledger_write_allowed_not_false');
  if (policy.canonical_workbook_write_allowed !== false) blockers.push('policy_canonical_workbook_write_allowed_not_false');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');
  if (policy.live_fetch_allowed !== false) blockers.push('policy_live_fetch_allowed_not_false');
  if (args.mode !== 'dry_run' && args.mode !== 'sandbox_ledger') blockers.push(`unsupported_mode:${args.mode}`);
  if (args.activate) blockers.push('activate_true_rejected_by_v32i');
  if (args.allowLive) blockers.push('allow_live_true_rejected_by_v32i');
  if (args.allowProductionLedgerWrite) blockers.push('production_ledger_write_true_rejected_by_v32i');
  if (args.allowCanonicalWorkbookWrite) blockers.push('canonical_workbook_write_true_rejected_by_v32i');
  if (args.execute && args.mode !== 'sandbox_ledger') blockers.push('execute_true_requires_mode_sandbox_ledger');
  if (args.execute && !args.operatorApproval) blockers.push('execute_true_requires_operator_approval');
  if (args.execute && !args.allowSandboxLedgerWrite) blockers.push('execute_true_requires_allow_sandbox_ledger_write');
  if (!preflight) blockers.push('missing_required_input:forecast_bundle_ledger_write_preflight');
  if (!ledgerContract) blockers.push('missing_required_input:forecast_bundle_ledger_contract');
  if (preflight && blockedLike(preflightStatus)) blockers.push(`blocked_preflight:${preflightStatus}`);
  if (ledgerContract && blockedLike(contractStatus)) blockers.push(`blocked_ledger_contract:${contractStatus}`);
  if (preflight && preflightStatus !== policy.required_preflight_status) blockers.push(`preflight_status_not_required:${preflightStatus}`);
  if (ledgerContract && contractStatus !== policy.required_contract_status) blockers.push(`ledger_contract_status_not_required:${contractStatus}`);
  blockers.push(...governanceIssues('preflight', preflight));
  blockers.push(...governanceIssues('ledger_contract', ledgerContract));

  const uniqueBlockers = Array.from(new Set(blockers));
  const sandboxLedgerWritePerformed = args.execute && uniqueBlockers.length === 0;
  const sandboxSnapshot = sandboxLedgerWritePerformed ? buildSandboxLedgerSnapshot(args, ledgerContract) : null;
  if (sandboxLedgerWritePerformed) writeJson(sandboxArtifactPath, sandboxSnapshot);

  const status = {
    schema_version: 'f1_session_processor_controlled_sandbox_forecast_ledger_v32i_2026-06-17',
    generated_utc: nowIso(),
    mode: args.mode,
    event_id: args.eventId,
    session_id: args.sessionId,
    execute_requested: args.execute,
    execute_performed: false,
    activate_requested: args.activate,
    activation_performed: false,
    live_fetch_requested: args.allowLive,
    live_fetch_performed: false,
    sandbox_forecast_ledger_write_requested: args.allowSandboxLedgerWrite,
    sandbox_forecast_ledger_write_performed: sandboxLedgerWritePerformed,
    sandbox_artifact_path: sandboxLedgerWritePerformed ? sandboxArtifactPath : '',
    production_forecast_ledger_write_requested: args.allowProductionLedgerWrite,
    production_forecast_ledger_write_performed: false,
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
    preflight_status: preflightStatus,
    ledger_contract_status: contractStatus,
    sandbox_forecast_ledger_status: uniqueBlockers.length > 0
      ? 'controlled_sandbox_forecast_ledger_blocked'
      : (sandboxLedgerWritePerformed ? 'controlled_sandbox_forecast_ledger_written_sandbox_only' : 'controlled_sandbox_forecast_ledger_ready_not_written'),
    readiness_quality: uniqueBlockers.length > 0
      ? 'sandbox_forecast_ledger_blockers_present'
      : (sandboxLedgerWritePerformed ? 'sandbox_only_forecast_ledger_snapshot_written' : 'sandbox_forecast_ledger_ready_for_operator_approved_write'),
    blockers: uniqueBlockers,
    sandbox_snapshot: sandboxSnapshot,
    blocked_write_targets: policy.blocked_write_targets || [],
    consumer_gates: closedGates(),
    activation_boundary: {
      this_patch_can_write_sandbox_forecast_ledger_artifact_only: true,
      this_patch_writes_production_forecast_ledger: false,
      this_patch_writes_canonical_workbook: false,
      future_race_fantasy_refresh_must_be_separate_patch: true,
      future_production_activation_must_be_separate_patch: true
    },
    next_step: uniqueBlockers.length > 0
      ? 'resolve_v32i_sandbox_forecast_ledger_blockers'
      : (sandboxLedgerWritePerformed ? policy.next_allowed_layer : 'run_v32i_with_operator_approval_or_prepare_review_gate')
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: uniqueBlockers.length === 0, generated_utc: status.generated_utc, out: args.out, ledger_status: status.sandbox_forecast_ledger_status, sandbox_artifact_path: status.sandbox_artifact_path });
  console.log(JSON.stringify({
    ok: uniqueBlockers.length === 0,
    out: args.out,
    sandbox_forecast_ledger_status: status.sandbox_forecast_ledger_status,
    sandbox_forecast_ledger_write_performed: sandboxLedgerWritePerformed,
    blocker_count: uniqueBlockers.length
  }, null, 2));
  process.exit(uniqueBlockers.length === 0 ? 0 : 1);
}

main();
