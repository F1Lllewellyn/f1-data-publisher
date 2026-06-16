#!/usr/bin/env node
/*
 * F1 v30S Control Room Forecast Bundle Ledger Wiring Dry-Run.
 *
 * Wires the Control Room readiness chain to the v30R Forecast Bundle Ledger
 * snapshot writer. This script may execute the v30R writer in dry-run mode,
 * then records the wiring result. It does not publish forecast bundles, refresh
 * Race Predictions/Fantasy outputs, mutate the canonical workbook, activate the
 * forecast gate, send notifications, or promote model logic.
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const DEFAULT_POLICY = 'scripts/autopilot/session_control_room_forecast_bundle_ledger_wiring_policy_v30s.json';
const DEFAULT_LEDGER_WRITER = 'scripts/autopilot/forecast_bundle_ledger_snapshot_writer_v30r.mjs';
const DEFAULT_LEDGER_POLICY = 'scripts/autopilot/forecast_bundle_ledger_snapshot_policy_v30r.json';
const DEFAULT_OUT = 'health/session_control_room_forecast_bundle_ledger_wiring_v30s_status.json';
const DEFAULT_LEDGER_STATUS_OUT = 'health/forecast_bundle_ledger_snapshot_v30r_status.json';
const DEFAULT_LEDGER_DIR = 'artifacts/forecast_bundle_ledger/v30s';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    ledgerWriter: DEFAULT_LEDGER_WRITER,
    ledgerPolicy: DEFAULT_LEDGER_POLICY,
    out: DEFAULT_OUT,
    ledgerStatusOut: DEFAULT_LEDGER_STATUS_OUT,
    ledgerDir: DEFAULT_LEDGER_DIR,
    logDir: '',
    event: 'unknown_event',
    session: 'unknown_session',
    controlRoom: '',
    sourceSummary: '',
    workbookReflection: '',
    materialChange: '',
    taxonomy: '',
    executeLedgerWriter: true,
    mode: 'dry_run'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--ledger-writer' && value) { args.ledgerWriter = value; i += 1; }
    else if (key === '--ledger-policy' && value) { args.ledgerPolicy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--ledger-status-out' && value) { args.ledgerStatusOut = value; i += 1; }
    else if (key === '--ledger-dir' && value) { args.ledgerDir = value; i += 1; }
    else if (key === '--log-dir' && value) { args.logDir = value; i += 1; }
    else if (key === '--event' && value) { args.event = value; i += 1; }
    else if (key === '--session' && value) { args.session = value; i += 1; }
    else if (key === '--control-room' && value) { args.controlRoom = value; i += 1; }
    else if (key === '--source-summary' && value) { args.sourceSummary = value; i += 1; }
    else if (key === '--workbook-reflection' && value) { args.workbookReflection = value; i += 1; }
    else if (key === '--material-change' && value) { args.materialChange = value; i += 1; }
    else if (key === '--taxonomy' && value) { args.taxonomy = value; i += 1; }
    else if (key === '--execute-ledger-writer' && value) { args.executeLedgerWriter = value === 'true'; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
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

function policyIssues(policy) {
  const issues = [];
  if (policy.production_automation !== 'OFF') issues.push('production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') issues.push('forecast_gate_not_off');
  if (policy.promotion_allowed !== false) issues.push('promotion_allowed_not_false');
  if (policy.stable_engine_protected !== true) issues.push('stable_engine_not_protected');
  if (policy.canonical_workbook_protected !== true) issues.push('canonical_workbook_not_protected');
  if (policy.ledger_wiring_mode !== 'dry_run_control_room_handoff') issues.push('ledger_wiring_mode_not_dry_run_control_room_handoff');
  return issues;
}

function artifactState(label, filePath) {
  const payload = readJsonMaybe(filePath);
  return {
    label,
    path: filePath || '',
    present: Boolean(payload),
    schema_version: payload?.schema_version || null,
    status: payload?.status || payload?.readiness_status || payload?.taxonomy_status || payload?.decision_status || null,
    ok: payload?.ok ?? null
  };
}

function buildLedgerWriterArgs(args) {
  const command = [
    args.ledgerWriter,
    '--policy', args.ledgerPolicy,
    '--out', args.ledgerStatusOut,
    '--ledger-dir', args.ledgerDir,
    '--event', args.event,
    '--session', args.session,
    '--mode', args.mode
  ];

  if (args.controlRoom) command.push('--control-room', args.controlRoom);
  if (args.sourceSummary) command.push('--source-summary', args.sourceSummary);
  if (args.workbookReflection) command.push('--workbook-reflection', args.workbookReflection);
  if (args.materialChange) command.push('--material-change', args.materialChange);
  if (args.taxonomy) command.push('--taxonomy', args.taxonomy);
  if (args.logDir) command.push('--log-dir', args.logDir);

  return command;
}

function runLedgerWriter(args) {
  if (!args.executeLedgerWriter) {
    return { executed: false, ok: true, reason: 'execution_disabled_by_argument', stdout: '', stderr: '', exit_code: null };
  }
  if (!fs.existsSync(args.ledgerWriter)) {
    return { executed: false, ok: false, reason: 'missing_ledger_writer_script', stdout: '', stderr: '', exit_code: null };
  }

  const command = buildLedgerWriterArgs(args);
  const result = spawnSync(process.execPath, command, { encoding: 'utf8' });
  return {
    executed: true,
    ok: result.status === 0,
    reason: result.status === 0 ? 'ledger_writer_completed' : 'ledger_writer_failed',
    exit_code: result.status,
    stdout: String(result.stdout || '').slice(0, 4000),
    stderr: String(result.stderr || '').slice(0, 4000),
    command: ['node', ...command]
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const issues = policyIssues(policy);
  const ledgerRun = issues.length === 0
    ? runLedgerWriter(args)
    : { executed: false, ok: false, reason: 'blocked_by_governance_policy', stdout: '', stderr: '', exit_code: null };
  const ledgerStatus = readJsonMaybe(args.ledgerStatusOut);
  const generatedUtc = nowIso();
  const stamp = generatedUtc.replaceAll(':', '').replaceAll('-', '').replaceAll('.', '');

  const upstreamArtifacts = [
    artifactState('control_room', args.controlRoom),
    artifactState('source_summary', args.sourceSummary),
    artifactState('workbook_reflection', args.workbookReflection),
    artifactState('material_change', args.materialChange),
    artifactState('taxonomy', args.taxonomy),
    artifactState('forecast_bundle_ledger_status', args.ledgerStatusOut)
  ];

  const ok = issues.length === 0 && ledgerRun.ok === true && (!ledgerStatus || ledgerStatus.ok !== false);
  const status = {
    schema_version: 'f1_session_control_room_forecast_bundle_ledger_wiring_v30s_2026-06-16',
    generated_utc: generatedUtc,
    ok,
    mode: args.mode,
    event: args.event,
    session: args.session,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    forecast_bundle_publish_enabled: false,
    race_predictions_refresh_enabled: false,
    fantasy_refresh_enabled: false,
    notification_send_enabled: false,
    governance_issues: issues,
    ledger_writer: {
      script: args.ledgerWriter,
      executed: ledgerRun.executed,
      ok: ledgerRun.ok,
      reason: ledgerRun.reason,
      exit_code: ledgerRun.exit_code,
      status_path: args.ledgerStatusOut,
      ledger_path: ledgerStatus?.ledger_path || null,
      ledger_hash: ledgerStatus?.ledger_hash || null,
      decision_status: ledgerStatus?.decision_status || null,
      decision_reason: ledgerStatus?.decision_reason || null
    },
    upstream_artifacts: upstreamArtifacts,
    consumer_gates: {
      canonical_workbook_write_enabled: false,
      forecast_bundle_publish_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: 'v30T_race_predictions_fantasy_readiness_refresh_gate_dry_run_after_review'
  };

  writeJson(args.out, status);
  if (args.logDir) {
    writeJson(path.join(args.logDir, `v30s_run_${stamp}.json`), status);
  }

  console.log(JSON.stringify({
    ok: status.ok,
    ledger_writer_executed: status.ledger_writer.executed,
    ledger_decision_status: status.ledger_writer.decision_status,
    next_step: status.next_step
  }, null, 2));
}

main();
