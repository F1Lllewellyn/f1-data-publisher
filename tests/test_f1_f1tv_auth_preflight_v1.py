"""Issue #367: mock-only F1TV auth preflight confidentiality and result tests."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "f1_f1tv_auth_preflight_v1",
    ROOT / "scripts/ops/f1_f1tv_auth_preflight_v1.py",
)
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)

FAKE_USER = "synthetic-user-not-real@example.invalid"
FAKE_PASSWORD = "synthetic-password-not-real"


class AuthPreflightTests(unittest.TestCase):
    def test_missing_secret_short_circuits_without_attempting_network(self):
        def never_call(*args, **kwargs):
            self.fail("Never authenticate with missing credentials")
        self.assertEqual(auth.verify_login({}, run_command=never_call), auth.MISSING)
        self.assertEqual(auth.verify_login({"F1_USERNAME": FAKE_USER}, run_command=never_call), auth.MISSING)
        self.assertEqual(auth.verify_login({"F1_PASSWORD": FAKE_PASSWORD}, run_command=never_call), auth.MISSING)

    def test_login_uses_env_not_commandline_and_discards_provider_output(self):
        def fake_run(argv, **kwargs):
            self.assertEqual(argv[1:], ["-m", "fastf1", "auth", "f1tv", "--authenticate"])
            self.assertFalse(any(FAKE_USER in a or FAKE_PASSWORD in a for a in argv))
            self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
            self.assertEqual(kwargs["timeout"], 75)
            self.assertEqual(kwargs["env"]["F1_USERNAME"], FAKE_USER)
            self.assertEqual(kwargs["env"]["F1_PASSWORD"], FAKE_PASSWORD)
            return types.SimpleNamespace(returncode=0)
        env = {"F1_USERNAME": FAKE_USER, "F1_PASSWORD": FAKE_PASSWORD}
        self.assertEqual(auth.verify_login(env, run_command=fake_run, check_token=lambda: True), auth.PASS)

    def test_failed_login_or_invalid_token_never_claims_auth_success(self):
        env = {"F1_USERNAME": FAKE_USER, "F1_PASSWORD": FAKE_PASSWORD}
        failed = lambda *a, **k: types.SimpleNamespace(returncode=1)
        success = lambda *a, **k: types.SimpleNamespace(returncode=0)
        self.assertEqual(auth.verify_login(env, run_command=failed), auth.REJECTED)
        self.assertEqual(auth.verify_login(env, run_command=success, check_token=lambda: False), auth.NO_TOKEN)

    def test_runtime_error_is_redacted(self):
        env = {"F1_USERNAME": FAKE_USER, "F1_PASSWORD": FAKE_PASSWORD}
        def fake_run(*a, **k):
            raise RuntimeError("credential data " + FAKE_PASSWORD)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(auth.verify_login(env, run_command=fake_run), auth.RUNTIME)
        self.assertNotIn(FAKE_PASSWORD, out.getvalue())

    def test_main_writes_only_sanitized_status(self):
        env = {"F1_USERNAME": FAKE_USER, "F1_PASSWORD": FAKE_PASSWORD}
        for status, expected in [(auth.MISSING, 2), (auth.PASS, 0)]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as td:
                with patch.object(auth, "verify_login", return_value=status), \
                     patch.object(auth.os, "environ", env):
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        result = auth.main(["--output-dir", td])
                self.assertEqual(result, expected)
                saved = (Path(td) / "status.json").read_text()
                self.assertEqual(json.loads(saved)["result"], status)
                self.assertFalse(json.loads(saved)["live_timing_packets_verified"])
                self.assertFalse(json.loads(saved)["prospective_forecast_authorized"])
                self.assertFalse(json.loads(saved)["credentials_or_token_exported_in_repository_or_artifact"])
                self.assertNotIn(FAKE_USER, saved + out.getvalue())
                self.assertNotIn(FAKE_PASSWORD, saved + out.getvalue())


if __name__ == "__main__":
    unittest.main()
