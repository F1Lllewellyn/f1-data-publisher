import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/control_room_operator_dashboard_packet_policy_v30z.json';
const DEFAULT_OUT = 'health/control_room_operator_dashboard_packet_v30z_status.json';
const DEFAULT_PACKET = 'logs/autopilot_bridge/control_room_operator_dashboard_packet_v30z.md';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    packet: DEFAULT_PACKET,
    log: '',
    watcher: '',
    source: '',
    replay: '',
    threshold: '',
    forecast: '',
    mode: 'dry_run',
    execute: false,
    allowLive: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--out' && value) { args.out = value; i += 1; }
    else if (key === '--packet' && value) { args.packet = value; i += 1; }
    else if (key === '--log' && value) { args.log = value; i += 1; }
    else if (key === '--watcher' && value) { args.watcher = value; i += 1; }
    else if (key === '--source' && value) { args.source = value; i += 1; }
    else if (key === '--replay' && value) { args.replay = value; i += 1; }
    else if (key === '--threshold' && value) { args.threshold = value; i += 1; }
    else if (key === '--forecast' && value) { args.forecast = value; i += 1; }
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

function writeText(filePath, text) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, text, 'utf8');
}

function writeJson(filePath, payload) {
  writeText(filePath, JSON.stringify(payload, null, 2) + '\n');
}

function lower(value) {
  return String(value ?? '').toLowerCase();
}

function bool(value) {
  return value === true;
}

function pickStatus(payload) {
  if (!payload) return 'missing';
  return String(
    payload.status ??
    payload.readiness_status ??
    payload.loop_readiness_status ??
    payload.pull_status ??
    payload.replay_status ??
    payload.threshold_gate_status ??
    payload.forecast_bundle_status ??
    payload.decision ??
    'present'
  );
}

function rankStatus(status) {
  const value = lower(status);
  if (value.includes('blocked') || value.includes('failure') || value.includes('failed') || value.includes('error')) return 0;
  if (value.includes('degraded') || value.includes('partial') || value.includes('stale') || value.includes('missing')) return 1;
  if (value.includes('contract') || value.includes('dry_run') || value.includes('preview') || value.includes('present')) return 2;
  if (value.includes('ready') || value.includes('passed') || value.includes('detected')) return 3;
  return 1;
}

function collectIssues(sectionName, payload, policy) {
  const issues = [];
  if (!payload) {
    issues.push({ section: sectionName, severity: 'info', code: 'snapshot_missing', detail: 'No upstream snapshot was supplied.' });
    return issues;
  }
  const status = lower(pickStatus(payload));
  if (status.includes('blocked') || status.includes('failure') || status.includes('failed') || status.includes('error')) {
    issues.push({ section: sectionName, severity: 'blocking', code: 'blocking_status', detail: pickStatus(payload) });
  }
  const failures = Array.isArray(payload.failures) ? payload.failures : [];
  for (const failure of failures) {
    issues.push({ section: sectionName, severity: 'blocking', code: String(failure), detail: 'Upstream failure reported.' });
  }
  if (bool(payload.live_fetch_performed) || bool(payload.live_fetch_enabled) || bool(payload.allow_live)) {
    issues.push({ section: sectionName, severity: 'blocking', code: 'live_fetch_observed', detail: 'Live fetch evidence is not allowed in this dry-run dashboard.' });
  }
  if (payload.forecast_gate && payload.forecast_gate !== 'OFF') {
    issues.push({ section: sectionName, severity: 'blocking', code: 'forecast_gate_not_off', detail: String(payload.forecast_gate) });
  }
  if (payload.production_automation && payload.production_automation !== 'OFF') {
    issues.push({ section: sectionName, severity: 'blocking', code: 'production_automation_not_off', detail: String(payload.production_automation) });
  }
  if (payload.promotion_allowed === true || payload.promotion === true) {
    issues.push({ section: sectionName, severity: 'blocking', code: 'promotion_allowed_true', detail: 'Promotion flag must remain false.' });
  }
  if (policy.require_consumer_gates_closed !== false) {
    const gates = payload.consumer_gates || {};
    for (const [key, value] of Object.entries(gates)) {
      if (value === true) {
        issues.push({ section: sectionName, severity: 'blocking', code: `consumer_gate_open:${key}`, detail: 'Consumer gate must remain closed.' });
      }
    }
  }
  return issues;
}

function section(name, payload) {
  const status = pickStatus(payload);
  return {
    name,
    supplied: Boolean(payload),
    status,
    rank: rankStatus(status),
    generated_utc: payload?.generated_utc ?? null,
    schema_version: payload?.schema_version ?? null,
    material_change: bool(payload?.material_change_detected) || bool(payload?.should_notify_preview),
    row_count: Number(payload?.row_count ?? payload?.rows ?? payload?.source_row_count ?? 0),
    source_count: Number(payload?.source_count ?? payload?.sources?.length ?? 0),
    failed_cases: Number(payload?.failed_cases ?? 0),
    total_cases: Number(payload?.total_cases ?? 0)
  };
}

