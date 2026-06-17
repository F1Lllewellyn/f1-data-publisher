import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_operator_review_verifier_policy_v33a.json';
const DEFAULT_OUT = 'health/session_processor_operator_review_verifier_v33a_status.json';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: '',
    handoffStatus: '',
    handoffPacket: '',
    mode: 'dry_run',
    execute: false,
    activate: false,
    allowLive: false,
    allowSandboxLive: false,
    allowProductionAutomation: false,
    allowForecastGate: false,
    allowCanonicalWorkbookWrite: false,
    allowForecastBundleWrite: false,
    allowRacePredictionsRefresh: false,
    allowFantasyRefresh: false,
    allowNotificationSend: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) {
      args.policy = value;
      i += 1;
    } else if (key === '--out' && value) {
      args.out = value;
      i += 1;
    } else if (key === '--log' && value) {
      args.log = value;
      i += 1;
    } else if (key === '--handoff-status' && value) {
      args.handoffStatus = value;
      i += 1;
    } else if (key === '--handoff-packet' && value) {
      args.handoffPacket = value;
      i += 1;
    } else if (key === '--mode' && value) {
      args.mode = value;
      i += 1;
    } else if (key === '--execute' && value) {
      args.execute = value === 'true';
      i += 1;
    } else if (key === '--activate' && value) {
      args.activate = value === 'true';
      i += 1;
    } else if (key === '--allow-live' && value) {
      args.allowLive = value === 'true';
      i += 1;
    } else if (key === '--allow-sandbox-live' && value) {
      args.allowSandboxLive = value === 'true';
      i += 1;
    } else if (key === '--allow-production-automation' && value) {
      args.allowProductionAutomation = value === 'true';
      i += 1;
    } else if (key === '--allow-forecast-gate' && value) {
      args.allowForecastGate = value === 'true';
      i += 1;
    } else if (key === '--allow-canonical-workbook-write' && value) {
      args.allowCanonicalWorkbookWrite = value === 'true';
      i += 1;
    } else if (key === '--allow-forecast-bundle-write' && value) {
      args.allowForecastBundleWrite = value === 'true';
      i += 1;
    } else if (key === '--allow-race-predictions-refresh' && value) {
      args.allowRacePredictionsRefresh = value === 'true';
      i += 1;
    } else if (key === '--allow-fantasy-refresh' && value) {
      args.allowFantasyRefresh = value === 'true';
      i += 1;
    } else if (key === '--allow-notification-send' && value) {
      args.allowNotificationSend = value === 'true';
      i += 1;
    }
  }
  return args;
}

