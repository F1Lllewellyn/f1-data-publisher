#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

function hasFlag(name) {
  return process.argv.includes(name);
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2) + '\n', 'utf8');
}

function fail(message, extra = {}) {
  const payload = { ok: false, error: message, ...extra };
  console.error(JSON.stringify(payload, null, 2));
  process.exit(1);
}

const manifestPath = arg('--manifest', 'scripts/autopilot/source_readiness_manifest_v30a.json');
const outPath = arg('--out', 'health/session_source_readiness_last_status.json');
const logDir = arg('--log-dir', 'logs/session_source_readiness');
const mode = arg('--mode', hasFlag('--dry-run') ? 'dry_run' : 'dry_run');

if (mode !== 'dry_run') {
  fail('v30A only supports dry_run mode', { mode });
}

const manifest = readJson(manifestPath);

const requiredGovernance = {
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_protected: true,
  canonical_workbook_protected: true
};

for (const [key, expected] of Object.entries(requiredGovernance)) {
  if (manifest[key] !== expected) {
    fail('governance_guard_failed', { key, expected, actual: manifest[key] });
  }
}

if (!Array.isArray(manifest.source_groups) || manifest.source_groups.length === 0) {
  fail('manifest_has_no_source_groups');
}

const generatedUtc = new Date().toISOString();
const sourceGroups = manifest.source_groups.map(group => ({
  id: group.id,
  label: group.label,
  adapter_status: group.adapter_status,
  readiness: 'not_checked',
  dry_run_reason: 'adapter_not_executed_in_v30a',
  required_for: group.required_for,
  freshness_minutes: group.freshness_minutes,
  minimum_records: group.minimum_records,
  failure_policy: group.failure_policy
}));

const status = {
  ok: true,
  schema_version: 'f1_session_source_readiness_status_v30a',
  generated_utc: generatedUtc,
  mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_protected: true,
  canonical_workbook_protected: true,
  source_groups: sourceGroups,
  overall_readiness: 'dry_run_not_ready',
  material_change_detected: false,
  next_steps: [
    'v30B: add OpenF1/FastF1 pull adapters',
    'v30C: add FIA/public source adapter validation',
    'v30D: add sandbox workbook/KPI readiness update path',
    'v30E: add material-change notification logic'
  ]
};

writeJson(outPath, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(logDir, 'run_' + stamp + '.json'), status);
console.log(JSON.stringify(status, null, 2));
