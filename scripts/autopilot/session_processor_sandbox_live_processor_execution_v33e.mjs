#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const VERSION = 'v33E';
const SCHEMA_VERSION = 'f1_session_processor_sandbox_live_processor_execution_v33e_2026-06-18';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_sandbox_live_processor_execution_policy_v33e.json';
const DEFAULT_OUT = 'health/session_processor_sandbox_live_processor_execution_v33e_status.json';
const DEFAULT_ARTIFACT_DIR = 'sandbox/session_processor/v33e';

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: DEFAULT_POLICY,
    source_evidence: null,
    source_quality: null,
    out: DEFAULT_OUT,
    artifact_dir: DEFAULT_ARTIFACT_DIR,
    execute: false,
    operator_approval: false,
    production_automation: false,
    workbook_write: false,
    ledger_write: false,
    race_predictions_refresh: false,
    fantasy_predictions_refresh: false,
    notification_send: false,
    model_promotion: false,
    activate: false
  };

  const keyMap = new Map([
    ['mode', 'mode'],
    ['policy', 'policy'],
    ['source-evidence', 'source_evidence'],
    ['source_evidence', 'source_evidence'],
    ['source-quality', 'source_quality'],
    ['source_quality', 'source_quality'],
    ['out', 'out'],
    ['artifact-dir', 'artifact_dir'],
    ['artifact_dir', 'artifact_dir'],
    ['execute', 'execute'],
    ['operator-approval', 'operator_approval'],
    ['operator_approval', 'operator_approval'],
    ['production-automation', 'production_automation'],
    ['workbook-write', 'workbook_write'],
    ['ledger-write', 'ledger_write'],
    ['race-predictions-refresh', 'race_predictions_refresh'],
    ['fantasy-predictions-refresh', 'fantasy_predictions_refresh'],
    ['notification-send', 'notification_send'],
    ['model-promotion', 'model_promotion'],
    ['activate', 'activate']
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

function isObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}

function bool(value) {
  return value === true;
}

function falseFlagIssues(args, policy) {
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
  if (bool(payload.workbook_write_performed) || bool(payload.workbook_write_allowed)) issues.push(`${name}:workbook_write_enabled_or_performed`);
  if (bool(payload.canonical_workbook_write_performed)) issues.push(`${name}:canonical_workbook_write_performed`);
  if (bool(payload.forecast_bundle_ledger_write_performed) || bool(payload.ledger_write_allowed)) issues.push(`${name}:ledger_write_enabled_or_performed`);
  if (bool(payload.race_predictions_refresh_performed) || bool(payload.prediction_refresh_enabled)) issues.push(`${name}:race_predictions_refresh_enabled_or_performed`);
  if (bool(payload.fantasy_refresh_performed) || bool(payload.fantasy_refresh_enabled)) issues.push(`${name}:fantasy_refresh_enabled_or_performed`);
  if (bool(payload.notification_sent) || bool(payload.notification_send_enabled)) issues.push(`${name}:notification_enabled_or_sent`);
  return issues;
}

function sourceResultMap(sourceEvidence) {
  const map = new Map();
  for (const result of Array.isArray(sourceEvidence?.fetch_results) ? sourceEvidence.fetch_results : []) {
    if (result?.request_id) map.set(result.request_id, result);
  }
  return map;
}

function sourceById(sourceEvidence, requestId) {
  return sourceResultMap(sourceEvidence).get(requestId) || null;
}

function sourceRecord(sourceEvidence, requestId, required) {
  const result = sourceById(sourceEvidence, requestId);
  return {
    request_id: requestId,
    endpoint: result?.endpoint || requestId.replace(/^openf1_/, ''),
    required,
    present: Boolean(result),
    ok: result?.ok === true,
    http_status: result?.http_status ?? null,
    row_count: result?.row_count ?? null,
    bytes: result?.bytes ?? null
  };
}

function classifyQuality(sourceQuality, policy) {
  const status = String(sourceQuality?.source_quality_status || '');
  if (!sourceQuality) return { accepted: false, status: 'missing', reason: 'missing_source_quality_artifact' };
  if (!(policy.accepted_source_quality_statuses || []).includes(status)) {
    return { accepted: false, status, reason: 'source_quality_status_not_accepted_for_v33e' };
  }
  return { accepted: true, status, reason: sourceQuality.source_quality_reason || 'accepted_source_quality_status' };
}

function buildProcessorPacket({ args, policy, sourceEvidence, sourceQuality, qualityClass }) {
  const requiredIds = policy.required_openf1_request_ids || [];
  const optionalIds = policy.optional_openf1_request_ids || [];
  const requiredSources = requiredIds.map((id) => sourceRecord(sourceEvidence, id, true));
  const optionalSources = optionalIds.map((id) => sourceRecord(sourceEvidence, id, false));
  const gate = isObject(sourceEvidence?.gate) ? sourceEvidence.gate : {};
  const rowCountTotal = [...requiredSources, ...optionalSources]
    .reduce((sum, item) => sum + (Number(item.row_count) || 0), 0);

  const readiness = {
    required_sources_ready: requiredSources.every((item) => item.present && item.ok && Number(item.row_count) > 0),
    optional_sources_ready_count: optionalSources.filter((item) => item.present && item.ok && Number(item.row_count) > 0).length,
    optional_source_count: optionalSources.length,
    row_count_total: rowCountTotal,
    quality_status: qualityClass.status,
    quality_reason: qualityClass.reason
  };

  const derivedSignalSurface = {
    timing_available: Number(sourceById(sourceEvidence, 'openf1_laps')?.row_count || 0) > 0,
    stint_available: Number(sourceById(sourceEvidence, 'openf1_stints')?.row_count || 0) > 0,
    track_position_available: Number(sourceById(sourceEvidence, 'openf1_position')?.row_count || 0) > 0,
    interval_available: Number(sourceById(sourceEvidence, 'openf1_intervals')?.row_count || 0) > 0,
    race_control_available: Number(sourceById(sourceEvidence, 'openf1_race_control')?.row_count || 0) > 0,
    weather_available: Number(sourceById(sourceEvidence, 'openf1_weather')?.row_count || 0) > 0,
    driver_metadata_available: Number(sourceById(sourceEvidence, 'openf1_drivers')?.row_count || 0) > 0,
    no_prediction_or_ranking_generated: true
  };

  return {
    artifact_type: 'sandbox_live_processor_execution_v33e',
    schema_version: SCHEMA_VERSION,
    generated_utc: new Date().toISOString(),
    version: VERSION,
    mode: args.mode,
    execution_scope: 'sandbox_processor_artifact_only',
    event: {
      event_name: gate.event_name || null,
      session_name: gate.session_name || null,
      session_key: gate.session_key ?? null,
      meeting_key: gate.meeting_key ?? null,
      year: gate.year ?? null,
      source_timestamp_utc: gate.source_timestamp_utc || null
    },
    inputs: {
      source_evidence_path: args.source_evidence || null,
      source_quality_path: args.source_quality || null,
      source_evidence_status: sourceEvidence?.pull_status || null,
      source_quality_status: sourceQuality?.source_quality_status || null
    },
    source_layers: {
      required: requiredSources,
      optional: optionalSources
    },
    processor_readiness: readiness,
    derived_signal_surface: derivedSignalSurface,
    processor_outputs: {
      sandbox_feature_packet_ready: readiness.required_sources_ready,
      raw_rows_consumed: false,
      summary_evidence_consumed: true,
      forecast_generated: false,
      fantasy_generated: false,
      workbook_written: false,
      ledger_written: false,
      notification_sent: false
    },
    next_step_candidate: qualityClass.status === 'SANDBOX_SOURCE_QUALITY_BLOCKED'
      ? 'resolve_v33d_source_quality_blockers'
      : 'v33F_sandbox_workbook_reflection_write'
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const policy = readJsonMaybe(args.policy) || {};
  const sourceEvidence = readJsonMaybe(args.source_evidence);
  const sourceQuality = readJsonMaybe(args.source_quality);

  const blockers = [];
  const warnings = [];
  if (!['dry_run', 'fixture', 'sandbox_execution'].includes(args.mode)) blockers.push(`unsupported_mode:${args.mode}`);
  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.sandbox_processor_execution_allowed !== true) blockers.push('policy_sandbox_processor_execution_not_allowed');
  if (policy.live_fetch_allowed !== false) blockers.push('policy_live_fetch_allowed_not_false');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');
  if (args.execute && args.mode !== 'sandbox_execution') blockers.push('execute_true_requires_mode_sandbox_execution');
  if (args.execute && policy.operator_approval_required === true && args.operator_approval !== true) blockers.push('execute_true_requires_operator_approval');
  if (!args.execute && args.mode === 'sandbox_execution') warnings.push('sandbox_execution_mode_without_execute_true');
  if (!sourceEvidence && args.mode !== 'dry_run') blockers.push('missing_source_evidence');
  if (!sourceQuality && args.mode !== 'dry_run') blockers.push('missing_source_quality');
  blockers.push(...falseFlagIssues(args, policy));
  blockers.push(...payloadGovernanceIssues('source_evidence', sourceEvidence));
  blockers.push(...payloadGovernanceIssues('source_quality', sourceQuality));

  const qualityClass = classifyQuality(sourceQuality, policy);
  if (args.mode !== 'dry_run' && !qualityClass.accepted) blockers.push(`source_quality_not_accepted:${qualityClass.status}`);
  const acceptedSourceEvidenceStatuses = policy.accepted_source_evidence_statuses || ['SANDBOX_SOURCE_EVIDENCE_READY'];
  if (sourceEvidence && !acceptedSourceEvidenceStatuses.includes(sourceEvidence.pull_status)) {
    blockers.push(`source_evidence_not_ready:${sourceEvidence.pull_status || 'unknown'}`);
  }

  const executePerformed = args.execute === true && blockers.length === 0;
  const processorPacket = executePerformed
    ? buildProcessorPacket({ args, policy, sourceEvidence, sourceQuality, qualityClass })
    : null;

  let processorArtifactPath = null;
  if (processorPacket) {
    processorArtifactPath = path.join(args.artifact_dir, `processor_execution_${timestampForPath()}.json`);
    writeJson(processorArtifactPath, processorPacket);
  }

  const status = {
    schema_version: SCHEMA_VERSION,
    generated_utc: new Date().toISOString(),
    version: VERSION,
    ok: blockers.length === 0,
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: executePerformed,
    operator_approval_recorded: args.operator_approval,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    workbook_write_allowed: false,
    ledger_write_allowed: false,
    prediction_refresh_enabled: false,
    fantasy_refresh_enabled: false,
    notification_send_enabled: false,
    live_fetch_performed: false,
    processor_execution_status: blockers.length > 0
      ? 'SANDBOX_PROCESSOR_EXECUTION_BLOCKED'
      : (executePerformed ? 'SANDBOX_PROCESSOR_EXECUTION_READY_ARTIFACT_WRITTEN' : 'SANDBOX_PROCESSOR_EXECUTION_READY_NOT_RUN'),
    processor_execution_reason: blockers.length > 0
      ? 'blocking_processor_execution_issue'
      : (executePerformed ? 'sandbox_processor_packet_written' : 'dry_run_or_awaiting_operator_execute'),
    source_quality_status: sourceQuality?.source_quality_status || null,
    source_evidence_status: sourceEvidence?.pull_status || null,
    blockers: Array.from(new Set(blockers)),
    warnings: Array.from(new Set(warnings)),
    processor_artifact_written: Boolean(processorArtifactPath),
    processor_artifact_path: processorArtifactPath,
    processor_packet: processorPacket,
    guardrails: {
      production_automation: false,
      workbook_write: false,
      ledger_write: false,
      race_predictions_refresh: false,
      fantasy_predictions_refresh: false,
      notification_send: false,
      model_promotion: false,
      activate: false,
      live_fetch: false,
      sandbox_processor_artifact_only: true
    },
    next_step: blockers.length > 0
      ? 'resolve_v33e_sandbox_processor_execution_blockers'
      : (executePerformed ? 'v33F_sandbox_workbook_reflection_write' : 'run_v33e_with_operator_approval')
  };

  writeJson(args.out, status);
  console.log(JSON.stringify({
    ok: status.ok,
    processor_execution_status: status.processor_execution_status,
    execute_performed: executePerformed,
    processor_artifact_written: status.processor_artifact_written,
    blocker_count: status.blockers.length,
    next_step: status.next_step
  }, null, 2));
  process.exit(status.ok ? 0 : 1);
}

main();