function readJsonMaybe(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function readTextMaybe(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return '';
  return fs.readFileSync(filePath, 'utf8');
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function bool(value) {
  return value === true;
}

function lower(value) {
  return String(value ?? '').toLowerCase();
}

function governanceIssues(name, payload) {
  const issues = [];
  if (!payload) return issues;
  if (payload.production_automation && payload.production_automation !== 'OFF') issues.push(`${name}:production_automation_not_off`);
  if (payload.forecast_gate && payload.forecast_gate !== 'OFF') issues.push(`${name}:forecast_gate_not_off`);
  if (bool(payload.promotion_allowed) || bool(payload.promotion) || bool(payload.model_promotion_allowed)) issues.push(`${name}:promotion_not_false`);
  if (bool(payload.execute_performed)) issues.push(`${name}:execute_performed`);
  if (bool(payload.live_fetch_performed)) issues.push(`${name}:live_fetch_performed`);
  if (bool(payload.forecast_bundle_ledger_write_performed)) issues.push(`${name}:forecast_bundle_ledger_write_performed`);
  if (bool(payload.race_predictions_refresh_performed)) issues.push(`${name}:race_predictions_refresh_performed`);
  if (bool(payload.fantasy_refresh_performed)) issues.push(`${name}:fantasy_refresh_performed`);
  if (bool(payload.notification_sent)) issues.push(`${name}:notification_sent`);
  if (bool(payload.canonical_workbook_overwrite)) issues.push(`${name}:canonical_workbook_overwrite`);
  if (bool(payload.stable_engine_modified)) issues.push(`${name}:stable_engine_modified`);
  for (const [gate, enabled] of Object.entries(payload.consumer_gates || {})) {
    if (enabled === true) issues.push(`${name}:consumer_gate_open:${gate}`);
  }
  return issues;
}

function verifyEvidenceChain(handoffStatus) {
  const expected = [
    'v32j_forecast_bundle_ledger_evidence_review',
    'v32k_race_predictions_readiness_refresh_preflight',
    'v32l_fantasy_predictions_readiness_refresh_preflight',
    'v32m_material_change_notification_preflight'
  ];
  const chain = Array.isArray(handoffStatus?.evidence_chain) ? handoffStatus.evidence_chain : [];
  const byName = new Map(chain.map(item => [item.name, item]));
  const blockers = [];
  const evidence = [];
  for (const name of expected) {
    const item = byName.get(name);
    if (!item) {
      blockers.push(`missing_evidence_chain_item:${name}`);
      evidence.push({ name, present: false, ready: false, status: 'missing' });
      continue;
    }
    const status = lower(item.status);
    const ready = item.present === true && status.includes('ready') && !status.includes('blocked') && !status.includes('failed');
    if (!ready) blockers.push(`not_ready_evidence_chain_item:${name}:${item.status}`);
    evidence.push({ name, present: item.present === true, ready, status: item.status, quality: item.quality || '' });
  }
  return { evidence, blockers };
}

function packetIssues(packetText) {
  const issues = [];
  if (!packetText.trim()) {
    issues.push('missing_handoff_packet_markdown');
    return issues;
  }
  if (!packetText.includes('Status: operator_handoff_readiness_packet_ready')) issues.push('handoff_packet_status_not_ready');
  if (!packetText.includes('Readiness quality: dry_run_readiness_chain_finalized_for_operator_review')) issues.push('handoff_packet_quality_not_finalized');
  if (!packetText.includes('- None')) issues.push('handoff_packet_blockers_not_none');
  return issues;
}

const args = parseArgs(process.argv);
const policy = readJsonMaybe(args.policy) || {};
const handoffStatus = readJsonMaybe(args.handoffStatus);
const handoffPacket = readTextMaybe(args.handoffPacket);

const blockers = [];
if (!handoffStatus) blockers.push('missing_handoff_status_json');
if (args.mode !== 'dry_run' && args.mode !== 'operator_review') blockers.push(`unsupported_mode:${args.mode}`);
if (args.execute) blockers.push('execute_true_rejected');
if (args.activate) blockers.push('activate_true_rejected');
if (args.allowLive) blockers.push('allow_live_true_rejected');
if (args.allowSandboxLive) blockers.push('allow_sandbox_live_true_rejected_for_v33a');
if (args.allowProductionAutomation) blockers.push('allow_production_automation_true_rejected');
if (args.allowForecastGate) blockers.push('allow_forecast_gate_true_rejected');
if (args.allowCanonicalWorkbookWrite) blockers.push('allow_canonical_workbook_write_true_rejected');
if (args.allowForecastBundleWrite) blockers.push('allow_forecast_bundle_write_true_rejected');
if (args.allowRacePredictionsRefresh) blockers.push('allow_race_predictions_refresh_true_rejected');
if (args.allowFantasyRefresh) blockers.push('allow_fantasy_refresh_true_rejected');
if (args.allowNotificationSend) blockers.push('allow_notification_send_true_rejected');

if (handoffStatus) {
  if (handoffStatus.operator_handoff_readiness_packet_status !== 'operator_handoff_readiness_packet_ready') blockers.push('handoff_status_not_ready');
  if (handoffStatus.readiness_quality !== 'dry_run_readiness_chain_finalized_for_operator_review') blockers.push('handoff_quality_not_finalized_for_operator_review');
  if (Array.isArray(handoffStatus.blockers) && handoffStatus.blockers.length > 0) blockers.push('handoff_contains_blockers');
  blockers.push(...governanceIssues('handoff_status', handoffStatus));
}
blockers.push(...packetIssues(handoffPacket));

const evidenceReview = verifyEvidenceChain(handoffStatus);
blockers.push(...evidenceReview.blockers);

const policyIssues = [];
if (policy.production_automation !== 'OFF') policyIssues.push('policy_production_automation_not_off');
if (policy.forecast_gate !== 'OFF') policyIssues.push('policy_forecast_gate_not_off');
if (policy.promotion_allowed !== false) policyIssues.push('policy_promotion_not_false');
if (policy.allow_sandbox_live_in_v33a !== false) policyIssues.push('policy_allow_sandbox_live_in_v33a_not_false');
blockers.push(...policyIssues);

const ready = blockers.length === 0;
const payload = {
  schema_version: 'f1_session_processor_operator_review_verifier_v33a_2026-06-17',
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
  forecast_bundle_ledger_write_performed: false,
  race_predictions_refresh_performed: false,
  fantasy_refresh_performed: false,
  notification_sent: false,
  operator_review_verifier_status: ready
    ? 'operator_review_verifier_ready_for_controlled_sandbox_live_review'
    : 'operator_review_verifier_blocked',
  readiness_quality: ready
    ? 'v32_handoff_chain_verified_no_activation_paths_open'
    : 'v32_handoff_chain_requires_repair_before_v33b',
  verified_handoff_status: handoffStatus ? {
    status: handoffStatus.operator_handoff_readiness_packet_status,
    quality: handoffStatus.readiness_quality,
    material_change_detected: handoffStatus.material_change_detected === true
  } : null,
  evidence_chain: evidenceReview.evidence,
  blockers,
  consumer_gates: {
    workbook_write_enabled: false,
    canonical_workbook_write_enabled: false,
    forecast_bundle_write_enabled: false,
    race_predictions_refresh_enabled: false,
    fantasy_refresh_enabled: false,
    notification_send_enabled: false,
    production_automation_enabled: false,
    sandbox_live_source_pull_enabled: false
  },
  next_step: ready
    ? 'v33b_one_command_end_to_end_dry_run_rehearsal'
    : 'repair_v33a_operator_review_verifier_blockers_before_v33b'
};

writeJson(args.out, payload);
if (args.log) writeJson(args.log, { ok: ready, generated_utc: payload.generated_utc, out: args.out, status: payload.operator_review_verifier_status });
console.log(JSON.stringify({
  ok: ready,
  out: args.out,
  operator_review_verifier_status: payload.operator_review_verifier_status,
  readiness_quality: payload.readiness_quality,
  blocker_count: blockers.length
}, null, 2));
process.exit(ready ? 0 : 1);
