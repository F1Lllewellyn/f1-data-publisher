import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_activation_protocol_policy_v31.json';
const DEFAULT_OUT = 'health/session_processor_activation_protocol_v31_status.json';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: '',
    dashboard: '',
    replay: '',
    source: '',
    threshold: '',
    request: '',
    mode: 'dry_run',
    execute: false,
    allowLive: false,
    allowNotification: false,
    allowWorkbookWrite: false,
    allowPredictionRefresh: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--dashboard' && value) { args.dashboard = value; i += 1; }
    else if (key === '--replay' && value) { args.replay = value; i += 1; }
    else if (key === '--source' && value) { args.source = value; i += 1; }
    else if (key === '--threshold' && value) { args.threshold = value; i += 1; }
    else if (key === '--request' && value) { args.request = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--allow-notification' && value) { args.allowNotification = value === 'true'; i += 1; }
    else if (key === '--allow-workbook-write' && value) { args.allowWorkbookWrite = value === 'true'; i += 1; }
    else if (key === '--allow-prediction-refresh' && value) { args.allowPredictionRefresh = value === 'true'; i += 1; }
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

function statusOf(payload) {
  if (!payload) return 'missing';
  return String(
    payload.status ??
    payload.dashboard_status ??
    payload.replay_status ??
    payload.pull_status ??
    payload.threshold_gate_status ??
    payload.readiness_status ??
    payload.decision ??
    'present'
  );
}

function hasBlockingStatus(payload) {
  const value = lower(statusOf(payload));
  return value.includes('blocked') || value.includes('failure') || value.includes('failed') || value.includes('error');
}

function isReadyLike(payload) {
  const value = lower(statusOf(payload));
  return value.includes('ready') || value.includes('passed') || value.includes('material_change_detected') || value.includes('operator_review');
}

function collectEvidence(policy, inputs) {
  const evidence = [];
  for (const [name, payload] of Object.entries(inputs)) {
    evidence.push({
      name,
      supplied: Boolean(payload),
      status: statusOf(payload),
      ready_like: payload ? isReadyLike(payload) : false,
      blocking: payload ? hasBlockingStatus(payload) : false,
      schema_version: payload?.schema_version ?? null,
      generated_utc: payload?.generated_utc ?? null
    });
  }
  const required = Array.isArray(policy.required_evidence) ? policy.required_evidence : [];
  return evidence.map((item) => ({
    ...item,
    required: required.includes(item.name)
  }));
}

function evaluate(policy, args, inputs) {
  const blockers = [];
  const warnings = [];
  const evidence = collectEvidence(policy, inputs);
  const request = inputs.request || {};
  const activationRequested = request.request_activation === true;
  for (const item of evidence) {
    if (item.required && !item.supplied) {
      const issue = { gate: 'evidence', code: `${item.name}_missing`, detail: 'Required evidence snapshot was not supplied.' };
      if (activationRequested) blockers.push(issue);
      else warnings.push(issue);
    }
    if (item.supplied && item.blocking) blockers.push({ gate: 'evidence', code: `${item.name}_blocking`, detail: item.status });
  }
  if (args.execute) blockers.push({ gate: 'execution', code: 'execute_requested', detail: 'v31 is protocol design only and does not execute activation.' });
  if (args.allowLive) blockers.push({ gate: 'live_fetch', code: 'live_fetch_requested', detail: 'Live fetch cannot be enabled by this dry-run protocol.' });
  if (args.allowNotification) blockers.push({ gate: 'notification', code: 'notification_requested', detail: 'Notification sending remains disabled.' });
  if (args.allowWorkbookWrite) blockers.push({ gate: 'workbook', code: 'workbook_write_requested', detail: 'Canonical workbook writes remain disabled.' });
  if (args.allowPredictionRefresh) blockers.push({ gate: 'prediction_refresh', code: 'prediction_refresh_requested', detail: 'Prediction and fantasy refresh remain disabled.' });
  if (policy.production_automation !== 'OFF') blockers.push({ gate: 'governance', code: 'production_automation_not_off', detail: String(policy.production_automation) });
  if (policy.forecast_gate !== 'OFF') blockers.push({ gate: 'governance', code: 'forecast_gate_not_off', detail: String(policy.forecast_gate) });
  if (policy.promotion_allowed !== false) blockers.push({ gate: 'governance', code: 'promotion_allowed_not_false', detail: String(policy.promotion_allowed) });
  if (request.approval_scope && !Array.isArray(request.approval_scope)) warnings.push({ gate: 'request', code: 'approval_scope_not_array', detail: 'Approval scope should be a list.' });
  const requiredApprovals = Array.isArray(policy.required_manual_approvals) ? policy.required_manual_approvals : [];
  const requestedApprovals = Array.isArray(request.approval_scope) ? request.approval_scope : [];
  const missingApprovals = requiredApprovals.filter((item) => !requestedApprovals.includes(item));
  if (activationRequested && missingApprovals.length > 0) {
    blockers.push({ gate: 'manual_approval', code: 'required_approvals_missing', detail: missingApprovals.join(',') });
  }
  const suppliedRequired = evidence.filter((item) => item.required && item.supplied && !item.blocking).length;
  const requiredCount = evidence.filter((item) => item.required).length;
  const dryRunReady = blockers.length === 0 && requiredCount > 0 && suppliedRequired === requiredCount;
  const contractReady = blockers.length === 0 && requiredCount > 0 && suppliedRequired < requiredCount;
  return {
    blockers,
    warnings,
    evidence,
    activation_protocol_status: dryRunReady ? 'activation_protocol_ready_for_manual_review' : (contractReady ? 'activation_protocol_contract_ready' : 'activation_protocol_blocked'),
    readiness_quality: dryRunReady ? 'all_required_evidence_supplied' : (contractReady ? 'awaiting_required_evidence_snapshots' : 'blocking_issue'),
    recommended_action: dryRunReady ? 'manual_operator_review_before_any_sandbox_live_step' : (contractReady ? 'supply_latest_required_evidence_snapshots' : 'repair_blockers_before_activation_review')
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const inputs = {
    dashboard: readJsonMaybe(args.dashboard),
    replay: readJsonMaybe(args.replay),
    source: readJsonMaybe(args.source),
    threshold: readJsonMaybe(args.threshold),
    request: readJsonMaybe(args.request)
  };
  const result = evaluate(policy, args, inputs);
  const status = {
    schema_version: 'f1_session_processor_activation_protocol_v31_2026-06-16',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    activation_protocol_status: result.activation_protocol_status,
    readiness_quality: result.readiness_quality,
    recommended_action: result.recommended_action,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    live_fetch_enabled: false,
    workbook_write_enabled: false,
    prediction_refresh_enabled: false,
    fantasy_refresh_enabled: false,
    notification_sending_enabled: false,
    evidence: result.evidence,
    blockers: result.blockers,
    warnings: result.warnings,
    required_manual_approvals: policy.required_manual_approvals || [],
    next_step: result.activation_protocol_status === 'activation_protocol_ready_for_manual_review'
      ? 'operator_manual_review_for_sandbox_live_protocol'
      : 'continue_collecting_required_evidence'
  };
  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: result.blockers.length === 0, generated_utc: status.generated_utc, out: args.out, activation_protocol_status: status.activation_protocol_status });
  console.log(JSON.stringify({ ok: result.blockers.length === 0, out: args.out, activation_protocol_status: status.activation_protocol_status, readiness_quality: status.readiness_quality }, null, 2));
  process.exit(result.blockers.length === 0 ? 0 : 1);
}

main();
