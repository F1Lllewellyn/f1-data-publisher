#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const VERSION = 'v33E';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_operator_decision_packet_policy_v33e.json';
const DEFAULT_V33C_STATUS = 'health/session_processor_end_to_end_rehearsal_evidence_review_v33c_status.json';
const DEFAULT_OUT = 'health/session_processor_operator_decision_packet_v33e_status.json';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    v33c_status: DEFAULT_V33C_STATUS,
    out: DEFAULT_OUT,
    packet_out: '',
    mode: 'operator_decision',
    execute: false,
    activate: false,
    allow_live: false,
    production_automation: false,
    workbook_write: false,
    ledger_write: false,
    race_predictions_refresh: false,
    fantasy_predictions_refresh: false,
    notification_send: false,
    model_promotion: false
  };

  const aliases = new Map([
    ['v33c-status', 'v33c_status'],
    ['packet-out', 'packet_out'],
    ['allow-live', 'allow_live'],
    ['production-automation', 'production_automation'],
    ['workbook-write', 'workbook_write'],
    ['ledger-write', 'ledger_write'],
    ['race-predictions-refresh', 'race_predictions_refresh'],
    ['fantasy-predictions-refresh', 'fantasy_predictions_refresh'],
    ['notification-send', 'notification_send'],
    ['model-promotion', 'model_promotion']
  ]);

  const booleans = new Set([
    'execute',
    'activate',
    'allow_live',
    'production_automation',
    'workbook_write',
    'ledger_write',
    'race_predictions_refresh',
    'fantasy_predictions_refresh',
    'notification_send',
    'model_promotion'
  ]);

  for (let i = 2; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith('--')) continue;
    const raw = item.slice(2);
    const key = aliases.get(raw) || raw.replaceAll('-', '_');
    if (!(key in args)) throw new Error(`Unknown argument: --${raw}`);
    const next = argv[i + 1];
    if (booleans.has(key)) {
      if (next === 'true' || next === 'false') {
        args[key] = next === 'true';
        i += 1;
      } else {
        args[key] = true;
      }
    } else {
      if (!next || next.startsWith('--')) throw new Error(`Missing value for --${raw}`);
      args[key] = next;
      i += 1;
    }
  }

  return args;
}

function readJsonMaybe(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeText(filePath, body) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, body, 'utf8');
}

function writeJson(filePath, payload) {
  writeText(filePath, `${JSON.stringify(payload, null, 2)}\n`);
}

function bool(value) {
  return value === true;
}

function upper(value) {
  return String(value || '').toUpperCase();
}

function hasOpenConsumerGate(payload) {
  return Object.entries(payload?.consumer_gates || {}).filter(([, enabled]) => enabled === true);
}

function sideEffectIssues(name, payload) {
  const issues = [];
  const side = payload?.side_effects || {};
  for (const key of [
    'execute_performed',
    'activation_performed',
    'live_fetch_performed',
    'production_automation',
    'workbook_write',
    'ledger_write',
    'race_predictions_refresh',
    'fantasy_predictions_refresh',
    'notification_send',
    'model_promotion',
    'stable_engine_modified',
    'canonical_workbook_overwrite'
  ]) {
    if (bool(side[key])) issues.push(`${name}:side_effect_${key}_true`);
  }
  return issues;
}

function governanceIssues(name, payload) {
  const issues = [];
  const governance = payload?.governance || {};
  if (governance.stable_engine_protected !== true) issues.push(`${name}:stable_engine_not_protected`);
  if (governance.no_accuracy_claim !== true) issues.push(`${name}:accuracy_claim_guard_missing`);
  if (governance.no_automation_change !== true) issues.push(`${name}:automation_change_guard_missing`);
  if (governance.pr_only !== true) issues.push(`${name}:pr_only_guard_missing`);
  if (governance.promotion_allowed !== false) issues.push(`${name}:promotion_allowed_not_false`);
  return issues;
}

