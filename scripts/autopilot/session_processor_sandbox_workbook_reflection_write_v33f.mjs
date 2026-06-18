#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const VERSION = 'v33F';
const SCHEMA_VERSION = 'f1_session_processor_sandbox_workbook_reflection_write_v33f_2026-06-18';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_sandbox_workbook_reflection_write_policy_v33f.json';
const DEFAULT_OUT = 'health/session_processor_sandbox_workbook_reflection_write_v33f_status.json';
const DEFAULT_ARTIFACT_DIR = 'sandbox/workbook_reflection/v33f';

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: DEFAULT_POLICY,
    processor_status: null,
    processor_artifact: null,
    out: DEFAULT_OUT,
    artifact_dir: DEFAULT_ARTIFACT_DIR,
    execute: false,
    operator_approval: false,
    allow_sandbox_workbook_write: false,
    allow_canonical_workbook_write: false,
    production_automation: false,
    ledger_write: false,
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
    ['processor-status', 'processor_status'],
    ['processor_status', 'processor_status'],
    ['processor-artifact', 'processor_artifact'],
    ['processor_artifact', 'processor_artifact'],
    ['out', 'out'],
    ['artifact-dir', 'artifact_dir'],
    ['artifact_dir', 'artifact_dir'],
    ['execute', 'execute'],
    ['operator-approval', 'operator_approval'],
    ['operator_approval', 'operator_approval'],
    ['allow-sandbox-workbook-write', 'allow_sandbox_workbook_write'],
    ['allow_sandbox_workbook_write', 'allow_sandbox_workbook_write'],
    ['allow-canonical-workbook-write', 'allow_canonical_workbook_write'],
    ['allow_canonical_workbook_write', 'allow_canonical_workbook_write'],
    ['production-automation', 'production_automation'],
    ['ledger-write', 'ledger_write'],
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

function bool(value) {
  return value === true;
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
  if (bool(payload.canonical_workbook_write_performed)) issues.push(`${name}:canonical_workbook_write_performed`);
  if (bool(payload.forecast_bundle_ledger_write_performed) || bool(payload.ledger_write_allowed)) issues.push(`${name}:ledger_write_enabled_or_performed`);
  if (bool(payload.race_predictions_refresh_performed) || bool(payload.prediction_refresh_enabled)) issues.push(`${name}:race_predictions_refresh_enabled_or_performed`);
  if (bool(payload.fantasy_refresh_performed) || bool(payload.fantasy_refresh_enabled)) issues.push(`${name}:fantasy_refresh_enabled_or_performed`);
  if (bool(payload.notification_sent) || bool(payload.notification_send_enabled)) issues.push(`${name}:notification_enabled_or_sent`);
  return issues;
}

function runtimeFalseFlagIssues(args, policy) {
  const issues = [];
  for (const flag of policy.required_false_runtime_flags || []) {
    if (args[flag] !== false) issues.push(`runtime_flag_must_be_false:${flag}`);
  }
  return issues;
}

function processorPacketFrom(processorStatus, processorArtifact) {
  return processorArtifact || processorStatus?.processor_packet || null;
}

function sourceRows(packet) {
  const required = Array.isArray(packet?.source_layers?.required) ? packet.source_layers.required : [];
  const optional = Array.isArray(packet?.source_layers?.optional) ? packet.source_layers.optional : [];
  return [...required, ...optional].reduce((sum, item) => sum + (Number(item.row_count) || 0), 0);
}

function sourceAvailability(packet) {
  const surface = packet?.derived_signal_surface || {};
  return {
    timing: Boolean(surface.timing_available),
    stint: Boolean(surface.stint_available),
    track_position: Boolean(surface.track_position_available),
    interval: Boolean(surface.interval_available),
    race_control: Boolean(surface.race_control_available),
    weather: Boolean(surface.weather_available),
    driver_metadata: Boolean(surface.driver_metadata_available)
  };
}

