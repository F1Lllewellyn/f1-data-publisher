#!/usr/bin/env node
/*
* F1 v30P Session Control Room Orchestrator Dry-Run
 *
 * Purpose:
 *   Consolidate the v30F-v30O Session Data Processor Loop layers into one
 *   machine-readable orchestration summary without mutating workbook, forecast,
 *   stable-engine, prediction, fantasy, or notification paths.
 *
 * Default behavior is dry-run/read-only. It inspects the expected scripts and
 * generated artifacts, then emits a readiness plan. It does not fetch network
 * data and does not execute downstream modules unless a later promoted command
 * explicitly extends this script.
 */
import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_control_room_orchestrator_policy_v30p.json';
const DEFAULT_OUT = 'health/session_control_room_orchestrator_v30p_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    event: '',
    mode: 'dry_run',
    execute: false,
    allowLive: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--event' && value) { args.event = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--execute' && value) { args.execute = value === 'true'; i += 1; }
    else if (key === '--allow-live' && value) { args.allowLive = value === 'true'; i += 1; }
  }
  return args;
}

function readJsonMaybe(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\\n', 'utf8');
}

function bool(value) {
  return value === true;
}

function classifyArtifact(payload) {
  if (!payload) return { present: false, status: 'missing', quality: 'missing' };
  const status = payload.status || payload.validation_status || payload.readiness_status || payload.overall_readiness || payload.decision || 'present';
  const quality = payload.readiness_quality || payload.quality || payload.validation_quality || payload.cache_status || payload.notification_decision || status;
  return { present: true, status, quality };
}

function gateEvent(event) {
  if (!event) {
    return {
      gate_detected: false,
      gate_type: 'none',
      event_id: 'none',
      event_name: 'none',
      session_key: 'unknown'
    };
  }
  const eventName = event.event_name || event.type || event.gate_type || 'unknown_event';
  const sessionKey = event.session_key || event.session || event.session_name || 'unknown_session';
  const isSessionEnd = String(eventName).toLowerCase().includes('session_end') || String(event.gate_type || '').toLowerCase().includes('session_end');
  return {
    gate_detected: isSessionEnd,
    gate_type: isSessionEnd ? 'session_end' : 'non_session_gate',
    event_id: event.event_id || event.id || 'unknown_event_id',
    event_name: eventName,
    session_key: sessionKey
  };
}

function summarizeScripts(requiredScripts) {
  return requiredScripts.map((scriptPath) => ({
    path: scriptPath,
    present: fs.existsSync(scriptPath),
    role: path.basename(scriptPath).replace(/\\.mjs$/, '')
  }));
}

function summarizeArtifacts(contracts) {
  return Object.entries(contracts).map(([artifactId, artifactPath]) => {
    const payload = readJsonMaybe(artifactPath);
    const classification = classifyArtifact(payload);
    return {
      artifact_id: artifactId,
      path: artifactPath,
      ...classification
    };
  });
}

function deriveReadiness({ scripts, artifacts, gate, policy, args }) {
  const missingScripts = scripts.filter((s) => !s.present).map((s) => s.path);
  const presentArtifacts = artifacts.filter((a) => a.present);
  const dataReadyArtifacts = artifacts.filter((a) => String(a.status).includes('data_ready') || String(a.quality).includes('data_ready'));
  const materialPreviewArtifacts = artifacts.filter((a) => String(a.artifact_id).includes('notifier') && a.present);

  const governanceIssues = [];
  if (policy.production_automation !== 'OFF') governanceIssues.push('production_automation_not_off');
  if (policy.forecast_gate !== 'OFF') governanceIssues.push('forecast_gate_not_off');
  if (policy.promotion_allowed !== false) governanceIssues.push('promotion_allowed_not_false');
  if (policy.stable_engine_protected !== true) governanceIssues.push('stable_engine_not_protected');
  if (policy.canonical_workbook_protected !== true) governanceIssues.push('canonical_workbook_not_protected');
  if (args.allowLive && args.mode !== 'sandbox_live') governanceIssues.push('allow_live_true_without_sandbox_live_mode');

  let orchestrator_status = 'blocked';
  let readiness_quality = 'missing_required_scripts';
  if (governanceIssues.length > 0) {
    orchestrator_status = 'blocked';
    readiness_quality = 'governance_issue';
  } else if (missingScripts.length > 0) {
    orchestrator_status = 'partial';
    readiness_quality = 'missing_required_scripts';
  } else if (!gate.gate_detected) {
    orchestrator_status = 'standby';
    readiness_quality = 'no_session_end_gate';
  } else if (presentArtifacts.length === 0) {
    orchestrator_status = 'contract_ready';
    readiness_quality = 'scripts_ready_artifacts_not_yet_generated';
  } else if (dataReadyArtifacts.length > 0) {
    orchestrator_status = 'data_ready_dry_run';
    readiness_quality = 'source_cache_or_validation_data_ready';
  } else {
    orchestrator_status = 'contract_ready';
    readiness_quality = 'artifacts_present_but_data_not_ready';
  }

  return {
    orchestrator_status,
    readiness_quality,
    missing_required_scripts: missingScripts,
    present_artifact_count: presentArtifacts.length,
    data_ready_artifact_count: dataReadyArtifacts.length,
    material_preview_artifact_count: materialPreviewArtifacts.length,
    governance_issues: governanceIssues,
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      model_promotion_enabled: false,
      production_automation_enabled: false
    }
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const event = readJsonMaybe(args.event);
  const gate = gateEvent(event);
  const requiredScripts = Array.isArray(policy.required_scripts) ? policy.required_scripts : [];
  const contracts = policy.status_artifact_contracts && typeof policy.status_artifact_contracts === 'object' ? policy.status_artifact_contracts : {};
  const scripts = summarizeScripts(requiredScripts);
  const artifacts = summarizeArtifacts(contracts);
  const readiness = deriveReadiness({ scripts, artifacts, gate, policy, args });

  const status = {
    schema_version: 'f1_session_control_room_orchestrator_v30p_2026-06-16',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    live_fetch_enabled: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    gate,
    scripts,
    artifacts,
    ...readiness,
    next_step: 'v30Q_live_source_hardening_or_real_session_replay_validation_before_any_activation'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: true, generated_utc: status.generated_utc, out: args.out, orchestrator_status: status.orchestrator_status });

  console.log(JSON.stringify({
    ok: true,
    out: args.out,
    orchestrator_status: status.orchestrator_status,
    readiness_quality: status.readiness_quality,
    missing_required_scripts: status.missing_required_scripts.length,
    present_artifact_count: status.present_artifact_count
  }, null, 2));
}

main();
