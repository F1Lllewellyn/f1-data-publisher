import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_end_to_end_rehearsal_policy_v31h.json';
const DEFAULT_OUT = 'health/session_processor_end_to_end_rehearsal_v31h_status.json';
const DEFAULT_MARKDOWN_OUT = 'health/session_processor_end_to_end_rehearsal_v31h_packet.md';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    markdownOut: DEFAULT_MARKDOWN_OUT,
    sourceReview: '',
    downstreamContract: '',
    sandboxReflection: '',
    forecastLedgerContract: '',
    raceFantasyMetadata: '',
    notificationPreview: '',
    activationProtocol: '',
    mode: 'dry_run',
    execute: false,
    allowLive: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--markdown-out' && value) { args.markdownOut = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--downstream-contract' && value) { args.downstreamContract = value; i += 1; }
    else if (key === '--sandbox-reflection' && value) { args.sandboxReflection = value; i += 1; }
    else if (key === '--forecast-ledger-contract' && value) { args.forecastLedgerContract = value; i += 1; }
    else if (key === '--race-fantasy-metadata' && value) { args.raceFantasyMetadata = value; i += 1; }
    else if (key === '--notification-preview' && value) { args.notificationPreview = value; i += 1; }
    else if (key === '--activation-protocol' && value) { args.activationProtocol = value; i += 1; }
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

function writeText(filePath, text) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, text, 'utf8');
}

function writeJson(filePath, payload) {
  writeText(filePath, `${JSON.stringify(payload, null, 2)}\n`);
}

function lower(value) {
  return String(value ?? '').toLowerCase();
}

function getStatus(payload) {
  if (!payload) return 'missing';
  return String(
    payload.status ||
    payload.rehearsal_status ||
    payload.contract_status ||
    payload.review_status ||
    payload.readiness_status ||
    payload.reflection_status ||
    payload.ledger_contract_status ||
    payload.metadata_contract_status ||
    payload.preview_gate_status ||
    payload.activation_protocol_status ||
    payload.threshold_gate_status ||
    payload.decision ||
    'present'
  );
}

function isReadyLike(status) {
  const value = lower(status);
  return value.includes('ready') || value.includes('eligible') || value.includes('preview') || value.includes('contract') || value.includes('passed');
}

function isBlockedLike(status) {
  const value = lower(status);
  return value.includes('blocked') || value.includes('failed') || value.includes('error') || value.includes('not_ready') || value.includes('rejected');
}

function bool(value) {
  return value === true;
}

function collectGate(name, payload, required) {
  const status = getStatus(payload);
  const present = payload !== null;
  const ready = present && isReadyLike(status) && !isBlockedLike(status);
  const blocked = present && isBlockedLike(status);
  return { name, present, required, status, ready, blocked };
}

function collectGovernance(payloads) {
  const issues = [];
  for (const item of payloads) {
    if (!item.payload) continue;
    const payload = item.payload;
    if (payload.production_automation && payload.production_automation !== 'OFF') issues.push(`${item.name}:production_automation_not_off`);
    if (payload.forecast_gate && payload.forecast_gate !== 'OFF') issues.push(`${item.name}:forecast_gate_not_off`);
    if (bool(payload.promotion_allowed) || bool(payload.promotion) || bool(payload.model_promotion_allowed)) issues.push(`${item.name}:promotion_not_false`);
    if (bool(payload.live_fetch_performed)) issues.push(`${item.name}:live_fetch_performed`);
    if (bool(payload.execute_performed)) issues.push(`${item.name}:execute_performed`);
    if (bool(payload.notification_sent)) issues.push(`${item.name}:notification_sent`);
    if (bool(payload.canonical_workbook_overwrite)) issues.push(`${item.name}:canonical_workbook_overwrite`);
    if (bool(payload.stable_engine_modified)) issues.push(`${item.name}:stable_engine_modified`);
    const consumerGates = payload.consumer_gates || {};
    for (const [gate, enabled] of Object.entries(consumerGates)) {
      if (enabled === true) issues.push(`${item.name}:consumer_gate_open:${gate}`);
    }
  }
  return issues;
}

