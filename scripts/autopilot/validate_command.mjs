#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function arg(name, fallback=null) { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : fallback; }
function fail(msg, extra={}) { const out = { ok: false, error: msg, ...extra }; console.error(JSON.stringify(out, null, 2)); process.exit(1); }
const payloadPath = arg('--payload');
const policyPath = arg('--policy', 'config/protected_paths.json');
const outPath = arg('--out', '.autopilot_runtime/validation.json');
if (!payloadPath) fail('missing --payload');
const payload = JSON.parse(fs.readFileSync(payloadPath, 'utf8'));
const policy = JSON.parse(fs.readFileSync(policyPath, 'utf8'));

const required = ['schema_name','schema_version','command_type','project','safety_mode','target_branch','base_branch','title','summary','files'];
for (const key of required) if (!(key in payload)) fail(`missing_required_field:${key}`);
if (payload.schema_name !== 'f1_autopilot_patch_command') fail('bad_schema_name');
if (payload.command_type !== 'assistant_patch') fail('bad_command_type');
if (payload.project !== 'F1_Prediction_Engine') fail('bad_project');
if (!['pr_only','outputs_only'].includes(payload.safety_mode)) fail('bad_safety_mode');
if (payload.activation_status && payload.activation_status !== 'NOT_ACTIVATED') fail('activation_blocked');
if (payload.promotion_status && payload.promotion_status !== 'NOT_PROMOTED') fail('promotion_blocked');
if (!/^(autopilot|install|outputs)\//.test(payload.target_branch)) fail('bad_target_branch_prefix');
if (!Array.isArray(payload.files) || payload.files.length === 0) fail('no_files');

const allowedRoots = policy.allowed_roots[payload.safety_mode] || [];
const blockedMarkers = policy.protected_markers.map(s => String(s).toLowerCase().replaceAll('\\','/'));
const blockedActions = new Set(policy.blocked_actions || []);
const allowedActions = new Set(policy.allowed_actions || ['upsert']);
const files = [];

for (const file of payload.files) {
  const action = String(file.action || 'upsert').toLowerCase();
  if (blockedActions.has(action) || !allowedActions.has(action)) fail('blocked_action', { path: file.path, action });
  if (!file.path || typeof file.path !== 'string') fail('bad_file_path');
  const normalized = file.path.replaceAll('\\','/').replace(/^\.\//,'');
  if (normalized.startsWith('/') || normalized.includes('../') || normalized === '..') fail('path_traversal_or_absolute', { path: file.path });
  const low = normalized.toLowerCase();
  for (const marker of blockedMarkers) if (low.includes(marker)) fail('protected_path_blocked', { path: normalized, marker });
  if (!allowedRoots.some(root => normalized.startsWith(root))) fail('root_not_allowed_for_safety_mode', { path: normalized, safety_mode: payload.safety_mode, allowedRoots });
  if (action === 'upsert' && typeof file.content_base64 !== 'string') fail('missing_content_base64', { path: normalized });
  files.push({ path: normalized, action });
}
const result = { ok: true, validated_at: new Date().toISOString(), safety_mode: payload.safety_mode, target_branch: payload.target_branch, base_branch: payload.base_branch, files, production_automation: 'OFF', forecast_gate: 'OFF', promotion: false, secrets_written: false };
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result, null, 2));
