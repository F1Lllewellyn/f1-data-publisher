#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const VERSION = 'v33D';
const SCHEMA_VERSION = 'f1_session_processor_sandbox_live_source_quality_review_v33d_2026-06-18';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_sandbox_live_source_quality_review_policy_v33d.json';
const DEFAULT_OUT = 'health/session_processor_sandbox_live_source_quality_review_v33d_status.json';
const DEFAULT_ARTIFACT_DIR = 'sandbox/session_quality/v33d';

function parseArgs(argv) {
  const args = {
    mode: 'dry_run',
    policy: DEFAULT_POLICY,
    source_evidence: null,
    status_in: null,
    out: DEFAULT_OUT,
    artifact_dir: DEFAULT_ARTIFACT_DIR,
    production_automation: false,
    workbook_write: false,
    ledger_write: false,
    race_predictions_refresh: false,
    fantasy_predictions_refresh: false,
    notification_send: false,
    model_promotion: false,
    activate: false
  };

  const keyMap = new Map([
    ['mode', 'mode'],
    ['policy', 'policy'],
    ['source-evidence', 'source_evidence'],
    ['source_evidence', 'source_evidence'],
    ['status-in', 'status_in'],
    ['status_in', 'status_in'],
    ['out', 'out'],
    ['artifact-dir', 'artifact_dir'],
    ['artifact_dir', 'artifact_dir'],
    ['production-automation', 'production_automation'],
    ['workbook-write', 'workbook_write'],
    ['ledger-write', 'ledger_write'],
    ['race-predictions-refresh', 'race_predictions_refresh'],
    ['fantasy-predictions-refresh', 'fantasy_predictions_refresh'],
    ['notification-send', 'notification_send'],
    ['model-promotion', 'model_promotion'],
    ['activate', 'activate']
  ]);

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) continue;
    const rawKey = token.slice(2);
    const mapped = keyMap.get(rawKey);
    if (!mapped) throw new Error(`Unknown argument: ${token}`);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith('--')) {
      args[mapped] = true;
    } else {
      args[mapped] = coerceValue(next);
      i += 1;
    }
  }
  return args;
}

