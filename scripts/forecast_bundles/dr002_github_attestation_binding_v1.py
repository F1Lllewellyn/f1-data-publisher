"""Offline bridge from verified GitHub provenance to Gate 2B-1 receipt bindings.

This module does not perform cryptographic verification. It accepts a result from
an independently approved verifier boundary, then fail-closes on exact canonical
receipt bytes, attested subject identity, GitHub execution identity and temporal
consistency before projecting one binding in the unchanged Gate 2B-1 shape.

A VERIFIED label in caller-supplied data is itself a trust interface. The caller
remains responsible for obtaining that result from the approved verifier. This
bridge authenticates neither the upstream publisher nor the runner's internal
first-observed clock.
"""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_forecast_integrity_receipts_v1 import (
    ReceiptError,
    canonical_json_bytes,
    receipt_sha256,
    sha256,
    validate_receipt_envelope,
    verify_temporal_bindings,
)

VERSION = 'dr002-github-attestation-binding-v1'
APPROVED_VERIFIER = 'github_cli_attestation_verify'
VERIFICATION_MEDIA_TYPE = 'application/vnd.dev.sigstore.verificationresult+json;version=0.1'
BUNDLE_MEDIA_TYPE = 'application/vnd.dev.sigstore.bundle.v0.3+json'
DSSE_PAYLOAD_TYPE = 'application/vnd.in-toto+json'
STATEMENT_TYPE = 'https://in-toto.io/Statement/v1'
PREDICATE_TYPE = 'https://slsa.dev/provenance/v1'
BUILD_TYPE = 'https://actions.github.io/buildtypes/workflow/v1'
OIDC_ISSUER = 'https://token.actions.githubusercontent.com'
TRUST_SCOPE = 'GITHUB_EXECUTION_PROVENANCE_ONLY'

HOLD_TRUST = dict(
    first_observed_clock_authenticated=False,
    publisher_authenticated=False,
    production_authenticated=False,
    historical_availability_proven=False,
    observation_completeness_proven=False,
    dr002_activated=False,
)


class BindingError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def require(ok, code):
    if not ok:
        raise BindingError(code)


def _strict_json_bytes(data, code):
    require(isinstance(data, bytes), code)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    try:
        return json.loads(
            data.decode('utf-8'),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(BindingError('nonfinite_json')),
        )
    except BindingError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BindingError(code)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _commit(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{40}', value) is not None


def _utc(value, code):
    require(_text(value), code)
    try:
        normalized = value[:-1] + '+00:00' if value.endswith('Z') else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise BindingError(code)
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, code)
    return parsed.astimezone(timezone.utc)


def _canonical_utc(value):
    text = value.astimezone(timezone.utc).isoformat()
    return text.replace('+00:00', 'Z')


def _dict(value, code):
    require(isinstance(value, dict), code)
    return value


def _path_from_signer_workflow(repository, signer_workflow):
    prefix = repository + '/'
    require(signer_workflow.startswith(prefix), 'signer_workflow_repository_mismatch')
    path = signer_workflow[len(prefix):]
    require(path.startswith('.github/workflows/') and path.endswith(('.yml', '.yaml')),
            'malformed_signer_workflow')
    return path


def _validate_identity(identity):
    required = {
        'repository', 'signer_workflow', 'source_ref', 'source_digest',
        'signer_digest', 'runner_environment', 'workflow_trigger',
        'run_invocation_uri', 'oidc_issuer',
    }
    require(isinstance(identity, dict) and set(identity) == required, 'malformed_expected_identity')
    require(_text(identity['repository']) and '/' in identity['repository'], 'malformed_repository')
    _path_from_signer_workflow(identity['repository'], identity['signer_workflow'])
    require(identity['source_ref'] == 'refs/heads/main', 'unsupported_source_ref')
    require(_commit(identity['source_digest']) and _commit(identity['signer_digest']),
            'malformed_commit_identity')
    require(identity['runner_environment'] == 'github-hosted', 'unsupported_runner_environment')
    require(_text(identity['workflow_trigger']), 'malformed_workflow_trigger')
    require(identity['oidc_issuer'] == OIDC_ISSUER, 'unsupported_oidc_issuer')
    expected_prefix = 'https://github.com/' + identity['repository'] + '/actions/runs/'
    parsed = urlparse(identity['run_invocation_uri'])
    require(parsed.scheme == 'https' and parsed.netloc == 'github.com'
            and identity['run_invocation_uri'].startswith(expected_prefix)
            and re.fullmatch(r'/[^/]+/[^/]+/actions/runs/\d+/attempts/\d+', parsed.path) is not None,
            'malformed_run_invocation_uri')
    return identity


def _validate_verification_ref(value, repository):
    require(_text(value), 'missing_verification_ref')
    parsed = urlparse(value)
    require(parsed.scheme == 'https' and parsed.netloc == 'github.com', 'malformed_verification_ref')
    require(parsed.query == '' and parsed.fragment == '', 'malformed_verification_ref')
    require(re.fullmatch('/' + re.escape(repository) + r'/attestations/\d+', parsed.path) is not None,
            'malformed_verification_ref')
    return value


