import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sourcelens import workflow as w
from sourcelens.contracts import ContractError
from sourcelens.quick import inspect_run, finish_run, readable_text

class QuickWorkflowTests(unittest.TestCase):
 def fixture(self, root):
  p=root/'source.md';p.write_text('A phone is visible.\n\nReview is manual.')
  run=root/'run';w.prepare(str(p),run);return run
 def notes(self, view, text='The phone displays a warning.'):
  eid=view['text_evidence_ids'][0]
  return {'schema':'sourcepack.findings.v1','review_id':view['review_id'],'inspected_ids':[eid],
          'observations':[{'text':text,'evidence_ids':[eid],'certainty':'observed'}], 'answer':f'{text} [{eid}]'}
 def test_inspect_is_read_only_and_finish_retains_searchable_findings(self):
  with tempfile.TemporaryDirectory() as td:
   run=self.fixture(Path(td));view=inspect_run(run);_,m=w.load(run)
   e=w.Engine(run/'state',run/'acquired');self.assertFalse(e.snapshot(m['jobs'][0]['job_id'])['results'])
   notes=self.notes(view);first=finish_run(run,notes);again=finish_run(run,notes)
   self.assertEqual(first,again);self.assertTrue(w.query(run,'phone message'));self.assertTrue((run/'answer.md').exists())
   results=e.snapshot(m['jobs'][0]['job_id'])['results'];self.assertEqual(len(results),1)
   self.assertEqual(results[0]['schema_version'],'sourcelens.host-result.v2')
 def test_tampered_view_and_unknown_or_uninspected_citations_rejected_before_writes(self):
  with tempfile.TemporaryDirectory() as td:
   run=self.fixture(Path(td));view=inspect_run(run);notes=self.notes(view)
   notes['answer']='Invented ev-'+'f'*32
   with self.assertRaises(ContractError):finish_run(run,notes)
   notes=self.notes(view);notes['inspected_ids']=[]
   with self.assertRaises(ContractError):finish_run(run,notes)
   notes=self.notes(view);Path(view['reading_file']).write_text('Changed')
   with self.assertRaises(ContractError):finish_run(run,notes)
 def test_no_findings_does_not_require_inventing_observation(self):
  with tempfile.TemporaryDirectory() as td:
   run=self.fixture(Path(td));view=inspect_run(run);notes=self.notes(view);notes['observations']=[];notes['answer']='No relevant finding.'
   finish_run(run,notes)
   _,m=w.load(run);r=w.Engine(run/'state',run/'acquired').snapshot(m['jobs'][0]['job_id'])['results'][0]
   self.assertEqual(r['observations'],[]);self.assertTrue(r['no_findings_reason'])
 def test_retry_after_submission_interruption_is_idempotent(self):
  with tempfile.TemporaryDirectory() as td:
   run=self.fixture(Path(td));view=inspect_run(run);notes=self.notes(view)
   with patch('sourcelens.pack.save_answer',side_effect=OSError('interrupt')):
    with self.assertRaises(OSError):finish_run(run,notes)
   finish_run(run,notes)
   _,m=w.load(run);r=w.Engine(run/'state',run/'acquired').snapshot(m['jobs'][0]['job_id'])['results']
   self.assertEqual(len(r),1)
 def test_followup_can_inspect_previously_uninspected_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   run=self.fixture(Path(td));view=inspect_run(run);notes=self.notes(view);finish_run(run,notes)
   view=inspect_run(run);notes=self.notes(view,'Another observation.');finish_run(run,notes)
   self.assertTrue(w.query(run,'Another'))
 def test_rolling_caption_reading_view_preserves_original_and_repeated_speech(self):
  span={'text':'We\nWe need\nWe need review.\nYes.\nYes.', 'locator':{'cue_map':[
    {'block_start':0,'block_end':2,'start_ms':0,'end_ms':1000},
    {'block_start':3,'block_end':10,'start_ms':100,'end_ms':1100},
    {'block_start':11,'block_end':26,'start_ms':200,'end_ms':1200},
    {'block_start':27,'block_end':31,'start_ms':2000,'end_ms':2300},
    {'block_start':32,'block_end':36,'start_ms':2500,'end_ms':2800}]}}
  original=span['text'];self.assertEqual(readable_text(span),'We need review.\nYes.\nYes.')
  self.assertEqual(span['text'],original)
 def test_plain_repetition_is_never_deduplicated(self):
  self.assertEqual(readable_text({'text':'Yes.\nYes.','locator':{}}),'Yes.\nYes.')
