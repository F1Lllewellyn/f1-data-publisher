#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const VERSION = 'v33J';
const SCHEMA_VERSION = 'f1_session_processor_final_activation_decision_packet_v33j_2026-06-18';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_final_activation_decision_packet_policy_v33j.json';
const DEFAULT_OUT = 'health/session_processor_final_activation_decision_packet_v33j_status.json';
const DEFAULT_ARTIFACT_DIR = 'sandbox/activation_decision_packets/v33j';

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: DEFAULT_POLICY,
    source_pull_status: null,
    source_quality_status: null,
    processor_status: null,
    workbook_reflection_status: null,
    ledger_status: null,
    readiness_metadata_status: null,
    notification_rehearsal_status: null,
    out: DEFAULT_OUT,
    artifact_dir: DEFAULT_ARTIFACT_DIR,
    execute: false,
    operator_approval: false,
    allow_decision_packet_write: false,
    allow_activation: false,
    allow_notification_send: false,
    allow_race_predictions_refresh: false,
    allow_fantasy_refresh: false,
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
    ['source-pull-status', 'source_pull_status'],
    ['source_pull_status', 'source_pull_status'],
    ['source-quality-status', 'source_quality_status'],
    ['source_quality_status', 'source_quality_status'],
    ['processor-status', 'processor_status'],
    ['processor_status', 'processor_status'],
    ['workbook-reflection-status', 'workbook_reflection_status'],
    ['workbook_reflection_status', 'workbook_reflection_status'],
    ['ledger-status', 'ledger_status'],
    ['ledger_status', 'ledger_status'],
    ['readiness-metadata-status', 'readiness_metadata_status'],
    ['readiness_metadata_status', 'readiness_metadata_status'],
    ['notification-rehearsal-status', 'notification_rehearsal_status'],
    ['notification_rehearsal_status', 'notification_rehearsal_status'],
    ['out', 'out'],
    ['artifact-dir', 'artifact_dir'],
    ['artifact_dir', 'artifact_dir'],
    ['execute', 'execute'],
    ['operator-approval', 'operator_approval'],
    ['operator_approval', 'operator_approval'],
    ['allow-decision-packet-write', 'allow_decision_packet_write'],
    ['allow_decision_packet_write', 'allow_decision_packet_write'],
    ['allow-activation', 'allow_activation'],
    ['allow_activation', 'allow_activation'],
    ['allow-notification-send', 'allow_notification_send'],
    ['allow_notification_send', 'allow_notification_send'],
    ['allow-race-predictions-refresh', 'allow_race_predictions_refresh'],
    ['allow_race_predictions_refresh', 'allow_race_predictions_refresh'],
    ['allow-fantasy-refresh', 'allow_fantasy_refresh'],
    ['allow_fantasy_refresh', 'allow_fantasy_refresh'],
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

function statusValue(payload, candidates) {
  for (const key of candidates) {
    if (payload && payload[key]) return payload[key];
  }
  return null;
}

function statusKeyForEvidence(name) {
  return {
    v33C_source_pull: 'pull_status',
    v33D_source_quality: 'source_quality_status',
    v33E_processor_execution: 'processor_execution_status',
    v33F_workbook_reflection: 'sandbox_workbook_reflection_status',
    v33G_ledger_snapshot: 'sandbox_forecast_bundle_ledger_status',
    v33H_readiness_metadata: 'race_fantasy_readiness_metadata_status',
    v33I_notification_rehearsal: 'material_change_notification_rehearsal_status'
  }[name] || null;
}

function evaluateEvidence(policy, namedPayloads) {
  const expectations = policy.required_statuses || {};
  return namedPayloads.map(({ name, payload }) => {
    const expected = expectations[name] || null;
    const primaryStatusKey = statusKeyForEvidence(name);
    const actual = primaryStatusKey ? statusValue(payload, [primaryStatusKey]) : null;
    return {
      name,
      present: Boolean(payload),
      ok: payload?.ok === true,
      status_key: primaryStatusKey,
      expected_status: expected,
      actual_status: actual,
      expected_status_matched: expected ? actual === expected : true,
      blockers: Array.isArray(payload?.blockers) ? payload.blockers : [],
      warnings: Array.isArray(payload?.warnings) ? payload.warnings : [],
      evidence_hash: payload ? sha256(payload) : null
    };
  });
}