def _decoded_bundle_statement(bundle_bytes):
    bundle = _strict_json_bytes(bundle_bytes, 'malformed_attestation_bundle')
    require(bundle.get('mediaType') == BUNDLE_MEDIA_TYPE, 'unsupported_attestation_bundle')
    envelope = _dict(bundle.get('dsseEnvelope'), 'malformed_dsse_envelope')
    require(envelope.get('payloadType') == DSSE_PAYLOAD_TYPE, 'unsupported_dsse_payload_type')
    signatures = envelope.get('signatures')
    require(isinstance(signatures, list) and len(signatures) >= 1
            and all(isinstance(x, dict) and _text(x.get('sig')) for x in signatures),
            'malformed_dsse_signatures')
    payload = envelope.get('payload')
    require(_text(payload), 'missing_dsse_payload')
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception:
        raise BindingError('malformed_dsse_payload')
    return _strict_json_bytes(raw, 'malformed_dsse_statement')


def _validate_subject(statement, exact_digest):
    require(statement.get('_type') == STATEMENT_TYPE, 'statement_type_mismatch')
    require(statement.get('predicateType') == PREDICATE_TYPE, 'predicate_type_mismatch')
    subjects = statement.get('subject')
    require(isinstance(subjects, list) and len(subjects) == 1, 'subject_count_mismatch')
    subject = subjects[0]
    require(isinstance(subject, dict) and set(subject) == {'name', 'digest'}, 'malformed_subject')
    require(subject['name'] == 'source_capture_receipt.json', 'subject_name_mismatch')
    digest = subject['digest']
    require(isinstance(digest, dict) and digest.get('sha256') == exact_digest
            and set(digest) == {'sha256'}, 'subject_digest_mismatch')


def _validate_verified_result(verified, bundle_statement, exact_digest, identity):
    require(isinstance(verified, dict)
            and set(verified) == {'verification_status', 'verifier', 'result'},
            'missing_or_malformed_verified_result')
    require(verified['verification_status'] == 'VERIFIED', 'attestation_not_verified')
    require(verified['verifier'] == APPROVED_VERIFIER, 'unapproved_verifier')
    result = _dict(verified['result'], 'malformed_verified_result')
    require(result.get('mediaType') == VERIFICATION_MEDIA_TYPE, 'verification_media_type_mismatch')
    statement = _dict(result.get('statement'), 'missing_verified_statement')
    require(statement == bundle_statement, 'verified_statement_bundle_mismatch')
    _validate_subject(statement, exact_digest)

    repository = identity['repository']
    workflow_path = _path_from_signer_workflow(repository, identity['signer_workflow'])
    repo_url = 'https://github.com/' + repository
    signer_uri = repo_url + '/' + workflow_path + '@' + identity['source_ref']

    signature = _dict(result.get('signature'), 'missing_verified_signature')
    cert = _dict(signature.get('certificate'), 'missing_verified_certificate')
    checks = {
        'certificate_subject_mismatch': cert.get('subjectAlternativeName') == signer_uri,
        'certificate_oidc_issuer_mismatch': cert.get('issuer') == identity['oidc_issuer'],
        'certificate_workflow_trigger_mismatch': cert.get('githubWorkflowTrigger') == identity['workflow_trigger'],
        'certificate_workflow_sha_mismatch': cert.get('githubWorkflowSHA') == identity['signer_digest'],
        'certificate_repository_mismatch': cert.get('githubWorkflowRepository') == repository,
        'certificate_source_ref_mismatch': cert.get('githubWorkflowRef') == identity['source_ref'],
        'certificate_signer_uri_mismatch': cert.get('buildSignerURI') == signer_uri,
        'certificate_signer_digest_mismatch': cert.get('buildSignerDigest') == identity['signer_digest'],
        'certificate_runner_mismatch': cert.get('runnerEnvironment') == identity['runner_environment'],
        'certificate_source_repository_mismatch': cert.get('sourceRepositoryURI') == repo_url,
        'certificate_source_digest_mismatch': cert.get('sourceRepositoryDigest') == identity['source_digest'],
        'certificate_source_repository_ref_mismatch': cert.get('sourceRepositoryRef') == identity['source_ref'],
        'certificate_build_config_uri_mismatch': cert.get('buildConfigURI') == signer_uri,
        'certificate_build_config_digest_mismatch': cert.get('buildConfigDigest') == identity['signer_digest'],
        'certificate_build_trigger_mismatch': cert.get('buildTrigger') == identity['workflow_trigger'],
        'certificate_run_invocation_mismatch': cert.get('runInvocationURI') == identity['run_invocation_uri'],
    }
    for code, ok in checks.items():
        require(ok, code)

    predicate = _dict(statement.get('predicate'), 'missing_predicate')
    build = _dict(predicate.get('buildDefinition'), 'missing_build_definition')
    require(build.get('buildType') == BUILD_TYPE, 'build_type_mismatch')
    external = _dict(build.get('externalParameters'), 'missing_external_parameters')
    workflow = _dict(external.get('workflow'), 'missing_workflow_parameters')
    require(workflow.get('repository') == repo_url, 'statement_repository_mismatch')
    require(workflow.get('path') == workflow_path, 'statement_workflow_mismatch')
    require(workflow.get('ref') == identity['source_ref'], 'statement_source_ref_mismatch')
    internal = _dict(build.get('internalParameters'), 'missing_internal_parameters')
    github = _dict(internal.get('github'), 'missing_github_parameters')
    require(github.get('event_name') == identity['workflow_trigger'], 'statement_trigger_mismatch')
    require(github.get('runner_environment') == identity['runner_environment'], 'statement_runner_mismatch')

    deps = build.get('resolvedDependencies')
    require(isinstance(deps, list) and len(deps) == 1, 'resolved_dependency_mismatch')
    dep = deps[0]
    require(isinstance(dep, dict)
            and dep.get('uri') == 'git+' + repo_url + '@' + identity['source_ref']
            and isinstance(dep.get('digest'), dict)
            and dep['digest'].get('gitCommit') == identity['source_digest'],
            'source_commit_mismatch')

    run = _dict(predicate.get('runDetails'), 'missing_run_details')
    builder = _dict(run.get('builder'), 'missing_builder')
    metadata = _dict(run.get('metadata'), 'missing_run_metadata')
    require(builder.get('id') == signer_uri, 'statement_signer_workflow_mismatch')
    require(metadata.get('invocationId') == identity['run_invocation_uri'], 'statement_run_invocation_mismatch')

    timestamps = result.get('verifiedTimestamps')
    require(isinstance(timestamps, list), 'missing_verified_tlog_timestamp')
    parsed = []
    for stamp in timestamps:
        if isinstance(stamp, dict) and stamp.get('type') == 'Tlog':
            parsed.append(_utc(stamp.get('timestamp'), 'malformed_verified_tlog_timestamp'))
    require(parsed, 'missing_verified_tlog_timestamp')
    return min(parsed)


