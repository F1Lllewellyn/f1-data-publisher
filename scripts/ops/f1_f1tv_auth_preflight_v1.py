#!/usr/bin/env python3
"""Non-disclosing F1TV GitHub Actions authentication preflight.

Authenticates using the official FastF1 CLI in a bounded child process with
stdout/stderr discarded. Emits only a coarse status enum and observation clock.
A valid account token does NOT establish live packet custody, event identity,
or eligibility for a protected-engine prospective prediction.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

PASS = "AUTH_TOKEN_VALID_LIVE_TIMING_UNVERIFIED"
MISSING = "HOLD_F1TV_REPOSITORY_SECRETS_NOT_AVAILABLE"
REJECTED = "HOLD_F1TV_LOGIN_REJECTED_OR_PROVIDER_UNAVAILABLE"
NO_TOKEN = "HOLD_F1TV_VALID_AUTH_TOKEN_NOT_RETAINED"
RUNTIME = "HOLD_F1TV_AUTH_PREFLIGHT_RUNTIME_ERROR"


def token_is_valid() -> bool:
    from fastf1.internals.f1account import token_manager
    token = token_manager.get_stored()
    return bool(token is not None and token.is_valid())


def verify_login(environ, *, run_command=subprocess.run, check_token=token_is_valid) -> str:
    # Do not place either secret value in output, a subprocess command line,
    # an exception, a committed file or an artifact.
    if not (environ.get("F1_USERNAME", "").strip() and environ.get("F1_PASSWORD", "").strip()):
        return MISSING
    try:
        result = run_command(
            [sys.executable, "-m", "fastf1", "auth", "f1tv", "--authenticate"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=75,
            env=dict(environ),
        )
        if result.returncode != 0:
            return REJECTED
        return PASS if check_token() else NO_TOKEN
    except Exception:
        # The exception may include login headers: do NOT preserve/print it.
        return RUNTIME


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="_runtime/f1tv_auth_preflight")
    args = parser.parse_args(argv)
    status = verify_login(os.environ)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "f1tv-auth-preflight-v1",
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "result": status,
        "live_timing_packets_verified": False,
        "original_source_bytes_verified": False,
        "stable_engine_executed": False,
        "prospective_forecast_authorized": False,
        "credentials_or_token_exported_in_repository_or_artifact": False,
    }
    (out / "status.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("F1TV authentication preflight result:", status)
    return 0 if status == PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
