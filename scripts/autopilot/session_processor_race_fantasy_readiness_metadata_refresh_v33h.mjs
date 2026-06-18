#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const VERSION = 'v33H';
const SCHEMA_VERSION = 'f1_session_processor_race_fantasy_readiness_metadata_refresh_v33h_2026-06-18';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_race_fantasy_readiness_metadata_refresh_policy_v33h.json';
const DEFAULT_OUT = 'health/session_processor_race_fantasy_readiness_metadata_refresh_v33h_status.json';
const DEFAULT_ARTIFACT_DIR = 'sandbox/readiness_metadata/v33h';

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: DEFAULT_POLICY,
    ledger_status: null,
    ledger_snapshot: null,
    out: DEFAULT_OUT,
    artifact_dir: DEFAULT_ARTIFACT_DIR,
    execute: false,
    operator_approval: false,
    allow_metadata_refresh: false,
    allow_race_predictions_refresh: false,
    allow_fantasy_refresh: false,
    allow_notification_send: false,
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
    ['ledger-status', 'ledger_status'],
    ['ledger_status', 'ledger_status'],
    ['ledger-snapshot', 'ledger_snapshot'],
    ['ledger_snapshot', 'ledger_snapshot'],
    ['out', 'out'],
    ['artifact-dir', 'artifact_dir'],
    ['artifact_dir', 'artifact_dir'],
    ['execute', 'execute'],
    ['operator-approval', 'operator_approval'],
    ['operator_approval', 'operator_approval'],
    ['allow-metadata-refresh', 'allow_metadata_refresh'],
    ['allow_metadata_refresh', 'allow_metadata_refresh'],
    ['allow-race-predictions-refresh', 'allow_race_predictions_refresh'],
    ['allow_race_predictions_refresh', 'allow_race_predictions_refresh'],
    ['allow-fantasy-refresh', 'allow_fantasy_refresh'],
    ['allow_fantasy_refresh', 'allow_fantasy_refresh'],
    ['allow-notification-send', 'allow_notification_send'],
    ['allow_notification_send', 'allow_notification_send'],
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

function ledgerSnapshotFrom(status, snapshot) {
  return snapshot || status?.ledger_snapshot || null;
}

function readinessStateFromLedger(snapshot) {
  const source = snapshot.source_readiness_snapshot || {};
  const controls = snapshot.forecast_bundle_controls || {};
  const signal = snapshot.signal_availability_snapshot || {};
  const requiredReady = source.required_sources_ready === true;
  const featureReady = controls.sandbox_feature_packet_ready === true;
  const generatedNothing = controls.no_prediction_or_ranking_generated === true &&
    controls.forecast_generated === false &&
    controls.fantasy_generated === false;
  const coreSignals = Boolean(signal.timing && signal.stint && signal.driver_metadata);
  return {
    required_sources_ready: requiredReady,
    sandbox_feature_packet_ready: featureReady,
    no_prediction_or_ranking_generated: generatedNothing,
    core_signals_available: coreSignals,
    overall: requiredReady && featureReady && generatedNothing && coreSignals ? 'ready' : 'review_required'
  };
}

