#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
function arg(name, fallback=null) { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : fallback; }
const payload = JSON.parse(fs.readFileSync(arg('--payload'), 'utf8'));
const allowed = JSON.parse(fs.readFileSync(arg('--allowed', 'config/autopilot_allowed_tests.json'), 'utf8'));
const outPath = arg('--out', '.autopilot_runtime/test_results.json');
const requested = Array.isArray(payload.tests) ? payload.tests : [];
const allowedMap = new Map((allowed.allowed_named_tests || []).map(t => [t.name, t.command]));
const results = [];
for (const name of requested) {
  if (!allowedMap.has(name)) {
    results.push({ name, ok: false, error: 'test_not_whitelisted' });
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, JSON.stringify({ ok: false, results }, null, 2) + '\n');
    process.exit(1);
  }
  const command = allowedMap.get(name);
  const cp = spawnSync(command[0], command.slice(1), { encoding: 'utf8' });
  results.push({ name, ok: cp.status === 0, status: cp.status, stdout: cp.stdout, stderr: cp.stderr });
  if (cp.status !== 0) {
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, JSON.stringify({ ok: false, results }, null, 2) + '\n');
    process.exit(cp.status || 1);
  }
}
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify({ ok: true, results }, null, 2) + '\n');
console.log(JSON.stringify({ ok: true, results }, null, 2));
