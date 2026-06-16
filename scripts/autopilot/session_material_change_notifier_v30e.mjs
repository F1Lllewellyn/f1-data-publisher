#!/usr/bin/env node
/*
 * F1 v30E Session Material Change Notifier dry-run.
 * Compares current Control Room readiness with an optional previous snapshot.
 * Emits notification candidates only; it does not send email/chat, mutate workbooks,
 * enable production automation, open forecast gates, or promote models.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_material_change_policy_v30e.json',
    current: 'health/session_readiness_control_room_v30d_status.json',
    previous: 'health/session_readiness_control_room_v30d_previous_status.json',
    out: 'health/session_material_change_v30e_status.json',
    logDir: 'logs/session_material_change_notifier'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--current' && value) { args.current = value; i += 1; }
    else if (key === '--previous' && value) { args.previous = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log-dir' && value) { args.logDir = value; i += 1; }
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

function inputMap(snapshot) {
  const rows = Array.isArray(snapshot?.inputs) ? snapshot.inputs : [];
  return new Map(rows.map(row => [row.id || row.label || row.path, row]));
}

function stableIssues(issues) {
  if (!Array.isArray(issues)) return [];
  return issues.map(issue => JSON.stringify(issue)).sort();
}

function compareScalar(changes, field, previousValue, currentValue) {
  if (JSON.stringify(previousValue) !== JSON.stringify(currentValue)) {
    changes.push({ field, previous: previousValue ?? null, current: currentValue ?? null });
  }
}

function compareInputs(previous, current) {
  const changes = [];
  const prevMap = inputMap(previous);
  const currMap = inputMap(current);
  const ids = Array.from(new Set([...prevMap.keys(), ...currMap.keys()])).sort();

  for (const id of ids) {
    const prev = prevMap.get(id) || null;
    const curr = currMap.get(id) || null;
    compareScalar(changes, `inputs.${id}.present`, prev?.present, curr?.present);
    compareScalar(changes, `inputs.${id}.ok`, prev?.ok, curr?.ok);
    compareScalar(changes, `inputs.${id}.status`, prev?.status, curr?.status);
    compareScalar(changes, `inputs.${id}.governance_issues`, stableIssues(prev?.governance_issues), stableIssues(curr?.governance_issues));
  }
  return changes;
}

function governanceIssues(snapshot) {
  const issues = [];
  if (!snapshot) return issues;
  if (snapshot.production_automation && snapshot.production_automation !== 'OFF') issues.push({ field: 'production_automation', actual: snapshot.production_automation, expected: 'OFF' });
  if (snapshot.forecast_gate && snapshot.forecast_gate !== 'OFF') issues.push({ field: 'forecast_gate', actual: snapshot.forecast_gate, expected: 'OFF' });
  if (snapshot.promotion_allowed !== undefined && snapshot.promotion_allowed !== false) issues.push({ field: 'promotion_allowed', actual: snapshot.promotion_allowed, expected: false });
  if (snapshot.stable_engine_modified === true) issues.push({ field: 'stable_engine_modified', actual: true, expected: false });
  if (snapshot.canonical_workbook_overwrite === true) issues.push({ field: 'canonical_workbook_overwrite', actual: true, expected: false });
  return issues;
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30E only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJsonMaybe(args.policy);
if (!policy) {
  console.error(JSON.stringify({ ok: false, error: 'missing_policy', policy: args.policy }, null, 2));
  process.exit(1);
}

const current = readJsonMaybe(args.current);
const previous = readJsonMaybe(args.previous);
const currentGovernanceIssues = governanceIssues(current);
const generatedUtc = nowIso();
const changes = [];

compareScalar(changes, 'snapshot_present', Boolean(previous), Boolean(current));
compareScalar(changes, 'ok', previous?.ok, current?.ok);
compareScalar(changes, 'overall_readiness', previous?.overall_readiness, current?.overall_readiness);
compareScalar(changes, 'present_inputs', previous?.present_inputs, current?.present_inputs);
compareScalar(changes, 'expected_inputs', previous?.expected_inputs, current?.expected_inputs);
changes.push(...compareInputs(previous, current));

const materialChanges = changes.filter(change => change.field !== 'snapshot_present' || change.current === false);
const materialChangeDetected = materialChanges.length > 0;
const blocked = !current || currentGovernanceIssues.length > 0;

const notificationCandidate = materialChangeDetected && !blocked ? {
  should_notify: true,
  channel: 'candidate_only',
  reason: 'session_readiness_material_change',
  title: 'F1 session readiness changed',
  summary: `${materialChanges.length} material readiness field(s) changed.`,
  changes: materialChanges
} : {
  should_notify: false,
  channel: 'candidate_only',
  reason: blocked ? 'blocked_or_missing_current_snapshot' : 'no_material_change',
  changes: materialChanges
};

const status = {
  ok: !blocked,
  schema_version: 'f1_session_material_change_status_v30e_2026-06-16',
  generated_utc: generatedUtc,
  mode: args.mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  policy_schema_version: policy.schema_version,
  current_snapshot_path: args.current,
  previous_snapshot_path: args.previous,
  current_snapshot_present: Boolean(current),
  previous_snapshot_present: Boolean(previous),
  material_change_detected: materialChangeDetected,
  material_change_count: materialChanges.length,
  governance_issues: currentGovernanceIssues,
  notification_candidate: notificationCandidate,
  next_step: 'v30F_watcher_processor_integration_dry_run_after_review'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, 'v30e_run_' + stamp + '.json'), status);
console.log(JSON.stringify({
  ok: status.ok,
  out: args.out,
  material_change_detected: materialChangeDetected,
  material_change_count: materialChanges.length,
  should_notify: notificationCandidate.should_notify
}, null, 2));
process.exit(status.ok ? 0 : 1);
