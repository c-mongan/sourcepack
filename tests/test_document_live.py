"""Optional real converter acceptance. Set SOURCEPACK_DOCUMENT_PYTHON explicitly."""
import os,tempfile,unittest
from pathlib import Path
from sourcelens.documents import convert_document
from sourcelens.contracts import ContractError

@unittest.skipUnless(os.environ.get('SOURCEPACK_DOCUMENT_PYTHON'),'optional document interpreter not configured')
class LiveDocumentTests(unittest.TestCase):
 def test_authored_documents_retain_facts_and_locators(self):
  fixtures=Path(__file__).parent/'fixtures/documents'
  expected={'policy.docx':('seven','derived-section'),'policy.pdf':('seven','derived-section'),'handoff.pptx':('manual','producer-slide-marker'),'budgets.xlsx':('Budgets','producer-sheet-heading')}
  with tempfile.TemporaryDirectory() as td:
   for name,(fact,basis) in expected.items():
    with self.subTest(name=name):
     result=convert_document(fixtures/name,Path(td)/name,'documents-basic',{'argv':[os.environ['SOURCEPACK_DOCUMENT_PYTHON']]})
     self.assertIn(fact,' '.join(b['text'] for b in result['blocks']))
     self.assertTrue(any(b['locator']['coordinate_basis']==basis for b in result['blocks']))
 def test_scan_is_not_falsely_summarized(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaisesRegex(ContractError,'No readable document text'):
    convert_document(Path(__file__).parent/'fixtures/documents/scan.pdf',Path(td),'documents-basic',{'argv':[os.environ['SOURCEPACK_DOCUMENT_PYTHON']]})
