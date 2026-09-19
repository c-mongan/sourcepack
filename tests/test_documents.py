import json, tempfile, unittest, zipfile,sys
from pathlib import Path
from sourcelens.documents import document_preflight,convert_document
from sourcelens.contracts import ContractError

class DocumentTests(unittest.TestCase):
 def test_archive_paths_and_expansion_are_bounded(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'bad.docx'
   with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','bad')
   with self.assertRaises(ContractError):document_preflight(p)
 def test_macro_format_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'bad.docm';p.write_bytes(b'bad')
   with self.assertRaises(ContractError):document_preflight(p)
 def test_missing_converter_is_explicit(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'a.pdf';p.write_bytes(b'%PDF-1.4\n')
   with self.assertRaises(ContractError):convert_document(p,Path(td)/'out','documents-basic',{'argv':['/missing/python']})
 def test_worker_contract_with_spaces_and_unicode(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'résumé file.pdf';source.write_bytes(b'%PDF-1.4')
   worker=root/'fake.py';worker.write_text("import json,sys,pathlib\nr=json.loads(pathlib.Path(sys.argv[-1]).read_text());pathlib.Path(r['output']).joinpath('producer.json').write_text(json.dumps({'markdown':'The limit is 7.','version':'fake','blocks':[{'text':'The limit is 7.','locator':{'coordinate_basis':'derived-section','section':1}}],'gaps':[]}))")
   result=convert_document(source,root/'output','documents-basic',{'argv':[sys.executable,str(worker)],'worker_override':True})
   self.assertEqual(result['blocks'][0]['text'],'The limit is 7.')
   self.assertEqual(result['source']['sha256'],__import__('hashlib').sha256(source.read_bytes()).hexdigest())