def _hold(code):
    return {
        'status': 'HOLD',
        'reason_codes': [code],
        'verified_receipt_bindings': {},
        'trust_scope': TRUST_SCOPE,
        **HOLD_TRUST,
    }


def build_verified_github_receipt_binding(
        receipt_bytes, attestation_bundle_bytes, verified_attestation_result,
        expected_identity, verification_ref):
    """Project verified GitHub provenance into the unchanged Gate 2B-1 binding shape.

    No cryptographic verification occurs here. Any HOLD returns no binding.
    """
    try:
        identity = _validate_identity(expected_identity)
        verification_ref = _validate_verification_ref(verification_ref, identity['repository'])

        receipt = _strict_json_bytes(receipt_bytes, 'malformed_receipt')
        validate_receipt_envelope(receipt)
        require(receipt['receipt_type'] == 'source_capture', 'wrong_receipt_type')
        verify_temporal_bindings(receipt)
        require(receipt['parent_receipt_ids'] == [], 'source_capture_has_parents')

        canonical = canonical_json_bytes(receipt)
        require(receipt_bytes == canonical, 'noncanonical_receipt_bytes')
        exact_digest = sha256(receipt_bytes)
        canonical_digest = receipt_sha256(receipt)
        require(exact_digest == canonical_digest, 'canonical_exact_digest_mismatch')

        bundle_statement = _decoded_bundle_statement(attestation_bundle_bytes)
        tlog_time = _validate_verified_result(
            verified_attestation_result, bundle_statement, exact_digest, identity)

        created = _utc(receipt['receipt_created_utc'], 'malformed_receipt_created_utc')
        require(tlog_time >= created, 'verified_tlog_before_receipt_creation')

        binding = {
            receipt['receipt_id']: {
                'receipt_sha256': canonical_digest,
                'verification_ref': verification_ref,
            }
        }
        return {
            'status': 'VERIFIED_GITHUB_PROVENANCE_BINDING',
            'schema_version': VERSION,
            'verified_receipt_bindings': binding,
            'receipt_id': receipt['receipt_id'],
            'canonical_receipt_sha256': canonical_digest,
            'exact_receipt_sha256': exact_digest,
            'attested_receipt_existed_by_utc': _canonical_utc(tlog_time),
            'internal_first_observed_utc': receipt['payload']['first_observed_utc'],
            'trust_scope': TRUST_SCOPE,
            **HOLD_TRUST,
        }
    except (BindingError, ReceiptError, KeyError, TypeError, ValueError) as exc:
        return _hold(getattr(exc, 'code', str(exc) or 'binding_validation_failed'))
