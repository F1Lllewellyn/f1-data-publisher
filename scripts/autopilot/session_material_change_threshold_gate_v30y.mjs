import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_POLICY = 'scripts/autopilot/session_material_change_threshold_gate_policy_v30y.json';
const DEFAULT_OUT = 'health/session_material_change_threshold_gate_v30y_status.json';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    policy: DEFAULT_POLICY,
    out: DEFAULT_OUT,
    log: '',
    current: '',
    previous: '',
    replay: '',
    source: '',
    mode: 'dry_run',
    execute: false,
    allowLive: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--policy' && value) {
      args.policy = value;
      i += 1;
    } else if (key === '--out' && value) {
      args.out = value;
      i += 1;
    } else if (key === '--log' && value) {
      args.log = value;
      i += 1;
    } else if (key === '--current' && value) {
      args.current = value;
      i += 1;
    } else if (key === '--previous' && value) {
      args.previous = value;
      i += 1;
    } else if (key === '--replay' && value) {
      args.replay = value;
      i += 1;
    } else if (key === '--source' && value) {
      args.source = value;
      i += 1;
    } else if (key === '--mode' && value) {
      args.mode = value;
      i += 1;
    } else if (key === '--execute' && value) {
      args.execute = value === 'true';
      i += 1;
    } else if (key === '--allow-live' && value) {
      args.allowLive = value === 'true';
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

function lower(value) {
  return String(value ?? '').toLowerCase();
}

function bool(value) {
  return value === true;
}

function num(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function pickStatus(payload) {
  if (!payload) return 'missing';
  return String(
    payload.status ||
    payload.readiness_status ||
    payload.replay_status ||
    payload.loop_readiness_status ||
    payload.pull_status ||
    payload.taxonomy_status ||
    payload.notification_decision ||
    payload.decision ||
    payload.validation_status ||
    'present'
  );
}

function readinessRank(status) {
  const value = lower(status);
  if (value.includes('blocked') || value.includes('failure') || value.includes('failed') || value.includes('error')) return 0;
  if (value.includes('degraded') || value.includes('partial') || value.includes('stale')) return 1;
  if (value.includes('contract') || value.includes('manifest') || value.includes('dry_run')) return 2;
  if (value.includes('ready') || value.includes('data_ready') || value.includes('refresh_ready')) return 3;
  if (value === 'present') return 2;
  return 1;
}

function gatherMetrics(payload) {
  const sourceCount = Array.isArray(payload?.sources) ? payload.sources.length : payload?.source_count;
  return {
    status: pickStatus(payload),
    readiness_quality: payload?.readiness_quality || payload?.quality || payload?.validation_quality || '',
    row_count: num(payload?.row_count ?? payload?.rows ?? payload?.record_count ?? payload?.result_count ?? payload?.source_row_count),
    source_count: num(sourceCount),
    blocking_count: num(payload?.blocking_source_count ?? payload?.blocking_failure_cases ?? payload?.blocking_failures ?? payload?.failed_cases),
    degraded_count: num(payload?.degraded_source_count ?? payload?.degraded_failures),
    data_ready_cases: num(payload?.data_ready_cases ?? payload?.data_ready_source_count),
    failed_cases: num(payload?.failed_cases),
    total_cases: num(payload?.total_cases),
    material_change: bool(payload?.material_change) || bool(payload?.should_notify),
    live_fetch_performed: bool(payload?.live_fetch_performed) || bool(payload?.live_fetch_enabled),
    forecast_gate: payload?.forecast_gate || 'OFF',
    production_automation: payload?.production_automation || 'OFF',
    promotion_allowed: payload?.promotion_allowed === true || payload?.promotion === true
  };
}

function buildCurrent(args) {
  const current = readJsonMaybe(args.current);
  if (current) return current;
  const replay = readJsonMaybe(args.replay);
  const source = readJsonMaybe(args.source);
  if (replay || source) {
    return {
      schema_version: 'composed_current_v30y_r2',
      generated_utc: nowIso(),
      status: pickStatus(replay || source),
      readiness_status: pickStatus(replay || source),
      row_count: num(source?.row_count ?? source?.rows),
      source_count: num(source?.source_count ?? source?.sources?.length),
      blocking_source_count: num(source?.blocking_source_count),
      failed_cases: num(replay?.failed_cases),
      total_cases: num(replay?.total_cases),
      data_ready_cases: num(replay?.data_ready_cases),
      replay_status: replay?.replay_status,
      pull_status: source?.pull_status,
      forecast_gate: 'OFF',
      production_automation: 'OFF',
      promotion_allowed: false
    };
  }
  return {
    schema_version: 'empty_current_v30y_r2',
    generated_utc: nowIso(),
    status: 'missing_current_snapshot',
    forecast_gate: 'OFF',
    production_automation: 'OFF',
    promotion_allowed: false
  };
}

function compare(current, previous, policy) {
  const c = gatherMetrics(current);
  const p = gatherMetrics(previous);
  const thresholds = policy.thresholds || {};
  const changes = [];

  if (!previous) {
    changes.push({
      type: 'initial_baseline',
      severity: 'info',
      material: false,
      detail: 'No previous snapshot supplied.'
    });
  }

  if (c.status !== p.status) {
    const delta = readinessRank(c.status) - readinessRank(p.status);
    changes.push({
      type: 'status_transition',
      from: p.status,
      to: c.status,
      severity: delta < 0 ? 'high' : 'medium',
      material: Math.abs(delta) >= (thresholds.min_readiness_rank_delta ?? 1)
    });
  }

  if (c.blocking_count !== p.blocking_count) {
    changes.push({
      type: 'blocking_source_count_change',
      from: p.blocking_count,
      to: c.blocking_count,
      severity: c.blocking_count > p.blocking_count ? 'critical' : 'high',
      material: true
    });
  }

  if (c.failed_cases !== p.failed_cases) {
    changes.push({
      type: 'failed_case_count_change',
      from: p.failed_cases,
      to: c.failed_cases,
      severity: c.failed_cases > p.failed_cases ? 'high' : 'medium',
      material: Math.abs(c.failed_cases - p.failed_cases) >= (thresholds.min_failed_case_delta ?? 1)
    });
  }

  if (c.row_count !== p.row_count) {
    const delta = c.row_count - p.row_count;
    changes.push({
      type: 'source_row_count_change',
      from: p.row_count,
      to: c.row_count,
      delta,
      severity: Math.abs(delta) >= (thresholds.material_row_delta ?? 10) ? 'medium' : 'low',
      material: Math.abs(delta) >= (thresholds.material_row_delta ?? 10)
    });
  }

  if (c.data_ready_cases !== p.data_ready_cases) {
    changes.push({
      type: 'data_ready_case_change',
      from: p.data_ready_cases,
      to: c.data_ready_cases,
      severity: 'medium',
      material: Math.abs(c.data_ready_cases - p.data_ready_cases) >= (thresholds.min_data_ready_case_delta ?? 1)
    });
  }

  if (c.live_fetch_performed) {
    changes.push({
      type: 'live_fetch_observed',
      severity: 'critical',
      material: true,
      detail: 'Live fetch evidence observed; notification sending remains disabled and manual review is required.'
    });
  }

  const governance = [];
  if (c.production_automation !== 'OFF') governance.push('production_automation_not_off');
  if (c.forecast_gate !== 'OFF') governance.push('forecast_gate_not_off');
  if (c.promotion_allowed) governance.push('promotion_allowed_true');
  if (governance.length) {
    changes.push({
      type: 'governance_issue',
      severity: 'critical',
      material: true,
      detail: governance.join(',')
    });
  }

  const materialChanges = changes.filter(change => change.material === true);
  const highestSeverity = materialChanges.some(change => change.severity === 'critical') ? 'critical'
    : materialChanges.some(change => change.severity === 'high') ? 'high'
    : materialChanges.some(change => change.severity === 'medium') ? 'medium'
    : materialChanges.length ? 'low'
    : 'none';

  return {
    current: c,
    previous: previous ? p : null,
    changes,
    material_changes: materialChanges,
    material_change_detected: materialChanges.length > 0,
    highest_severity: highestSeverity,
    governance_issues: governance
  };
}

function main() {
  const args = parseArgs(process.argv);
  const policy = readJsonMaybe(args.policy) || {};
  const current = buildCurrent(args);
  const previous = readJsonMaybe(args.previous);
  const comparison = compare(current, previous, policy);
  const shouldPreview = comparison.material_change_detected && policy.write_preview_artifact !== false;

  const status = {
    schema_version: 'f1_session_material_change_threshold_gate_v30y_r2_2026-06-16',
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
    threshold_gate_status: comparison.material_change_detected ? 'material_change_detected' : 'no_material_change',
    highest_severity: comparison.highest_severity,
    should_notify_preview: shouldPreview,
    governance_issues: comparison.governance_issues,
    current: comparison.current,
    previous: comparison.previous,
    changes: comparison.changes,
    material_changes: comparison.material_changes,
    consumer_gates: {
      workbook_write_enabled: false,
      canonical_workbook_write_enabled: false,
      forecast_bundle_write_enabled: false,
      race_predictions_refresh_enabled: false,
      fantasy_refresh_enabled: false,
      notification_send_enabled: false,
      production_automation_enabled: false
    },
    next_step: comparison.material_change_detected
      ? 'v30z_control_room_operator_dashboard_packet_after_review'
      : 'continue_monitoring_no_notification'
  };

  writeJson(args.out, status);
  if (args.log) {
    writeJson(args.log, {
      ok: true,
      generated_utc: status.generated_utc,
      out: args.out,
      threshold_gate_status: status.threshold_gate_status,
      should_notify_preview: status.should_notify_preview
    });
  }

  console.log(JSON.stringify({
    ok: true,
    out: args.out,
    threshold_gate_status: status.threshold_gate_status,
    should_notify_preview: status.should_notify_preview,
    material_change_count: status.material_changes.length
  }, null, 2));
}

main();
