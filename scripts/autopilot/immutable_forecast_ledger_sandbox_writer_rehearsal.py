#!/usr/bin/env python3
"""01H sandbox-only immutable forecast ledger writer rehearsal."""
import argparse,hashlib,json,tempfile
from pathlib import Path
G={"production_automation":"OFF","forecast_gate":"OFF","promotion_allowed":False,"stable_engine_modified":False,"canonical_workbook_overwrite":False}
BAD=("engine_2026-06-07_stable","canonical workbook","canonical_workbook","prediction_model_data_workbook",".github",".git",".env")
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha(r):
    u=dict(r); u.pop("record_hash",None); return hashlib.sha256(canon(u).encode()).hexdigest()
def record(prev=None):
    r={"schema_name":"immutable_forecast_ledger_record","schema_version":"2026-06-18_01h","record_type":"sandbox_writer_rehearsal","forecast_id":"SANDBOX-REHEARSAL-01H","source_workstream":"1B/1C Engine Optimization","enhancement_id":"enhancement_01h_immutable_forecast_ledger_sandbox_writer_rehearsal","prediction_generated":False,"guardrails":G,"forecast_payload":{"forecast_scope":"none; rehearsal only","prediction_values":[],"activation_status":"NOT_ACTIVATED","promotion_status":"NOT_PROMOTED"},"previous_record_hash":prev,"record_hash":""}
    r["record_hash"]=sha(r); return r
def check_path(p):
    s="/".join(x.lower() for x in Path(p).expanduser().resolve(strict=False).parts)
    if any(b in s for b in BAD): raise ValueError("forbidden path")
    if "sandbox" not in s and "tmp" not in s: raise ValueError("output must be sandbox/tmp only")
def check_record(r):
    assert r["prediction_generated"] is False
    assert r["guardrails"]==G
    assert r["record_hash"]==sha(r)
def append(p,r,write=False):
    check_path(p); check_record(r); line=canon(r)
    if write:
        p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); p.open("a",encoding="utf-8").write(line+"\n")
    return line
def selfcheck():
    r=record()
    with tempfile.TemporaryDirectory(prefix="f1_01h_sandbox_") as d:
        p=Path(d)/"sandbox_artifacts"/"ledger.jsonl"; append(p,r,True); assert p.read_text().count("\n")==1
    try: append(Path("Engine_2026-06-07_STABLE/ledger.jsonl"),r,False)
    except ValueError: return
    raise SystemExit("stable path was not rejected")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",default="sandbox_artifacts/immutable_forecast_ledger/rehearsal_ledger.jsonl"); ap.add_argument("--previous-record-hash"); ap.add_argument("--write",action="store_true"); ap.add_argument("--self-check",action="store_true"); a=ap.parse_args()
    if a.self_check: selfcheck(); print("SELF_CHECK_OK"); return 0
    print(append(Path(a.output),record(a.previous_record_hash),a.write)); return 0
if __name__=="__main__": raise SystemExit(main())