function buildMetadataArtifact({ args, ledgerStatus, snapshot }) {
  const readiness = readinessStateFromLedger(snapshot);
  const source = snapshot.source_readiness_snapshot || {};
  const signal = snapshot.signal_availability_snapshot || {};
  const event = snapshot.event || {};
  const common = {
    event,
    row_count_total: source.row_count_total ?? null,
    required_sources_ready: source.required_sources_ready === true,
    optional_sources_ready_count: source.optional_sources_ready_count ?? null,
    optional_source_count: source.optional_source_count ?? null,
    signal_availability: signal,
    source_evidence_status: snapshot.upstream?.source_evidence_status || null,
    source_quality_status: snapshot.upstream?.source_quality_status || null,
    processor_status: snapshot.upstream?.processor_status || null,
    ledger_status: ledgerStatus?.sandbox_forecast_bundle_ledger_status || null
  };

  return {
    artifact_type: 'race_fantasy_readiness_metadata_refresh_v33h',
    schema_version: SCHEMA_VERSION,
    generated_utc: new Date().toISOString(),
    version: VERSION,
    mode: args.mode,
    metadata_scope: 'sandbox_readiness_metadata_only',
    production_activation_target: 'blocked',
    race_predictions_output_target: 'blocked',
    fantasy_output_target: 'blocked',
    event,
    readiness_state: readiness,
    metadata_records: [
      {
        metadata_id: 'race_predictions_readiness_metadata_v33h',
        surface: 'race_predictions',
        metadata_only: true,
        refresh_performed: false,
        produces_prediction: false,
        activation_required: 'explicit_future_approval',
        readiness_status: readiness.overall,
        ...common
      },
      {
        metadata_id: 'fantasy_readiness_metadata_v33h',
        surface: 'fantasy_predictions',
        metadata_only: true,
        refresh_performed: false,
        produces_fantasy_pick: false,
        activation_required: 'explicit_future_approval',
        readiness_status: readiness.overall,
        ...common
      }
    ],
    guardrail_summary: {
      race_predictions_generated: false,
      fantasy_picks_generated: false,
      notification_sent: false,
      production_activation_performed: false,
      canonical_workbook_written: false,
      production_ledger_written: false,
      model_promoted: false
    },
    evidence_hashes: {
      sandbox_ledger_snapshot_sha256: sha256(snapshot)
    },
    next_step_candidate: 'v33I_material_change_notification_rehearsal'
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const policy = readJsonMaybe(args.policy) || {};
  const ledgerStatus = readJsonMaybe(args.ledger_status);
  const ledgerSnapshotFile = readJsonMaybe(args.ledger_snapshot);
  const snapshot = ledgerSnapshotFrom(ledgerStatus, ledgerSnapshotFile);
  const blockers = [];
  const warnings = [];

  if (!['dry_run', 'sandbox_metadata_refresh'].includes(args.mode)) blockers.push(`unsupported_mode:${args.mode}`);
  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.sandbox_readiness_metadata_refresh_allowed !== true) blockers.push('policy_sandbox_readiness_metadata_refresh_not_allowed');
  if (policy.race_predictions_refresh_allowed !== false) blockers.push('policy_race_predictions_refresh_allowed_not_false');
  if (policy.fantasy_refresh_allowed !== false) blockers.push('policy_fantasy_refresh_allowed_not_false');
  if (policy.notification_send_allowed !== false) blockers.push('policy_notification_send_allowed_not_false');
  if (policy.production_activation_allowed !== false) blockers.push('policy_production_activation_allowed_not_false');
  if (policy.live_fetch_allowed !== false) blockers.push('policy_live_fetch_allowed_not_false');

  blockers.push(...runtimeFalseFlagIssues(args, policy));
  blockers.push(...payloadGovernanceIssues('ledger_status', ledgerStatus));
  blockers.push(...payloadGovernanceIssues('ledger_snapshot', ledgerSnapshotFile));

  if (args.execute && args.mode !== 'sandbox_metadata_refresh') blockers.push('execute_true_requires_mode_sandbox_metadata_refresh');
  if (args.execute && policy.operator_approval_required === true && args.operator_approval !== true) blockers.push('execute_true_requires_operator_approval');
  if (args.execute && args.allow_metadata_refresh !== true) blockers.push('execute_true_requires_allow_metadata_refresh');
  if (args.allow_race_predictions_refresh) blockers.push('race_predictions_refresh_true_rejected_by_v33h');
  if (args.allow_fantasy_refresh) blockers.push('fantasy_refresh_true_rejected_by_v33h');
  if (args.allow_notification_send) blockers.push('notification_send_true_rejected_by_v33h');
  if (args.allow_production_activation) blockers.push('production_activation_true_rejected_by_v33h');
  if (args.allow_canonical_workbook_write) blockers.push('canonical_workbook_write_true_rejected_by_v33h');
  if (args.allow_production_ledger_write) blockers.push('production_ledger_write_true_rejected_by_v33h');
  if (!ledgerStatus && args.mode !== 'dry_run') blockers.push('missing_ledger_status');
  if (!snapshot && args.mode !== 'dry_run') blockers.push('missing_ledger_snapshot');

  const requiredStatus = policy.required_ledger_status || 'SANDBOX_FORECAST_BUNDLE_LEDGER_WRITTEN_SANDBOX_ONLY';
  if (ledgerStatus && ledgerStatus.sandbox_forecast_bundle_ledger_status !== requiredStatus) {
    blockers.push(`ledger_status_not_required:${ledgerStatus.sandbox_forecast_bundle_ledger_status || 'unknown'}`);
  }
  if (snapshot && snapshot.artifact_type !== 'sandbox_forecast_bundle_ledger_snapshot_v33g') {
    blockers.push(`ledger_snapshot_artifact_type_not_v33g:${snapshot.artifact_type || 'unknown'}`);
  }
  if (snapshot && snapshot.forecast_bundle_controls?.sandbox_feature_packet_ready !== true) {
    blockers.push('ledger_snapshot_feature_packet_not_ready');
  }
  if (snapshot && snapshot.forecast_bundle_controls?.no_prediction_or_ranking_generated !== true) {
    blockers.push('ledger_snapshot_prediction_or_ranking_guard_missing');
  }
  if (snapshot && (snapshot.forecast_bundle_controls?.forecast_generated || snapshot.forecast_bundle_controls?.fantasy_generated)) {
    blockers.push('ledger_snapshot_generated_forecast_or_fantasy');
  }
  if (snapshot && (snapshot.forecast_bundle_controls?.production_forecast_ledger_written || snapshot.forecast_bundle_controls?.canonical_workbook_written || snapshot.forecast_bundle_controls?.notification_sent || snapshot.forecast_bundle_controls?.model_promoted)) {
    blockers.push('ledger_snapshot_has_forbidden_downstream_effect');
  }
  if (!args.execute && args.mode === 'sandbox_metadata_refresh') warnings.push('sandbox_metadata_refresh_mode_without_execute_true');

  const uniqueBlockers = Array.from(new Set(blockers));
  const executePerformed = args.execute === true && uniqueBlockers.length === 0;
  let metadataArtifact = null;
  let metadataArtifactPath = null;
  if (executePerformed) {
    metadataArtifact = buildMetadataArtifact({ args, ledgerStatus, snapshot });
    metadataArtifactPath = path.join(args.artifact_dir, `race_fantasy_readiness_metadata_${timestampForPath()}.json`);
    writeJson(metadataArtifactPath, metadataArtifact);
  }

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
    notification_sent: false,
    model_promotion_performed: false,
    readiness_metadata_artifact_written: Boolean(metadataArtifactPath),
    readiness_metadata_artifact_path: metadataArtifactPath,
    ledger_status: ledgerStatus?.sandbox_forecast_bundle_ledger_status || null,
    ledger_snapshot_path: ledgerStatus?.sandbox_forecast_bundle_ledger_snapshot_path || args.ledger_snapshot || null,
    race_fantasy_readiness_metadata_status: uniqueBlockers.length > 0
      ? 'RACE_FANTASY_READINESS_METADATA_BLOCKED'
      : (executePerformed ? 'RACE_FANTASY_READINESS_METADATA_REFRESHED_SANDBOX_ONLY' : 'RACE_FANTASY_READINESS_METADATA_READY_NOT_REFRESHED'),
    race_fantasy_readiness_metadata_reason: uniqueBlockers.length > 0
      ? 'blocking_readiness_metadata_issue'
      : (executePerformed ? 'sandbox_readiness_metadata_refreshed_no_predictions_or_fantasy_outputs' : 'dry_run_or_awaiting_operator_execute'),
    blockers: uniqueBlockers,
    warnings: Array.from(new Set(warnings)),
    readiness_metadata_artifact: metadataArtifact,
    guardrails: {
      metadata_only: true,
      race_predictions_refresh: false,
      fantasy_predictions_refresh: false,
      notification_send: false,
      production_activation: false,
      canonical_workbook_write: false,
      production_forecast_bundle_ledger_write: false,
      model_promotion: false,
      live_fetch: false
    },
    next_step: uniqueBlockers.length > 0
      ? 'resolve_v33h_readiness_metadata_blockers'
      : (executePerformed ? policy.next_allowed_layer : 'run_v33h_with_operator_approval')
  };

  writeJson(args.out, status);
  console.log(JSON.stringify({
    ok: status.ok,
    race_fantasy_readiness_metadata_status: status.race_fantasy_readiness_metadata_status,
    execute_performed: status.execute_performed,
    readiness_metadata_artifact_written: status.readiness_metadata_artifact_written,
    blocker_count: status.blockers.length,
    next_step: status.next_step
  }, null, 2));
  process.exit(status.ok ? 0 : 1);
}

main();
