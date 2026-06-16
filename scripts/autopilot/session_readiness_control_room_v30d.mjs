#!/usr/bin/env node
/*
 * F1 v30D Session Readiness Control Room dry-run.
 * Consolidates v30A/v30B/v30C readiness manifests into one summary.
 * Does not fetch data, mutate workbooks, promote models, or enable automation.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() { return new Date().toISOString(); }

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_readiness_control_room_policy_v30d.json',
    out: 'health/session_readiness_control_room_v30d_status.json',
    logDir: 'logs/session_readiness_control_room',
    v30a: 'health/session_source_readiness_last_status.json',
    v30b: 'health/session_source_readiness_v30b_last_status.json',
    v30c: 'health/source_crosscheck_v30c_status.json'
  };
  for (let i = 2; i < argv.length; i++) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i++; }
    else if (key === '--policy' && value) { args.policy = value; i++; }
    else if (key === '--out' && value) { args.out = value; i++; }
    else if (key === '--log-dir' && value) { args.logDir = value; i++; }
    else if (key === '--v30a' && value) { args.v30a = value; i++; }
    else if (key === '--v30b' && value) { args.v30b = value; i++; }
    else if (key === '--v30c' && value) { args.v30c = value; i++; }
  }
  return args;
}

function readJsonMaybe(filePath) {
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

function governanceValue(payload, keys) {
  for (const key of keys) {
    if (payload && Object.prototype.hasOwnProperty.call(payload, key)) return payload[key];
  }
  return undefined;
}

function checkGovernance(payload) {
  if (!payload) return { ok: true, issues: [] };
  const checks = [
    { label: 'production_automation', expected: 'OFF', keys: ['production_automation'] },
    { label: 'forecast_gate', expected: 'OFF', keys: ['forecast_gate'] },
    { label: 'promotion_allowed', expected: false, keys: ['promotion_allowed', 'promotion'] }
  ];
  const issues = [];
  for (const check of checks) {
    const actual = governanceValue(payload, check.keys);
    if (actual !== undefined && actual !== check.expected) {
      issues.push({ field: check.label, expected: check.expected, actual });
    }
  }
  const stableTouched = governanceValue(payload, ['stable_engine_modified']);
  if (stableTouched === true) issues.push({ field: 'stable_engine_modified', expected: false, actual: true });
  const workbookTouched = governanceValue(payload, ['canonical_workbook_overwrite']);
  if (workbookTouched === true) issues.push({ field: 'canonical_workbook_overwrite', expected: false, actual: true });
  return { ok: issues.length === 0, issues };
}

function summarizeInput(id, label, filePath, payload) {
  const governance = checkGovernance(payload);
  const present = Boolean(payload);
  return {
    id,
    label,
    path: filePath,
    present,
    ok: present ? governance.ok : false,
    status: present ? (payload.status || payload.overall_readiness || payload.readiness_quality || payload.schema_version || 'present') : 'missing',
    schema_version: payload?.schema_version || null,
    governance_issues: governance.issues
  };
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30D only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJsonMaybe(args.policy);
if (!policy) {
  console.error(JSON.stringify({ ok: false, error: 'missing_policy', policy: args.policy }, null, 2));
  process.exit(1);
}

const generatedUtc = nowIso();
const inputs = [
  summarizeInput('v30a_source_readiness', 'v30A source readiness foundation', args.v30a, readJsonMaybe(args.v30a)),
  summarizeInput('v30b_adapter_readiness', 'v30B OpenF1/FastF1 adapter readiness', args.v30b, readJsonMaybe(args.v30b)),
  summarizeInput('v30c_public_crosscheck', 'v30C public/FIA crosscheck readiness', args.v30c, readJsonMaybe(args.v30c))
];

const governanceBlocked = inputs.some(input => input.governance_issues.length > 0);
const presentCount = inputs.filter(input => input.present).length;
const overallReadiness = governanceBlocked ? 'blocked' : (presentCount === inputs.length ? 'ready' : 'partial');

const status = {
  ok: !governanceBlocked,
  schema_version: 'f1_session_readiness_control_room_status_v30d_2026-06-16',
  generated_utc: generatedUtc,
  mode: args.mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  policy_schema_version: policy.schema_version,
  overall_readiness: overallReadiness,
  present_inputs: presentCount,
  expected_inputs: inputs.length,
  inputs,
  material_change_detected: false,
  workbook_mutation_enabled: false,
  forecast_bundle_ledger_write_enabled: false,
  next_step: 'v30E_material_change_notification_or_v31_generated_status_conflict_hardening'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, 'v30d_run_' + stamp + '.json'), status);
console.log(JSON.stringify({ ok: status.ok, out: args.out, overall_readiness: status.overall_readiness, present_inputs: presentCount }, null, 2));
process.exit(status.ok ? 0 : 1);
