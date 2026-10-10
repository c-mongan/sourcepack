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
 def test_collection_export_rejects_unregistered_acquisition_symlinks(self):
  for kind in ('file', 'directory', 'broken'):
   with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
    root=Path(td);source=root/'source.md';source.write_text('Synthetic source.')
    run=root/'run';w.prepare(str(source),run)
    outside=root/'outside';outside.mkdir();private=outside/'private.txt';private.write_text('Synthetic private data.')
    target={'file':private,'directory':outside,'broken':outside/'missing'}[kind]
    (run/'acquired'/'unregistered').symlink_to(target,target_is_directory=kind=='directory')
    destination=root/'export'
    with self.assertRaisesRegex(ContractError,'symlink'):
     build_pack(run,destination)
    self.assertFalse(destination.exists())
    self.assertEqual(private.read_text(),'Synthetic private data.')
 def test_collection_export_rejects_supporting_source_acquisition_symlink(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'source.md';source.write_text('Synthetic source.')
   run=root/'run';child=root/'child';w.prepare(str(source),run);w.prepare(str(source),child)
   register_supporting_source(run,child,'official docs')
   private=root/'private.txt';private.write_text('Synthetic private data.')
   (child/'acquired'/'unregistered.txt').symlink_to(private)
   with self.assertRaisesRegex(ContractError,'symlink'):
    build_pack(run,root/'export')
   self.assertFalse((root/'export').exists())
 def test_lightweight_collection_export_does_not_read_unregistered_symlink(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'source.md';source.write_text('Synthetic source.')
   run=root/'run';w.prepare(str(source),run)
   private=root/'private.txt';private.write_text('Synthetic private data.')
   (run/'acquired'/'unregistered.txt').symlink_to(private)
   build_pack(run,root/'export',include_originals=False)
   self.assertFalse((root/'export'/'acquired').exists())
   self.assertFalse(json.loads((root/'export'/'manifest.json').read_text())['self_contained_originals'])
