"""Exact retained São Paulo evidence replay; never fabricate availability or locks.

Original source/manifest bytes are copied into an isolated replay root. Derived
selectors are generated at replay time and are not original historical receipts.
The first scientific boundary is HOLD: per-source observation times and the full
original session catalog were not retained in this chosen snapshot.
"""
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_f1_1b_integrated_recovery_weekend_replay as chain

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'history/session_data_processor/2026_1299_brazil_s_o_paulo_interlagos/20261108T142405Z/qualifying_11408'
EXPECTED = {'forecast_bundle_ledger_snapshot.json': {'blob': '22f6d5a03b08d6066af5c6ce8cefaec251b55f85',
                                          'bytes': 754,
                                          'sha256': '2f5b5b2eb1fc0000897b6ffeb84d3231a00b0a6027a34ba6b9cc63fa86b79e67'},
 'raw/openf1_drivers.json': {'blob': 'b3820c3a5ad2b66d75a59255134e665660ad8db4',
                             'bytes': 10746,
                             'sha256': 'bda486edf26808dc61ba79399a1b6d4d5770b22d2d011f7629f23a67cd0906ca'},
 'raw/openf1_intervals.json': {'blob': '0637a088a01e8ddab3bf3fa98dbe804cbde1a0dc',
                               'bytes': 2,
                               'sha256': '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'},
 'raw/openf1_laps.json': {'blob': 'a012ab97169ece4cfc96fb6b69591a60caaff488',
                          'bytes': 286520,
                          'sha256': 'b8e3efacc4f15870d7cd9aedf878e2ff4c58d212459bb137bd8b15e40aafe428'},
 'raw/openf1_pit.json': {'blob': '47d4ce2430667038bec2a899038f5656f6a314ca',
                         'bytes': 19207,
                         'sha256': '0a6527e4317b78ed04c3c02e7bb6ef416a820632f6fa918f8c1c7c7eb870e8ec'},
 'raw/openf1_position.json': {'blob': '3913d71d43937e3af7346e95f6f52554ab34d722',
                              'bytes': 285201,
                              'sha256': '6fc3ffaa68c62b5b3e7fc96cb8c10f32c34d6d4192cd61b75afbd818c5ec871c'},
 'raw/openf1_race_control.json': {'blob': 'a6b408502dc57bd674b9f76eff8ef8c6e83ed8f5',
                                  'bytes': 30066,
                                  'sha256': 'a0eed0f8a6dcee219894c84663bac634fcd75a8c3f797938681c8d17facb9248'},
 'raw/openf1_session_result.json': {'blob': '0afd4e16f870d2f1c2134c3720ce183c0e0e3cce',
                                    'bytes': 6910,
                                    'sha256': '6c8a94dcc5ee36a09d4a6f1e7844bf158a08f82b1a5b4d894b3ac587e46b7dd4'},
 'raw/openf1_sessions.json': {'blob': '662e18448460ec1065d7dee895a55fa63a08060b',
                              'bytes': 474,
                              'sha256': '85eff2b65cd3a811935d9badf5b7844b250075241939df0b0d1d5fc121cb4b85'},
 'raw/openf1_starting_grid.json': {'blob': '0ddb72f38a3532f39398dec8aee132f4f7abcb2f',
                                   'bytes': 2891,
                                   'sha256': 'd76c5c9f1afb359826338f296d4e6601e75c60f17de4d6e003bddd9ce015f4ae'},
 'raw/openf1_stints.json': {'blob': 'f7a86743ca55e76085e59f9a144e356c87605c1d',
                            'bytes': 16439,
                            'sha256': 'feb957d03f781e83cb17bce168824f6c249afd769da3cd2a0d9485bb83a834b5'},
 'raw/openf1_weather.json': {'blob': '0dbd4fa44e204daec9e312971cd11fef9e7b4f86',
                             'bytes': 44849,
                             'sha256': '36964208d1c12eeb7181876aea75469378d3f8c27af3c97ef7df912c32ca1b27'},
 'sandbox_workbook_update_plan.json': {'blob': '0dec74a7578416be9508d5111c38248a31808306',
                                       'bytes': 423,
                                       'sha256': 'd4785622215792e253a98eac3c225771ab4c8cf0d029e042a8f900a81fcc76ed'},
 'source_readiness_manifest.json': {'blob': '15b464f2419b4a37dcd5d04ae0b584fbdf87607d',
                                    'bytes': 20317,
                                    'sha256': '23c8dd59bd97b3f7681ae702d7d607b5af1a51694ec9cce440b71e2192c317a8'},
 'workbook_kpi_readiness.csv': {'blob': 'fb6029bff647815627ec7accd05056208ecc2752',
                                'bytes': 403,
                                'sha256': '96df17cb3d0d6bc8de8e22b4629b9a893704a9999007410b26ae4593759caa06'},
 'workbook_kpi_readiness.json': {'blob': '54b0bc643d42dfe9c070fe2602fddd596b510856',
                                 'bytes': 2058,
                                 'sha256': '802c5a0617e0a0073819cc83c12d70cde823e10bf6fc6c43e52af0a501034ec1'}}