function buildReflectionArtifact({ args, processorStatus, packet }) {
  const readiness = packet.processor_readiness || {};
  const outputs = packet.processor_outputs || {};
  const event = packet.event || {};
  return {
    artifact_type: 'sandbox_workbook_reflection_write_v33f',
    schema_version: SCHEMA_VERSION,
    generated_utc: new Date().toISOString(),
    version: VERSION,
    mode: args.mode,
    write_scope: 'sandbox_workbook_reflection_artifact_only',
    canonical_workbook_target: 'blocked',
    real_workbook_file_written: false,
    sandbox_json_artifact_written: true,
    event,
    upstream: {
      processor_status: processorStatus?.processor_execution_status || null,
      processor_artifact_path: processorStatus?.processor_artifact_path || args.processor_artifact || null,
      source_evidence_status: packet.inputs?.source_evidence_status || processorStatus?.source_evidence_status || null,
      source_quality_status: packet.inputs?.source_quality_status || processorStatus?.source_quality_status || null
    },
    workbook_reflection_tabs: [
      {
        tab_name: 'Session Source Readiness',
        status: readiness.required_sources_ready ? 'ready' : 'blocked',
        row_count_total: Number(readiness.row_count_total ?? sourceRows(packet)),
        required_sources_ready: Boolean(readiness.required_sources_ready),
        optional_sources_ready_count: Number(readiness.optional_sources_ready_count || 0),
        optional_source_count: Number(readiness.optional_source_count || 0)
      },
      {
        tab_name: 'Signal Availability',
        status: outputs.sandbox_feature_packet_ready ? 'ready' : 'blocked',
        source_availability: sourceAvailability(packet)
      },
      {
        tab_name: 'Governance Guardrails',
        status: 'locked',
        canonical_workbook_write: false,
        production_automation: false,
        forecast_bundle_ledger_write: false,
        race_predictions_refresh: false,
        fantasy_predictions_refresh: false,
        notification_send: false,
        model_promotion: false
      }
    ],
    workbook_reflection_summary: {
      sandbox_feature_packet_ready: Boolean(outputs.sandbox_feature_packet_ready),
      no_prediction_or_ranking_generated: packet.derived_signal_surface?.no_prediction_or_ranking_generated === true,
      forecast_generated: false,
      fantasy_generated: false,
      workbook_written: false,
      canonical_workbook_written: false,
      ledger_written: false,
      notification_sent: false
    },
    next_step_candidate: 'v33G_sandbox_forecast_bundle_ledger_snapshot'
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const policy = readJsonMaybe(args.policy) || {};
  const processorStatus = readJsonMaybe(args.processor_status);
  const processorArtifact = readJsonMaybe(args.processor_artifact);
  const packet = processorPacketFrom(processorStatus, processorArtifact);
  const blockers = [];
  const warnings = [];

  if (!['dry_run', 'sandbox_reflection_write'].includes(args.mode)) blockers.push(`unsupported_mode:${args.mode}`);
  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.sandbox_workbook_reflection_write_allowed !== true) blockers.push('policy_sandbox_workbook_reflection_write_not_allowed');
  if (policy.canonical_workbook_write_allowed !== false) blockers.push('policy_canonical_workbook_write_allowed_not_false');
  if (policy.live_fetch_allowed !== false) blockers.push('policy_live_fetch_allowed_not_false');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');

  blockers.push(...runtimeFalseFlagIssues(args, policy));
  blockers.push(...payloadGovernanceIssues('processor_status', processorStatus));
  blockers.push(...payloadGovernanceIssues('processor_artifact', processorArtifact));

  if (args.execute && args.mode !== 'sandbox_reflection_write') blockers.push('execute_true_requires_mode_sandbox_reflection_write');
  if (args.execute && policy.operator_approval_required === true && args.operator_approval !== true) blockers.push('execute_true_requires_operator_approval');
  if (args.execute && args.allow_sandbox_workbook_write !== true) blockers.push('execute_true_requires_allow_sandbox_workbook_write');
  if (args.allow_canonical_workbook_write) blockers.push('canonical_workbook_write_true_rejected_by_v33f');
  if (!processorStatus && args.mode !== 'dry_run') blockers.push('missing_processor_status');
  if (!packet && args.mode !== 'dry_run') blockers.push('missing_processor_packet_or_artifact');

  const acceptedStatus = policy.required_processor_execution_status || 'SANDBOX_PROCESSOR_EXECUTION_READY_ARTIFACT_WRITTEN';
  if (processorStatus && processorStatus.processor_execution_status !== acceptedStatus) {
    blockers.push(`processor_execution_status_not_required:${processorStatus.processor_execution_status || 'unknown'}`);
  }
  if (packet && packet.artifact_type !== 'sandbox_live_processor_execution_v33e') {
    blockers.push(`processor_artifact_type_not_v33e:${packet.artifact_type || 'unknown'}`);
  }
  if (packet && packet.processor_outputs?.sandbox_feature_packet_ready !== true) {
    blockers.push('processor_packet_not_sandbox_feature_ready');
  }
  if (packet && packet.derived_signal_surface?.no_prediction_or_ranking_generated !== true) {
    blockers.push('processor_packet_prediction_or_ranking_guard_missing');
  }
  if (packet && (packet.processor_outputs?.forecast_generated || packet.processor_outputs?.fantasy_generated)) {
    blockers.push('processor_packet_generated_forecast_or_fantasy');
  }
  if (packet && (packet.processor_outputs?.workbook_written || packet.processor_outputs?.ledger_written || packet.processor_outputs?.notification_sent)) {
    blockers.push('processor_packet_has_downstream_write');
  }
  if (!args.execute && args.mode === 'sandbox_reflection_write') warnings.push('sandbox_reflection_write_mode_without_execute_true');

  const uniqueBlockers = Array.from(new Set(blockers));
  const executePerformed = args.execute === true && uniqueBlockers.length === 0;
  let reflectionArtifact = null;
  let reflectionArtifactPath = null;
  if (executePerformed) {
    reflectionArtifact = buildReflectionArtifact({ args, processorStatus, packet });
    reflectionArtifactPath = path.join(args.artifact_dir, `sandbox_workbook_reflection_${timestampForPath()}.json`);
    writeJson(reflectionArtifactPath, reflectionArtifact);
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
    sandbox_workbook_reflection_artifact_written: Boolean(reflectionArtifactPath),
    sandbox_workbook_reflection_artifact_path: reflectionArtifactPath,
    canonical_workbook_write_performed: false,
    forecast_bundle_ledger_write_performed: false,
    race_predictions_refresh_performed: false,
    fantasy_refresh_performed: false,
    notification_sent: false,
    model_promotion_performed: false,
    processor_execution_status: processorStatus?.processor_execution_status || null,
    processor_artifact_path: processorStatus?.processor_artifact_path || args.processor_artifact || null,
    sandbox_workbook_reflection_status: uniqueBlockers.length > 0
      ? 'SANDBOX_WORKBOOK_REFLECTION_BLOCKED'
      : (executePerformed ? 'SANDBOX_WORKBOOK_REFLECTION_WRITTEN_SANDBOX_ONLY' : 'SANDBOX_WORKBOOK_REFLECTION_READY_NOT_WRITTEN'),
    sandbox_workbook_reflection_reason: uniqueBlockers.length > 0
      ? 'blocking_sandbox_workbook_reflection_issue'
      : (executePerformed ? 'sandbox_reflection_artifact_written_no_canonical_workbook_touch' : 'dry_run_or_awaiting_operator_execute'),
    blockers: uniqueBlockers,
    warnings: Array.from(new Set(warnings)),
    reflection_artifact: reflectionArtifact,
    guardrails: {
      sandbox_artifact_only: true,
      canonical_workbook_write: false,
      production_automation: false,
      forecast_bundle_ledger_write: false,
      race_predictions_refresh: false,
      fantasy_predictions_refresh: false,
      notification_send: false,
      model_promotion: false,
      activate: false,
      live_fetch: false
    },
    next_step: uniqueBlockers.length > 0
      ? 'resolve_v33f_sandbox_workbook_reflection_blockers'
      : (executePerformed ? policy.next_allowed_layer : 'run_v33f_with_operator_approval')
  };

  writeJson(args.out, status);
  console.log(JSON.stringify({
    ok: status.ok,
    sandbox_workbook_reflection_status: status.sandbox_workbook_reflection_status,
    execute_performed: status.execute_performed,
    sandbox_workbook_reflection_artifact_written: status.sandbox_workbook_reflection_artifact_written,
    blocker_count: status.blockers.length,
    next_step: status.next_step
  }, null, 2));
  process.exit(status.ok ? 0 : 1);
}

main();
