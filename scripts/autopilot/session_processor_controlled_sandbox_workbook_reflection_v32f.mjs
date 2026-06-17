import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_controlled_sandbox_workbook_reflection_policy_v32f.json';
const DEFAULT_OUT = 'health/session_processor_controlled_sandbox_workbook_reflection_v32f_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    sandboxArtifact: '',
    preflight: '',
    reflectionContract: '',
    eventId: 'unknown_event',
    sessionId: 'unknown_session',
    mode: 'dry_run',
    execute: false,
    activate: false,
    allowLive: false,
    allowSandboxWorkbookWrite: false,
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
    else if (key === '--reflection-contract' && value) { args.reflectionContract = value; i += 1; }
    else if (key === '--event-id' && value) { args.eventId = value; i += 1; }
    else if (key === '--session-id' && value) { args.sessionId = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--activate' && value) { args.activate = value === 'true'; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--allow-sandbox-workbook-write' && value) { args.allowSandboxWorkbookWrite = value === 'true'; i += 1; }
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

function statusOf(payload) {
  if (!payload) return 'missing';
  return String(
    payload.sandbox_workbook_reflection_preflight_status ||
    payload.reflection_status ||
    payload.sandbox_kpi_reflection_status ||
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
  if (bool(payload.activation_performed)) issues.push(`${name}:activation_performed`);
  if (bool(payload.stable_engine_modified)) issues.push(`${name}:stable_engine_modified`);
  if (bool(payload.canonical_workbook_overwrite)) issues.push(`${name}:canonical_workbook_overwrite`);
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

function buildSandboxArtifact(args, preflight, reflectionContract) {
  const packet = reflectionContract?.reflection_packet || {};
  return {
    artifact_type: 'sandbox_workbook_reflection_v32f',
    generated_utc: nowIso(),
    event_id: args.eventId,
    session_id: args.sessionId,
    target: 'sandbox_only',
    canonical_workbook_target: 'blocked',
    write_scope: 'sandbox_artifact_only',
    source_review_status: packet.source_review_status || 'unknown',
    downstream_contract_status: packet.downstream_contract_status || 'unknown',
    source_pull_status: packet.source_pull_status || 'unknown',
    source_count: packet.source_count ?? null,
    ready_source_count: packet.ready_source_count ?? null,
    degraded_source_count: packet.degraded_source_count ?? null,
    failed_source_count: packet.failed_source_count ?? null,
    row_count: packet.row_count ?? null,
    preflight_status: statusOf(preflight),
    reflection_status: statusOf(reflectionContract),
    consumer_gates: closedGates()
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const preflight = readJsonMaybe(args.preflight);
  const reflectionContract = readJsonMaybe(args.reflectionContract);
  const preflightStatus = statusOf(preflight);
  const reflectionStatus = statusOf(reflectionContract);
  const sandboxArtifactPath = args.sandboxArtifact || policy.sandbox_artifact_default || 'sandbox/session_processor/workbook_reflection_v32f.json';
  const blockers = [];

  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.sandbox_workbook_write_allowed !== true) blockers.push('policy_sandbox_workbook_write_allowed_not_true');
  if (policy.canonical_workbook_write_allowed !== false) blockers.push('policy_canonical_workbook_write_allowed_not_false');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');
  if (policy.live_fetch_allowed !== false) blockers.push('policy_live_fetch_allowed_not_false');
  if (args.mode !== 'dry_run' && args.mode !== 'sandbox_reflection') blockers.push(`unsupported_mode:${args.mode}`);
  if (args.activate) blockers.push('activate_true_rejected_by_v32f');
  if (args.allowLive) blockers.push('allow_live_true_rejected_by_v32f');
  if (args.allowCanonicalWorkbookWrite) blockers.push('canonical_workbook_write_true_rejected_by_v32f');
  if (args.execute && args.mode !== 'sandbox_reflection') blockers.push('execute_true_requires_mode_sandbox_reflection');
  if (args.execute && !args.operatorApproval) blockers.push('execute_true_requires_operator_approval');
  if (args.execute && !args.allowSandboxWorkbookWrite) blockers.push('execute_true_requires_allow_sandbox_workbook_write');
  if (!preflight) blockers.push('missing_required_input:sandbox_workbook_reflection_preflight');
  if (!reflectionContract) blockers.push('missing_required_input:sandbox_reflection_contract');
  if (preflight && blockedLike(preflightStatus)) blockers.push(`blocked_preflight:${preflightStatus}`);
  if (reflectionContract && blockedLike(reflectionStatus)) blockers.push(`blocked_reflection_contract:${reflectionStatus}`);
  if (preflight && preflightStatus !== policy.required_preflight_status) blockers.push(`preflight_status_not_required:${preflightStatus}`);
  if (reflectionContract && reflectionStatus !== policy.required_reflection_status) blockers.push(`reflection_status_not_required:${reflectionStatus}`);
  blockers.push(...governanceIssues('preflight', preflight));
  blockers.push(...governanceIssues('reflection_contract', reflectionContract));

  const uniqueBlockers = Array.from(new Set(blockers));
  const sandboxWritePerformed = args.execute && uniqueBlockers.length === 0;
  const sandboxArtifact = sandboxWritePerformed ? buildSandboxArtifact(args, preflight, reflectionContract) : null;
  if (sandboxWritePerformed) writeJson(sandboxArtifactPath, sandboxArtifact);

  const status = {
    schema_version: 'f1_session_processor_controlled_sandbox_workbook_reflection_v32f_2026-06-17',
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
    sandbox_workbook_write_requested: args.allowSandboxWorkbookWrite,
    sandbox_workbook_write_performed: sandboxWritePerformed,
    sandbox_artifact_path: sandboxWritePerformed ? sandboxArtifactPath : '',
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
    reflection_contract_status: reflectionStatus,
    sandbox_workbook_reflection_status: uniqueBlockers.length > 0
      ? 'controlled_sandbox_workbook_reflection_blocked'
      : (sandboxWritePerformed ? 'controlled_sandbox_workbook_reflection_written_sandbox_only' : 'controlled_sandbox_workbook_reflection_ready_not_written'),
    readiness_quality: uniqueBlockers.length > 0
      ? 'sandbox_workbook_reflection_blockers_present'
      : (sandboxWritePerformed ? 'sandbox_only_reflection_artifact_written' : 'sandbox_reflection_ready_for_operator_approved_write'),
    blockers: uniqueBlockers,
    sandbox_artifact: sandboxArtifact,
    blocked_write_targets: policy.blocked_write_targets || [],
    consumer_gates: closedGates(),
    activation_boundary: {
      this_patch_can_write_sandbox_artifact_only: true,
      this_patch_writes_canonical_workbook: false,
      future_forecast_bundle_write_must_be_separate_patch: true,
      future_production_activation_must_be_separate_patch: true
    },
    next_step: uniqueBlockers.length > 0
      ? 'resolve_v32f_sandbox_workbook_reflection_blockers'
      : (sandboxWritePerformed ? policy.next_allowed_layer : 'run_v32f_with_operator_approval_or_prepare_review_gate')
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: uniqueBlockers.length === 0, generated_utc: status.generated_utc, out: args.out, reflection_status: status.sandbox_workbook_reflection_status, sandbox_artifact_path: status.sandbox_artifact_path });
  console.log(JSON.stringify({
    ok: uniqueBlockers.length === 0,
    out: args.out,
    sandbox_workbook_reflection_status: status.sandbox_workbook_reflection_status,
    sandbox_workbook_write_performed: sandboxWritePerformed,
    blocker_count: uniqueBlockers.length
  }, null, 2));
  process.exit(uniqueBlockers.length === 0 ? 0 : 1);
}

main();
