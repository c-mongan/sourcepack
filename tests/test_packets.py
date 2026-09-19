import tempfile
from pathlib import Path
import unittest
from sourcelens import workflow as w
from sourcelens.packets import present_packet,record_packet
from sourcelens.contracts import ContractError

class PacketTests(unittest.TestCase):
 def test_explicit_inspection_and_stale_packet(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'a.md';p.write_text('The retry limit is seven.');run=root/'run';w.prepare(str(p),run)
   packet=present_packet(run);eid=packet['spans'][0]['id']
   with self.assertRaises(ContractError):record_packet(run,packet['packet_id'],{'inspected_ids':['unknown'],'observations':[],'gaps':[]})
   result=record_packet(run,packet['packet_id'],{'inspected_ids':[eid],'observations':[{'text':'Retry limit seven','evidence_ids':[eid],'certainty':'observed'}],'gaps':[]})
   self.assertTrue(w.query(run,'seven'))
   with self.assertRaises(ContractError):record_packet(run,packet['packet_id'],{'inspected_ids':[],'observations':[],'gaps':[]})
 def test_presentation_does_not_attest_inspection(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'a.md';p.write_text('First\nSecond');run=root/'run';w.prepare(str(p),run)
   packet=present_packet(run)
   with self.assertRaises(ContractError):record_packet(run,packet['packet_id'],{'inspected_ids':[],'observations':[],'gaps':[]})
   self.assertEqual(present_packet(run)['packet_id'],packet['packet_id'])
 def test_presented_content_tampering_rejected(self):
  import json
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'a.md';p.write_text('Setting seven.');run=root/'run';w.prepare(str(p),run)
   packet=present_packet(run);path=run/'packets'/(packet['packet_id']+'.json');saved=json.loads(path.read_text());saved['spans'][0]['text']='Setting ninety.';path.write_text(json.dumps(saved));eid=packet['spans'][0]['id']
   with self.assertRaises(ContractError):record_packet(run,packet['packet_id'],{'inspected_ids':[eid],'observations':[{'text':'Setting ninety.','evidence_ids':[eid],'certainty':'observed'}],'gaps':[]})
 def test_followup_singular_word_finds_plural_observation(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'a.md';p.write_text('A setting is shown.');run=root/'run';w.prepare(str(p),run);packet=present_packet(run);eid=packet['spans'][0]['id']
   record_packet(run,packet['packet_id'],{'inspected_ids':[eid],'observations':[{'text':'Turn on notifications.','evidence_ids':[eid],'certainty':'observed'}],'gaps':[]})
   hits=w.query(run,'notification');self.assertTrue(hits);self.assertEqual(hits[0]['id'],eid)
