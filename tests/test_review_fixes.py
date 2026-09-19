import base64,json,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from sourcelens import workflow as w
from sourcelens.engine import Engine
from sourcelens.normalized import payload_for,file_sha
from sourcelens.pack import build_pack,save_answer

class ExportFixTests(unittest.TestCase):
 def fixture(self,root):
  source=root/'note.md';source.write_text('Review manually.');run=root/'run';w.prepare(str(source),run);acq=run/'acquired'
  original=acq/'original.txt';original.write_text('synthetic source')
  frame=acq/'image.png';frame.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZ0AAAAASUVORK5CYII='))
  asset={'path':'image.png','sha256':file_sha(frame),'source_sha256':file_sha(original),'locator':{'source_pts_ms':5000}}
  block={'id':'one','kind':'frame','text':'','source_sha256':file_sha(original),'method':'fixture','locator':{'source_pts_ms':5000},'asset_path':'image.png'}
  path=acq/'frame.json';path.write_text(json.dumps(payload_for(original,[block],acq,'test',assets=[asset])))
  engine=Engine(run/'state',acq);job=engine.ingest(path,input_format='normalized');_,m=w.load(run);m['jobs'].append({'job_id':job['job_id'],'source':'acquired/frame.json'});w.write_json(run/'run.json',m)
  ids=[]
  while True:
   packet=w.next_ticket(run)
   if 'ticket' not in packet:break
   r=packet['result_template'];r['inspection_records']=[{'evidence_id':s['id'],'provenance':'model_self_report'} for s in packet['spans']];ids.extend(s['id'] for s in packet['spans']);r['observations']=[{'text':'Synthetic fixture inspected.','evidence_ids':[packet['spans'][0]['id']],'certainty':'observed'}];engine.submit(r)
  return run,ids
 def test_existing_markdown_links_and_bare_text_citations_relocated(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run,ids=self.fixture(root);answer=root/'answer.md';answer.write_text(f"Shown [{ids[1]}](old/path.png). Text {ids[0]}.");save_answer(run,answer)
   with patch('sourcelens.pack.subprocess.run',return_value=subprocess.CompletedProcess([],1)):
    build_pack(run,root/'pack')
   text=(root/'pack/answer.md').read_text();self.assertNotIn('[[',text);self.assertNotIn('old/path.png',text)
   self.assertIn(f'[{ids[0]}](source-001/evidence.md#{ids[0]})',text)
 def test_sheet_timeout_keeps_pack_and_records_gap(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run,ids=self.fixture(root)
   with patch('sourcelens.pack.subprocess.run',side_effect=subprocess.TimeoutExpired('ffmpeg',60)):
    build_pack(run,root/'pack')
   self.assertIn('Contact sheet', (root/'pack/gaps.md').read_text())
 def test_sheet_nonzero_gap_is_visible(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run,ids=self.fixture(root)
   with patch('sourcelens.pack.subprocess.run',return_value=subprocess.CompletedProcess([],1)):
    build_pack(run,root/'pack')
   self.assertIn('Contact sheet',(root/'pack/gaps.md').read_text())
