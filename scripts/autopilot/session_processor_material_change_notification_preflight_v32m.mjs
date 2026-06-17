import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_material_change_notification_preflight_policy_v32m.json';
const DEFAULT_OUT = 'health/session_processor_material_change_notification_preflight_v32m_status.json';

function nowIso() { return new Date().toISOString(); }

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: '',
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

function isTrue(value) { return value === true; }

function statusOf(payload) {
  if (!payload) return 'missing';
  return String(
    payload.material_change_notification_preflight_status ||
    payload.fantasy_predictions_readiness_refresh_preflight_status ||
    payload.status ||
    payload.decision ||
    'present'
  );
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

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const fantasyPreflight = readJsonMaybe(args.fantasyPreflight);
  const blockers = [];
  const fantasyStatus = statusOf(fantasyPreflight);
  const fantasyQuality = String(fantasyPreflight?.readiness_quality || '');

  if (!fantasyPreflight) blockers.push('missing_v32l_fantasy_preflight');
  else if (fantasyStatus !== policy.required_fantasy_preflight_status) blockers.push(`fantasy_preflight_status_mismatch:${fantasyStatus}`);
  else if (fantasyQuality !== policy.required_fantasy_preflight_quality) blockers.push(`fantasy_preflight_quality_mismatch:${fantasyQuality || 'missing'}`);

  blockers.push(...governanceIssues('fantasy_preflight', fantasyPreflight));

  if (args.execute) blockers.push('execute_true_not_supported_in_v32m_preflight');
  if (args.activate) blockers.push('activate_true_not_supported_in_v32m_preflight');
  if (args.allowLive) blockers.push('allow_live_true_not_supported_in_v32m_preflight');
  if (args.allowRacePredictionsRefresh) blockers.push('race_predictions_refresh_request_rejected');
  if (args.allowFantasyRefresh) blockers.push('fantasy_refresh_request_rejected');
  if (args.allowForecastBundleWrite) blockers.push('forecast_bundle_write_request_rejected');
  if (args.allowCanonicalWorkbookWrite) blockers.push('canonical_workbook_write_request_rejected');
  if (args.allowNotificationSend) blockers.push('notification_send_request_rejected');
  if (args.mode !== 'dry_run' && args.mode !== 'preflight') blockers.push(`unsupported_mode:${args.mode}`);

  const readyGateCount = fantasyPreflight ? 1 : 0;
  const materialChangeDetected = blockers.length === 0 &&
    policy.material_change_policy?.treat_ready_preflight_chain_as_material === true &&
    readyGateCount >= Number(policy.material_change_policy?.min_ready_gate_count ?? 1);
  const notificationPreviewReady = materialChangeDetected && policy.material_change_policy?.notification_preview_allowed !== false;
  const ok = blockers.length === 0;

  const output = {
    schema_version: 'f1_session_processor_material_change_notification_preflight_v32m_2026-06-17',
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
    notification_sending_enabled: false,
    material_change_notification_preflight_status: ok ? 'material_change_notification_preflight_ready' : 'material_change_notification_preflight_blocked',
    readiness_quality: ok ? 'fantasy_preflight_verified_notification_preview_only' : 'blocked_or_missing_fantasy_preflight',
    material_change_detected: materialChangeDetected,
    notification_preview_ready: notificationPreviewReady,
    notification_send_allowed: false,
    fantasy_preflight_status: fantasyStatus,
    fantasy_preflight_quality: fantasyQuality || null,
    blockers,
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: ok ? (policy.next_layer || 'v32n_operator_handoff_readiness_packet_finalizer') : 'resolve_v32m_notification_preflight_blockers_before_v32n'
  };

  writeJson(args.out, output);
  if (args.log) writeJson(args.log, { ok, generated_utc: output.generated_utc, out: args.out, blocker_count: blockers.length, material_change_detected: materialChangeDetected });
  console.log(JSON.stringify({
    ok,
    out: args.out,
    material_change_notification_preflight_status: output.material_change_notification_preflight_status,
    readiness_quality: output.readiness_quality,
    material_change_detected: output.material_change_detected,
    notification_sent: output.notification_sent,
    blocker_count: blockers.length
  }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
