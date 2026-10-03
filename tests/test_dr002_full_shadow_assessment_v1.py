import ast
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('assessment',Path(__file__).resolve().parents[1]/'scripts/forecast_bundles/dr002_full_shadow_assessment_v1.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint=b'synthetic accepted checkpoint'
        producer=b'def find_sources(repo):\n    return repo.rglob("drivers.csv")\n'
        locker=b'config={"stable_baseline":"Engine_2026-06-07_STABLE"}\nmanifest={"blind_validation_eligible":source_found}\n'
        codes={a.PRODUCER_PATH:producer,a.LOCKER_PATH:locker}
        self.kw=dict(checkpoint_bytes=self.checkpoint,artifacts={rid:{**v,'expired':False} for rid,v in a.ARTIFACTS.items()},
            runs={rid:dict(id=rid,head_sha=v,run_attempt=1,event='workflow_dispatch',conclusion='success') for rid,v in a.HEADS.items()},
            dependency_bytes=codes,dependency_fingerprints=[dict(path=p,blob_sha=a.blob_sha(b)) for p,b in codes.items()],observed_main_sha='a'*40)
    def go(self):
        with patch.object(a,'CHECKPOINT_SHA256',a.sha256(self.checkpoint)):return a.assess(**self.kw)
    def layer(self,name):return next(r for r in self.go()['matrix'] if r['layer']==name)
    def test_all_layers_explicit(self):self.assertEqual(tuple(r['layer'] for r in self.go()['matrix']),a.LAYERS)
    def test_states_vocabulary(self):self.assertTrue(all(r['status'] in a.STATUSES for r in self.go()['matrix']))
    def test_completed_with_holds(self):self.assertEqual(self.go()['assessment_result'],'COMPLETED');self.assertEqual(self.layer('readiness for production enforcement')['status'],'HOLD')
    def test_live_claim_ceiling(self):self.assertEqual(self.layer('producer execution')['status'],'PROVEN_LIVE');self.assertIn('execution-shadow',self.layer('producer execution')['strongest_defensible_claim'])
    def test_no_zip_reinspection_claim(self):self.assertIn('No ZIP re-download',self.go()['evidence_basis'])
    def test_engine_not_proven(self):self.assertEqual(self.layer('engine execution')['status'],'NOT_PROVEN')
    def test_lock_not_proven(self):self.assertEqual(self.layer('forecast lock')['status'],'NOT_PROVEN')
    def test_outcome_not_proven(self):self.assertEqual(self.layer('outcome boundary')['status'],'NOT_PROVEN')
    def test_revision_not_proven(self):self.assertEqual(self.layer('revision handling')['status'],'NOT_PROVEN')
    def test_offline_capabilities_separate(self):self.assertTrue(all(x['status']=='CONTRACT_PROVEN_OFFLINE' for x in self.go()['contract_capabilities']))
    def test_unbound(self):self.assertEqual(self.go()['trust']['binding_status'],'UNBOUND')
    def test_authentication_false(self):self.assertIs(self.go()['trust']['production_authenticated'],False);self.assertEqual(self.layer('external binding/authentication')['status'],'NOT_PROVEN')
    def test_postevent_not_blind(self):c=self.go()['integrity_classification'];self.assertEqual(c['state'],'OUTCOME_AWARE_EVALUATION_ONLY');self.assertFalse(c['blind_validation_eligible'])
    def test_no_historical_upgrade(self):self.assertIs(self.go()['trust']['historical_availability_proven'],False);self.assertEqual(self.layer('historical availability')['status'],'NOT_PROVEN')
    def test_production_discovery_inspected(self):self.assertEqual(self.go()['production_inspection']['broad_discovery'][0]['function'],'find_sources');self.assertEqual(self.layer('current production-producer containment')['status'],'HOLD')
    def test_stable_label_not_proof(self):self.assertEqual(self.layer('stable-engine provenance')['status'],'NOT_PROVEN');self.assertTrue(self.go()['production_inspection']['lane_labels'])
    def test_source_found_bug_reported(self):self.assertTrue(self.go()['production_inspection']['source_found_blind'])
    def test_tampered_digest(self):self.kw['artifacts'][37152568516]['digest']='sha256:'+'0'*64;self.assertEqual(self.go()['assessment_result'],'HOLD');self.assertEqual(self.layer('producer execution')['status'],'HOLD')
    def test_wrong_artifact_id(self):self.kw['artifacts'][37152568516]['id']=1;self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_wrong_artifact_name(self):self.kw['artifacts'][37152568516]['name']='other';self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_missing_artifact(self):self.kw['artifacts'].pop(37133694090);self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_expired_artifact(self):self.kw['artifacts'][37152568516]['expired']=True;self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_wrong_run_head(self):self.kw['runs'][37152568516]['head_sha']='0'*40;self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_wrong_attempt(self):self.kw['runs'][37152568516]['run_attempt']=2;self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_unsuccessful_run(self):self.kw['runs'][37152568516]['conclusion']='failure';self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_checkpoint_tampering(self):self.kw['checkpoint_bytes']=b'changed';self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_dependency_change(self):self.kw['dependency_bytes'][a.PRODUCER_PATH]+=b'\n';self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_missing_dependency(self):self.kw['dependency_bytes'].pop(a.PRODUCER_PATH);self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_unknown_inspection_pattern_holds(self):
        self.kw['dependency_bytes'][a.PRODUCER_PATH]=b'def find_sources(repo): return []'
        self.kw['dependency_fingerprints'][0]['blob_sha']=a.blob_sha(self.kw['dependency_bytes'][a.PRODUCER_PATH]);self.assertEqual(self.go()['assessment_result'],'HOLD')
    def test_no_mutation(self):before=copy.deepcopy(self.kw);self.go();self.assertEqual(before,self.kw)
    def test_deterministic(self):self.assertEqual(a.canonical_json_bytes(self.go()),a.canonical_json_bytes(self.go()))
    def test_no_forecast_or_activation(self):r=self.go();self.assertFalse(r['production_forecast_generated']);self.assertFalse(r['trust']['dr002_activated']);self.assertFalse(r['gate2b6_started']);self.assertFalse(r['gate2b7_started'])
    def test_no_fabricated_bindings_or_receipts(self):r=self.go();self.assertNotIn('verified_receipt_bindings',r);self.assertNotIn('receipts',r)
    def test_no_io_network_clock_discovery(self):
        tree=ast.parse(Path(a.__file__).read_text());names={x.name for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)) for x in n.names};attrs={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and not (isinstance(n.value,ast.Name) and n.value.id=='ast')}
        self.assertFalse(names&{'requests','urllib','random','uuid','datetime','glob'});self.assertFalse(attrs&{'glob','rglob','walk','iterdir','now','open','read_bytes','write_bytes','write_text','listdir','scandir'})
    def test_unrelated_main_movement_not_hold(self):self.kw['observed_main_sha']='b'*40;self.assertEqual(self.go()['assessment_result'],'COMPLETED')
if __name__=='__main__':unittest.main()
