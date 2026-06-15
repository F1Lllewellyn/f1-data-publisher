#!/usr/bin/env node
/*
* F1 v30C public-source adapter dry-run.
 * Sandbox-only scaffolding for FIA/public-source readiness cross-checks.
 * No network fetch is performed unless --live is explicitly supplied in a later promoted adapter.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = { out: 'health/public_source_adapter_v30c_status.json', event: 'unknown_event', session: 'unknown_session', mode: 'dry_run' };
  for (let i = 2; i < argv.length; i++) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--out' && value) { args.out = value; i++; }
    else if (key === '--event' && value) { args.event = value; i++; }
    else if (key === '--session' && value) { args.session = value; i++; }
    else if (key === '--mode' && value) { args.mode = value; i++; }
  }
  return args;}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

const args = parseArgs(process.argv);
const liveRequested = args.mode === 'live';
const status = {
  schema_version: 'f1_public_source_adapter_v30c_2026-06-15',
  generated_utc: nowIso(),
  adapter: 'public_source_adapter_v30c',
  mode: args.mode,
  event: args.event,
  session: args.session,
  live_fetch_enabled: false,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  sources: [
    {
      source_id: 'fia_documents_index',
      source_type: 'official_public_document_index',
      required_for: ['race_result', 'classification_validation', 'penalty_validation'],
      fetch_status: liveRequested ? 'blocked_live_mode_not_enabled' : 'dry_run_not_fetched',
      readiness_role: 'crosscheck',
      blocking_in_dry_run: false
    },
    {
      source_id: 'formula1_official_event_pages',
      source_type: 'official_public_context',
      required_for: ['event_schedule', 'session_context', 'public_quote_context'],
      fetch_status: liveRequested ? 'blocked_live_mode_not_enabled' : 'dry_run_not_fetched',
      readiness_role: 'context',
      blocking_in_dry_run: false
    },
    {
      source_id: 'existing_openf1_manifest',
      source_type: 'existing_repo_artifact',
      required_for: ['telemetry_timing_source_readiness'],
      fetch_status: 'external_manifest_expected_from_v30b_or_control_room',
      readiness_role: 'primary_or_existing',
      blocking_in_dry_run: false
    }
  ]
};

writeJson(args.out, status);
console.log(JSON.stringify({ ok: true, out: args.out, mode: args.mode, source_count: status.sources.length }, null, 2));
