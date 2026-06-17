import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_operator_handoff_readiness_packet_policy_v32n.json';
const DEFAULT_OUT = 'health/session_processor_operator_handoff_readiness_packet_v32n_status.json';

function nowIso() { return new Date().toISOString(); }

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: '',
    packetOut: '',
    materialChangePreflight: '',
    ledgerEvidenceReview: '',
    racePreflight: '',
    fantasyPreflight: '',
    mode: 'dry_run',
    execute: false,
    activate: false,
    allowLive: false,
    allowRacePredictionsRefresh: false,
    allowFantasyRefresh: false,
    allowForecastBundleWrite: false,
    allowCanonicalWorkbookWrite: false,
    allowNotificationSend: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--packet-out' && value) { args.packetOut = value; i += 1; }
    else if (key === '--material-change-preflight' && value) { args.materialChangePreflight = value; i += 1; }
    else if (key === '--ledger-evidence-review' && value) { args.ledgerEvidenceReview = value; i += 1; }
    else if (key === '--race-preflight' && value) { args.racePreflight = value; i += 1; }
    else if (key === '--fantasy-preflight' && value) { args.fantasyPreflight = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--activate' && value) { args.activate = value === 'true'; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
    else if (key === '--allow-race-predictions-refresh' && value) { args.allowRacePredictionsRefresh = value === 'true'; i += 1; }
    else if (key === '--allow-fantasy-refresh' && value) { args.allowFantasyRefresh = value === 'true'; i += 1; }
    else if (key === '--allow-forecast-bundle-write' && value) { args.allowForecastBundleWrite = value === 'true'; i += 1; }
    else if (key === '--allow-canonical-workbook-write' && value) { args.allowCanonicalWorkbookWrite = value === 'true'; i += 1; }
    else if (key === '--allow-notification-send' && value) { args.allowNotificationSend = value === 'true'; i += 1; }
  }
  return args;
}

function readJsonMaybe(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function writeText(filePath, text) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, text, 'utf8');
}

function isTrue(value) { return value === true; }

function statusOf(payload, preferredKeys = []) {
  if (!payload) return 'missing';
  for (const key of preferredKeys) {
    if (payload[key]) return String(payload[key]);
  }
  return String(payload.status || payload.decision || 'present');
}

function governanceIssues(name, payload) {
  const issues = [];
  if (!payload) return issues;
  if (payload.production_automation && payload.production_automation !== 'OFF') issues.push(`${name}:production_automation_not_off`);
  if (payload.forecast_gate && payload.forecast_gate !== 'OFF') issues.push(`${name}:forecast_gate_not_off`);
  if (isTrue(payload.promotion_allowed) || isTrue(payload.promotion) || isTrue(payload.model_promotion_allowed)) issues.push(`${name}:promotion_not_false`);
  if (isTrue(payload.live_fetch_performed) || isTrue(payload.live_fetch_enabled)) issues.push(`${name}:live_fetch_detected`);
  if (isTrue(payload.execute_performed)) issues.push(`${name}:execute_performed_detected`);
  if (isTrue(payload.activation_performed) || isTrue(payload.activate)) issues.push(`${name}:activation_detected`);
  if (isTrue(payload.forecast_bundle_ledger_write_performed) || isTrue(payload.forecast_bundle_write_performed)) issues.push(`${name}:forecast_bundle_write_detected`);
  if (isTrue(payload.canonical_workbook_overwrite) || isTrue(payload.canonical_workbook_write_enabled) || isTrue(payload.canonical_workbook_written)) issues.push(`${name}:canonical_workbook_write_detected`);
  if (isTrue(payload.race_predictions_refresh_performed) || isTrue(payload.race_predictions_refresh_enabled)) issues.push(`${name}:race_predictions_refresh_detected`);
  if (isTrue(payload.fantasy_refresh_performed) || isTrue(payload.fantasy_refresh_enabled)) issues.push(`${name}:fantasy_refresh_detected`);
  if (isTrue(payload.notification_sent) || isTrue(payload.notification_send_enabled)) issues.push(`${name}:notification_send_detected`);
  if (isTrue(payload.stable_engine_modified)) issues.push(`${name}:stable_engine_modified_detected`);
  for (const [gate, enabled] of Object.entries(payload.consumer_gates || {})) {
    if (enabled === true) issues.push(`${name}:consumer_gate_open:${gate}`);
  }
  return issues;
}

