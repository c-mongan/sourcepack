import json
import tempfile
import unittest
from pathlib import Path
from sourcelens import workflow as w
from sourcelens.quick import inspect_run,finish_run
from sourcelens.contracts import ContractError

class Boundaries(unittest.TestCase):
 def setup_run(self,root,name):
  path=root/(name+'.md');path.write_text('Only source text.');run=root/name;w.prepare(str(path),run);view=inspect_run(run)
  return run,view
 def test_foreign_observation_and_fake_quote_do_not_record_anything(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run,view=self.setup_run(root,'one');other,ov=self.setup_run(root,'two');eid=view['text_evidence_ids'][0]
   n={'schema':'sourcepack.findings.v1','review_id':view['review_id'],'inspected_ids':[eid],'observations':[{'text':'Claim','evidence_ids':[ov['text_evidence_ids'][0]],'certainty':'observed'}],'answer':'Claim.'}
   with self.assertRaises(ContractError):finish_run(run,n)
   n['observations'][0].update(evidence_ids=[eid],quote='Not actually quoted')
   with self.assertRaises(ContractError):finish_run(run,n)
   _,m=w.load(run);self.assertFalse(w.Engine(run/'state',run/'acquired').snapshot(m['jobs'][0]['job_id'])['results'])
 def test_cancelled_job_and_changed_artifact_are_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   run,view=self.setup_run(Path(td),'one');_,m=w.load(run);e=w.Engine(run/'state',run/'acquired');jid=m['jobs'][0]['job_id'];eid=view['text_evidence_ids'][0]
   n={'schema':'sourcepack.findings.v1','review_id':view['review_id'],'inspected_ids':[eid],'observations':[],'answer':'Nothing relevant.'}
   artifact=Path(e.read(jid,eid)['artifact_path']);artifact.write_text('Tampered')
   with self.assertRaises(ContractError):finish_run(run,n)
   e.cancel(jid)
   with self.assertRaises(ContractError):inspect_run(run)
 def test_core_selection_is_bounded_and_foreign_evidence_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run,v=self.setup_run(root,'one');other,ov=self.setup_run(root,'two');_,m=w.load(run);e=w.Engine(run/'state',run/'acquired');jid=m['jobs'][0]['job_id']
   for ids in ([],['unknown'],v['text_evidence_ids']*9,ov['text_evidence_ids']):
    with self.assertRaises(ContractError):e.inspection_ticket(jid,ids,'request')
 def test_empty_source_gap_is_visible_in_review_and_saved_receipt(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'empty.md';source.write_text('  \n');run=root/'run';w.prepare(str(source),run)
   view=inspect_run(run)
   self.assertIn('No readable text extracted',json.dumps(view['gaps']))
   self.assertIn('No readable text extracted',Path(view['reading_file']).read_text())
   receipt=finish_run(run,{'schema':'sourcepack.findings.v1','review_id':view['review_id'],'inspected_ids':[],'observations':[],'answer':'No text available.'})
   self.assertIn('No readable text extracted',json.dumps(receipt['gaps']))
 def test_prior_inspection_gap_is_preserved_and_changed_gaps_invalidate_view(self):
  with tempfile.TemporaryDirectory() as td:
   run,before=self.setup_run(Path(td),'one');packet=w.next_ticket(run);r=packet['result_template'];eid=packet['spans'][0]['id']
   r['gaps']=[{'evidence_id':eid,'reason':'Source text needs external clarification.'}]
   w.Engine(run/'state',run/'acquired').submit(r)
   notes={'schema':'sourcepack.findings.v1','review_id':before['review_id'],'inspected_ids':[],'observations':[],'answer':'Unclear.'}
   with self.assertRaises(ContractError):finish_run(run,notes)
   after=inspect_run(run);self.assertIn('external clarification',json.dumps(after['gaps']));self.assertIn(eid,json.dumps(after['gaps']))
   notes['review_id']=after['review_id'];receipt=finish_run(run,notes)
   self.assertIn('external clarification',json.dumps(receipt['gaps']))
