#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
function arg(name, fallback=null) { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : fallback; }
function fail(msg) { console.error(msg); process.exit(1); }
const payload = JSON.parse(fs.readFileSync(arg('--payload'), 'utf8'));
const validation = JSON.parse(fs.readFileSync(arg('--validation'), 'utf8'));
const outPath = arg('--out', '.autopilot_runtime/applied_files.json');
if (!validation.ok) fail('validation_not_ok');
const applied = [];
for (const file of payload.files) {
  const rel = file.path.replaceAll('\\','/').replace(/^\.\//,'');
  if (file.action !== 'upsert') fail(`unsupported_action:${file.action}`);
  const bytes = Buffer.from(file.content_base64, 'base64');
  fs.mkdirSync(path.dirname(rel), { recursive: true });
  fs.writeFileSync(rel, bytes);
  applied.push({ path: rel, action: 'upsert', bytes: bytes.length });
}
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify({ ok: true, applied }, null, 2) + '\n');
console.log(JSON.stringify({ ok: true, applied }, null, 2));
