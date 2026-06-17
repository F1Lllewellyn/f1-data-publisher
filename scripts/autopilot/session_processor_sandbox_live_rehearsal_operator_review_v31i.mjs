import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_sandbox_live_rehearsal_policy_v31i.json';
const DEFAULT_OUT = 'health/session_processor_sandbox_live_rehearsal_operator_review_v31i_status.json';
const DEFAULT_MARKDOWN_OUT = 'health/session_processor_sandbox_live_rehearsal_operator_review_v31i_packet.md';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    markdownOut: DEFAULT_MARKDOWN_OUT,
    sourceEvidence: '',
    sourceReview: '',
    rehearsalPacket: '',
    activationProtocol: '',
    mode: 'dry_run',
    execute: false,
    allowLive: false,
    operatorApproval: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--markdown-out' && value) { args.markdownOut = value; i += 1; }
    else if (key === '--source-evidence' && value) { args.sourceEvidence = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--rehearsal-packet' && value) { args.rehearsalPacket = value; i += 1; }
    else if (key === '--activation-protocol' && value) { args.activationProtocol = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--operator-approval' && value) { args.operatorApproval = value === 'true'; i += 1; }
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

function bool(value) {
  return value === true;
}

function statusOf(payload) {
  if (!payload) return 'missing';
  return String(
    payload.status ||
    payload.rehearsal_status ||
    payload.review_status ||
    payload.evidence_status ||
    payload.readiness_status ||
    payload.activation_protocol_status ||
    payload.decision ||
    'present'
  );
}

function readyLike(status) {
  const value = lower(status);
  return value.includes('ready') || value.includes('eligible') || value.includes('accepted') || value.includes('passed') || value.includes('contract');
}

function blockedLike(status) {
  const value = lower(status);
  return value.includes('blocked') || value.includes('failed') || value.includes('error') || value.includes('rejected') || value.includes('not_ready');
}

function gatherGovernanceIssues(items) {
  const issues = [];
  for (const item of items) {
    const payload = item.payload;
    if (!payload) continue;
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

function evidenceQuality(evidence) {
  if (!evidence) return 'missing';
  const status = lower(statusOf(evidence));
  if (blockedLike(status)) return 'blocked';
  if (bool(evidence.live_fetch_performed) && !bool(evidence.sandbox_live_mode)) return 'blocked_live_fetch_not_sandbox';
  if (bool(evidence.sandbox_live_mode) || status.includes('sandbox') || status.includes('source_data_ready')) return 'sandbox_live_evidence_present';
  if (readyLike(status)) return 'contract_or_fixture_evidence_present';
  return 'present_unclassified';
}

function renderMarkdown(status) {
  const lines = [];
  lines.push('# v31I Sandbox-Live Rehearsal Operator Review');
  lines.push('');
  lines.push(`Generated UTC: ${status.generated_utc}`);
  lines.push('');
  lines.push(`Rehearsal status: ${status.rehearsal_status}`);
  lines.push(`Evidence quality: ${status.evidence_quality}`);
  lines.push(`Readiness quality: ${status.readiness_quality}`);
  lines.push('');
  lines.push('## Inputs');
  for (const input of status.inputs) {
    lines.push(`- ${input.name}: present=${input.present} status=${input.status} ready=${input.ready} blocked=${input.blocked}`);
  }
  lines.push('');
  lines.push('## Operator Review Checklist');
  for (const item of status.operator_review_checklist) {
    lines.push(`- ${item}`);
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
  lines.push('- workbook/prediction/fantasy/notification consumers: disabled');
  lines.push('');
  lines.push(`Next step: ${status.next_step}`);
  lines.push('');
  return `${lines.join('\n')}\n`;
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const sourceEvidence = readJsonMaybe(args.sourceEvidence);
  const sourceReview = readJsonMaybe(args.sourceReview);
  const rehearsalPacket = readJsonMaybe(args.rehearsalPacket);
  const activationProtocol = readJsonMaybe(args.activationProtocol);

  const rawInputs = [
    { name: 'source_evidence', payload: sourceEvidence, required: true },
    { name: 'source_review', payload: sourceReview, required: true },
    { name: 'end_to_end_rehearsal_packet', payload: rehearsalPacket, required: true },
    { name: 'activation_protocol', payload: activationProtocol, required: false }
  ];
  const inputs = rawInputs.map(item => {
    const status = statusOf(item.payload);
    const present = item.payload !== null;
    const blocked = present && blockedLike(status);
    const ready = present && readyLike(status) && !blocked;
    return { name: item.name, present, required: item.required, status, ready, blocked };
  });

  const blockers = [];
  for (const input of inputs) {
    if (input.required && !input.present) blockers.push(`missing_required_input:${input.name}`);
    if (input.required && input.blocked) blockers.push(`blocked_required_input:${input.name}:${input.status}`);
    if (input.required && input.present && !input.ready && !input.blocked) blockers.push(`not_ready_required_input:${input.name}:${input.status}`);
  }

  const governanceIssues = gatherGovernanceIssues(rawInputs);
  blockers.push(...governanceIssues);
  if (args.execute) blockers.push('execute_true_not_supported_in_v31i');
  if (args.allowLive) blockers.push('allow_live_true_not_supported_in_v31i_evidence_replay');
  if (args.mode !== 'dry_run' && args.mode !== 'contract' && args.mode !== 'operator_review') blockers.push(`unsupported_mode:${args.mode}`);

  const quality = evidenceQuality(sourceEvidence);
  if (quality.startsWith('blocked')) blockers.push(`source_evidence_quality_blocked:${quality}`);
  const requiredCount = inputs.filter(input => input.required).length;
  const readyRequiredCount = inputs.filter(input => input.required && input.ready).length;

  let rehearsalStatus = 'contract_ready_missing_evidence';
  let readinessQuality = 'contract_only';
  if (blockers.length > 0) {
    rehearsalStatus = 'sandbox_live_rehearsal_blocked';
    readinessQuality = inputs.some(input => input.required && !input.present) ? 'missing_required_evidence' : 'blocked_or_not_ready';
  } else if (readyRequiredCount === requiredCount) {
    rehearsalStatus = 'sandbox_live_rehearsal_ready_for_operator_review';
    readinessQuality = quality === 'sandbox_live_evidence_present' ? 'sandbox_live_evidence_replay_ready' : 'fixture_or_contract_evidence_ready';
  }

  const operatorChecklist = [
    'Confirm source evidence came from sandbox-live or approved fixture replay only.',
    'Confirm source review gate is ready and has no blocking failures.',
    'Confirm end-to-end rehearsal packet is ready with all required gates present.',
    'Confirm no consumer gate is open and no notification was sent.',
    'Confirm stable engine and canonical workbook remain untouched.',
    'Do not activate production automation without separate explicit approval.'
  ];

  const status = {
    schema_version: 'f1_session_processor_sandbox_live_rehearsal_operator_review_v31i_2026-06-16',
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
    evidence_quality: quality,
    required_gate_count: requiredCount,
    ready_required_gate_count: readyRequiredCount,
    inputs,
    blockers,
    governance_issues: governanceIssues,
    operator_review_checklist: operatorChecklist,
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: rehearsalStatus === 'sandbox_live_rehearsal_ready_for_operator_review'
      ? 'v31J_activation_review_packet_after_operator_review'
      : 'resolve_v31i_rehearsal_blockers_before_v31J'
  };

  writeJson(args.out, status);
  if (policy.write_markdown_packet !== false && args.markdownOut) writeText(args.markdownOut, renderMarkdown(status));
  console.log(JSON.stringify({
    ok: blockers.length === 0,
    out: args.out,
    markdown_out: args.markdownOut,
    rehearsal_status: status.rehearsal_status,
    readiness_quality: status.readiness_quality,
    evidence_quality: status.evidence_quality,
    blocker_count: blockers.length
  }, null, 2));
  process.exit(blockers.length === 0 ? 0 : 1);
}

main();
