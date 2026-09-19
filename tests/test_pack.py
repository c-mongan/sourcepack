import tempfile,unittest,json,shutil
from pathlib import Path
from sourcelens import workflow as w
from sourcelens.pack import build_pack,register_supporting_source
from sourcelens.contracts import ContractError

class PackTests(unittest.TestCase):
 def test_portable_pack_preserves_original_and_removes_machine_paths(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'a.md';p.write_text('Retry limit seven.');run=root/'run';w.prepare(str(p),run)
   out=root/'out';build_pack(run,out)
   self.assertTrue((out/'acquired/source.md').exists())
   self.assertNotIn(str(root), (out/'run.json').read_text())
   self.assertTrue((out/'answer.md').exists())
   moved=root/'moved';shutil.move(out,moved)
   manifest=json.loads((moved/'manifest.json').read_text())
   for name in manifest['files']:self.assertTrue((moved/name).exists())
 def test_supporting_sources_are_bounded_and_uninspected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'a.md';p.write_text('test');run=root/'run';w.prepare(str(p),run)
   for i in range(3):
    child=root/f'child{i}';w.prepare(str(p),child);register_supporting_source(run,child,'official docs')
   child=root/'child4';w.prepare(str(p),child)
   with self.assertRaises(ContractError):register_supporting_source(run,child,'extra')
   self.assertEqual(len(w.load(run)[1]['supporting_sources']),3)
