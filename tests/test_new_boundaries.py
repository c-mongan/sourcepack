import json, tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
from sourcelens import workflow as w
from sourcelens.contracts import ContractError
from sourcelens.documents import convert_document

class BoundaryTests(unittest.TestCase):
 def test_empty_scan_has_actionable_error(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);src=root/'scan.pdf';src.write_bytes(b'%PDF-1.4');script=root/'fake.py'
   script.write_text("import json,sys,pathlib\nr=json.loads(pathlib.Path(sys.argv[-1]).read_text());pathlib.Path(r['output']).joinpath('producer.json').write_text(json.dumps({'version':'fake','markdown':'','blocks':[]}))")
   with self.assertRaisesRegex(ContractError,'No readable document text'):convert_document(src,root/'out','documents-basic',{'argv':[sys.executable,str(script)],'worker_override':True})
 def test_artifact_parent_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);outside=root/'outside';outside.mkdir();(outside/'a').write_text('test');run=root/'run';run.mkdir();(run/'link').symlink_to(outside,target_is_directory=True)
   with self.assertRaises(ContractError):w.check_artifacts(run,{'artifacts':{'link/a':w.sha(outside/'a')}})
 def test_doctor_reports_versions(self):
  result=w.doctor()
  self.assertIn('version',result['tools']['ffmpeg'])
  self.assertIn('documents-basic',result['profiles'])
