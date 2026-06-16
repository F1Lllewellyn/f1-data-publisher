#!/usr/bin/env node
/*
 * F1 v30T Race Predictions / Fantasy Readiness Refresh Gate Dry-Run.
 *
 * Reads Forecast Bundle Ledger readiness and determines whether Race
 * Predictions and Fantasy refresh would be allowed. It never performs those
 * refreshes, never writes prediction outputs, never mutates the canonical
 * workbook, never activates forecast gate, and never promotes model logic.
 */
import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/race_predictions_fantasy_readiness_gate_policy_v30t.json';
const DEFAULT_OUT = 'health/race_predictions_fantasy_readiness_gate_v30t_status.json';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    logDir: '',
    event: 'unknown_event',
    session: 'unknown_session',
    controlRoomLedgerWiring: '',
    ledgerStatus: '',
    ledgerSnapshot: '',
    mode: 'dry_run'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log-dir' && value) { args.logDir = value; i += 1; }
    else if (key === '--event' && value) { args.event = value; i += 1; }
    else if (key === '--session' && value) { args.session = value; i += 1; }
    else if (key === '--control-room-ledger-wiring' && value) { args.controlRoomLedgerWiring = value; i += 1; }
    else if (key === '--ledger-status' && value) { args.ledgerStatus = value; i += 1; }
    else if (key === '--ledger-snapshot' && value) { args.ledgerSnapshot = value; i += 1; }
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
  if (policy.race_predictions_refresh_enabled !== false) issues.push('race_predictions_refresh_not_disabled');
  if (policy.fantasy_refresh_enabled !== false) issues.push('fantasy_refresh_not_disabled');
  return issues;
}

function resolveLedgerSnapshotPath(args, wiring, ledgerStatus) {
  if (args.ledgerSnapshot) return args.ledgerSnapshot;
  if (ledgerStatus?.ledger_path) return ledgerStatus.ledger_path;
  if (wiring?.ledger_writer?.ledger_path) return wiring.ledger_writer.ledger_path;
  return '';
}

function deriveGate(policy, wiring, ledgerStatus, ledgerSnapshot, governanceIssues) {
  if (governanceIssues.length > 0) {
    return {
      readiness_status: 'blocked',
      reason: 'governance_issue',
      race_predictions_refresh_allowed: false,
      fantasy_refresh_allowed: false
    };
  }

  if (!wiring && !ledgerStatus && !ledgerSnapshot) {
    return {
      readiness_status: 'not_ready',
      reason: 'missing_forecast_bundle_ledger_evidence',
      race_predictions_refresh_allowed: false,
      fantasy_refresh_allowed: false
    };
  }

  if (wiring && wiring.ok === false) {
    return {
      readiness_status: 'blocked',
      reason: 'control_room_ledger_wiring_not_ok',
      race_predictions_refresh_allowed: false,
      fantasy_refresh_allowed: false
    };
  }

  if (ledgerStatus && ledgerStatus.ok === false) {
    return {
      readiness_status: 'blocked',
      reason: 'forecast_bundle_ledger_status_not_ok',
      race_predictions_refresh_allowed: false,
      fantasy_refresh_allowed: false
    };
  }

  const decisionStatus = ledgerSnapshot?.decision_status || ledgerStatus?.decision_status || wiring?.ledger_writer?.decision_status || '';
  if (decisionStatus === 'blocked') {
    return {
      readiness_status: 'blocked',
      reason: 'forecast_bundle_ledger_blocked',
      race_predictions_refresh_allowed: false,
      fantasy_refresh_allowed: false
    };
  }

  if (decisionStatus === 'snapshot_written') {
    return {
      readiness_status: 'refresh_ready_dry_run',
      reason: 'forecast_bundle_ledger_snapshot_available',
      race_predictions_refresh_allowed: false,
      fantasy_refresh_allowed: false
    };
  }

  if (decisionStatus === 'contract_ready') {
    return {
      readiness_status: 'contract_ready_no_refresh',
      reason: 'ledger_contract_ready_without_upstream_artifacts',
      race_predictions_refresh_allowed: false,
      fantasy_refresh_allowed: false
    };
  }

  return {
    readiness_status: 'not_ready',
    reason: 'unrecognized_or_missing_ledger_decision',
    race_predictions_refresh_allowed: false,
    fantasy_refresh_allowed: false
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const wiring = readJsonMaybe(args.controlRoomLedgerWiring);
  const ledgerStatus = readJsonMaybe(args.ledgerStatus) || (wiring?.ledger_writer?.status_path ? readJsonMaybe(wiring.ledger_writer.status_path) : null);
  const ledgerSnapshotPath = resolveLedgerSnapshotPath(args, wiring, ledgerStatus);
  const ledgerSnapshot = readJsonMaybe(ledgerSnapshotPath);
  const issues = policyIssues(policy);
  const gate = deriveGate(policy, wiring, ledgerStatus, ledgerSnapshot, issues);
  const generatedUtc = nowIso();
  const stamp = generatedUtc.replaceAll(':', '').replaceAll('-', '').replaceAll('.', '');

  const status = {
    schema_version: 'f1_race_predictions_fantasy_readiness_gate_v30t_2026-06-16',
    generated_utc: generatedUtc,
    ok: issues.length === 0 && gate.readiness_status !== 'blocked',
    mode: args.mode,
    event: args.event,
    session: args.session,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    readiness_status: gate.readiness_status,
    readiness_reason: gate.reason,
    race_predictions_refresh_allowed: false,
    fantasy_refresh_allowed: false,
    race_predictions_refresh_executed: false,
    fantasy_refresh_executed: false,
    governance_issues: issues,
    inputs: {
      control_room_ledger_wiring_path: args.controlRoomLedgerWiring || '',
      control_room_ledger_wiring_present: Boolean(wiring),
      ledger_status_path: args.ledgerStatus || wiring?.ledger_writer?.status_path || '',
      ledger_status_present: Boolean(ledgerStatus),
      ledger_snapshot_path: ledgerSnapshotPath,
      ledger_snapshot_present: Boolean(ledgerSnapshot),
      ledger_decision_status: ledgerSnapshot?.decision_status || ledgerStatus?.decision_status || wiring?.ledger_writer?.decision_status || null,
      ledger_hash: ledgerSnapshot?.ledger_hash || ledgerStatus?.ledger_hash || wiring?.ledger_writer?.ledger_hash || null
    },
    consumer_gates: {
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      forecast_bundle_publish_enabled: false,
      canonical_workbook_write_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: 'v30U_session_processor_loop_readiness_orchestrator_after_review'
  };

  writeJson(args.out, status);
  if (args.logDir) {
    writeJson(path.join(args.logDir, `v30t_run_${stamp}.json`), status);
  }

  console.log(JSON.stringify({
    ok: status.ok,
    readiness_status: status.readiness_status,
    readiness_reason: status.readiness_reason,
    race_predictions_refresh_allowed: status.race_predictions_refresh_allowed,
    fantasy_refresh_allowed: status.fantasy_refresh_allowed,
    next_step: status.next_step
  }, null, 2));
}

main();
