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
