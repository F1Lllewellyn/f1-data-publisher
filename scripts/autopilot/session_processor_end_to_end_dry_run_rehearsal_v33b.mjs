import fs from 'node:fs';
import path from 'node:path';
const VERSION = 'v33B-R4-R2';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_end_to_end_dry_run_policy_v33b.json';
const DEFAULT_FIXTURE = 'scripts/autopilot/session_processor_end_to_end_dry_run_fixture_v33b.json';
const aliases = new Map([
  ['repo-root', 'repoRoot'], ['repoRoot', 'repoRoot'], ['repo_root', 'repoRoot'],
  ['allow-live', 'allow_live'], ['production-automation', 'production_automation'],
  ['workbook-write', 'workbook_write'], ['ledger-write', 'ledger_write'],
  ['race-predictions-refresh', 'race_predictions_refresh'],
  ['fantasy-predictions-refresh', 'fantasy_predictions_refresh'],
  ['notification-send', 'notification_send'], ['model-promotion', 'model_promotion']
]);
const boolKeys = new Set(['allow_live','production_automation','workbook_write','ledger_write','race_predictions_refresh','fantasy_predictions_refresh','notification_send','model_promotion']);
function parseArgs(argv) {
  const args = { repoRoot: process.cwd(), policy: DEFAULT_POLICY, mode: 'repo', fixture: null, output: null, allow_live: false, production_automation: false, workbook_write: false, ledger_write: false, race_predictions_refresh: false, fantasy_predictions_refresh: false, notification_send: false, model_promotion: false };
  for (let i = 2; i < argv.length; i++) {
    const item = argv[i];
    if (!item.startsWith('--')) continue;
    const raw = item.slice(2);
    const key = aliases.get(raw) || raw.replaceAll('-', '_');
    if (key === 'help') { printHelp(); process.exit(0); }
    if (!(key in args)) throw new Error(`Unknown argument: --${raw}`);
    const next = argv[i + 1];
    if (boolKeys.has(key)) {
      if (next === 'true' || next === 'false') { args[key] = next === 'true'; i += 1; }
      else args[key] = true;
    } else {
      if (!next || next.startsWith('--')) throw new Error(`Missing value for --${raw}`);
      args[key] = next;
      i += 1;
    }
  }
  return args;
}
function printHelp() {
  console.log(`Usage: node scripts/autopilot/session_processor_end_to_end_dry_run_rehearsal_v33b.mjs --repo-root . --mode repo --output artifacts/autopilot/v33b/rehearsal_output_v33b.json\nFixture: node scripts/autopilot/session_processor_end_to_end_dry_run_rehearsal_v33b.mjs --mode fixture --fixture ${DEFAULT_FIXTURE}`);
}
function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function maybeJson(file) { try { return fs.existsSync(file) ? readJson(file) : null; } catch (error) { return { __error: String(error.message || error) }; } }
function norm(rel) { return String(rel || '').replaceAll('\\', '/').replace(/^\.\//, ''); }
function inside(parent, child) { const rel = path.relative(parent, child); return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel)); }
function status(value) { return String(value || '').toUpperCase(); }
function outputPlan(args, policy) {
  if (!args.output) return { permitted: false, rel: null, abs: null, blockers: [], touches: [] };
  const root = path.resolve(args.repoRoot);
  const abs = path.resolve(root, args.output);
  const rel = norm(path.relative(root, abs));
  const blockers = [];
  if (!inside(root, abs)) blockers.push(`output outside repo: ${rel}`);
  const roots = policy.allowed_output_roots || ['artifacts/autopilot/v33b/', 'verification/'];
  const allowed = roots.some((allowedRoot) => rel === norm(allowedRoot).replace(/\/$/, '') || rel.startsWith(norm(allowedRoot)));
  if (!allowed) blockers.push(`output not under allowed roots: ${roots.join(',')}`);
  const touches = (policy.protected_paths || []).filter((protectedPath) => {
    const p = norm(protectedPath);
    return rel === p || rel.startsWith(p.endsWith('/') ? p : `${p}/`);
  }).map((protectedPath) => ({ writePath: rel, protectedPath }));
  if (touches.length) blockers.push('output touches protected path');
  return { permitted: blockers.length === 0, rel, abs, blockers, touches };
}
function evidenceFromFixture(args) {
  const file = path.resolve(args.repoRoot, args.fixture || DEFAULT_FIXTURE);
  const obj = readJson(file);
  return {
    v32N_dry_run_operator_packet: { found: Boolean(obj.v32N_dry_run_operator_packet), path: args.fixture || DEFAULT_FIXTURE, obj: obj.v32N_dry_run_operator_packet || null },
    v33A_operator_review_verifier: { found: Boolean(obj.v33A_operator_review_verifier), path: args.fixture || DEFAULT_FIXTURE, obj: obj.v33A_operator_review_verifier || null }
  };
}
function findFirst(root, paths) {
  for (const rel of paths || []) {
    const obj = maybeJson(path.resolve(root, rel));
    if (obj) return { found: !obj.__error, path: rel, obj };
  }
  return { found: false, path: null, obj: null };
}
function evidenceFromRepo(args, policy) {
  const root = path.resolve(args.repoRoot);
  const chain = policy.required_evidence_chain || {};
  return Object.fromEntries(Object.entries(chain).map(([name, spec]) => [name, findFirst(root, spec.candidate_paths || [])]));
}
function validateEvidence(evidence, policy) {
  const blockers = [];
  for (const [name, spec] of Object.entries(policy.required_evidence_chain || {})) {
    const item = evidence[name];
    if (!item?.found) { blockers.push(`${name}: missing evidence`); continue; }
    for (const [field, expected] of Object.entries(spec.required_fields || {})) {
      if (!(field in item.obj)) blockers.push(`${name}: missing ${field}`);
      else if (item.obj[field] !== expected) blockers.push(`${name}: ${field} expected ${JSON.stringify(expected)} got ${JSON.stringify(item.obj[field])}`);
    }
    const allowed = (spec.allowed_statuses || []).map(status);
    if (!allowed.includes(status(item.obj.status))) blockers.push(`${name}: status not allowed`);
  }
  return blockers;
}
function run() {
  const args = parseArgs(process.argv);
  const root = path.resolve(args.repoRoot);
  const policy = readJson(path.resolve(root, args.policy));
  const out = outputPlan(args, policy);
  const blockers = [...out.blockers];
  for (const flag of policy.required_explicit_false_flags || []) if (args[flag] !== false) blockers.push(`safety flag ${flag} must remain false`);
  const evidence = args.mode === 'fixture' ? evidenceFromFixture(args) : evidenceFromRepo(args, policy);
  blockers.push(...validateEvidence(evidence, policy));
  const ready = blockers.length === 0;
  const result = {
    version: VERSION,
    status: ready ? 'READY' : 'BLOCKED',
    mode: args.mode,
    blockers: [...new Set(blockers)],
    planned_writes: out.rel ? [out.rel] : [],
    output_write_permitted: out.permitted,
    side_effects: { network_fetch: false, production_automation: false, workbook_write: false, ledger_write: false, race_predictions_refresh: false, fantasy_predictions_refresh: false, notification_send: false, model_promotion: false, protected_path_touch: out.touches.length > 0, rehearsal_artifact_written: Boolean(args.output && out.permitted) },
    stages: (policy.dry_run_stage_contract || []).map((name) => ({ name, status: ready ? 'pass' : 'blocked', details: { mutation: false, network_fetch: false } })),
    governance: { stable_engine_protected: true, no_accuracy_claim: true, no_automation_change: true, pr_only: true }
  };
  const rendered = JSON.stringify(result, null, 2);
  if (args.output && out.permitted) { fs.mkdirSync(path.dirname(out.abs), { recursive: true }); fs.writeFileSync(out.abs, `${rendered}\n`, 'utf8'); }
  console.log(rendered);
  process.exit(ready ? 0 : 2);
}
try { run(); } catch (error) { console.error(JSON.stringify({ version: VERSION, status: 'ERROR', error: String(error.stack || error.message || error), side_effects: { network_fetch: false, production_automation: false, workbook_write: false, ledger_write: false, race_predictions_refresh: false, fantasy_predictions_refresh: false, notification_send: false, model_promotion: false } }, null, 2)); process.exit(1); }
