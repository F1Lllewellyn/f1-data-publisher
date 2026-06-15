#!/usr/bin/env node
/*
* F1 v30C source crosscheck validator dry-run.
 * Reads optional adapter outputs and writes a single crosscheck manifest.
 */
import fs from 'node:fs';
import path from 'node:path';

function nowIso() { return new Date().toISOString(); }

function parseArgs(argv) {
  const args = {
    publicSource: 'health/public_source_adapter_v30c_status.json',
    out: 'health/source_crosscheck_v30c_status.json',
    log: ''
  };
  for (let i = 2; i < argv.length; i++) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--public-source' && value) { args.publicSource = value; i++; }
    else if (key === '--out' && value) { args.out = value; i++; }
    else if (key === '--log' && value) { args.log = value; i++; }
  }
  return args;
}

function readJsonMaybe(filePath) {
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

const args = parseArgs(process.argv);
const publicSource = readJsonMaybe(args.publicSource);
const missing = [];
if (!publicSource) missing.push(args.publicSource);

const dryRunOk = Boolean(publicSource && publicSource.live_fetch_enabled === false && publicSource.promotion_allowed === false);
const manifest = {
  schema_version: 'f1_source_crosscheck_validator_v30c_2026-06-15',
  generated_utc: nowIso(),
  status: dryRunOk ? 'pass' : 'blocked',
  readiness_quality: dryRunOk ? 'dry_run_contract_ready' : 'missing_dry_run_source_manifest',
  missing_inputs: missing,
  source_backed: false,
  dry_run_only: true,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_allowed: false,
  stable_engine_modified: false,
  canonical_workbook_overwrite: false,
  public_source_adapter: publicSource ? {
    schema_version: publicSource.schema_version,
    source_count: Array.isArray(publicSource.sources) ? publicSource.sources.length : 0,
    live_fetch_enabled: publicSource.live_fetch_enabled,
    source_ids: Array.isArray(publicSource.sources) ? publicSource.sources.map(s => s.source_id) : []
  } : null,
  next_step: 'v30D_live_adapter_validation_or_control_room_integration_after_review'
};

writeJson(args.out, manifest);
if (args.log) writeJson(args.log, { ok: dryRunOk, generated_utc: manifest.generated_utc, out: args.out });
console.log(JSON.stringify({ ok: dryRunOk, out: args.out, readiness_quality: manifest.readiness_quality }, null, 2));
process.exit(dryRunOk ? 0 : 1);
