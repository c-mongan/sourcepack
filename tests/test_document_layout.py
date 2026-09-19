import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from sourcelens.documents import layout_readiness,convert_document
from sourcelens.contracts import ContractError

class LayoutTests(unittest.TestCase):
 def test_missing_models_fail_before_subprocess(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'a.pdf';p.write_bytes(b'%PDF-1.4')
   with patch('sourcelens.documents.subprocess.run',side_effect=AssertionError('must not start')):
    with self.assertRaises(ContractError):convert_document(p,root/'out','documents-layout',{'argv':['python']})
 def test_incomplete_manifest_is_not_ready(self):
  with tempfile.TemporaryDirectory() as td:
   self.assertFalse(layout_readiness({'artifacts_path':td,'artifacts_manifest':[{'path':'missing','sha256':'a'*64}]})['ready'])
 def test_arbitrary_hash_manifest_does_not_prove_model_readiness(self):
  import hashlib
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'README';p.write_text('not models')
   result=layout_readiness({'artifacts_path':td,'artifacts_manifest':[{'path':'README','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]})
   self.assertFalse(result['ready'])
   self.assertIn('completeness', ' '.join(result['gaps']).lower())