COUNTS = {'drivers':22, 'laps':391, 'position':1885, 'weather':160,
          'session_result':22, 'race_control':96, 'pit':82, 'stints':82,
          'starting_grid':22, 'sessions':1, 'intervals':0}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class RetainedSaoPauloReplayTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root=Path(temp.name)
        self.original={}
        self.source_rel='latest/session_data_processor/2026_1299_brazil_s_o_paulo_interlagos/qualifying_11408'
        for relative, expected in EXPECTED.items():
            raw=(ARCHIVE/relative).read_bytes()
            self.assertEqual((len(raw),sha(raw)),(expected['bytes'],expected['sha256']),relative)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),expected['blob'])
            self.original[relative]=raw
            path=self.root/self.source_rel/relative; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
        self.source=json.loads(self.original['source_readiness_manifest.json'])
        self.selector={'latest_session_data_processor_manifest':self.source_rel+'/source_readiness_manifest.json'}
        self.now=datetime.now(timezone.utc)

    def source_checks(self):
        reasons=[]
        chain.dashboard.verify_current_bytes(self.root,self.selector,self.source,{},
            self.source['readiness_aggregation']['per_source'],self.now,reasons)
        return reasons

    def test_retained_bytes_identity_counts_and_driver_membership_are_exact(self):
        self.assertEqual(self.source['session']['session_key'],11408)
        self.assertEqual(self.source['session']['meeting_key'],1299)
        roster={row['driver_number'] for row in json.loads(self.original['raw/openf1_drivers.json'])}
        self.assertEqual(len(roster),22)
        for endpoint,count in COUNTS.items():
            raw=self.original[f'raw/openf1_{endpoint}.json']; rows=json.loads(raw)
            self.assertEqual(len(rows),count,endpoint)
            self.assertEqual(sha(raw),self.source['sources'][f'openf1_{endpoint}']['json_sha256'])
            for row in rows:
                self.assertEqual((row['meeting_key'],row['session_key']),(1299,11408),endpoint)
                if row.get('driver_number') is not None:
                    self.assertIn(row['driver_number'],roster,endpoint)
        self.assertEqual(self.source['created_utc'],'2026-11-08T14:24:14.931133Z')
        self.assertNotIn('session_schedule_snapshot',self.source)
        for report in self.source['sources'].values():
            self.assertNotIn('observed_at_utc',report)

    def test_real_source_replay_holds_without_replacing_missing_custody(self):
        reasons=self.source_checks()
        expected={f'source_bytes_unverified:openf1_{e}:availability_clock'
                  for e in ('drivers','laps','position','weather','session_result')}
        self.assertTrue(expected.issubset(reasons),reasons)
        # Derived selector files are explicitly present-time replay outputs.
        with patch.object(chain.processor,'ROOT',self.root):
            chain.processor.write_latest_public_manifests(self.root/self.source_rel,self.source,{})
        with patch.object(sys,'argv',['workbook','--repo-root',str(self.root)]),contextlib.redirect_stdout(io.StringIO()):
            chain.workbook.main()
        state=chain.dashboard.discover_state(self.root)
        self.assertFalse(state['downstream_eligible']); self.assertFalse(state['prediction_locked'])
        self.assertFalse(state['stable_engine_executed'])
        self.assertIn('missing_or_invalid_session_schedule_snapshot',state['readiness_reasons'])
        self.assertFalse(list((self.root/'latest/workbook_kpi_refresh_applier').glob('*.xlsx')))
        self.assertFalse((self.root/'latest/forecast_bundles').exists())
        for relative,raw in self.original.items():
            self.assertEqual((ARCHIVE/relative).read_bytes(),raw)
            self.assertEqual((self.root/self.source_rel/relative).read_bytes(),raw)
        if os.environ.get('F1_RECOVERY_REPORT_DIR'):
            target=Path(os.environ['F1_RECOVERY_REPORT_DIR'])/'retained_sao_paulo_replay.json'
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(dict(evaluated_utc=datetime.now(timezone.utc).isoformat(),
                replay_type='RETROSPECTIVE_ONLY',archive_path=ARCHIVE.relative_to(ROOT).as_posix(),
                original_manifest_created_utc=self.source['created_utc'],fingerprints=EXPECTED,
                source_row_counts=COUNTS,source_byte_identity='PASS',
                first_invalid_boundary='HOLD_SOURCE_AVAILABILITY_CLOCK_NOT_RETAINED',
                source_hold_reasons=sorted(expected),dashboard=state,
                prediction_locked=False,stable_engine_executed=False,original_bytes_unchanged=True),indent=2))

    def test_corrupted_replay_copy_is_rejected_without_touching_archive(self):
        path=self.root/self.source_rel/'raw/openf1_laps.json';path.write_bytes(path.read_bytes()+b' ')
        self.assertIn('source_bytes_unverified:openf1_laps:digest',self.source_checks())
        self.assertEqual((ARCHIVE/'raw/openf1_laps.json').read_bytes(),self.original['raw/openf1_laps.json'])
