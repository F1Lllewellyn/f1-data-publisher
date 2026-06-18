#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const VERSION = 'v33G';
const SCHEMA_VERSION = 'f1_session_processor_sandbox_forecast_bundle_ledger_snapshot_v33g_2026-06-18';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_sandbox_forecast_bundle_ledger_snapshot_policy_v33g.json';
const DEFAULT_OUT = 'health/session_processor_sandbox_forecast_bundle_ledger_snapshot_v33g_status.json';
const DEFAULT_ARTIFACT_DIR = 'sandbox/forecast_bundle_ledger/v33g';

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: DEFAULT_POLICY,
    workbook_reflection_status: null,
    workbook_reflection_artifact: null,
    out: DEFAULT_OUT,
    artifact_dir: DEFAULT_ARTIFACT_DIR,
    execute: false,
    operator_approval: false,
    allow_sandbox_ledger_write: false,
    allow_production_ledger_write: false,
    allow_canonical_workbook_write: false,
    production_automation: false,
    race_predictions_refresh: false,
    fantasy_predictions_refresh: false,
    notification_send: false,
    model_promotion: false,
    activate: false,
    live_fetch: false
  };

  const keyMap = new Map([
    ['mode', 'mode'],
    ['policy', 'policy'],
    ['workbook-reflection-status', 'workbook_reflection_status'],
    ['workbook_reflection_status', 'workbook_reflection_status'],
    ['workbook-reflection-artifact', 'workbook_reflection_artifact'],
    ['workbook_reflection_artifact', 'workbook_reflection_artifact'],
    ['out', 'out'],
    ['artifact-dir', 'artifact_dir'],
    ['artifact_dir', 'artifact_dir'],
    ['execute', 'execute'],
    ['operator-approval', 'operator_approval'],
    ['operator_approval', 'operator_approval'],
    ['allow-sandbox-ledger-write', 'allow_sandbox_ledger_write'],
    ['allow_sandbox_ledger_write', 'allow_sandbox_ledger_write'],
    ['allow-production-ledger-write', 'allow_production_ledger_write'],
    ['allow_production_ledger_write', 'allow_production_ledger_write'],
    ['allow-canonical-workbook-write', 'allow_canonical_workbook_write'],
    ['allow_canonical_workbook_write', 'allow_canonical_workbook_write'],
    ['production-automation', 'production_automation'],
    ['race-predictions-refresh', 'race_predictions_refresh'],
    ['fantasy-predictions-refresh', 'fantasy_predictions_refresh'],
    ['notification-send', 'notification_send'],
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
  if (bool(payload.forecast_bundle_ledger_write_performed)) issues.push(`${name}:forecast_bundle_ledger_write_performed`);
  if (bool(payload.race_predictions_refresh_performed)) issues.push(`${name}:race_predictions_refresh_performed`);
  if (bool(payload.fantasy_refresh_performed)) issues.push(`${name}:fantasy_refresh_performed`);
  if (bool(payload.notification_sent)) issues.push(`${name}:notification_sent`);
  return issues;
}

function reflectionArtifactFrom(status, artifact) {
  return artifact || status?.reflection_artifact || null;
}

function buildLedgerSnapshot({ args, workbookReflectionStatus, reflectionArtifact }) {
  const event = reflectionArtifact.event || {};
  const summary = reflectionArtifact.workbook_reflection_summary || {};
  const sourceTab = (reflectionArtifact.workbook_reflection_tabs || []).find((tab) => tab.tab_name === 'Session Source Readiness') || {};
  const signalTab = (reflectionArtifact.workbook_reflection_tabs || []).find((tab) => tab.tab_name === 'Signal Availability') || {};
  const upstream = reflectionArtifact.upstream || {};
  return {
    artifact_type: 'sandbox_forecast_bundle_ledger_snapshot_v33g',
    schema_version: SCHEMA_VERSION,
    generated_utc: new Date().toISOString(),
    version: VERSION,
    mode: args.mode,
    ledger_scope: 'sandbox_forecast_bundle_ledger_snapshot_only',
    production_ledger_target: 'blocked',
    canonical_workbook_target: 'blocked',
    event,
    upstream: {
      workbook_reflection_status: workbookReflectionStatus?.sandbox_workbook_reflection_status || null,
      workbook_reflection_artifact_path: workbookReflectionStatus?.sandbox_workbook_reflection_artifact_path || args.workbook_reflection_artifact || null,
      processor_status: upstream.processor_status || null,
      source_evidence_status: upstream.source_evidence_status || null,
      source_quality_status: upstream.source_quality_status || null
    },
    source_readiness_snapshot: {
      row_count_total: sourceTab.row_count_total ?? null,
      required_sources_ready: sourceTab.required_sources_ready === true,
      optional_sources_ready_count: sourceTab.optional_sources_ready_count ?? null,
      optional_source_count: sourceTab.optional_source_count ?? null
    },
    signal_availability_snapshot: signalTab.source_availability || {},
    forecast_bundle_controls: {
      sandbox_feature_packet_ready: summary.sandbox_feature_packet_ready === true,
      no_prediction_or_ranking_generated: summary.no_prediction_or_ranking_generated === true,
      forecast_generated: false,
      fantasy_generated: false,
      production_forecast_ledger_written: false,
      canonical_workbook_written: false,
      notification_sent: false,
      model_promoted: false
    },
    evidence_hashes: {
      workbook_reflection_sha256: sha256(reflectionArtifact)
    },
    next_step_candidate: 'v33H_race_fantasy_readiness_metadata_refresh'
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const policy = readJsonMaybe(args.policy) || {};
  const workbookReflectionStatus = readJsonMaybe(args.workbook_reflection_status);
  const workbookReflectionArtifact = readJsonMaybe(args.workbook_reflection_artifact);
  const reflectionArtifact = reflectionArtifactFrom(workbookReflectionStatus, workbookReflectionArtifact);
  const blockers = [];
  const warnings = [];

  if (!['dry_run', 'sandbox_ledger_snapshot'].includes(args.mode)) blockers.push(`unsupported_mode:${args.mode}`);
  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.sandbox_forecast_bundle_ledger_snapshot_allowed !== true) blockers.push('policy_sandbox_forecast_bundle_ledger_snapshot_not_allowed');
  if (policy.production_forecast_bundle_ledger_write_allowed !== false) blockers.push('policy_production_forecast_bundle_ledger_write_allowed_not_false');
  if (policy.canonical_workbook_write_allowed !== false) blockers.push('policy_canonical_workbook_write_allowed_not_false');
  if (policy.live_fetch_allowed !== false) blockers.push('policy_live_fetch_allowed_not_false');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');

  blockers.push(...runtimeFalseFlagIssues(args, policy));
  blockers.push(...payloadGovernanceIssues('workbook_reflection_status', workbookReflectionStatus));
  blockers.push(...payloadGovernanceIssues('workbook_reflection_artifact', workbookReflectionArtifact));

  if (args.execute && args.mode !== 'sandbox_ledger_snapshot') blockers.push('execute_true_requires_mode_sandbox_ledger_snapshot');
  if (args.execute && policy.operator_approval_required === true && args.operator_approval !== true) blockers.push('execute_true_requires_operator_approval');
  if (args.execute && args.allow_sandbox_ledger_write !== true) blockers.push('execute_true_requires_allow_sandbox_ledger_write');
  if (args.allow_production_ledger_write) blockers.push('production_ledger_write_true_rejected_by_v33g');
  if (args.allow_canonical_workbook_write) blockers.push('canonical_workbook_write_true_rejected_by_v33g');
  if (!workbookReflectionStatus && args.mode !== 'dry_run') blockers.push('missing_workbook_reflection_status');
  if (!reflectionArtifact && args.mode !== 'dry_run') blockers.push('missing_workbook_reflection_artifact');

  const requiredStatus = policy.required_workbook_reflection_status || 'SANDBOX_WORKBOOK_REFLECTION_WRITTEN_SANDBOX_ONLY';
  if (workbookReflectionStatus && workbookReflectionStatus.sandbox_workbook_reflection_status !== requiredStatus) {
    blockers.push(`workbook_reflection_status_not_required:${workbookReflectionStatus.sandbox_workbook_reflection_status || 'unknown'}`);
  }
  if (reflectionArtifact && reflectionArtifact.artifact_type !== 'sandbox_workbook_reflection_write_v33f') {
    blockers.push(`workbook_reflection_artifact_type_not_v33f:${reflectionArtifact.artifact_type || 'unknown'}`);
  }
  if (reflectionArtifact && reflectionArtifact.workbook_reflection_summary?.sandbox_feature_packet_ready !== true) {
    blockers.push('workbook_reflection_not_feature_ready');
  }
  if (reflectionArtifact && reflectionArtifact.workbook_reflection_summary?.no_prediction_or_ranking_generated !== true) {
    blockers.push('workbook_reflection_prediction_or_ranking_guard_missing');
  }
  if (reflectionArtifact && (reflectionArtifact.workbook_reflection_summary?.forecast_generated || reflectionArtifact.workbook_reflection_summary?.fantasy_generated)) {
    blockers.push('workbook_reflection_generated_forecast_or_fantasy');
  }
  if (reflectionArtifact && (reflectionArtifact.workbook_reflection_summary?.canonical_workbook_written || reflectionArtifact.workbook_reflection_summary?.ledger_written || reflectionArtifact.workbook_reflection_summary?.notification_sent)) {
    blockers.push('workbook_reflection_has_downstream_write');
  }
  if (!args.execute && args.mode === 'sandbox_ledger_snapshot') warnings.push('sandbox_ledger_snapshot_mode_without_execute_true');

  const uniqueBlockers = Array.from(new Set(blockers));
  const executePerformed = args.execute === true && uniqueBlockers.length === 0;
  let ledgerSnapshot = null;
  let ledgerSnapshotPath = null;
  if (executePerformed) {
    ledgerSnapshot = buildLedgerSnapshot({ args, workbookReflectionStatus, reflectionArtifact });
    ledgerSnapshotPath = path.join(args.artifact_dir, `sandbox_forecast_bundle_ledger_snapshot_${timestampForPath()}.json`);
    writeJson(ledgerSnapshotPath, ledgerSnapshot);
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
    forecast_bundle_ledger_write_performed: false,
    sandbox_forecast_bundle_ledger_snapshot_written: Boolean(ledgerSnapshotPath),
    sandbox_forecast_bundle_ledger_snapshot_path: ledgerSnapshotPath,
    production_forecast_bundle_ledger_write_performed: false,
    race_predictions_refresh_performed: false,
    fantasy_refresh_performed: false,
    notification_sent: false,
    model_promotion_performed: false,
    workbook_reflection_status: workbookReflectionStatus?.sandbox_workbook_reflection_status || null,
    workbook_reflection_artifact_path: workbookReflectionStatus?.sandbox_workbook_reflection_artifact_path || args.workbook_reflection_artifact || null,
    sandbox_forecast_bundle_ledger_status: uniqueBlockers.length > 0
      ? 'SANDBOX_FORECAST_BUNDLE_LEDGER_BLOCKED'
      : (executePerformed ? 'SANDBOX_FORECAST_BUNDLE_LEDGER_WRITTEN_SANDBOX_ONLY' : 'SANDBOX_FORECAST_BUNDLE_LEDGER_READY_NOT_WRITTEN'),
    sandbox_forecast_bundle_ledger_reason: uniqueBlockers.length > 0
      ? 'blocking_sandbox_forecast_bundle_ledger_issue'
      : (executePerformed ? 'sandbox_forecast_bundle_ledger_snapshot_written_no_production_ledger_touch' : 'dry_run_or_awaiting_operator_execute'),
    blockers: uniqueBlockers,
    warnings: Array.from(new Set(warnings)),
    ledger_snapshot: ledgerSnapshot,
    guardrails: {
      sandbox_artifact_only: true,
      production_forecast_bundle_ledger_write: false,
      canonical_workbook_write: false,
      production_automation: false,
      race_predictions_refresh: false,
      fantasy_predictions_refresh: false,
      notification_send: false,
      model_promotion: false,
      activate: false,
      live_fetch: false
    },
    next_step: uniqueBlockers.length > 0
      ? 'resolve_v33g_sandbox_forecast_bundle_ledger_blockers'
      : (executePerformed ? policy.next_allowed_layer : 'run_v33g_with_operator_approval')
  };

  writeJson(args.out, status);
  console.log(JSON.stringify({
    ok: status.ok,
    sandbox_forecast_bundle_ledger_status: status.sandbox_forecast_bundle_ledger_status,
    execute_performed: status.execute_performed,
    sandbox_forecast_bundle_ledger_snapshot_written: status.sandbox_forecast_bundle_ledger_snapshot_written,
    blocker_count: status.blockers.length,
    next_step: status.next_step
  }, null, 2));
  process.exit(status.ok ? 0 : 1);
}

main();
