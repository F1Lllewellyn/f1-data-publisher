import fs from 'node:fs';
import path from 'node:path';
const pairs=[]; for(let i=2;i<process.argv.length;i++){ if(process.argv[i].startsWith('--')) pairs.push([process.argv[i].slice(2),process.argv[i+1]]); }
const args=Object.fromEntries(pairs);
const handoff=args.handoff||'';
const out=args.out||'health/session_processor_operator_review_verifier_v33a_status.json';
const md=args['markdown-out']||'health/session_processor_operator_review_verifier_v33a_packet.md';
const flagNames=['execute','activate','allow-live','allow-canonical-workbook-write','allow-ledger-write','allow-notification-send','allow-race-refresh','allow-fantasy-refresh'];
function readJson(p){if(!p||!fs.existsSync(p))return null;return JSON.parse(fs.readFileSync(p,'utf8'));}
function low(x){return String(x??'').toLowerCase();}
function stat(x){return low(x?.operator_handoff_status||x?.readiness_packet_status||x?.status||x?.decision||'missing');}
function ready(s){return /(ready|passed|complete|accepted|final)/.test(s)&&!/(blocked|failed|error|rejected|not_ready|missing)/.test(s);}
function gov(n,x){const b=[];if(!x)return b;if(x.production_automation&&x.production_automation!=='OFF')b.push(`${n}:production_automation_not_off`);if(x.forecast_gate&&x.forecast_gate!=='OFF')b.push(`${n}:forecast_gate_not_off`);if(x.promotion_allowed||x.model_promotion_allowed||x.promotion)b.push(`${n}:promotion_not_false`);if(x.live_fetch_performed)b.push(`${n}:live_fetch_performed`);if(x.notification_sent)b.push(`${n}:notification_sent`);if(x.canonical_workbook_overwrite||x.canonical_workbook_write||x.canonical_workbook_written)b.push(`${n}:canonical_workbook_write_detected`);for(const [k,v] of Object.entries(x.consumer_gates||{}))if(v===true)b.push(`${n}:consumer_gate_open:${k}`);return b;}
const h=readJson(handoff);const blockers=[];if(!h)blockers.push('missing_v32n_handoff_packet');const hs=stat(h);if(h&&!ready(hs))blockers.push(`v32n_handoff_not_ready:${hs}`);blockers.push(...gov('v32n',h));for(const f of flagNames)if(args[f]==='true')blockers.push(`explicit_${f}_not_allowed_in_v33a`);
const ok=blockers.length===0;const result={schema_version:'f1_session_processor_operator_review_verifier_v33a_2026-06-17',step:'v33A',step_number:'1_of_10',operator_review_status:ok?'ready_for_v33B_one_command_dry_run_rehearsal':'blocked',production_automation:'OFF',forecast_gate:'OFF',promotion_allowed:false,live_fetch_performed:false,canonical_workbook_written:false,forecast_bundle_ledger_written:false,race_predictions_refreshed:false,fantasy_refreshed:false,notification_sent:false,input_status:{v32n_handoff_status:hs,handoff_present:!!h},blockers,next_step:ok?'v33B_one_command_end_to_end_dry_run_rehearsal':'resolve_v33A_blockers'};
fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(result,null,2)+'\n');fs.mkdirSync(path.dirname(md),{recursive:true});fs.writeFileSync(md,`# v33A Operator Review Verifier\n\nStep: 1 of 10\nStatus: ${result.operator_review_status}\n\nBlockers:\n${blockers.length?blockers.map(b=>`- ${b}`).join('\n'):'- None'}\n\nGovernance: all production/live/write/refresh/notification/promotion paths remain closed.\n\nNext: ${result.next_step}\n`);
console.log(JSON.stringify({ok,status:result.operator_review_status,blockers:blockers.length},null,2));process.exit(ok?0:1);
