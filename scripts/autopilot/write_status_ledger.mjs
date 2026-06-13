#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
function arg(name, fallback=null) { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : fallback; }
const payload = JSON.parse(fs.readFileSync(arg('--payload'), 'utf8'));
const validation = JSON.parse(fs.readFileSync(arg('--validation'), 'utf8'));
const applied = JSON.parse(fs.readFileSync(arg('--applied'), 'utf8'));
let tests = { ok: true, results: [] };
const testPath = arg('--tests');
if (testPath && fs.existsSync(testPath)) tests = JSON.parse(fs.readFileSync(testPath, 'utf8'));
const status = arg('--status', 'PASS');
const now = new Date().toISOString();
const ledger = { status, written_at: now, command_title: payload.title, safety_mode: payload.safety_mode, target_branch: payload.target_branch, base_branch: payload.base_branch, validation, applied, tests, production_automation: 'OFF', forecast_gate: 'OFF', promotion_status: payload.promotion_status || 'NOT_PROMOTED', activation_status: payload.activation_status || 'NOT_ACTIVATED', secrets_written: false };
fs.mkdirSync('health', { recursive: true });
fs.mkdirSync('logs/autopilot_bridge', { recursive: true });
fs.writeFileSync('health/autopilot_last_status.json', JSON.stringify(ledger, null, 2) + '\n');
const stamp = now.replace(/[:.]/g, '-');
fs.writeFileSync(`logs/autopilot_bridge/dispatch_${stamp}.json`, JSON.stringify(ledger, null, 2) + '\n');
console.log(JSON.stringify({ ok: true, health: 'health/autopilot_last_status.json' }, null, 2));
