"""Mechanical one-shot send ledger for local gating. Sandbox-only; does not send email."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any
import json, hashlib, time

class SendLatchError(Exception):
    pass

@dataclass
class SendAttempt:
    gate_id: str
    subject: str
    body_sha256: str
    status: str
    route: str
    message_id: str | None = None
    error: str | None = None
    timestamp: float = 0.0

class SendLatch:
    def __init__(self, ledger_path: str | Path):
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self.ledger_path.write_text(json.dumps({"attempts": []}, indent=2), encoding="utf-8")

    def _read(self) -> Dict[str, Any]:
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))

    def _write(self, obj: Dict[str, Any]) -> None:
        self.ledger_path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def body_hash(body: str) -> str:
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def preflight(self, gate_id: str, subject: str, body: str, route: str = "inline") -> Dict[str, Any]:
        ledger = self._read()
        body_sha = self.body_hash(body)
        for att in ledger["attempts"]:
            if att["gate_id"] == gate_id and att["status"] == "SEND_SUCCEEDED_MESSAGE_ID_RETURNED":
                raise SendLatchError("gate_already_sent")
            if att["gate_id"] == gate_id and att.get("body_sha256") == body_sha and att.get("route") == route and att["status"].startswith("SEND_ATTEMPT_FAILED"):
                raise SendLatchError("same_failed_route_and_body_retry_blocked")
        return {"gate_id": gate_id, "subject": subject, "body_sha256": body_sha, "route": route, "send_authorized": True}

    def record_failed(self, gate_id: str, subject: str, body: str, route: str, error: str) -> None:
        ledger = self._read()
        ledger["attempts"].append(asdict(SendAttempt(gate_id, subject, self.body_hash(body), "SEND_ATTEMPT_FAILED_NO_MESSAGE_ID", route, None, error, time.time())))
        self._write(ledger)

    def record_success(self, gate_id: str, subject: str, body: str, route: str, message_id: str) -> None:
        ledger = self._read()
        for att in ledger["attempts"]:
            if att["gate_id"] == gate_id and att["status"] == "SEND_SUCCEEDED_MESSAGE_ID_RETURNED":
                raise SendLatchError("second_success_record_blocked")
        ledger["attempts"].append(asdict(SendAttempt(gate_id, subject, self.body_hash(body), "SEND_SUCCEEDED_MESSAGE_ID_RETURNED", route, message_id, None, time.time())))
        self._write(ledger)