function buildDecisionPacket({ args, evidence, namedPayloads, blockers }) {
  const allRequiredReady = evidence.every((item) => item.present && item.ok && item.expected_status_matched && item.blockers.length === 0);
  const classification = blockers.length > 0
    ? 'blocked'
    : (allRequiredReady ? 'safe_for_explicit_operator_activation_review' : 'degraded_review_required');

  const sourcePull = namedPayloads.find((item) => item.name === 'v33C_source_pull')?.payload;
  const notification = namedPayloads.find((item) => item.name === 'v33I_notification_rehearsal')?.payload;

  return {
    artifact_type: 'final_activation_decision_packet_v33j',
    schema_version: SCHEMA_VERSION,
    generated_utc: new Date().toISOString(),
    version: VERSION,
    mode: args.mode,
    packet_scope: 'operator_decision_packet_only',
    activation_performed: false,
    activation_allowed_by_this_packet: false,
    activation_requires_future_explicit_approval: true,
    decision_classification: classification,
    decision_summary: classification === 'safe_for_explicit_operator_activation_review'
      ? 'v33C-v33I sandbox chain evidence is internally consistent and ready for operator activation review. This packet does not activate production.'
      : (classification === 'blocked'
        ? 'Activation review is blocked by missing or failing evidence.'
        : 'Activation review requires manual review because evidence is present but not fully clean.'),
    roadmap_evidence: evidence,
    event_context: sourcePull?.event || notification?.notification_preview_artifact?.preview_body?.event || {},
    operator_decision_options: [
      'hold_and_harden_bridge_vulnerability_before_any_activation',
      'request_targeted_repair_for_any_blocker',
      'prepare_separate_activation_patch_later_after_explicit_approval'
    ],
    explicit_non_actions: [
      'activation_not_performed',
      'notification_not_sent',
      'race_predictions_not_generated',
      'fantasy_picks_not_generated',
      'canonical_workbook_not_written',
      'production_forecast_bundle_ledger_not_written',
      'stable_engine_not_modified',
      'model_not_promoted',
      'live_fetch_not_performed'
    ],
    final_guardrails: {
      production_automation: 'OFF',
      forecast_gate: 'OFF',
      promotion_allowed: false,
      stable_engine_modified: false,
      canonical_workbook_overwrite: false,
      activation_performed: false,
      notification_sent: false,
      race_predictions_refresh_performed: false,
      fantasy_refresh_performed: false,
      production_forecast_bundle_ledger_write_performed: false
    },
    blockers,
    next_step_candidate: 'post_v33_bridge_hardening_then_operator_activation_decision'
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const policy = readJsonMaybe(args.policy) || {};
  const namedPayloads = [
    { name: 'v33C_source_pull', payload: readJsonMaybe(args.source_pull_status) },
    { name: 'v33D_source_quality', payload: readJsonMaybe(args.source_quality_status) },
    { name: 'v33E_processor_execution', payload: readJsonMaybe(args.processor_status) },
    { name: 'v33F_workbook_reflection', payload: readJsonMaybe(args.workbook_reflection_status) },
    { name: 'v33G_ledger_snapshot', payload: readJsonMaybe(args.ledger_status) },
    { name: 'v33H_readiness_metadata', payload: readJsonMaybe(args.readiness_metadata_status) },
    { name: 'v33I_notification_rehearsal', payload: readJsonMaybe(args.notification_rehearsal_status) }
  ];
  const blockers = [];
  const warnings = [];

  if (!['dry_run', 'final_decision_packet'].includes(args.mode)) blockers.push(`unsupported_mode:${args.mode}`);
  if (policy.production_automation !== 'OFF') blockers.push('policy_production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') blockers.push('policy_forecast_gate_not_off');
  if (policy.promotion_allowed !== false) blockers.push('policy_promotion_allowed_not_false');
  if (policy.final_decision_packet_allowed !== true) blockers.push('policy_final_decision_packet_not_allowed');
  if (policy.activation_allowed !== false) blockers.push('policy_activation_allowed_not_false');
  if (policy.notification_send_allowed !== false) blockers.push('policy_notification_send_allowed_not_false');
  if (policy.race_predictions_refresh_allowed !== false) blockers.push('policy_race_predictions_refresh_allowed_not_false');
  if (policy.fantasy_refresh_allowed !== false) blockers.push('policy_fantasy_refresh_allowed_not_false');
  if (policy.live_fetch_allowed !== false) blockers.push('policy_live_fetch_allowed_not_false');

  blockers.push(...runtimeFalseFlagIssues(args, policy));
  for (const item of namedPayloads) {
    blockers.push(...payloadGovernanceIssues(item.name, item.payload));
  }

  if (args.execute && args.mode !== 'final_decision_packet') blockers.push('execute_true_requires_mode_final_decision_packet');
  if (args.execute && policy.operator_approval_required === true && args.operator_approval !== true) blockers.push('execute_true_requires_operator_approval');
  if (args.execute && args.allow_decision_packet_write !== true) blockers.push('execute_true_requires_allow_decision_packet_write');
  if (args.allow_activation || args.activate) blockers.push('activation_true_rejected_by_v33j');
  if (args.allow_notification_send) blockers.push('notification_send_true_rejected_by_v33j');
  if (args.allow_race_predictions_refresh) blockers.push('race_predictions_refresh_true_rejected_by_v33j');
  if (args.allow_fantasy_refresh) blockers.push('fantasy_refresh_true_rejected_by_v33j');
  if (args.allow_canonical_workbook_write) blockers.push('canonical_workbook_write_true_rejected_by_v33j');
  if (args.allow_production_ledger_write) blockers.push('production_ledger_write_true_rejected_by_v33j');
  if (args.model_promotion) blockers.push('model_promotion_true_rejected_by_v33j');
  if (args.live_fetch) blockers.push('live_fetch_true_rejected_by_v33j');

  const evidence = evaluateEvidence(policy, namedPayloads);
  for (const item of evidence) {
    if (!item.present && args.mode !== 'dry_run') blockers.push(`missing_required_evidence:${item.name}`);
    if (item.present && !item.ok) blockers.push(`evidence_not_ok:${item.name}`);
    if (item.present && !item.expected_status_matched) blockers.push(`unexpected_status:${item.name}:${item.actual_status || 'unknown'}`);
    if (item.blockers.length > 0) blockers.push(`upstream_blockers_present:${item.name}`);
  }
  if (!args.execute && args.mode === 'final_decision_packet') warnings.push('final_decision_packet_mode_without_execute_true');

  const uniqueBlockers = Array.from(new Set(blockers));
  const executePerformed = args.execute === true && uniqueBlockers.length === 0;
  let decisionPacket = null;
  let decisionPacketPath = null;
  if (executePerformed) {
    decisionPacket = buildDecisionPacket({ args, evidence, namedPayloads, blockers: uniqueBlockers });
    decisionPacketPath = path.join(args.artifact_dir, `final_activation_decision_packet_${timestampForPath()}.json`);
    writeJson(decisionPacketPath, decisionPacket);
  }

  const classification = decisionPacket?.decision_classification || (uniqueBlockers.length > 0 ? 'blocked' : 'ready_not_written');
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
    activation_performed: false,
    model_promotion_performed: false,
    final_activation_decision_packet_written: Boolean(decisionPacketPath),
    final_activation_decision_packet_path: decisionPacketPath,
    final_activation_decision_status: uniqueBlockers.length > 0
      ? 'FINAL_ACTIVATION_DECISION_PACKET_BLOCKED'
      : (executePerformed ? 'FINAL_ACTIVATION_DECISION_PACKET_READY_REVIEW_ONLY' : 'FINAL_ACTIVATION_DECISION_PACKET_READY_NOT_WRITTEN'),
    activation_decision_classification: classification,
    activation_decision_reason: uniqueBlockers.length > 0
      ? 'blocking_activation_decision_packet_issue'
      : (executePerformed ? 'sandbox_chain_ready_for_operator_review_no_activation_performed' : 'dry_run_or_awaiting_operator_execute'),
    evidence,
    blockers: uniqueBlockers,
    warnings: Array.from(new Set(warnings)),
    final_activation_decision_packet: decisionPacket,
    guardrails: {
      decision_packet_only: true,
      activation: false,
      notification_send: false,
      race_predictions_refresh: false,
      fantasy_predictions_refresh: false,
      canonical_workbook_write: false,
      production_forecast_bundle_ledger_write: false,
      model_promotion: false,
      live_fetch: false
    },
    consumer_gates: closedConsumerGates(),
    next_step: uniqueBlockers.length > 0
      ? 'resolve_v33j_final_decision_packet_blockers'
      : (executePerformed ? policy.next_allowed_layer : 'run_v33j_with_operator_approval')
  };

  writeJson(args.out, status);
  console.log(JSON.stringify({
    ok: status.ok,
    final_activation_decision_status: status.final_activation_decision_status,
    activation_decision_classification: status.activation_decision_classification,
    execute_performed: status.execute_performed,
    activation_performed: status.activation_performed,
    notification_sent: status.notification_sent,
    blocker_count: status.blockers.length,
    next_step: status.next_step
  }, null, 2));
  process.exit(status.ok ? 0 : 1);
}

main();
