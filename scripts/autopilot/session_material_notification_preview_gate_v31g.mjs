import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_material_notification_preview_gate_policy_v31g.json';
const DEFAULT_OUT = 'health/session_material_notification_preview_gate_v31g_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    readinessMetadata: '',
    materialGate: '',
    ledgerContract: '',
    sourceReview: '',
    mode: 'dry_run',
    execute: false,
    allowNotificationSend: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--readiness-metadata' && value) { args.readinessMetadata = value; i += 1; }
    else if (key === '--material-gate' && value) { args.materialGate = value; i += 1; }
    else if (key === '--ledger-contract' && value) { args.ledgerContract = value; i += 1; }
    else if (key === '--source-review' && value) { args.sourceReview = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
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
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

function text(value) {
  return String(value ?? '').toLowerCase();
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
  if (policy.notification_sending_enabled !== false) issues.push('policy_notification_sending_not_false');
  if (args.execute) issues.push('execute_true_not_supported_for_v31g_preview_gate');
  if (args.allowNotificationSend) issues.push('allow_notification_send_true_not_supported_for_v31g_preview_gate');
  for (const payload of payloads.filter(Boolean)) {
    if (payload.production_automation !== undefined && payload.production_automation !== 'OFF') issues.push('upstream_production_automation_not_off');
    if (payload.forecast_gate !== undefined && payload.forecast_gate !== 'OFF') issues.push('upstream_forecast_gate_not_off');
    if (payload.promotion_allowed !== undefined && payload.promotion_allowed !== false) issues.push('upstream_promotion_allowed_not_false');
    if (payload.stable_engine_modified === true) issues.push('stable_engine_modified_true');
    if (payload.canonical_workbook_overwrite === true) issues.push('canonical_workbook_overwrite_true');
    if (payload.notification_sent === true) issues.push('upstream_notification_sent_true');
    const gates = payload.consumer_gates || {};
    for (const [key, expected] of Object.entries(closedGates())) {
      if (gates[key] !== undefined && gates[key] !== expected) issues.push(`${key}_not_closed`);
    }
  }
  return Array.from(new Set(issues));
}

function deriveStatus(readinessMetadata, materialGate, ledgerContract, sourceReview, issues) {
  if (issues.length > 0) {
    return {
      notification_preview_status: 'notification_preview_gate_blocked',
      readiness_quality: 'governance_issue',
      should_create_preview: false,
      action: 'hold_notification_preview',
      severity: 'blocking'
    };
  }

  const metadata = text(readinessMetadata?.readiness_contract_status || readinessMetadata?.status);
  const material = text(materialGate?.threshold_gate_status || materialGate?.notification_preview_status || materialGate?.status);
  const ledger = text(ledgerContract?.ledger_contract_status || ledgerContract?.status);
  const review = text(sourceReview?.review_status || sourceReview?.status);

  if ([metadata, material, ledger, review].some((s) => s.includes('blocked') || s.includes('failed'))) {
    return {
      notification_preview_status: 'notification_preview_gate_blocked',
      readiness_quality: 'upstream_blocked',
      should_create_preview: false,
      action: 'repair_upstream_before_notification_preview',
      severity: 'blocking'
    };
  }

  if ([metadata, ledger, review].some((s) => s.includes('review_required') || s.includes('degraded'))) {
    return {
      notification_preview_status: 'notification_preview_gate_review_required',
      readiness_quality: 'manual_review_required',
      should_create_preview: true,
      action: 'create_review_preview_only',
      severity: 'review_required'
    };
  }

  if (material.includes('material_change_detected') || material.includes('preview') || readinessMetadata?.readiness_contract_status === 'prediction_fantasy_readiness_contract_ready') {
    return {
      notification_preview_status: 'notification_preview_gate_preview_ready',
      readiness_quality: 'preview_ready_notification_send_disabled',
      should_create_preview: true,
      action: 'create_preview_artifact_only',
      severity: 'none'
    };
  }

  return {
    notification_preview_status: 'notification_preview_gate_no_material_change',
    readiness_quality: 'no_preview_required',
    should_create_preview: false,
    action: 'continue_monitoring',
    severity: 'none'
  };
}

function buildPreview(policy, readinessMetadata, materialGate, ledgerContract, sourceReview, derived) {
  const contracts = Array.isArray(readinessMetadata?.metadata_contracts) ? readinessMetadata.metadata_contracts : [];
  const surfaces = contracts.map((item) => item.surface || item.contract_id).filter(Boolean);
  return {
    preview_type: 'material_readiness_notification_preview',
    preview_created: derived.should_create_preview,
    notification_send_enabled: false,
    notification_sent: false,
    channel: policy.preview_channel || 'operator_review_artifact',
    subject: derived.should_create_preview ? 'F1 Session Data Processor readiness preview' : '',
    summary: derived.should_create_preview
      ? 'Session source/readiness contracts are ready for operator review. Notification sending remains disabled.'
      : 'No material notification preview required.',
    readiness_contract_status: readinessMetadata?.readiness_contract_status || '',
    ledger_contract_status: ledgerContract?.ledger_contract_status || '',
    source_review_status: sourceReview?.review_status || '',
    material_gate_status: materialGate?.threshold_gate_status || materialGate?.status || '',
    surfaces,
    blocked_consumers: [
      'workbook_write',
      'canonical_workbook_write',
      'forecast_bundle_write',
      'race_predictions_refresh',
      'fantasy_refresh',
      'notification_send',
      'production_automation'
    ]
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const readinessMetadata = readJsonMaybe(args.readinessMetadata);
  const materialGate = readJsonMaybe(args.materialGate);
  const ledgerContract = readJsonMaybe(args.ledgerContract);
  const sourceReview = readJsonMaybe(args.sourceReview);
  const payloads = [readinessMetadata, materialGate, ledgerContract, sourceReview];
  const issues = governanceIssues(policy, args, payloads);
  const derived = deriveStatus(readinessMetadata, materialGate, ledgerContract, sourceReview, issues);
  const preview = buildPreview(policy, readinessMetadata, materialGate, ledgerContract, sourceReview, derived);

  const status = {
    schema_version: 'f1_session_material_notification_preview_gate_v31g_2026-06-17',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    notification_sending_enabled: false,
    notification_sent: false,
    readiness_metadata_supplied: Boolean(readinessMetadata),
    material_gate_supplied: Boolean(materialGate),
    ledger_contract_supplied: Boolean(ledgerContract),
    source_review_supplied: Boolean(sourceReview),
    ...derived,
    governance_issues: issues,
    preview,
    consumer_gates: closedGates(),
    next_step: derived.notification_preview_status === 'notification_preview_gate_preview_ready'
      ? 'v31h_end_to_end_session_processor_loop_rehearsal_packet'
      : 'continue_monitoring_or_repair_before_rehearsal'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: status.notification_preview_status !== 'notification_preview_gate_blocked', generated_utc: status.generated_utc, out: args.out, notification_preview_status: status.notification_preview_status });
  const ok = status.notification_preview_status !== 'notification_preview_gate_blocked';
  console.log(JSON.stringify({ ok, out: args.out, notification_preview_status: status.notification_preview_status, should_create_preview: status.should_create_preview }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
