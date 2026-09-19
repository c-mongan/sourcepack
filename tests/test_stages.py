import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sourcelens import workflow as w
from sourcelens.contracts import ContractError
from sourcelens.stages import run_stage, invalidate

class StageTests(unittest.TestCase):
    def test_stage_reuses_hashes_and_retries_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);m={'stages':{}};calls=[]
            def action():
                calls.append(1);p=root/'a';p.write_text('yes');return [p]
            run_stage(root,m,'transcript',{},action)
            run_stage(root,m,'transcript',{},action)
            self.assertEqual(len(calls),1)
            (root/'a').write_text('tamper')
            with self.assertRaises(ContractError):run_stage(root,m,'transcript',{},action)
    def test_invalidation_is_scoped(self):
        m={'stages':{k:{'status':'ok'} for k in ['metadata','transcript','video','visual-index','report']}}
        invalidate(m,'video')
        self.assertEqual(m['stages']['transcript']['status'],'ok')
        self.assertEqual(m['stages']['visual-index']['status'],'pending')
    def test_partial_transcript_and_question_change_do_not_reacquire(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);run=root/'run'
            def acquire(run,m):
                p=run/'acquired/a.md';p.write_text('Setting limit is seven.')
                m['imports']=[{'path':'acquired/a.md','format':None}]
                m['stages']={'video':{'status':'failed','error':'403'}}
                m['gaps'].append('video: 403')
            with patch.object(w,'source_identity',return_value={'kind':'youtube','source':'url'}),patch.object(w,'extract_youtube',side_effect=acquire) as a:
                result=w.prepare('url',run,question='explain')
                self.assertEqual(result['status'],'ready_partial')
                self.assertIn('ticket',w.next_ticket(run))
                w.prepare('url',run,question='follow-up')
                self.assertEqual(a.call_count,1)
                self.assertEqual(len(w.load(run)[1]['analysis_requests']),2)
    def test_v1_upgrade_keeps_original(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'a.md';source.write_text('test');run=root/'run'
            w.prepare(str(source),run);p=run/'run.json';m=json.loads(p.read_text());m['schema']='sourcepack.run.v1';p.write_text(json.dumps(m))
            old=p.read_bytes();w.upgrade_run(run)
            self.assertEqual((run/'run.v1.json').read_bytes(),old)
            self.assertEqual(w.load(run)[1]['schema'],'sourcepack.run.v2')