function coerceValue(value) {
  if (value === 'true') return true;
  if (value === 'false') return false;
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  return value;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`);
}

function timestampForPath(date = new Date()) {
  return date.toISOString().replace(/[-:.]/g, '').replace('Z', 'Z');
}

function isObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}

function safeDate(value) {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function hoursBetween(a, b) {
  if (!a || !b) return null;
  return Math.abs(a.getTime() - b.getTime()) / 36e5;
}

function hasWriteFlagViolation(args, policy) {
  const issues = [];
  for (const flag of policy.required_false_flags || []) {
    if (args[flag] !== false) issues.push(`flag_must_be_false:${flag}`);
  }
  return issues;
}

function evidenceFlagIssues(evidence, policy) {
  const issues = [];
  const required = policy.required_evidence_flags || {};
  for (const [key, expected] of Object.entries(required)) {
    if (evidence[key] !== expected) {
      issues.push({
        field: key,
        expected,
        actual: evidence[key] ?? null
      });
    }
  }
  return issues;
}

function sourceResultMap(evidence) {
  const map = new Map();
  for (const result of Array.isArray(evidence.fetch_results) ? evidence.fetch_results : []) {
    if (result?.request_id) map.set(result.request_id, result);
  }
  return map;
}

function manifestMap(evidence) {
  const map = new Map();
  for (const item of Array.isArray(evidence.request_manifest) ? evidence.request_manifest : []) {
    if (item?.request_id) map.set(item.request_id, item);
  }
  return map;
}

function classifyCompleteness(evidence, policy) {
  const results = sourceResultMap(evidence);
  const requiredIds = policy.required_openf1_request_ids || [];
  const optionalIds = policy.optional_openf1_request_ids || [];
  const minimums = policy.minimum_required_row_counts || {};
  const blockers = [];
  const warnings = [];

  for (const requestId of requiredIds) {
    const result = results.get(requestId);
    const minimum = Number(minimums[requestId] ?? 1);
    if (!result) {
      blockers.push({ gate: 'required_source_present', request_id: requestId, issue: 'missing_required_source_result' });
      continue;
    }
    if (result.ok !== true) {
      blockers.push({ gate: 'required_source_ok', request_id: requestId, issue: 'required_source_not_ok', http_status: result.http_status ?? null });
    }
    if (!(Number(result.row_count) >= minimum)) {
      blockers.push({ gate: 'required_source_row_count', request_id: requestId, issue: 'required_source_below_minimum', minimum, actual: result.row_count ?? null });
    }
    if (result.http_status !== undefined && !(Number(result.http_status) >= 200 && Number(result.http_status) <= 299)) {
      blockers.push({ gate: 'required_source_http_status', request_id: requestId, issue: 'required_source_non_2xx_http_status', http_status: result.http_status });
    }
  }

  for (const requestId of optionalIds) {
    const result = results.get(requestId);
    if (!result) {
      warnings.push({ gate: 'optional_source_present', request_id: requestId, issue: 'missing_optional_source_result' });
      continue;
    }
    if (result.ok !== true) {
      warnings.push({ gate: 'optional_source_ok', request_id: requestId, issue: 'optional_source_not_ok', http_status: result.http_status ?? null });
    } else if (!(Number(result.row_count) > 0)) {
      warnings.push({ gate: 'optional_source_row_count', request_id: requestId, issue: 'optional_source_empty', actual: result.row_count ?? null });
    }
  }

  return { blockers, warnings };
}

function classifySessionAlignment(evidence) {
  const blockers = [];
  const warnings = [];
  const gate = isObject(evidence.gate) ? evidence.gate : {};
  const manifest = manifestMap(evidence);
  const sessionKey = gate.session_key;
  const meetingKey = gate.meeting_key;
  const sessionName = gate.session_name;

  if (!sessionKey) blockers.push({ gate: 'session_key', issue: 'missing_session_key' });
  if (!meetingKey) warnings.push({ gate: 'meeting_key', issue: 'missing_meeting_key' });
  if (!sessionName) warnings.push({ gate: 'session_name', issue: 'missing_session_name' });

  for (const [requestId, item] of manifest.entries()) {
    const url = String(item.url || '');
    if (requestId !== 'openf1_resolve_session' && sessionKey && !url.includes(`session_key=${sessionKey}`)) {
      blockers.push({
        gate: 'manifest_session_key_alignment',
        request_id: requestId,
        issue: 'manifest_url_not_aligned_to_gate_session_key',
        session_key: sessionKey,
        url
      });
    }
    if (requestId === 'openf1_resolve_session' && meetingKey && !url.includes(`meeting_key=${meetingKey}`)) {
      warnings.push({
        gate: 'manifest_meeting_key_alignment',
        request_id: requestId,
        issue: 'resolve_session_url_not_aligned_to_gate_meeting_key',
        meeting_key: meetingKey,
        url
      });
    }
  }

  return { blockers, warnings };
}

function classifyTimestamps(evidence, policy) {
  const blockers = [];
  const warnings = [];
  const generated = safeDate(evidence.generated_utc);
  const gateTimestamp = safeDate(evidence.gate?.source_timestamp_utc || evidence.source_summary?.source_timestamp_utc);
  const maxAge = Number(policy.maximum_source_age_hours || 168);

  if (!generated) blockers.push({ gate: 'generated_utc', issue: 'missing_or_invalid_generated_utc' });
  if (!gateTimestamp) blockers.push({ gate: 'source_timestamp_utc', issue: 'missing_or_invalid_source_timestamp_utc' });

  if (generated && gateTimestamp) {
    if (generated.getTime() < gateTimestamp.getTime()) {
      warnings.push({ gate: 'timestamp_order', issue: 'evidence_generated_before_source_timestamp', generated_utc: generated.toISOString(), source_timestamp_utc: gateTimestamp.toISOString() });
    }
    const age = hoursBetween(generated, gateTimestamp);
    if (age !== null && age > maxAge) {
      blockers.push({ gate: 'source_age', issue: 'source_timestamp_exceeds_maximum_age', maximum_hours: maxAge, actual_hours: Number(age.toFixed(3)) });
    }
  }

  return { blockers, warnings };
}

function classifySourceHealth(evidence) {
  const blockers = [];
  const warnings = [];
  const results = Array.isArray(evidence.fetch_results) ? evidence.fetch_results : [];
  if (!results.length) {
    blockers.push({ gate: 'fetch_results', issue: 'no_fetch_results_present' });
    return { blockers, warnings };
  }

  for (const result of results) {
    const entry = {
      request_id: result.request_id || null,
      endpoint: result.endpoint || null,
      required: result.required === true,
      ok: result.ok === true,
      http_status: result.http_status ?? null,
      row_count: result.row_count ?? null,
      bytes: result.bytes ?? null
    };
    if (result.required === true && result.ok !== true) blockers.push({ gate: 'source_health', issue: 'required_source_unhealthy', ...entry });
    if (result.required !== true && result.ok !== true) warnings.push({ gate: 'source_health', issue: 'optional_source_unhealthy', ...entry });
    if (result.ok === true && Number(result.bytes || 0) <= 0) warnings.push({ gate: 'source_bytes', issue: 'source_reported_zero_bytes', ...entry });
  }

  return { blockers, warnings };
}

function reviewEvidence(evidence, policy, args) {
  const blockers = [];
  const warnings = [];

  if (!isObject(evidence)) {
    blockers.push({ gate: 'evidence_shape', issue: 'source_evidence_not_json_object' });
    return { blockers, warnings };
  }

  if (evidence.version !== 'v33C') warnings.push({ gate: 'source_version', issue: 'source_evidence_not_declared_v33c', actual: evidence.version ?? null });
  if (evidence.ok !== true) blockers.push({ gate: 'source_ok', issue: 'v33c_evidence_not_ok', actual: evidence.ok ?? null });
  if (!(policy.allowed_v33c_source_readiness || []).includes(evidence.pull_status)) {
    blockers.push({ gate: 'v33c_pull_status', issue: 'v33c_evidence_not_ready_for_quality_review', actual: evidence.pull_status ?? null });
  }
  if (evidence.sandbox_artifact_written !== true) {
    blockers.push({ gate: 'sandbox_artifact_written', issue: 'v33c_sandbox_artifact_not_written', actual: evidence.sandbox_artifact_written ?? null });
  }

  const flagIssues = evidenceFlagIssues(evidence, policy);
  for (const issue of flagIssues) blockers.push({ gate: 'evidence_guardrail_flag', issue: 'evidence_guardrail_flag_mismatch', ...issue });

  const writeFlagIssues = hasWriteFlagViolation(args, policy);
  for (const issue of writeFlagIssues) blockers.push({ gate: 'runtime_guardrail_flag', issue });

  for (const section of [
    classifyCompleteness(evidence, policy),
    classifySessionAlignment(evidence),
    classifyTimestamps(evidence, policy),
    classifySourceHealth(evidence)
  ]) {
    blockers.push(...section.blockers);
    warnings.push(...section.warnings);
  }

  if (Array.isArray(evidence.validation?.degraded_sources) && evidence.validation.degraded_sources.length > 0) {
    for (const degraded of evidence.validation.degraded_sources) {
      warnings.push({ gate: 'v33c_degraded_source', issue: 'v33c_reported_degraded_source', degraded });
    }
  }

  return { blockers, warnings };
}

function decisionFromReview(review) {
  if (review.blockers.length > 0) return { status: 'SANDBOX_SOURCE_QUALITY_BLOCKED', reason: 'blocking_source_quality_issue' };
  if (review.warnings.length > 0) return { status: 'SANDBOX_SOURCE_QUALITY_DEGRADED', reason: 'required_sources_pass_optional_or_warning_degraded' };
  return { status: 'SANDBOX_SOURCE_QUALITY_READY', reason: 'source_quality_review_passed' };
}

function artifactPayload({ evidence, review, decision, args }) {
  return {
    schema_version: SCHEMA_VERSION,
    generated_utc: new Date().toISOString(),
    version: VERSION,
    ok: decision.status !== 'SANDBOX_SOURCE_QUALITY_BLOCKED',
    mode: args.mode,
    production_automation: 'OFF',
    forecast_gate: 'OFF',
    promotion_allowed: false,
    stable_engine_modified: false,
    canonical_workbook_overwrite: false,
    workbook_write_allowed: false,
    ledger_write_allowed: false,
    prediction_refresh_enabled: false,
    fantasy_refresh_enabled: false,
    notification_send_enabled: false,
    live_fetch_performed: false,
    source_quality_status: decision.status,
    source_quality_reason: decision.reason,
    source_evidence_path: args.source_evidence,
    source_status_path: args.status_in,
    reviewed_v33c_status: evidence?.pull_status ?? null,
    reviewed_v33c_reason: evidence?.pull_reason ?? null,
    gate: evidence?.gate ?? null,
    source_summary: evidence?.source_summary ?? null,
    quality_review: {
      completeness: {
        required_source_ids: review.required_source_ids,
        optional_source_ids: review.optional_source_ids,
        fetch_result_count: Array.isArray(evidence?.fetch_results) ? evidence.fetch_results.length : 0,
        row_count_total: evidence?.validation?.row_count_total ?? null
      },
      blockers: review.blockers,
      warnings: review.warnings,
      missing_source_classification: review.missing_source_classification,
      required_sources: review.required_sources,
      optional_sources: review.optional_sources
    },
    guardrails: {
      production_automation: false,
      workbook_write: false,
      ledger_write: false,
      race_predictions_refresh: false,
      fantasy_predictions_refresh: false,
      notification_send: false,
      model_promotion: false,
      activate: false,
      quality_review_only: true,
      processor_execution_enabled: false
    },
    next_step: decision.status === 'SOURCE_QUALITY_REVIEW_CONTRACT_READY_NO_EVIDENCE_LOADED'
      ? 'supply_v33c_source_evidence_before_v33d'
      : decision.status === 'SANDBOX_SOURCE_QUALITY_BLOCKED'
      ? 'resolve_v33d_source_quality_blockers'
      : 'v33E_sandbox_live_processor_execution'
  };
}

function summarizeSources(evidence, policy) {
  const results = sourceResultMap(evidence || {});
  const summarize = (requestId) => {
    const result = results.get(requestId);
    if (!result) return { request_id: requestId, present: false, classification: 'missing' };
    if (result.ok !== true) return { request_id: requestId, present: true, classification: 'failed', http_status: result.http_status ?? null, row_count: result.row_count ?? null };
    if (!(Number(result.row_count) > 0)) return { request_id: requestId, present: true, classification: 'empty', http_status: result.http_status ?? null, row_count: result.row_count ?? null };
    return { request_id: requestId, present: true, classification: 'ready', http_status: result.http_status ?? null, row_count: result.row_count ?? null, bytes: result.bytes ?? null };
  };
  const requiredSources = (policy.required_openf1_request_ids || []).map(summarize);
  const optionalSources = (policy.optional_openf1_request_ids || []).map(summarize);
  return {
    requiredSources,
    optionalSources,
    missingSourceClassification: {
      missing_required: requiredSources.filter((item) => item.classification === 'missing').map((item) => item.request_id),
      failed_required: requiredSources.filter((item) => item.classification === 'failed').map((item) => item.request_id),
      empty_required: requiredSources.filter((item) => item.classification === 'empty').map((item) => item.request_id),
      missing_optional: optionalSources.filter((item) => item.classification === 'missing').map((item) => item.request_id),
      failed_optional: optionalSources.filter((item) => item.classification === 'failed').map((item) => item.request_id),
      empty_optional: optionalSources.filter((item) => item.classification === 'empty').map((item) => item.request_id)
    }
  };
}

function loadEvidence(args) {
  if (args.source_evidence) return readJson(args.source_evidence);
  if (args.status_in) {
    const status = readJson(args.status_in);
    if (status.sandbox_artifact_path && fs.existsSync(status.sandbox_artifact_path)) {
      return readJson(status.sandbox_artifact_path);
    }
    return status;
  }
  return null;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const policy = readJson(args.policy);
  if (!policy.allowed_modes.includes(args.mode)) throw new Error(`Mode not allowed by policy: ${args.mode}`);

  const evidence = args.mode === 'dry_run' && !args.source_evidence && !args.status_in
    ? null
    : loadEvidence(args);

  let review = {
    blockers: [],
    warnings: []
  };

  if (!evidence && args.mode === 'dry_run') {
    review.warnings.push({ gate: 'source_evidence', issue: 'dry_run_no_v33c_source_evidence_loaded' });
  } else if (!evidence) {
    review.blockers.push({ gate: 'source_evidence', issue: 'no_v33c_source_evidence_supplied' });
  } else {
    review = reviewEvidence(evidence, policy, args);
  }

  const sourceSummary = summarizeSources(evidence || {}, policy);
  review = {
    ...review,
    required_source_ids: policy.required_openf1_request_ids || [],
    optional_source_ids: policy.optional_openf1_request_ids || [],
    required_sources: sourceSummary.requiredSources,
    optional_sources: sourceSummary.optionalSources,
    missing_source_classification: sourceSummary.missingSourceClassification
  };

  const decision = args.mode === 'dry_run' && !evidence
    ? { status: 'SOURCE_QUALITY_REVIEW_CONTRACT_READY_NO_EVIDENCE_LOADED', reason: 'dry_run_contract_ready' }
    : decisionFromReview(review);

  const payload = artifactPayload({ evidence, review, decision, args });
  const shouldWriteArtifact = !['dry_run'].includes(args.mode) && evidence;
  if (shouldWriteArtifact) {
    const artifactPath = path.join(args.artifact_dir, `source_quality_review_${timestampForPath()}.json`);
    writeJson(artifactPath, payload);
    payload.quality_artifact_written = true;
    payload.quality_artifact_path = artifactPath;
  } else {
    payload.quality_artifact_written = false;
    payload.quality_artifact_path = null;
  }

  writeJson(args.out, payload);
  if (payload.source_quality_status === 'SANDBOX_SOURCE_QUALITY_BLOCKED') {
    process.exitCode = 2;
  }
}

main();
