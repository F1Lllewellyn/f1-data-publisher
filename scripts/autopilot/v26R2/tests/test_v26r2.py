import unittest, json, base64, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v26r2_contracts import validate_patch_command, validate_merge_command, body_envelope, dispatch_payload_size
from v26r2_chunk_planner import plan_sequential_chunks
from v26r2_send_latch import SendLatch, SendLatchError
from v26r2_evidence_classifier import classify, can_claim
from v26r2_receiver_log_classifier import classify_log_text


def b64(s): return base64.b64encode(s.encode()).decode()

def valid_patch(files=None):
    files = files or [{"path":"docs/autopilot_bridge/v26R2/README.md","action":"upsert","content_base64":b64("hello"),"content_sha256":"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824","content_byte_length":5}]
    return {
        "schema_name":"f1_autopilot_patch_command","schema_version":"1.0","command_type":"assistant_patch","project":"F1_Prediction_Engine","repository":"F1Lllewellyn/f1-data-publisher","safety_mode":"pr_only","promotion_status":"NOT_PROMOTED","activation_status":"NOT_ACTIVATED","production_automation":"OFF","forecast_gate":"OFF","stable_engine_modified":False,"canonical_workbook_overwrite":False,"title":"CONTINUITY-V26R2: test","base_branch":"main","target_branch":"autopilot/v26r2-test","summary":"test summary","expected_changed_file_count":len(files),"expected_changed_files":[f["path"] for f in files],"files":files}

class TestV26R2(unittest.TestCase):
    def test_valid_patch(self):
        r=validate_patch_command(valid_patch())
        self.assertTrue(r.ok, r.errors)
    def test_missing_project_blocked(self):
        c=valid_patch(); c.pop("project")
        self.assertIn("missing_required_field:project", validate_patch_command(c).errors)
    def test_missing_summary_blocked(self):
        c=valid_patch(); c.pop("summary")
        self.assertIn("missing_required_field:summary", validate_patch_command(c).errors)
    def test_missing_action_blocked(self):
        c=valid_patch(); c["files"][0].pop("action")
        self.assertIn("files[0].unsupported_or_missing_action:None", validate_patch_command(c).errors)
    def test_bad_branch_prefix_blocked(self):
        c=valid_patch(); c["target_branch"]="f1-02h-bad"
        self.assertTrue(any(e.startswith("invalid_target_branch_prefix") for e in validate_patch_command(c).errors))
    def test_oversize_blocked(self):
        big="x"*70000
        c=valid_patch([{"path":"docs/autopilot_bridge/v26R2/big.md","action":"upsert","content_base64":b64(big)}])
        self.assertTrue(any(e.startswith("repository_dispatch_payload_oversize") for e in validate_patch_command(c).errors))
    def test_chunk_planner_under_budget(self):
        files=[]
        for i in range(5):
            content="x"*9000
            files.append({"path":f"docs/autopilot_bridge/v26R2/f{i}.md","action":"upsert","content_base64":b64(content)})
        chunks=plan_sequential_chunks(valid_patch(files), threshold=60000, branch_prefix="autopilot/v26r2-test")
        self.assertGreater(len(chunks), 1)
        for ch in chunks:
            self.assertLessEqual(dispatch_payload_size(ch), 60000)
            self.assertTrue(validate_patch_command(ch).ok)
    def test_send_latch_success_blocks_second(self):
        with tempfile.TemporaryDirectory() as d:
            l=SendLatch(Path(d)/"ledger.json")
            body="abc"
            l.preflight("g","s",body,"inline")
            l.record_success("g","s",body,"inline","m1")
            with self.assertRaises(SendLatchError): l.preflight("g","s",body,"inline")
    def test_send_latch_failed_same_route_retry_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            l=SendLatch(Path(d)/"ledger.json")
            body="abc"
            l.preflight("g","s",body,"body_file")
            l.record_failed("g","s",body,"body_file","ConnectorFileReference")
            with self.assertRaises(SendLatchError): l.preflight("g","s",body,"body_file")
    def test_evidence_dispatch_not_pr(self):
        c=classify({"status":"DISPATCH_ACCEPTED"})
        self.assertEqual(c.state,"DISPATCH_ACCEPTED")
        self.assertFalse(can_claim(c.state,"PR_STATUS_READY"))
    def test_generic_repo_inventory_no_promotion(self):
        c=classify({"status_subject":"F1 1C STATUS | REPO_INVENTORY_READY | main"})
        self.assertEqual(c.state,"NO_EVIDENCE")
    def test_main_path_not_content_hash(self):
        c=classify({"main_branch":True,"changed_path_validated":True})
        self.assertEqual(c.state,"MAIN_PATH_VALIDATED")
        self.assertFalse(can_claim(c.state,"CONTENT_HASH_READY"))
    def test_receiver_log_classification(self):
        self.assertEqual(classify_log_text("missing_required_field:summary")["primary_stage"],"VALIDATE_COMMAND_FAILED")
        self.assertEqual(classify_log_text("unsupported_action:undefined")["primary_stage"],"APPLY_COMMAND_FILES_FAILED")

    def test_raw_shell_test_command_blocked(self):
        c=valid_patch(); c["tests"]=["python scripts/autopilot/v26R2/tests/run_tests.py"]
        self.assertIn("tests[0].not_whitelisted:python scripts/autopilot/v26R2/tests/run_tests.py", validate_patch_command(c).errors)
    def test_allowed_named_receiver_test_passes_contract(self):
        c=valid_patch(); c["tests"]=["node_syntax_autopilot_scripts"]
        self.assertTrue(validate_patch_command(c).ok, validate_patch_command(c).errors)
    def test_merge_head_sha_warning(self):
        cmd={"schema_name":"x","schema_version":"1","command_type":"assistant_merge_pr","safety_mode":"approved_merge_gate","repository":"r","pull_number":1,"expected_base":"main","expected_head_prefixes":["autopilot/"],"allowed_author_logins":["F1Lllewellyn"],"allowed_path_prefixes":["docs/autopilot_bridge/"],"merge_method":"squash","production_automation":"OFF","forecast_gate":"OFF","promotion_status":"NOT_PROMOTED","activation_status":"NOT_ACTIVATED"}
        r=validate_merge_command(cmd)
        self.assertTrue(r.ok)
        self.assertTrue(any("expected_head_sha" in w for w in r.warnings))

if __name__ == '__main__': unittest.main()
