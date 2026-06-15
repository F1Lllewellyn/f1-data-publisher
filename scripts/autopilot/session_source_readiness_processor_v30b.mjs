#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : fallback;
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

const manifestPath = arg('--manifest', 'scripts/autopilot/source_readiness_manifest_v30b.json');
const outPath = arg('--out', 'health/session_source_readiness_v30b_last_status.json');
const logDir = arg('--log-dir', 'logs/session_source_readiness');
const mode = arg('--mode', 'dry_run');

if (mode !== 'dry_run') {
  fail('v30B only supports dry_run mode', { mode });
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

if (!Array.isArray(manifest.adapter_groups) || manifest.adapter_groups.length === 0) {
  fail('manifest_has_no_adapter_groups');
}

const generatedUtc = new Date().toISOString();
fs.mkdirSync(logDir, { recursive: true });

const adapters = [];
for (const adapter of manifest.adapter_groups) {
  const adapterOut = path.join(logDir, adapter.id + '_adapter_v30b.json');
  const cp = spawnSync(process.execPath, [adapter.adapter_script, '--mode', 'dry_run', '--out', adapterOut], { encoding: 'utf8' });
  let payload = null;
  if (fs.existsSync(adapterOut)) payload = readJson(adapterOut);
  adapters.push({
    id: adapter.id,
    label: adapter.label,
    adapter_script: adapter.adapter_script,
    ok: cp.status === 0 && payload?.ok === true,
    status: cp.status,
    readiness: payload?.readiness || 'adapter_failed',
    output: adapterOut,
    stderr: cp.stderr || ''
  });
}

const status = {
  ok: adapters.every(adapter => adapter.ok),
  schema_version: 'f1_session_source_readiness_status_v30b',
  generated_utc: generatedUtc,
  mode,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_protected: true,
  canonical_workbook_protected: true,
  adapters,
  overall_readiness: adapters.every(adapter => adapter.ok) ? 'dry_run_adapters_ready' : 'dry_run_adapter_failure',
  material_change_detected: false,
  next_steps: [
    'v30C: add live source validation with bounded fetches',
    'v30D: add sandbox workbook/KPI readiness update path',
    'v30E: add material-change notification logic'
  ]
};

writeJson(outPath, status);
const stamp = generatedUtc.replaceAll(':', '-').replaceAll('.', '-');
writeJson(path.join(logDir, 'v30b_run_' + stamp + '.json'), status);
console.log(JSON.stringify(status, null, 2));
if (!status.ok) process.exit(1);
