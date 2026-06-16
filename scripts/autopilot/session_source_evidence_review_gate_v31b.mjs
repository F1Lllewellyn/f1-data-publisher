import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_source_evidence_review_gate_policy_v31b.json';
const DEFAULT_OUT = 'health/session_source_evidence_review_gate_v31b_status.json';
const DEFAULT_LOG = '';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: DEFAULT_LOG,
    sourceEvidence: '',
    dashboard: '',
    protocol: '',
    mode: 'dry_run',
    allowLive: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--source-evidence' && value) { args.sourceEvidence = value; i += 1; }
    else if (key === '--dashboard' && value) { args.dashboard = value; i += 1; }
    else if (key === '--protocol' && value) { args.protocol = value; i += 1; }
    else if (key === '--mode' && value) { args.mode = value; i += 1; }
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
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

function text(value) {
  return String(value ?? '').toLowerCase();
}

function bool(value) {
  return value === true;
}

function num(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function consumerGateIssues(payload) {
  const gates = payload?.consumer_gates || {};
  const expectedClosed = {
    workbook_write_enabled: false,
    canonical_workbook_write_enabled: false,
    forecast_bundle_write_enabled: false,
    race_predictions_refresh_enabled: false,
    fantasy_refresh_enabled: false,
    notification_send_enabled: false,
    production_automation_enabled: false
  };
  const issues = [];
  for (const [key, expected] of Object.entries(expectedClosed)) {
    if (gates[key] !== undefined && gates[key] !== expected) issues.push(`${key}_not_closed`);
  }
  if (payload?.workbook_write_enabled === true) issues.push('workbook_write_enabled_true');
  if (payload?.prediction_refresh_enabled === true) issues.push('prediction_refresh_enabled_true');
  if (payload?.fantasy_refresh_enabled === true) issues.push('fantasy_refresh_enabled_true');
  if (payload?.notification_sending_enabled === true) issues.push('notification_sending_enabled_true');
  return Array.from(new Set(issues));
}

function governanceIssues(policy, payload, args) {
  const issues = [];
  if ((payload?.production_automation || policy.production_automation) !== 'OFF') issues.push('production_automation_not_off');
  if ((payload?.forecast_gate || policy.forecast_gate) !== 'OFF') issues.push('forecast_gate_not_off');
  if ((payload?.promotion_allowed ?? policy.promotion_allowed) !== false) issues.push('promotion_allowed_not_false');
  if (payload?.stable_engine_modified === true) issues.push('stable_engine_modified_true');
  if (payload?.canonical_workbook_overwrite === true) issues.push('canonical_workbook_overwrite_true');
  if (args.allowLive) issues.push('allow_live_cli_not_supported_for_review_gate');
  if (bool(payload?.live_fetch_performed)) {
    if (payload?.mode !== 'sandbox_live') issues.push('live_fetch_evidence_not_sandbox_live');
    if (payload?.live_fetch_allowed_by_policy !== true) issues.push('live_fetch_missing_policy_allowance');
    if (payload?.production_automation !== 'OFF') issues.push('live_fetch_with_production_automation_not_off');
    if (payload?.forecast_gate !== 'OFF') issues.push('live_fetch_with_forecast_gate_not_off');
    if (payload?.promotion_allowed !== false) issues.push('live_fetch_with_promotion_allowed');
  }
  return Array.from(new Set([...issues, ...consumerGateIssues(payload)]));
}

function summarizeSources(payload) {
  const rows = Array.isArray(payload?.results) ? payload.results : [];
  return rows.map((row) => ({
    source_id: row.source_id || 'unknown_source',
    provider: row.provider || '',
    status: row.status || '',
    row_count: num(row.row_count),
    http_status: row.http_status ?? null,
    failures: Array.isArray(row.failures) ? row.failures : [],
    warnings: Array.isArray(row.warnings) ? row.warnings : [],
    cache_path_present: Boolean(row.cache_path)
  }));
}

function classifyEvidence(payload, issues) {
  if (!payload) {
    return {
      review_status: 'source_evidence_review_contract_ready',
      readiness_quality: 'no_source_evidence_supplied_contract_only',
      review_action: 'continue_contract_build_no_downstream_consumers',
      severity: 'none'
    };
  }

  const status = text(payload.pull_status || payload.status || payload.readiness_status);
  const failed = num(payload.failed_source_count);
  const degraded = num(payload.degraded_source_count);
  const ready = num(payload.ready_source_count);
  const rows = num(payload.row_count);

  if (issues.length > 0) {
    return {
      review_status: 'source_evidence_review_blocked',
      readiness_quality: 'governance_or_consumer_gate_issue',
      review_action: 'hold_downstream_consumers',
      severity: 'blocking'
    };
  }

  if (status.includes('blocked') || status.includes('failed') || status.includes('failure') || failed > 0) {
    return {
      review_status: 'source_evidence_review_blocked',
      readiness_quality: 'source_evidence_failure_detected',
      review_action: 'repair_source_evidence_before_downstream_consumers',
      severity: 'blocking'
    };
  }

  if (status.includes('degraded') || degraded > 0) {
    return {
      review_status: 'source_evidence_review_degraded',
      readiness_quality: 'source_evidence_degraded_manual_review_required',
      review_action: 'manual_review_or_fallback_before_activation',
      severity: 'degraded'
    };
  }

  if (status.includes('ready') && ready > 0 && rows > 0) {
    return {
      review_status: 'source_evidence_review_ready',
      readiness_quality: 'sandbox_live_source_evidence_review_ready',
      review_action: 'eligible_for_next_dry_run_layer_after_review',
      severity: 'none'
    };
  }

  if (status.includes('contract') || status.includes('dry_run')) {
    return {
      review_status: 'source_evidence_review_contract_ready',
      readiness_quality: 'dry_run_contract_ready_no_live_evidence',
      review_action: 'continue_contract_build_no_downstream_consumers',
      severity: 'none'
    };
  }

  return {
    review_status: 'source_evidence_review_degraded',
    readiness_quality: 'source_evidence_present_but_not_ready',
    review_action: 'manual_review_before_downstream_consumers',
    severity: 'degraded'
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const evidence = readJsonMaybe(args.sourceEvidence);
  const dashboard = readJsonMaybe(args.dashboard);
  const protocol = readJsonMaybe(args.protocol);
  const issues = governanceIssues(policy, evidence || {}, args);
  const classification = classifyEvidence(evidence, issues);

  const status = {
    schema_version: 'f1_session_source_evidence_review_gate_v31b_2026-06-16',
    generated_utc: nowIso(),
    mode: args.mode,
    source_evidence_supplied: Boolean(evidence),
    dashboard_supplied: Boolean(dashboard),
    protocol_supplied: Boolean(protocol),
    live_fetch_performed: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    ...classification,
    governance_issues: issues,
    source_evidence: evidence ? {
      schema_version: evidence.schema_version || '',
      mode: evidence.mode || '',
      event: evidence.event || '',
      session: evidence.session || '',
      pull_status: evidence.pull_status || evidence.status || '',
      readiness_quality: evidence.readiness_quality || '',
      live_fetch_performed: bool(evidence.live_fetch_performed),
      source_count: num(evidence.source_count),
      ready_source_count: num(evidence.ready_source_count),
      degraded_source_count: num(evidence.degraded_source_count),
      failed_source_count: num(evidence.failed_source_count),
      row_count: num(evidence.row_count),
      sources: summarizeSources(evidence)
    } : null,
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: classification.review_status === 'source_evidence_review_ready'
      ? 'v31c_downstream_consumer_contract_wiring_dry_run_after_review'
      : 'continue_source_evidence_review_or_repair_before_consumers'
  };

  writeJson(args.out, status);
  if (args.log) writeJson(args.log, { ok: status.review_status !== 'source_evidence_review_blocked', generated_utc: status.generated_utc, out: args.out, review_status: status.review_status });

  const ok = status.review_status !== 'source_evidence_review_blocked';
  console.log(JSON.stringify({ ok, out: args.out, review_status: status.review_status, readiness_quality: status.readiness_quality }, null, 2));
  process.exit(ok ? 0 : 1);
}

main();
