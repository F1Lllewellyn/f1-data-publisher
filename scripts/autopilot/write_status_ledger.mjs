#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function parseArgs(argv) {
  const flags = {};
  const positionals = [];
  for (let i = 2; i < argv.length; i += 1) {
    const item = argv[i];
    if (item.startsWith('--')) {
      const key = item.slice(2);
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        flags[key] = 'true';
      } else {
        flags[key] = value;
        i += 1;
      }
    } else {
      positionals.push(item);
    }
  }
  return { flags, positionals };
}

function fail(message, details = {}) {
  console.error(JSON.stringify({ ok: false, error: message, ...details }, null, 2));
  process.exit(1);
}

function readJson(filePath, fallback = null) {
  if (!filePath || !fs.existsSync(filePath)) return fallback;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function boolFrom(value, fallback = false) {
  if (value == null || value === '') return fallback;
  return ['1', 'true', 'yes', 'on'].includes(String(value).trim().toLowerCase());
}

function normalizeRel(filePath) {
  return String(filePath || '').replaceAll('\\', '/').replace(/^\.\//, '');
}

function inferApplied(payload) {
  const files = Array.isArray(payload.files) ? payload.files : [];
  return {
    ok: true,
    inferred: true,
    applied: files.map((file) => {
      const rel = normalizeRel(file.path);
      let bytes = null;
      if (typeof file.content_base64 === 'string') {
        bytes = Buffer.from(file.content_base64, 'base64').length;
      }
      return { path: rel, action: file.action || 'upsert', bytes };
    })
  };
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

const { flags, positionals } = parseArgs(process.argv);
const payloadPath = flags.payload || positionals[0];
if (!payloadPath) fail('missing_payload_path');

const payload = readJson(payloadPath);
if (!payload) fail('payload_not_found', { payload_path: payloadPath });

const validation = readJson(flags.validation, { ok: true, source: 'not_provided' });
const applied = readJson(flags.applied, inferApplied(payload));
const tests = readJson(flags.tests, { ok: true, results: [] });
const status = flags.status || 'PASS';
const now = new Date().toISOString();

const ledger = {
  schema_version: 'f1_autopilot_bridge_status_v31',
  status,
  written_at: now,
  command_title: payload.title,
  safety_mode: payload.safety_mode,
  target_branch: payload.target_branch,
  base_branch: payload.base_branch,
  validation,
  applied,
  tests,
  production_automation: 'OFF',
  forecast_gate: 'OFF',
  promotion_status: payload.promotion_status || 'NOT_PROMOTED',
  activation_status: payload.activation_status || 'NOT_ACTIVATED',
  secrets_written: false
};

const runtimeDir = flags['runtime-dir'] || '_runtime/autopilot_bridge';
const runtimeStatus = flags.out || path.join(runtimeDir, 'status_ledger.json');
writeJson(runtimeStatus, ledger);

const writeTracked = boolFrom(flags['write-tracked-status'], boolFrom(process.env.F1_BRIDGE_WRITE_TRACKED_STATUS, false));
let trackedHealth = null;
let trackedLog = null;

if (writeTracked) {
  trackedHealth = 'health/autopilot_last_status.json';
  const stamp = now.replace(/[:.]/g, '-');
  trackedLog = `logs/autopilot_bridge/dispatch_${stamp}.json`;
  writeJson(trackedHealth, ledger);
  writeJson(trackedLog, ledger);
}

console.log(JSON.stringify({
  ok: true,
  runtime_status: runtimeStatus,
  tracked_status_written: writeTracked,
  tracked_health: trackedHealth,
  tracked_log: trackedLog,
  status
}, null, 2));
