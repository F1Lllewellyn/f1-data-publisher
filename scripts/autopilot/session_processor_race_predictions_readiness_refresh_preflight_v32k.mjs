import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_processor_race_predictions_readiness_refresh_preflight_policy_v32k.json';
const DEFAULT_OUT = 'health/session_processor_race_predictions_readiness_refresh_preflight_v32k_status.json';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: '',
    ledgerEvidenceReview: '',
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
    else if (key === '--ledger-evidence-review' && value) { args.ledgerEvidenceReview = value; i += 1; }
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

function lower(value) {
  return String(value ?? '').toLowerCase();
}

function isTrue(value) {
  return value === true;
}

function statusOf(payload) {
  if (!payload) return 'missing';
  return String(
    payload.race_predictions_readiness_refresh_preflight_status ||
    payload.forecast_bundle_ledger_evidence_review_status ||
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
  const review = readJsonMaybe(args.ledgerEvidenceReview);
  const blockers = [];
  const reviewStatus = statusOf(review);
  const reviewQuality = String(review?.readiness_quality || '');

  if (!review) blockers.push('missing_v32j_ledger_evidence_review');
  else if (reviewStatus !== policy.required_ledger_evidence_review_status) blockers.push(`ledger_evidence_review_status_mismatch:${reviewStatus}`);
  else if (reviewQuality !== policy.required_ledger_quality) blockers.push(`ledger_evidence_review_quality_mismatch:${reviewQuality || 'missing'}`);

  blockers.push(...governanceIssues('ledger_evidence_review', review));

  if (args.execute) blockers.push('execute_true_not_supported_in_v32k_preflight');
  if (args.activate) blockers.push('activate_true_not_supported_in_v32k_preflight');
  if (args.allowLive) blockers.push('allow_live_true_not_supported_in_v32k_preflight');
  if (args.allowRacePredictionsRefresh) blockers.push('race_predictions_refresh_request_rejected');
  if (args.allowFantasyRefresh) blockers.push('fantasy_refresh_request_rejected');
  if (args.allowForecastBundleWrite) blockers.push('forecast_bundle_write_request_rejected');
  if (args.allowCanonicalWorkbookWrite) blockers.push('canonical_workbook_write_request_rejected');
  if (args.allowNotificationSend) blockers.push('notification_send_request_rejected');
  if (args.mode !== 'dry_run' && args.mode !== 'preflight') blockers.push(`unsupported_mode:${args.mode}`);

  const ok = blockers.length === 0;
  const output = {
    schema_version: 'f1_session_processor_race_predictions_readiness_refresh_preflight_v32k_2026-06-17',
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
    race_predictions_readiness_refresh_preflight_status: ok ? 'race_predictions_readiness_refresh_preflight_ready' : 'race_predictions_readiness_refresh_preflight_blocked',
    readiness_quality: ok ? 'ledger_evidence_review_verified_no_refresh_performed' : 'blocked_or_missing_ledger_evidence_review',
    ledger_evidence_review_status: reviewStatus,
    ledger_evidence_review_quality: reviewQuality || null,
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
    next_step: ok ? (policy.next_layer || 'v32l_fantasy_predictions_readiness_refresh_preflight_after_race_preflight') : 'resolve_v32k_race_predictions_preflight_blockers_before_v32l'
  };

  writeJson(args.out, output);
  if (args.log) writeJson(args.log, { ok, generated_utc: output.generated_utc, out: args.out, blocker_count: blockers.length });
  console.log(JSON.stringify({
    ok,
    out: args.out,
    race_predictions_readiness_refresh_preflight_status: output.race_predictions_readiness_refresh_preflight_status,
    readiness_quality: output.readiness_quality,
    blocker_count: blockers.length
  }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