function renderMarkdown(packet) {
  const lines = [];
  lines.push('# v32N Operator Handoff Readiness Packet');
  lines.push('');
  lines.push(`Generated UTC: ${packet.generated_utc}`);
  lines.push(`Status: ${packet.operator_handoff_readiness_packet_status}`);
  lines.push(`Readiness quality: ${packet.readiness_quality}`);
  lines.push('');
  lines.push('## Governance');
  lines.push(`- production automation: ${packet.production_automation}`);
  lines.push(`- forecast gate: ${packet.forecast_gate}`);
  lines.push(`- promotion allowed: ${packet.promotion_allowed}`);
  lines.push(`- stable engine modified: ${packet.stable_engine_modified}`);
  lines.push(`- canonical workbook overwrite: ${packet.canonical_workbook_overwrite}`);
  lines.push(`- notification sent: ${packet.notification_sent}`);
  lines.push('');
  lines.push('## Evidence Chain');
  for (const item of packet.evidence_chain) {
    lines.push(`- ${item.name}: present=${item.present} status=${item.status} quality=${item.quality || 'n/a'}`);
  }
  lines.push('');
  lines.push('## Operator Checklist');
  for (const item of packet.operator_handoff_checklist) lines.push(`- ${item}`);
  lines.push('');
  lines.push('## Blockers');
  if (packet.blockers.length === 0) lines.push('- None');
  else for (const blocker of packet.blockers) lines.push(`- ${blocker}`);
  lines.push('');
  lines.push(`Next step: ${packet.next_step}`);
  lines.push('');
  return `${lines.join('\n')}\n`;
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const material = readJsonMaybe(args.materialChangePreflight);
  const ledgerReview = readJsonMaybe(args.ledgerEvidenceReview);
  const race = readJsonMaybe(args.racePreflight);
  const fantasy = readJsonMaybe(args.fantasyPreflight);
  const blockers = [];

  const materialStatus = statusOf(material, ['material_change_notification_preflight_status']);
  const materialQuality = String(material?.readiness_quality || '');
  const materialDetected = material?.material_change_detected === true;

  if (!material) blockers.push('missing_v32m_material_change_preflight');
  else if (materialStatus !== policy.required_material_change_status) blockers.push(`material_change_status_mismatch:${materialStatus}`);
  else if (materialQuality !== policy.required_material_change_quality) blockers.push(`material_change_quality_mismatch:${materialQuality || 'missing'}`);
  else if (materialDetected !== policy.required_material_change_detected) blockers.push('material_change_detected_mismatch');

  const evidenceChain = [
    {
      name: 'v32j_forecast_bundle_ledger_evidence_review',
      payload: ledgerReview,
      status: statusOf(ledgerReview, ['forecast_bundle_ledger_evidence_review_status']),
      quality: ledgerReview?.readiness_quality || null
    },
    {
      name: 'v32k_race_predictions_readiness_refresh_preflight',
      payload: race,
      status: statusOf(race, ['race_predictions_readiness_refresh_preflight_status']),
      quality: race?.readiness_quality || null
    },
    {
      name: 'v32l_fantasy_predictions_readiness_refresh_preflight',
      payload: fantasy,
      status: statusOf(fantasy, ['fantasy_predictions_readiness_refresh_preflight_status']),
      quality: fantasy?.readiness_quality || null
    },
    {
      name: 'v32m_material_change_notification_preflight',
      payload: material,
      status: materialStatus,
      quality: materialQuality || null
    }
  ].map(item => ({
    name: item.name,
    present: item.payload !== null,
    status: item.status,
    quality: item.quality
  }));

  for (const item of [
    ['v32j', ledgerReview],
    ['v32k', race],
    ['v32l', fantasy],
    ['v32m', material]
  ]) {
    blockers.push(...governanceIssues(item[0], item[1]));
  }

  if (args.execute) blockers.push('execute_true_not_supported_in_v32n_finalizer');
  if (args.activate) blockers.push('activate_true_not_supported_in_v32n_finalizer');
  if (args.allowLive) blockers.push('allow_live_true_not_supported_in_v32n_finalizer');
  if (args.allowRacePredictionsRefresh) blockers.push('race_predictions_refresh_request_rejected');
  if (args.allowFantasyRefresh) blockers.push('fantasy_refresh_request_rejected');
  if (args.allowForecastBundleWrite) blockers.push('forecast_bundle_write_request_rejected');
  if (args.allowCanonicalWorkbookWrite) blockers.push('canonical_workbook_write_request_rejected');
  if (args.allowNotificationSend) blockers.push('notification_send_request_rejected');
  if (args.mode !== 'dry_run' && args.mode !== 'finalize') blockers.push(`unsupported_mode:${args.mode}`);

  const ok = blockers.length === 0;
  const packet = {
    schema_version: 'f1_session_processor_operator_handoff_readiness_packet_v32n_2026-06-17',
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
    operator_handoff_readiness_packet_status: ok ? 'operator_handoff_readiness_packet_ready' : 'operator_handoff_readiness_packet_blocked',
    readiness_quality: ok ? 'dry_run_readiness_chain_finalized_for_operator_review' : 'blocked_or_missing_material_change_preflight',
    material_change_detected: materialDetected,
    evidence_chain: evidenceChain,
    blockers,
    operator_review_required: true,
    operator_handoff_checklist: Array.isArray(policy.handoff_checklist) ? policy.handoff_checklist : [],
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: ok ? (policy.next_layer || 'v33_controlled_operator_review_before_any_sandbox_live_or_refresh_activation') : 'resolve_v32n_operator_handoff_blockers_before_v33'
  };

  writeJson(args.out, packet);
  if (args.packetOut) writeText(args.packetOut, renderMarkdown(packet));
  if (args.log) writeJson(args.log, { ok, generated_utc: packet.generated_utc, out: args.out, packet_out: args.packetOut || null, blocker_count: blockers.length });
  console.log(JSON.stringify({
    ok,
    out: args.out,
    packet_out: args.packetOut || null,
    operator_handoff_readiness_packet_status: packet.operator_handoff_readiness_packet_status,
    readiness_quality: packet.readiness_quality,
    blocker_count: blockers.length
  }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
