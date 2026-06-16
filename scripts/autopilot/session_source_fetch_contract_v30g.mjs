#!/usr/bin/env node
/*
 * F1 v30G Session Source Fetch Contract dry-run.
 *
 * Defines the source plan required after a session-end gate is detected.
 * This script does not fetch live data, mutate workbooks, send notifications,
 * open forecast gates, enable production automation, or promote models.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: 'scripts/autopilot/session_source_fetch_policy_v30g.json',
    event: '',
    out: 'health/session_source_fetch_contract_v30g_status.json',
    logDir: 'logs/session_source_fetch_contract'
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--mode' && value) { args.mode = value; i += 1; }
    else if (key === '--policy' && value) { args.policy = value; i += 1; }
    else if (key === '--event' && value) { args.event = value; i += 1; }
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

function classifySession(event) {
  const eventType = String(event?.event_type || event?.type || '').toLowerCase();
  const sessionType = String(event?.session_type || event?.session || '').toLowerCase();
  const status = String(event?.session_status || event?.status || '').toLowerCase();
  const explicitGate = event?.gate_detected === true || event?.session_end_detected === true;
  const terminalEvent = ['session_end', 'session_complete', 'session_completed', 'race_session_complete'].includes(eventType);
  const terminalStatus = ['ended', 'complete', 'completed', 'final'].includes(status);

  return {
    gate_detected: explicitGate || terminalEvent || terminalStatus,
    event_type: eventType || null,
    session_type: sessionType || null,
    session_id: event?.session_id || event?.session_key || event?.session || null,
    meeting_key: event?.meeting_key || event?.meeting || null,
    round: event?.round || null,
    year: event?.year || 2026
  };
}

function sourcePlan(session, policy) {
  const liveFetchEnabled = false;
  const base = {
    fetch_mode: 'contract_only',
    live_fetch_enabled: liveFetchEnabled,
    cache_write_allowed: true,
    workbook_write_allowed: false,
    stable_engine_write_allowed: false
  };

  return [
    {
      ...base,
      source_id: 'openf1_session_data',
      source_family: 'openf1',
      role: 'primary_public_api',
      required_for: [
        'session_metadata',
        'driver_list',
        'stints',
        'laps',
        'intervals',
        'position',
        'race_control_messages',
        'weather'
      ],
      minimum_fields: [
        'meeting_key',
        'session_key',
        'driver_number',
        'date',
        'lap_number',
        'position',
        'compound',
        'tyre_age',
        'duration'
      ],
      validation_checks: [
        'session_key_matches_gate_event',
        'driver_count_reasonable',
        'lap_count_nonzero_when_session_complete',
        'timestamps_monotonic_or_explainable',
        'weather_timestamp_coverage'
      ],
      blocking_if_missing: true
    },
    {
      ...base,
      source_id: 'fastf1_session_cache',
      source_family: 'fastf1',
      role: 'secondary_timing_cache',
      required_for: [
        'lap_time_crosscheck',
        'sector_time_crosscheck',
        'tyre_stint_crosscheck',
        'telemetry_availability_manifest'
      ],
      minimum_fields: [
        'driver',
        'lap_number',
        'lap_time',
        'sector_1_time',
        'sector_2_time',
        'sector_3_time',
        'compound',
        'stint'
      ],
      validation_checks: [
        'lap_count_matches_or_explains_openf1_delta',
        'driver_mapping_resolved',
        'sector_sum_consistency',
        'cache_age_recorded'
      ],
      blocking_if_missing: false
    },
    {
      ...base,
      source_id: 'fia_documents_index',
      source_family: 'fia_public_documents',
      role: 'official_classification_penalty_crosscheck',
      required_for: [
        'classification_validation',
        'penalty_validation',
        'stewards_decision_validation',
        'official_result_confirmation'
      ],
      minimum_fields: [
        'document_title',
        'published_utc',
        'document_type',
        'url_or_reference',
        'event_round'
      ],
      validation_checks: [
        'classification_document_present_when_available',
        'penalty_documents_indexed',
        'document_round_matches_event',
        'official_result_lag_recorded'
      ],
      blocking_if_missing: false
    },
    {
      ...base,
      source_id: 'formula1_official_event_context',
      source_family: 'formula1_public_site',
      role: 'public_context_and_schedule_crosscheck',
      required_for: [
        'event_schedule_context',
        'session_name_crosscheck',
        'public_quote_context',
        'weekend_context'
      ],
      minimum_fields: [
        'event_name',
        'session_name',
        'published_context',
        'source_timestamp'
      ],
      validation_checks: [
        'event_identity_matches_gate_event',
        'session_label_consistent',
        'context_timestamp_recorded'
      ],
      blocking_if_missing: false
    }
  ].map(item => ({
    ...item,
    requested_year: session.year,
    requested_meeting_key: session.meeting_key,
    requested_session_id: session.session_id,
    default_timeout_seconds: policy?.default_timeout_seconds || 30
  }));
}

const args = parseArgs(process.argv);
if (args.mode !== 'dry_run') {
  console.error(JSON.stringify({ ok: false, error: 'v30G only supports dry_run mode', mode: args.mode }, null, 2));
  process.exit(1);
}

const policy = readJsonMaybe(args.policy);
if (!policy) {
  console.error(JSON.stringify({ ok: false, error: 'missing_policy', policy: args.policy }, null, 2));
  process.exit(1);
}

const event = readJsonMaybe(args.event);
const session = classifySession(event);
const generatedUtc = nowIso();
const plan = session.gate_detected ? sourcePlan(session, policy) : [];
const blockingSources = plan.filter(source => source.blocking_if_missing).map(source => source.source_id);

const status = {
  ok: session.gate_detected,
  schema_version: 'f1_session_source_fetch_contract_status_v30g_2026-06-16',
  generated_utc: generatedUtc,
  mode: args.mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  live_fetch_enabled: false,
  workbook_write_allowed: false,
  notification_sending_enabled: false,
  policy_schema_version: policy.schema_version,
  session,
  source_plan: plan,
  source_count: plan.length,
  blocking_sources: blockingSources,
  readiness_contract: {
    required_before_forecast_refresh: [
      'openf1_session_data',
      'at_least_one_crosscheck_source_or_recorded_lag_reason',
      'source_timestamp_manifest',
      'validation_summary'
    ],
    output_artifacts: [
      'health/session_source_fetch_contract_v30g_status.json',
      'logs/session_source_fetch_contract/v30g_run_*.json'
    ]
  },
  next_step: 'v30H_live_fetch_adapter_sandbox_or_v30G_control_room_wiring_after_review'
};

writeJson(args.out, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(args.logDir, `v30g_run_${stamp}.json`), status);

console.log(JSON.stringify({
  ok: status.ok,
  out: args.out,
  gate_detected: session.gate_detected,
  source_count: status.source_count,
  blocking_sources: status.blocking_sources
}, null, 2));

process.exit(status.ok ? 0 : 1);
