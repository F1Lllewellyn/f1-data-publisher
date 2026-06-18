#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const VERSION = 'v33I';
const SCHEMA_VERSION = 'f1_session_processor_material_change_notification_rehearsal_v33i_2026-06-18';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_material_change_notification_rehearsal_policy_v33i.json';
const DEFAULT_OUT = 'health/session_processor_material_change_notification_rehearsal_v33i_status.json';
const DEFAULT_ARTIFACT_DIR = 'sandbox/notification_previews/v33i';

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: DEFAULT_POLICY,
    readiness_status: null,
    readiness_artifact: null,
    out: DEFAULT_OUT,
    artifact_dir: DEFAULT_ARTIFACT_DIR,
    execute: false,
    operator_approval: false,
    allow_notification_preview: false,
    allow_notification_send: false,
    allow_race_predictions_refresh: false,
    allow_fantasy_refresh: false,
    allow_production_activation: false,
    allow_canonical_workbook_write: false,
    allow_production_ledger_write: false,
    production_automation: false,
    model_promotion: false,
    activate: false,
    live_fetch: false
  };

  const keyMap = new Map([
    ['mode', 'mode'],
    ['policy', 'policy'],
    ['readiness-status', 'readiness_status'],
    ['readiness_status', 'readiness_status'],
    ['readiness-artifact', 'readiness_artifact'],
    ['readiness_artifact', 'readiness_artifact'],
    ['out', 'out'],
    ['artifact-dir', 'artifact_dir'],
    ['artifact_dir', 'artifact_dir'],
    ['execute', 'execute'],
    ['operator-approval', 'operator_approval'],
    ['operator_approval', 'operator_approval'],
    ['allow-notification-preview', 'allow_notification_preview'],
    ['allow_notification_preview', 'allow_notification_preview'],
    ['allow-notification-send', 'allow_notification_send'],
    ['allow_notification_send', 'allow_notification_send'],
    ['allow-race-predictions-refresh', 'allow_race_predictions_refresh'],
    ['allow_race_predictions_refresh', 'allow_race_predictions_refresh'],
    ['allow-fantasy-refresh', 'allow_fantasy_refresh'],
    ['allow_fantasy_refresh', 'allow_fantasy_refresh'],
    ['allow-production-activation', 'allow_production_activation'],
    ['allow_production_activation', 'allow_production_activation'],
    ['allow-canonical-workbook-write', 'allow_canonical_workbook_write'],
    ['allow_canonical_workbook_write', 'allow_canonical_workbook_write'],
    ['allow-production-ledger-write', 'allow_production_ledger_write'],
    ['allow_production_ledger_write', 'allow_production_ledger_write'],
    ['production-automation', 'production_automation'],
    ['model-promotion', 'model_promotion'],
    ['activate', 'activate'],
    ['live-fetch', 'live_fetch']
  ]);

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) continue;
    const mapped = keyMap.get(token.slice(2));
    if (!mapped) throw new Error(`Unknown argument: ${token}`);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith('--')) {
      args[mapped] = true;
    } else {
      args[mapped] = coerceValue(next);
      i += 1;
    }
  }
  return args;
}

function coerceValue(value) {
  if (value === 'true') return true;
  if (value === 'false') return false;
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  return value;
}

