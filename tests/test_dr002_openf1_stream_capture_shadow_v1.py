import ast
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/forecast_bundles/dr002_openf1_stream_capture_shadow_v1.py"
WORKFLOW = ROOT / ".github/workflows/dr002-openf1-stream-capture-shadow.yml"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("openf1_capture_shadow", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit):
        return self.body


class OpenF1StreamCaptureShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "runtime"
        self.counter = 1000
        self.workflow_text = WORKFLOW.read_text()
        self.script_text = SCRIPT.read_text()
        self.base_env = {
            "OPENF1_USERNAME": "secret-user@example.invalid",
            "OPENF1_PASSWORD": "secret-password-value",
            "GITHUB_REPOSITORY": "F1Lllewellyn/f1-data-publisher",
            "GITHUB_WORKFLOW": "DR-002 OpenF1 stream capture shadow",
            "GITHUB_WORKFLOW_REF": "F1Lllewellyn/f1-data-publisher/"
            + m.WORKFLOW_PATH + "@refs/heads/main",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": str(self.counter),
            "GITHUB_RUN_ATTEMPT": "1",
        }
        self.messages = [
            {"topic": m.MQTT_TOPIC, "raw_json_bytes": raw({"_id": 4, "_key": "weather-1", "rainfall": 0}), "received_order_index": 0},
            {"topic": m.MQTT_TOPIC, "raw_json_bytes": raw({"_id": 9, "_key": "weather-1", "rainfall": 1}), "received_order_index": 1},
        ]

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, *, messages=None, environ=None, token_fetcher=None,
                transport=None, unsupported_claims=None):
        self.counter += 1
        env = dict(self.base_env if environ is None else environ)
        env["GITHUB_RUN_ID"] = str(self.counter)
        supplied_messages = self.messages if messages is None else messages
        token_fetcher = token_fetcher or (lambda username, password: ("memory-token-value", 3600))
        transport = transport or (lambda token: {
            "connection_outcome": "CONNECTED_AND_SUBSCRIBED",
            "messages": supplied_messages,
        })
        result = m.execute_capture_shadow(
            environ=env,
            token_fetcher=token_fetcher,
            transport=transport,
            output_base=self.output,
            utc_now=lambda: "2026-10-07T16:00:00.000000Z",
            unsupported_claims=unsupported_claims,
        )
        return result, env

    def test_exact_provider_broker_port_and_topic_constants(self):
        self.assertEqual((m.PROVIDER, m.MQTT_BROKER, m.MQTT_PORT, m.MQTT_TOPIC),
                         ("openf1", "mqtt.openf1.org", 8883, "v1/weather"))

    def test_workflow_is_manual_only_and_main_only(self):
        yaml.safe_load(self.workflow_text)
        self.assertIn("on:\n  workflow_dispatch:\n", self.workflow_text)
        self.assertNotIn("schedule:", self.workflow_text)
        self.assertNotIn("push:", self.workflow_text)
        self.assertIn("if: github.ref == 'refs/heads/main'", self.workflow_text)

    def test_least_permissions_and_checkout_credentials_disabled(self):
        self.assertIn("permissions:\n  contents: read\n  id-token: write\n  attestations: write\n", self.workflow_text)
        self.assertNotIn("contents: write", self.workflow_text)
        self.assertIn("persist-credentials: false", self.workflow_text)
        uses = re.findall(r"uses: ([^\s]+)", self.workflow_text)
        self.assertTrue(uses)
        self.assertTrue(all(re.search(r"@[0-9a-f]{40}$", item) for item in uses))

    def test_exact_secret_names_and_no_secret_literals(self):
        self.assertEqual(set(re.findall(r"secrets\.([A-Z0-9_]+)", self.workflow_text)),
                         {"OPENF1_USERNAME", "OPENF1_PASSWORD"})
        self.assertNotIn(self.base_env["OPENF1_USERNAME"], self.workflow_text + self.script_text)
        self.assertNotIn(self.base_env["OPENF1_PASSWORD"], self.workflow_text + self.script_text)

    def test_missing_credentials_fail_closed(self):
        for missing in ("OPENF1_USERNAME", "OPENF1_PASSWORD"):
            env = dict(self.base_env)
            env.pop(missing)
            with self.subTest(missing=missing):
                result, _ = self.execute(environ=env)
                self.assertEqual(result["status"], m.HOLD)
                self.assertIn("missing_openf1_", result["manifest"]["reason_codes"][0])

    def test_token_endpoint_method_and_content_type_are_fixed(self):
        observed = {}

        def fake_urlopen(request, timeout, context):
            observed.update(request=request, timeout=timeout, context=context)
            return Response(b'{"access_token":"token","expires_in":3600}')

        with mock.patch.object(m.urllib.request, "urlopen", side_effect=fake_urlopen):
            token, expires = m.acquire_openf1_token("user", "password")
        request = observed["request"]
        self.assertEqual(request.full_url, "https://api.openf1.org/token")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Content-type"], "application/x-www-form-urlencoded")
        self.assertEqual((token, expires), ("token", 3600))
        self.assertIsInstance(observed["context"], m.ssl.SSLContext)

    def test_documented_string_token_expiry_normalizes_to_integer_manifest_seconds(self):
        response = Response(b'{"access_token":"token","expires_in":"3600"}')
        with mock.patch.object(m.urllib.request, "urlopen", return_value=response):
            result, _ = self.execute(
                token_fetcher=lambda username, password: m.acquire_openf1_token(username, password)
            )
        expires = result["manifest"]["token_declared_expires_in_seconds"]
        self.assertEqual(expires, 3600)
        self.assertIs(type(expires), int)

    def test_token_expiry_rejects_boolean_malformed_and_non_positive_values(self):
        invalid_values = (True, False, "", "0", "-1", "+1", "1.0", " 3600 ", "abc", 0, -1, 1.0)
        for expires in invalid_values:
            with self.subTest(expires=expires):
                body = json.dumps({"access_token": "token", "expires_in": expires}).encode()
                with mock.patch.object(m.urllib.request, "urlopen", return_value=Response(body)):
                    with self.assertRaises(m.CaptureHold) as caught:
                        m.acquire_openf1_token("user", "password")
                self.assertEqual(str(caught.exception), "openf1_token_expiry_invalid")

    def test_credentials_and_token_never_serialize(self):
        result, _ = self.execute()
        all_bytes = b"".join(path.read_bytes() for path in result["root"].rglob("*") if path.is_file())
        for secret in (self.base_env["OPENF1_USERNAME"], self.base_env["OPENF1_PASSWORD"], "memory-token-value"):
            self.assertNotIn(secret.encode(), all_bytes)

    def test_auth_and_network_errors_are_sanitized(self):
        error = urllib.error.HTTPError(
            m.TOKEN_ENDPOINT, 401, "secret-password-value token-body", {}, None
        )
        with mock.patch.object(m.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(m.CaptureHold) as caught:
                m.acquire_openf1_token("secret-user", "secret-password-value")
        self.assertEqual(str(caught.exception), "openf1_token_request_failed")

    def test_tls_certificate_verification_cannot_be_disabled(self):
        self.assertGreaterEqual(self.script_text.count("ssl.create_default_context()"), 2)
        for forbidden in ("CERT_NONE", "check_hostname = False", "verify=False", "tls_insecure_set(True)"):
            self.assertNotIn(forbidden, self.script_text)

    def test_mqtt_endpoint_tls_and_no_reconnect_loop_are_fixed(self):
        self.assertIn("client.connect(MQTT_BROKER, MQTT_PORT", self.script_text)
        self.assertIn("client.tls_set_context(ssl.create_default_context())", self.script_text)
        self.assertIn("reconnect_on_failure=False", self.script_text)
        self.assertNotIn("client.reconnect(", self.script_text)
        self.assertEqual(m.MQTT_CLIENT_USERNAME, "f1-data-publisher-shadow")

    def test_topic_is_single_exact_and_has_no_wildcard(self):
        self.assertEqual(m.MQTT_TOPIC, "v1/weather")
        self.assertNotIn("#", m.MQTT_TOPIC)
        self.assertNotIn("+", m.MQTT_TOPIC)
        self.assertIn("client.subscribe(MQTT_TOPIC, qos=0)", self.script_text)

    def test_hard_capture_bounds(self):
        self.assertEqual((m.CAPTURE_MAX_SECONDS, m.CAPTURE_MAX_MESSAGES), (180, 500))
        too_many = [
            {"topic": m.MQTT_TOPIC, "raw_json_bytes": raw({"_id": i, "_key": str(i)}), "received_order_index": i}
            for i in range(501)
        ]
        result, _ = self.execute(messages=too_many)
        self.assertEqual(result["status"], m.HOLD)
        self.assertIn("message_bound_exceeded", result["manifest"]["reason_codes"])

    def test_zero_messages_hold(self):
        result, _ = self.execute(messages=[])
        self.assertEqual(result["status"], m.HOLD)
        self.assertEqual(result["manifest"]["message_count"], 0)
        self.assertIn("zero_messages_captured", result["manifest"]["reason_codes"])

    def test_exact_mqtt_payload_bytes_are_preserved_and_hashed(self):
        result, _ = self.execute()
        for source, binding in zip(self.messages, result["manifest"]["messages"]):
            stored = (result["root"] / binding["relative_path"]).read_bytes()
            self.assertEqual(stored, source["raw_json_bytes"])
            self.assertEqual(binding["raw_json_sha256"], hashlib.sha256(stored).hexdigest())

    def test_malformed_message_holds_instead_of_drop(self):
        messages = [{"topic": m.MQTT_TOPIC, "raw_json_bytes": b"{", "received_order_index": 0}]
        result, _ = self.execute(messages=messages)
        self.assertEqual(result["status"], m.HOLD)
        self.assertEqual(result["manifest"]["message_count"], 1)
        self.assertEqual((result["root"] / "messages/message-000000.bin").read_bytes(), b"{")

    def test_duplicate_id_or_k2_hold_causes_capture_hold(self):
        messages = [
            {"topic": m.MQTT_TOPIC, "raw_json_bytes": raw({"_id": 1, "_key": "a"}), "received_order_index": 0},
            {"topic": m.MQTT_TOPIC, "raw_json_bytes": raw({"_id": 1, "_key": "b"}), "received_order_index": 1},
        ]
        result, _ = self.execute(messages=messages)
        self.assertEqual(result["status"], m.HOLD)
        self.assertEqual(result["k2_result"]["status"], m.K2_HOLD)

    def test_valid_synthetic_messages_compose_through_k2(self):
        result, _ = self.execute()
        self.assertEqual(result["status"], m.SUCCESS)
        self.assertEqual(result["k2_result"]["status"], m.K2_VALIDATED)
        self.assertEqual((result["manifest"]["min_observed_id"], result["manifest"]["max_observed_id"]), (4, 9))

    def test_k2_hash_and_message_manifest_bindings_are_exact(self):
        result, _ = self.execute()
        k2_bytes = (result["root"] / "stream_version_evidence.json").read_bytes()
        self.assertEqual(result["manifest"]["k2_result_sha256"], hashlib.sha256(k2_bytes).hexdigest())
        manifest = json.loads((result["root"] / "capture_execution_manifest.json").read_bytes())
        self.assertEqual(manifest, result["manifest"])

    def test_k1_coverage_is_not_fabricated(self):
        result, _ = self.execute()
        self.assertFalse(result["manifest"]["k1_observer_coverage_supplied"])
        self.assertFalse(result["manifest"]["declared_window_schedule_coverage_proven"])
        self.assertFalse(result["k2_result"]["k1_observer_coverage_supplied"])

    def test_manifest_binds_exact_workflow_identity(self):
        result, env = self.execute()
        manifest = result["manifest"]
        self.assertEqual(manifest["repository"], env["GITHUB_REPOSITORY"])
        self.assertEqual(manifest["workflow_path"], m.WORKFLOW_PATH)
        self.assertEqual(manifest["workflow_ref"], env["GITHUB_WORKFLOW_REF"])
        self.assertEqual(manifest["git_ref"], "refs/heads/main")
        self.assertEqual(manifest["implementation_git_sha"], env["GITHUB_SHA"])
        self.assertEqual(manifest["github_run_id"], env["GITHUB_RUN_ID"])
        self.assertEqual(manifest["github_run_attempt"], env["GITHUB_RUN_ATTEMPT"])

    def test_all_required_trust_ceilings_remain_false(self):
        result, _ = self.execute()
        for field in m.TRUST_CEILINGS:
            self.assertIs(result["manifest"][field], False)

    def test_caller_cannot_assert_unsupported_trust_true(self):
        for field in m.TRUST_CEILINGS:
            with self.subTest(field=field):
                result, _ = self.execute(unsupported_claims={field: True})
                self.assertEqual(result["status"], m.HOLD)

    def test_future_attestation_subject_is_exact_manifest(self):
        result, env = self.execute()
        subject = result["root"] / "capture_execution_manifest.json"
        statement = {"subject": [{"name": subject.name, "digest": {"sha256": hashlib.sha256(subject.read_bytes()).hexdigest()}}]}
        bundle = {"dsseEnvelope": {"payload": base64.b64encode(json.dumps(statement).encode()).decode()}}
        bundle_path = Path(self.temp.name) / "bundle.json"
        bundle_bytes = json.dumps(bundle).encode()
        bundle_path.write_bytes(bundle_bytes)
        env.update({
            "ATTESTATION_BUNDLE_PATH": str(bundle_path),
            "ATTESTATION_ID": "123",
            "ATTESTATION_URL": "https://github.com/" + env["GITHUB_REPOSITORY"] + "/attestations/123",
        })
        metadata = m.preserve_attestation_from_env(environ=env, output_base=self.output)
        self.assertEqual(metadata["subject_relative_path"], "capture_execution_manifest.json")
        self.assertEqual((result["root"] / "github_attestation.bundle.json").read_bytes(), bundle_bytes)
        self.assertIn("subject-path: _runtime/dr002_pre2b7k_openf1_stream_capture_shadow/gha-${{ github.run_id }}-${{ github.run_attempt }}/capture_execution_manifest.json", self.workflow_text)

    def test_no_repo_write_push_dispatch_stable_or_protected_paths(self):
        combined = self.workflow_text + self.script_text
        for forbidden in ("git push", "git commit", "contents: write", "workflow_dispatches", "Engine_2026-06-07_STABLE", "workbook", "latest/", "history/", "ledger"):
            self.assertNotIn(forbidden, combined)

    def test_no_pipedream_or_gmail(self):
        combined = (self.workflow_text + self.script_text).lower()
        self.assertNotIn("pipedream", combined)
        self.assertNotIn("gmail", combined)

    def test_tests_use_no_real_network(self):
        with mock.patch.object(m.urllib.request, "urlopen") as urlopen:
            result, _ = self.execute()
        urlopen.assert_not_called()
        self.assertEqual(result["status"], m.SUCCESS)

    def test_named_dependency_blobs_unchanged(self):
        expected = {
            "scripts/forecast_bundles/dr002_openf1_stream_version_evidence_v1.py": "503f422ca511eff56544a4d66b312c9fbc501dbe",
            "tests/test_dr002_openf1_stream_version_evidence_v1.py": "c0a1a9138e0aa524167b840cc1de136ecb8284d6",
            "docs/DR002_PRE2B7K2_OPENF1_STREAM_VERSION_EVIDENCE_CONTRACT_2026-10-07.md": "49b125855db50c04c628c6c734ef8c94c3701115",
            "scripts/forecast_bundles/dr002_observer_coverage_contract_v1.py": "e0794e3c901b70a636b5d552ffd673576aeea412",
            "docs/DR002_PRE2B7K1_OBSERVER_COVERAGE_COMPLETENESS_CONTRACT_2026-10-07.md": "63d5e579ed7c95a74e0fdf878bb37c366b90c9e3",
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob_sha((ROOT / path).read_bytes()), digest)


if __name__ == "__main__":
    unittest.main()