function validateV33C(status, policy) {
  const blockers = [];
  if (!status) return ['missing_v33c_status'];

  if (status.version !== policy.required_v33c_version) {
    blockers.push(`v33c_version_mismatch:${status.version || 'missing'}`);
  }
  if (upper(status.status) !== policy.required_v33c_status) {
    blockers.push(`v33c_status_mismatch:${status.status || 'missing'}`);
  }
  if (!policy.allowed_v33c_modes.includes(status.mode)) {
    blockers.push(`v33c_mode_not_allowed:${status.mode || 'missing'}`);
  }
  if (Array.isArray(status.blockers) && status.blockers.length > 0) {
    blockers.push('v33c_blockers_present');
  }
  if (!Array.isArray(status.v33b_planned_writes) || status.v33b_planned_writes.length < 1) {
    blockers.push('v33c_v33b_planned_writes_missing');
  }
  if (!String(status.next_step || '').includes('v34_session_processor_loop_preflight')) {
    blockers.push('v33c_next_step_does_not_reference_v34_preflight');
  }

  for (const [gate] of hasOpenConsumerGate(status)) {
    blockers.push(`v33c_consumer_gate_open:${gate}`);
  }

  blockers.push(...sideEffectIssues('v33c', status));
  blockers.push(...governanceIssues('v33c', status));
  return blockers;
}

function renderPacket(output) {
  const blockers = output.blockers.length
    ? output.blockers.map((item) => `- ${item}`).join('\n')
    : '- None';

  const evidence = output.evidence.map((item) => (
    `- ${item.name}: ${item.status}`
  )).join('\n');

  return `# v33E Operator Decision Packet

Generated UTC: ${output.generated_utc}

Status: ${output.status}
Decision quality: ${output.decision_quality}
Next step: ${output.next_step}

## Evidence

${evidence}

## Blockers

${blockers}

## Closed gates confirmed

- Production automation: OFF
- Live fetch: OFF
- Workbook write: OFF
- Canonical workbook overwrite: OFF
- Forecast Bundle Ledger production write: OFF
- Race Predictions refresh: OFF
- Fantasy refresh: OFF
- Notification send: OFF
- Model promotion: OFF
- Stable engine modification: OFF

## Operator note

This packet authorizes only review of the next preflight layer. It does not authorize activation, live data fetch, workbook write, ledger write, Race/Fantasy refresh, notification send, or model promotion.
`;
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const v33cStatus = readJsonMaybe(args.v33c_status);
  const blockers = [];

  for (const flag of policy.required_false_flags || []) {
    if (args[flag] !== false) blockers.push(`safety_flag_${flag}_must_remain_false`);
  }
  if (!policy.allowed_modes.includes(args.mode)) blockers.push(`unsupported_mode:${args.mode}`);
  if (args.execute) blockers.push('execute_true_rejected');
  if (args.activate) blockers.push('activate_true_rejected');

  blockers.push(...validateV33C(v33cStatus, policy));

  const uniqueBlockers = Array.from(new Set(blockers));
  const ready = uniqueBlockers.length === 0;
  const output = {
    schema_version: 'f1_session_processor_operator_decision_packet_v33e_2026-06-17',
    generated_utc: nowIso(),
    version: VERSION,
    status: ready ? 'READY_FOR_V34_PREFLIGHT_OPERATOR_REVIEW' : 'BLOCKED',
    mode: args.mode,
    decision_quality: ready
      ? 'v33c_evidence_review_verified_all_downstream_gates_closed'
      : 'v33c_evidence_review_requires_repair_before_v34_preflight',
    evidence: [
      {
        name: 'v33c_end_to_end_rehearsal_evidence_review',
        status: v33cStatus ? `${v33cStatus.version || 'missing'}:${v33cStatus.status || 'missing'}` : 'missing'
      }
    ],
    blockers: uniqueBlockers,
    side_effects: {
      execute_performed: false,
      activation_performed: false,
      live_fetch_performed: false,
      production_automation: false,
      workbook_write: false,
      ledger_write: false,
      race_predictions_refresh: false,
      fantasy_predictions_refresh: false,
      notification_send: false,
      model_promotion: false,
      stable_engine_modified: false,
      canonical_workbook_overwrite: false
    },
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false,
      live_source_pull_enabled: false
    },
    governance: {
      stable_engine_protected: true,
      no_accuracy_claim: true,
      no_automation_change: true,
      pr_only: true,
      promotion_allowed: false
    },
    next_step: ready
      ? 'v34_session_processor_loop_preflight_pr_only'
      : 'resolve_v33e_operator_decision_packet_blockers_before_v34'
  };

  writeJson(args.out, output);
  if (args.packet_out) writeText(args.packet_out, renderPacket(output));
  console.log(JSON.stringify({
    ok: ready,
    out: args.out,
    packet_out: args.packet_out || null,
    status: output.status,
    blocker_count: uniqueBlockers.length,
    next_step: output.next_step
  }, null, 2));
  process.exit(ready ? 0 : 1);
}

main();
