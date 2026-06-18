import fs from 'node:fs';
import path from 'node:path';

const VERSION = 'v33C';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_end_to_end_rehearsal_evidence_review_policy_v33c.json';
const DEFAULT_OUT = 'health/session_processor_end_to_end_rehearsal_evidence_review_v33c_status.json';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    status: '',
    out: DEFAULT_OUT,
    mode: 'review',
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

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function upper(value) {
  return String(value || '').toUpperCase();
}

function bool(value) {
  return value === true;
}

function allStagesPass(stages) {
  return Array.isArray(stages) && stages.length > 0 && stages.every((stage) => upper(stage.status) === 'PASS');
}

function governanceIssues(name, payload) {
  const issues = [];
  if (!payload) return issues;
  const side = payload.side_effects || {};
  const gates = payload.consumer_gates || {};
  const governance = payload.governance || {};

  for (const key of [
    'network_fetch',
    'production_automation',
    'workbook_write',
    'ledger_write',
    'race_predictions_refresh',
    'fantasy_predictions_refresh',
    'notification_send',
    'model_promotion',
    'protected_path_touch'
  ]) {
    if (bool(side[key])) issues.push(`${name}:side_effect_${key}_true`);
  }

  for (const [gate, enabled] of Object.entries(gates)) {
    if (enabled === true) issues.push(`${name}:consumer_gate_open:${gate}`);
  }

  if (governance.stable_engine_protected !== true) issues.push(`${name}:stable_engine_not_protected`);
  if (governance.no_accuracy_claim !== true) issues.push(`${name}:accuracy_claim_guard_missing`);
  if (governance.no_automation_change !== true) issues.push(`${name}:automation_change_guard_missing`);
  if (governance.pr_only !== true) issues.push(`${name}:pr_only_guard_missing`);

  return issues;
}

function validateV33B(status, policy) {
  const blockers = [];
  if (!status) return ['missing_v33b_rehearsal_status'];

  if (status.version !== policy.required_v33b_version) blockers.push(`version_mismatch:${status.version || 'missing'}`);
  if (upper(status.status) !== policy.required_status) blockers.push(`status_mismatch:${status.status || 'missing'}`);
  if (!policy.allowed_modes.includes(status.mode)) blockers.push(`mode_not_allowed:${status.mode || 'missing'}`);
  if (Array.isArray(status.blockers) && status.blockers.length > 0) blockers.push('v33b_blockers_present');
  if (status.output_write_permitted !== true) blockers.push('v33b_output_write_not_permitted');
  if (!Array.isArray(status.planned_writes) || status.planned_writes.length < 1) blockers.push('v33b_planned_writes_missing');
  if (!allStagesPass(status.stages)) blockers.push('v33b_stage_contract_not_all_pass');

  blockers.push(...governanceIssues('v33b', status));

  return blockers;
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const status = readJsonMaybe(args.status);
  const blockers = [];

  for (const flag of policy.required_false_flags || []) {
    if (args[flag] !== false) blockers.push(`safety_flag_${flag}_must_remain_false`);
  }

  if (args.mode !== 'review' && args.mode !== 'dry_run') blockers.push(`unsupported_mode:${args.mode}`);
  if (args.execute) blockers.push('execute_true_rejected');
  if (args.activate) blockers.push('activate_true_rejected');

  blockers.push(...validateV33B(status, policy));

  const uniqueBlockers = Array.from(new Set(blockers));
  const ok = uniqueBlockers.length === 0;
  const output = {
    schema_version: 'f1_session_processor_end_to_end_rehearsal_evidence_review_v33c_2026-06-17',
    generated_utc: nowIso(),
    version: VERSION,
    status: ok ? 'READY' : 'BLOCKED',
    mode: args.mode,
    v33b_status: status?.status || null,
    v33b_version: status?.version || null,
    v33b_mode: status?.mode || null,
    v33b_stage_count: Array.isArray(status?.stages) ? status.stages.length : 0,
    v33b_planned_writes: Array.isArray(status?.planned_writes) ? status.planned_writes : [],
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
      production_automation_enabled: false
    },
    governance: {
      stable_engine_protected: true,
      no_accuracy_claim: true,
      no_automation_change: true,
      pr_only: true,
      promotion_allowed: false
    },
    next_step: ok ? 'v33D_operator_decision_packet_or_v34_session_processor_loop_preflight_after_review' : 'resolve_v33c_blockers_before_next_layer'
  };

  writeJson(args.out, output);
  console.log(JSON.stringify({
    ok,
    out: args.out,
    status: output.status,
    blocker_count: uniqueBlockers.length,
    next_step: output.next_step
  }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
