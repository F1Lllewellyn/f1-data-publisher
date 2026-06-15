#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2) + '\n', 'utf8');
}

function fail(message, extra = {}) {
  const payload = { ok: false, adapter: 'openf1', error: message, ...extra };
  console.error(JSON.stringify(payload, null, 2));
  process.exit(1);
}

const mode = arg('--mode', 'dry_run');
const outPath = arg('--out', 'logs/session_source_readiness/openf1_adapter_v30b.json');
const baseUrl = arg('--base-url', 'https://api.openf1.org/v1');

if (mode !== 'dry_run') {
  fail('v30B OpenF1 adapter only supports dry_run mode', { mode });
}

const endpoints = [
  'meetings',
  'sessions',
  'drivers',
  'laps',
  'stints',
  'pit',
  'position',
  'weather',
  'race_control'
];

const result = {
  ok: true,
  adapter: 'openf1',
  schema_version: 'f1_source_adapter_openf1_v30b',
  generated_utc: new Date().toISOString(),
  mode,
  base_url: baseUrl,
  readiness: 'dry_run_adapter_ready',
  fetch_performed: false,
  auth_required_for_historical: false,
  planned_endpoints: endpoints.map(endpoint => ({
    endpoint,
    url_template: baseUrl + '/' + endpoint,
    default_validation: {
      response_type: 'json_array',
      minimum_records: endpoint === 'meetings' || endpoint === 'sessions' ? 1 : 0,
      freshness_policy: 'session_context_dependent'
    }
  })),
  governance: {
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false
  }
};

writeJson(outPath, result);
console.log(JSON.stringify(result, null, 2));
