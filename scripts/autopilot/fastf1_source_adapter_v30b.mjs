#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2) + '\n', 'utf8');
}

function fail(message, extra = {}) {
  const payload = { ok: false, adapter: 'fastf1', error: message, ...extra };
  console.error(JSON.stringify(payload, null, 2));
  process.exit(1);
}

const mode = arg('--mode', 'dry_run');
const outPath = arg('--out', 'logs/session_source_readiness/fastf1_adapter_v30b.json');
const python = arg('--python', 'python');

if (mode !== 'dry_run') {
  fail('v30B FastF1 adapter only supports dry_run mode', { mode });
}

const probe = spawnSync(python, ['-c', "import importlib.util, json; print(json.dumps({'fastf1_available': importlib.util.find_spec('fastf1') is not None}))"], { encoding: 'utf8' });
let packageProbe = { fastf1_available: false, probe_status: probe.status, probe_error: probe.stderr || '' };
try {
  if (probe.stdout) packageProbe = { ...packageProbe, ...JSON.parse(probe.stdout) };
} catch {
  packageProbe.probe_parse_error = true;
}

const result = {
  ok: true,
  adapter: 'fastf1',
  schema_version: 'f1_source_adapter_fastf1_v30b',
  generated_utc: new Date().toISOString(),
  mode,
  readiness: 'dry_run_adapter_ready',
  fetch_performed: false,
  package_probe: packageProbe,
  planned_python_contract: {
    package: 'fastf1',
    cache_required: true,
    planned_calls: [
      'fastf1.get_session(year, event, session)',
      'session.load()',
      'session.laps',
      'session.results',
      'session.weather_data'
    ]
  },
  governance: {
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false
  }
};

writeJson(outPath, result);
console.log(JSON.stringify(result, null, 2));