function renderMarkdown(status) {
  const lines = [];
  lines.push('# v31H Session Processor End-to-End Rehearsal Packet');
  lines.push('');
  lines.push(`Generated UTC: ${status.generated_utc}`);
  lines.push('');
  lines.push(`Rehearsal status: ${status.rehearsal_status}`);
  lines.push(`Readiness quality: ${status.readiness_quality}`);
  lines.push('');
  lines.push('## Gates');
  for (const gate of status.gates) {
    lines.push(`- ${gate.name}: ${gate.status} | present=${gate.present} | ready=${gate.ready} | required=${gate.required}`);
  }
  lines.push('');
  lines.push('## Blockers');
  if (status.blockers.length === 0) lines.push('- None');
  for (const blocker of status.blockers) lines.push(`- ${blocker}`);
  lines.push('');
  lines.push('## Governance');
  lines.push('- production automation: OFF');
  lines.push('- forecast gate: OFF');
  lines.push('- model promotion: false');
  lines.push('- stable engine modified: false');
  lines.push('- canonical workbook overwrite: false');
  lines.push('- notification sending: disabled');
  lines.push('');
  lines.push(`Next step: ${status.next_step}`);
  lines.push('');
  return `${lines.join('\n')}\n`;
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const payloads = [
    { name: 'activation_protocol', payload: readJsonMaybe(args.activationProtocol), required: false },
    { name: 'source_review', payload: readJsonMaybe(args.sourceReview), required: true },
    { name: 'downstream_contract', payload: readJsonMaybe(args.downstreamContract), required: true },
    { name: 'sandbox_reflection', payload: readJsonMaybe(args.sandboxReflection), required: true },
    { name: 'forecast_ledger_contract', payload: readJsonMaybe(args.forecastLedgerContract), required: true },
    { name: 'race_fantasy_metadata', payload: readJsonMaybe(args.raceFantasyMetadata), required: true },
    { name: 'notification_preview', payload: readJsonMaybe(args.notificationPreview), required: false }
  ];
  const gates = payloads.map(item => collectGate(item.name, item.payload, item.required));
  const missingRequired = gates.filter(gate => gate.required && !gate.present).map(gate => `missing_required_gate:${gate.name}`);
  const blockedRequired = gates.filter(gate => gate.required && gate.blocked).map(gate => `blocked_required_gate:${gate.name}:${gate.status}`);
  const notReadyRequired = gates.filter(gate => gate.required && gate.present && !gate.ready && !gate.blocked).map(gate => `not_ready_required_gate:${gate.name}:${gate.status}`);
  const governanceIssues = collectGovernance(payloads);
  const cliIssues = [];
  if (args.execute) cliIssues.push('execute_true_not_supported_for_rehearsal_packet');
  if (args.allowLive) cliIssues.push('allow_live_true_not_supported_for_rehearsal_packet');
  if (args.mode !== 'dry_run' && args.mode !== 'contract') cliIssues.push(`unsupported_mode:${args.mode}`);
  const blockers = [...missingRequired, ...blockedRequired, ...notReadyRequired, ...governanceIssues, ...cliIssues];
  const readyGateCount = gates.filter(gate => gate.required && gate.ready).length;
  const requiredGateCount = gates.filter(gate => gate.required).length;
  let rehearsalStatus = 'contract_ready_missing_evidence';
  let readinessQuality = 'contract_only';
  if (blockers.length > 0) {
    rehearsalStatus = 'rehearsal_blocked';
    readinessQuality = missingRequired.length > 0 ? 'missing_required_evidence' : 'blocked_or_not_ready';
  } else if (readyGateCount === requiredGateCount) {
    rehearsalStatus = 'rehearsal_ready_dry_run_no_execution';
    readinessQuality = 'all_required_contracts_ready';
  }
  const status = {
    schema_version: 'f1_session_processor_end_to_end_rehearsal_packet_v31h_2026-06-16',
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
    notification_sending_enabled: false,
    notification_sent: false,
    rehearsal_status: rehearsalStatus,
    readiness_quality: readinessQuality,
    required_gate_count: requiredGateCount,
    ready_gate_count: readyGateCount,
    gates,
    blockers,
    governance_issues: governanceIssues,
    cli_issues: cliIssues,
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: rehearsalStatus === 'rehearsal_ready_dry_run_no_execution'
      ? 'v31I_sandbox_live_rehearsal_with_evidence_replay_operator_review'
      : 'resolve_rehearsal_blockers_before_v31I'
  };
  writeJson(args.out, status);
  if (policy.write_markdown_packet !== false && args.markdownOut) {
    writeText(args.markdownOut, renderMarkdown(status));
  }
  console.log(JSON.stringify({
    ok: blockers.length === 0,
    out: args.out,
    markdown_out: args.markdownOut,
    rehearsal_status: status.rehearsal_status,
    readiness_quality: status.readiness_quality,
    ready_gate_count: status.ready_gate_count,
    required_gate_count: status.required_gate_count,
    blocker_count: blockers.length
  }, null, 2));
  process.exit(blockers.length === 0 ? 0 : 1);
}

main();