function deriveDecision(sections, issues, args) {
  const blocking = issues.filter((issue) => issue.severity === 'blocking');
  if (args.execute || args.allowLive) {
    blocking.push({ section: 'governance', severity: 'blocking', code: 'execution_or_live_requested', detail: 'v30Z supports dry-run operator packet only.' });
  }
  if (blocking.length > 0) {
    return {
      dashboard_status: 'operator_blocked',
      readiness_quality: 'blocking_issue',
      recommended_action: 'hold_downstream_consumers_and_review_blockers',
      blocking
    };
  }
  const suppliedCount = sections.filter((item) => item.supplied).length;
  const materialChange = sections.some((item) => item.material_change);
  if (suppliedCount === 0) {
    return {
      dashboard_status: 'operator_packet_contract_ready',
      readiness_quality: 'no_upstream_snapshots_supplied',
      recommended_action: 'wire_latest_v30v_to_v30y_snapshots_for_operator_review',
      blocking: []
    };
  }
  return {
    dashboard_status: materialChange ? 'operator_review_material_change' : 'operator_review_ready',
    readiness_quality: materialChange ? 'material_change_preview_ready' : 'dry_run_dashboard_ready',
    recommended_action: materialChange ? 'operator_review_before_any_notification_or_refresh' : 'continue_monitoring_no_consumer_activation',
    blocking: []
  };
}

function renderPacket(status) {
  const lines = [];
  lines.push('# V30Z Control Room Operator Dashboard Packet');
  lines.push('');
  lines.push(`Generated UTC: ${status.generated_utc}`);
  lines.push(`Dashboard status: ${status.dashboard_status}`);
  lines.push(`Readiness quality: ${status.readiness_quality}`);
  lines.push(`Recommended action: ${status.recommended_action}`);
  lines.push('');
  lines.push('## Governance');
  lines.push(`- Production automation: ${status.production_automation}`);
  lines.push(`- Forecast gate: ${status.forecast_gate}`);
  lines.push(`- Promotion allowed: ${status.promotion_allowed}`);
  lines.push(`- Stable engine modified: ${status.stable_engine_modified}`);
  lines.push(`- Canonical workbook overwrite: ${status.canonical_workbook_overwrite}`);
  lines.push(`- Live fetch performed: ${status.live_fetch_performed}`);
  lines.push(`- Notification sent: ${status.notification_sent}`);
  lines.push('');
  lines.push('## Sections');
  for (const item of status.sections) {
    lines.push(`- ${item.name}: ${item.status} (supplied=${item.supplied})`);
  }
  lines.push('');
  lines.push('## Blocking Issues');
  if (status.blocking_issues.length === 0) {
    lines.push('- None.');
  } else {
    for (const issue of status.blocking_issues) {
      lines.push(`- ${issue.section}: ${issue.code} - ${issue.detail}`);
    }
  }
  lines.push('');
  lines.push('## Consumer Gates');
  for (const [key, value] of Object.entries(status.consumer_gates)) {
    lines.push(`- ${key}: ${value}`);
  }
  lines.push('');
  return lines.join('\n');
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const watcher = readJsonMaybe(args.watcher);
  const source = readJsonMaybe(args.source);
  const replay = readJsonMaybe(args.replay);
  const threshold = readJsonMaybe(args.threshold);
  const forecast = readJsonMaybe(args.forecast);
  const payloads = { watcher, source, replay, threshold, forecast };
  const sections = Object.entries(payloads).map(([name, payload]) => section(name, payload));
  const issues = Object.entries(payloads).flatMap(([name, payload]) => collectIssues(name, payload, policy));
  const decision = deriveDecision(sections, issues, args);
  const status = {
    schema_version: 'f1_control_room_operator_dashboard_packet_v30z_2026-06-16',
    generated_utc: nowIso(),
    mode: args.mode,
    execute_requested: args.execute,
    execute_performed: false,
    live_fetch_performed: false,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    notification_sending_enabled: false,
    notification_sent: false,
    dashboard_status: decision.dashboard_status,
    readiness_quality: decision.readiness_quality,
    recommended_action: decision.recommended_action,
    sections,
    blocking_issues: decision.blocking,
    all_issues: issues,
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: decision.dashboard_status === 'operator_blocked'
      ? 'repair_blockers_before_v31_activation_design'
      : 'v31_activation_protocol_design_after_operator_review'
  };
  writeJson(args.out, status);
  writeText(args.packet, renderPacket(status));
  if (args.log) writeJson(args.log, { ok: decision.dashboard_status !== 'operator_blocked', generated_utc: status.generated_utc, out: args.out, packet: args.packet, dashboard_status: status.dashboard_status });
  console.log(JSON.stringify({ ok: decision.dashboard_status !== 'operator_blocked', out: args.out, packet: args.packet, dashboard_status: status.dashboard_status, readiness_quality: status.readiness_quality }, null, 2));
  process.exit(decision.dashboard_status === 'operator_blocked' ? 1 : 0);
}

main();
