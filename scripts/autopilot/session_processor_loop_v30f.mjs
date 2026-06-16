#!/usr/bin/env node
/*
 * F1 v30F Session Processor Loop dry-run orchestrator.
 * Wires the dry-run pieces together:
 * session gate event -> v30D readiness summary -> v30E material-change candidate.
 *
 * This script does not fetch live data, mutate workbooks, send notifications,
 * open forecast gates, enable production automation, or promote models.
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_processor_loop_policy_v30f.json',
    event: '',
    out: 'health/session_processor_loop_v30f_status.json',
    logDir: 'logs/session_processor_loop',
    readinessOut: 'health/session_readiness_control_room_v30d_status.json',
    materialOut: 'health/session_material_change_v30e_status.json',
    previousReadiness: 'health/session_readiness_control_room_v30d_previous_status.json',
    runReadiness: true,
    runMaterialChange: true
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--event' && value) { args.event = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log-dir' && value) { args.logDir = value; i += 1; }
    else if (key === '--readiness-out' && value) { args.readinessOut = value; i += 1; }
    else if (key === '--material-out' && value) { args.materialOut = value; i += 1; }
    else if (key === '--previous-readiness' && value) { args.previousReadiness = value; i += 1; }
    else if (key === '--run-readiness' && value) { args.runReadiness = value !== 'false'; i += 1; }
    else if (key === '--run-material-change' && value) { args.runMaterialChange = value !== 'false'; i += 1; }
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

function runNodeStep(label, args) {
  const result = spawnSync(process.execPath, args, { encoding: 'utf8' });
  return {
    label,
    command: ['node', ...args],
    exit_code: result.status,
    ok: result.status === 0,
    stdout: (result.stdout || '').trim(),
    stderr: (result.stderr || '').trim()
  };
}

function classifyGate(event) {
  if (!event) {
    return {
      gate_detected: false,
      reason: 'missing_event',
      session_id: null,
      event_type: null
    };
  }

  const eventType = event.event_type || event.type || event.kind || null;
  const sessionStatus = event.session_status || event.status || null;
  const explicitGate = event.gate_detected === true || event.session_end_detected === true;
  const terminalEvent = ['session_end', 'session_complete', 'session_completed', 'race_session_complete'].includes(String(eventType || '').toLowerCase());
  const terminalStatus = ['ended', 'complete', 'completed', 'final'].includes(String(sessionStatus || '').toLowerCase());
  const gateDetected = explicitGate || terminalEvent || terminalStatus;

  return {
    gate_detected: gateDetected,
    reason: gateDetected ? 'session_end_signal_detected' : 'no_session_end_signal',
    session_id: event.session_id || event.session || event.event || null,
    event_type: eventType
  };
}

function governanceIssues(payload) {
  const issues = [];
  if (!payload) return issues;
  if (payload.production_automation && payload.production_automation !== 'OFF') issues.push({ field: 'production_automation', actual: payload.production_automation, expected: 'OFF' });
  if (payload.forecast_gate && payload.forecast_gate !== 'OFF') issues.push({ field: 'forecast_gate', actual: payload.forecast_gate, expected: 'OFF' });
  if (payload.promotion_allowed !== undefined && payload.promotion_allowed !== false) issues.push({ field: 'promotion_allowed', actual: payload.promotion_allowed, expected: false });
  if (payload.stable_engine_modified === true) issues.push({ field: 'stable_engine_modified', actual: true, expected: false });
  if (payload.canonical_workbook_overwrite === true) issues.push({ field: 'canonical_workbook_overwrite', actual: true, expected: false });
  return issues;
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30F only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJsonMaybe(args.policy);
if (!policy) {
  console.error(JSON.stringify({ ok: false, error: 'missing_policy', policy: args.policy }, null, 2));
  process.exit(1);
}

const event = readJsonMaybe(args.event);
const gate = classifyGate(event);
const generatedUtc = nowIso();
const steps = [];

if (gate.gate_detected && args.runReadiness) {
  steps.push(runNodeStep('v30d_session_readiness_control_room', [
    'scripts/autopilot/session_readiness_control_room_v30d.mjs',
    '--mode', 'dry_run',
    '--out', args.readinessOut,
    '--log-dir', 'logs/session_readiness_control_room'
  ]));
}

if (gate.gate_detected && args.runMaterialChange) {
  steps.push(runNodeStep('v30e_material_change_notifier', [
    'scripts/autopilot/session_material_change_notifier_v30e.mjs',
    '--mode', 'dry_run',
    '--current', args.readinessOut,
    '--previous', args.previousReadiness,
    '--out', args.materialOut,
    '--log-dir', 'logs/session_material_change_notifier'
  ]));
}

const readiness = readJsonMaybe(args.readinessOut);
const material = readJsonMaybe(args.materialOut);
const previousReadiness = readJsonMaybe(args.previousReadiness);
const readinessGovernanceIssues = governanceIssues(readiness);
const materialGovernanceIssues = governanceIssues(material);
const stepFailures = steps.filter(step => !step.ok);
const blocked = !gate.gate_detected || stepFailures.length > 0 || readinessGovernanceIssues.length > 0 || materialGovernanceIssues.length > 0;
const initialBaseline = !previousReadiness;
const rawCandidate = material?.notification_candidate || null;
const effectiveShouldNotify = Boolean(rawCandidate?.should_notify) && !initialBaseline;

const status = {
  ok: !blocked,
  schema_version: 'f1_session_processor_loop_status_v30f_2026-06-16',
  generated_utc: generatedUtc,
  mode: args.mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  policy_schema_version: policy.schema_version,
  gate,
  steps,
  readiness_snapshot_path: args.readinessOut,
  material_change_snapshot_path: args.materialOut,
  previous_readiness_snapshot_path: args.previousReadiness,
  readiness_present: Boolean(readiness),
  material_change_present: Boolean(material),
  previous_readiness_present: Boolean(previousReadiness),
  initial_baseline: initialBaseline,
  readiness_governance_issues: readinessGovernanceIssues,
  material_governance_issues: materialGovernanceIssues,
  raw_notification_candidate: rawCandidate,
  effective_notification_candidate: {
    should_notify: effectiveShouldNotify,
    reason: effectiveShouldNotify ? 'material_change_after_baseline' : (initialBaseline ? 'initial_baseline_suppressed' : rawCandidate?.reason || 'no_candidate'),
    source: 'v30f_dry_run'
  },
  next_step: 'v30G_processor_source_fetch_contract_after_review'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, 'v30f_run_' + stamp + '.json'), status);
console.log(JSON.stringify({
  ok: status.ok,
  out: args.out,
  gate_detected: gate.gate_detected,
  readiness_present: status.readiness_present,
  material_change_present: status.material_change_present,
  effective_should_notify: effectiveShouldNotify
}, null, 2));
process.exit(status.ok ? 0 : 1);