function readJsonMaybe(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`);
}

function timestampForPath(date = new Date()) {
  return date.toISOString().replace(/[-:.]/g, '').replace('Z', 'Z');
}

function sha256(value) {
  return crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

function bool(value) {
  return value === true;
}

function runtimeFalseFlagIssues(args, policy) {
  const issues = [];
  for (const flag of policy.required_false_runtime_flags || []) {
    if (args[flag] !== false) issues.push(`runtime_flag_must_be_false:${flag}`);
  }
  return issues;
}

function payloadGovernanceIssues(name, payload) {
  const issues = [];
  if (!payload) return issues;
  if (payload.production_automation !== undefined && payload.production_automation !== 'OFF') issues.push(`${name}:production_automation_not_off`);
  if (payload.forecast_gate !== undefined && payload.forecast_gate !== 'OFF') issues.push(`${name}:forecast_gate_not_off`);
  if (bool(payload.promotion_allowed) || bool(payload.promotion) || bool(payload.model_promotion_allowed)) issues.push(`${name}:promotion_not_false`);
  if (bool(payload.live_fetch_performed)) issues.push(`${name}:live_fetch_performed`);
  if (bool(payload.activation_performed)) issues.push(`${name}:activation_performed`);
  if (bool(payload.stable_engine_modified)) issues.push(`${name}:stable_engine_modified`);
  if (bool(payload.canonical_workbook_overwrite)) issues.push(`${name}:canonical_workbook_overwrite`);
  if (bool(payload.workbook_write_performed) || bool(payload.canonical_workbook_write_performed)) issues.push(`${name}:workbook_or_canonical_write_performed`);
  if (bool(payload.forecast_bundle_ledger_write_performed) || bool(payload.production_forecast_bundle_ledger_write_performed)) issues.push(`${name}:production_ledger_write_performed`);
  if (bool(payload.race_predictions_refresh_performed)) issues.push(`${name}:race_predictions_refresh_performed`);
  if (bool(payload.fantasy_refresh_performed)) issues.push(`${name}:fantasy_refresh_performed`);
  if (bool(payload.notification_sent)) issues.push(`${name}:notification_sent`);
  if (bool(payload.model_promotion_performed)) issues.push(`${name}:model_promotion_performed`);
  return issues;
}

function readinessArtifactFrom(status, artifact) {
  return artifact || status?.readiness_metadata_artifact || null;
}

function closedConsumerGates() {
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

function summarizeReadiness(readinessArtifact) {
  const records = Array.isArray(readinessArtifact?.metadata_records) ? readinessArtifact.metadata_records : [];
  const race = records.find((record) => record.surface === 'race_predictions') || null;
  const fantasy = records.find((record) => record.surface === 'fantasy_predictions') || null;
  const readyRecords = records.filter((record) => record.readiness_status === 'ready').length;
  const allRecordsReady = records.length > 0 && readyRecords === records.length;
  return {
    event: readinessArtifact?.event || {},
    readiness_state: readinessArtifact?.readiness_state || {},
    metadata_record_count: records.length,
    ready_metadata_record_count: readyRecords,
    all_metadata_records_ready: allRecordsReady,
    race_predictions_metadata_ready: race?.readiness_status === 'ready',
    fantasy_metadata_ready: fantasy?.readiness_status === 'ready',
    row_count_total: race?.row_count_total ?? fantasy?.row_count_total ?? null,
    required_sources_ready: readinessArtifact?.readiness_state?.required_sources_ready === true,
    sandbox_feature_packet_ready: readinessArtifact?.readiness_state?.sandbox_feature_packet_ready === true,
    no_prediction_or_ranking_generated: readinessArtifact?.readiness_state?.no_prediction_or_ranking_generated === true,
    core_signals_available: readinessArtifact?.readiness_state?.core_signals_available === true,
    upstream_statuses: {
      source_evidence_status: race?.source_evidence_status || fantasy?.source_evidence_status || null,
      source_quality_status: race?.source_quality_status || fantasy?.source_quality_status || null,
      processor_status: race?.processor_status || fantasy?.processor_status || null,
      ledger_status: race?.ledger_status || fantasy?.ledger_status || null
    }
  };
}

function buildPreview({ args, readinessStatus, readinessArtifact }) {
  const readiness = summarizeReadiness(readinessArtifact);
  const materialChangeDetected =
    readiness.all_metadata_records_ready &&
    readiness.required_sources_ready &&
    readiness.sandbox_feature_packet_ready &&
    readiness.core_signals_available;

  const materialReason = materialChangeDetected
    ? 'race_fantasy_readiness_metadata_available_from_sandbox_evidence'
    : 'readiness_metadata_not_fully_ready_for_material_preview';

  const previewSubject = materialChangeDetected
    ? 'F1 sandbox readiness update preview: Race/Fantasy metadata ready'
    : 'F1 sandbox readiness update preview: review required';

  const previewSummary = materialChangeDetected
    ? 'Sandbox evidence indicates Race/Fantasy readiness metadata is ready for operator review. This is a rehearsal preview only; no notification was sent and no prediction or fantasy output was generated.'
    : 'Sandbox readiness metadata is not fully ready. This rehearsal preview records the blocker/review condition only; no notification was sent.';

  return {
    artifact_type: 'material_change_notification_rehearsal_preview_v33i',
    schema_version: SCHEMA_VERSION,
    generated_utc: new Date().toISOString(),
    version: VERSION,
    mode: args.mode,
    preview_scope: 'sandbox_notification_preview_only',
    notification_channel: 'operator_review_artifact_only',
    notification_send_target: 'blocked',
    notification_sent: false,
    material_change_detected: materialChangeDetected,
    material_change_reason: materialReason,
    preview_subject: previewSubject,
    preview_body: {
      summary: previewSummary,
      event: readiness.event,
      readiness: {
        metadata_record_count: readiness.metadata_record_count,
        ready_metadata_record_count: readiness.ready_metadata_record_count,
        race_predictions_metadata_ready: readiness.race_predictions_metadata_ready,
        fantasy_metadata_ready: readiness.fantasy_metadata_ready,
        required_sources_ready: readiness.required_sources_ready,
        sandbox_feature_packet_ready: readiness.sandbox_feature_packet_ready,
        core_signals_available: readiness.core_signals_available,
        row_count_total: readiness.row_count_total
      },
      upstream_statuses: readiness.upstream_statuses,
      explicit_non_actions: [
        'notification_not_sent',
        'race_predictions_not_generated',
        'fantasy_picks_not_generated',
        'canonical_workbook_not_written',
        'production_forecast_bundle_ledger_not_written',
        'stable_engine_not_modified',
        'model_not_promoted',
        'production_automation_not_activated'
      ]
    },
    preview_delivery: {
      delivery_performed: false,
      delivery_requires_future_explicit_approval: true
    },
    source_evidence_hashes: {
      readiness_status_sha256: readinessStatus ? sha256(readinessStatus) : null,
      readiness_artifact_sha256: readinessArtifact ? sha256(readinessArtifact) : null
    },
    next_step_candidate: 'v33J_final_activation_decision_packet'
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const policy = readJsonMaybe(args.policy) || {};
  const readinessStatus = readJsonMaybe(args.readiness_status);
  const readinessArtifactFile = readJsonMaybe(args.readiness_artifact);
  const readinessArtifact = readinessArtifactFrom(readinessStatus, readinessArtifactFile);
  const blockers = [];
  const warnings = [];

  if (!['dry_run', 'notification_preview_rehearsal'].includes(args.mode)) blockers.push(`unsupported_mode:${args.mode}`);
  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.notification_preview_rehearsal_allowed !== true) blockers.push('policy_notification_preview_rehearsal_not_allowed');
  if (policy.notification_send_allowed !== false) blockers.push('policy_notification_send_allowed_not_false');
  if (policy.race_predictions_refresh_allowed !== false) blockers.push('policy_race_predictions_refresh_allowed_not_false');
  if (policy.fantasy_refresh_allowed !== false) blockers.push('policy_fantasy_refresh_allowed_not_false');
  if (policy.production_activation_allowed !== false) blockers.push('policy_production_activation_allowed_not_false');
  if (policy.live_fetch_allowed !== false) blockers.push('policy_live_fetch_allowed_not_false');

  blockers.push(...runtimeFalseFlagIssues(args, policy));
  blockers.push(...payloadGovernanceIssues('readiness_status', readinessStatus));
  blockers.push(...payloadGovernanceIssues('readiness_artifact', readinessArtifactFile));

  if (args.execute && args.mode !== 'notification_preview_rehearsal') blockers.push('execute_true_requires_mode_notification_preview_rehearsal');
  if (args.execute && policy.operator_approval_required === true && args.operator_approval !== true) blockers.push('execute_true_requires_operator_approval');
  if (args.execute && args.allow_notification_preview !== true) blockers.push('execute_true_requires_allow_notification_preview');
  if (args.allow_notification_send) blockers.push('notification_send_true_rejected_by_v33i');
  if (args.allow_race_predictions_refresh) blockers.push('race_predictions_refresh_true_rejected_by_v33i');
  if (args.allow_fantasy_refresh) blockers.push('fantasy_refresh_true_rejected_by_v33i');
  if (args.allow_production_activation) blockers.push('production_activation_true_rejected_by_v33i');
  if (args.allow_canonical_workbook_write) blockers.push('canonical_workbook_write_true_rejected_by_v33i');
  if (args.allow_production_ledger_write) blockers.push('production_ledger_write_true_rejected_by_v33i');
  if (!readinessStatus && args.mode !== 'dry_run') blockers.push('missing_readiness_status');
  if (!readinessArtifact && args.mode !== 'dry_run') blockers.push('missing_readiness_artifact');

  const requiredStatus = policy.required_readiness_metadata_status || 'RACE_FANTASY_READINESS_METADATA_REFRESHED_SANDBOX_ONLY';
  if (readinessStatus && readinessStatus.race_fantasy_readiness_metadata_status !== requiredStatus) {
    blockers.push(`readiness_status_not_required:${readinessStatus.race_fantasy_readiness_metadata_status || 'unknown'}`);
  }
  if (readinessArtifact && readinessArtifact.artifact_type !== 'race_fantasy_readiness_metadata_refresh_v33h') {
    blockers.push(`readiness_artifact_type_not_v33h:${readinessArtifact.artifact_type || 'unknown'}`);
  }
  if (readinessArtifact && readinessArtifact.guardrail_summary?.notification_sent !== false) {
    blockers.push('readiness_artifact_notification_guard_missing');
  }
  if (readinessArtifact && (readinessArtifact.guardrail_summary?.race_predictions_generated || readinessArtifact.guardrail_summary?.fantasy_picks_generated)) {
    blockers.push('readiness_artifact_generated_prediction_or_fantasy');
  }
  if (!args.execute && args.mode === 'notification_preview_rehearsal') warnings.push('notification_preview_rehearsal_mode_without_execute_true');

  const uniqueBlockers = Array.from(new Set(blockers));
  const executePerformed = args.execute === true && uniqueBlockers.length === 0;
  let previewArtifact = null;
  let previewArtifactPath = null;
  if (executePerformed) {
    previewArtifact = buildPreview({ args, readinessStatus, readinessArtifact });
    previewArtifactPath = path.join(args.artifact_dir, `material_change_notification_preview_${timestampForPath()}.json`);
    writeJson(previewArtifactPath, previewArtifact);
  }

  const materialChangeDetected = previewArtifact?.material_change_detected === true;
  const status = {
    schema_version: SCHEMA_VERSION,
    generated_utc: new Date().toISOString(),
    version: VERSION,
    ok: uniqueBlockers.length === 0,
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: executePerformed,
    operator_approval_recorded: args.operator_approval,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    live_fetch_performed: false,
    workbook_write_performed: false,
    canonical_workbook_write_performed: false,
    production_forecast_bundle_ledger_write_performed: false,
    race_predictions_refresh_performed: false,
    fantasy_refresh_performed: false,
    notification_preview_artifact_written: Boolean(previewArtifactPath),
    notification_preview_artifact_path: previewArtifactPath,
    notification_sent: false,
    model_promotion_performed: false,
    readiness_metadata_status: readinessStatus?.race_fantasy_readiness_metadata_status || null,
    readiness_metadata_artifact_path: readinessStatus?.readiness_metadata_artifact_path || args.readiness_artifact || null,
    material_change_notification_rehearsal_status: uniqueBlockers.length > 0
      ? 'MATERIAL_CHANGE_NOTIFICATION_REHEARSAL_BLOCKED'
      : (executePerformed ? 'MATERIAL_CHANGE_NOTIFICATION_PREVIEW_READY_SANDBOX_ONLY' : 'MATERIAL_CHANGE_NOTIFICATION_REHEARSAL_READY_NOT_WRITTEN'),
    material_change_notification_rehearsal_reason: uniqueBlockers.length > 0
      ? 'blocking_notification_rehearsal_issue'
      : (executePerformed ? 'sandbox_notification_preview_created_without_send' : 'dry_run_or_awaiting_operator_execute'),
    material_change_detected_for_preview: materialChangeDetected,
    blockers: uniqueBlockers,
    warnings: Array.from(new Set(warnings)),
    notification_preview_artifact: previewArtifact,
    guardrails: {
      preview_only: true,
      notification_send: false,
      race_predictions_refresh: false,
      fantasy_predictions_refresh: false,
      production_activation: false,
      canonical_workbook_write: false,
      production_forecast_bundle_ledger_write: false,
      model_promotion: false,
      live_fetch: false
    },
    consumer_gates: closedConsumerGates(),
    next_step: uniqueBlockers.length > 0
      ? 'resolve_v33i_notification_rehearsal_blockers'
      : (executePerformed ? policy.next_allowed_layer : 'run_v33i_with_operator_approval')
  };

  writeJson(args.out, status);
  console.log(JSON.stringify({
    ok: status.ok,
    material_change_notification_rehearsal_status: status.material_change_notification_rehearsal_status,
    execute_performed: status.execute_performed,
    notification_preview_artifact_written: status.notification_preview_artifact_written,
    notification_sent: status.notification_sent,
    blocker_count: status.blockers.length,
    next_step: status.next_step
  }, null, 2));
  process.exit(status.ok ? 0 : 1);
}

main();
