import hashlib
import tempfile
from pathlib import Path
import unittest
from sourcelens.normalized import group_cues, validate_normalized, payload_for, cues_from_vtt
from sourcelens.contracts import ContractError
from sourcelens.engine import Engine

class NormalizedTests(unittest.TestCase):
    def test_lossless_repetition_unicode_and_split_mapping(self):
        cues=[{'id':str(i),'start_ms':i*2000,'end_ms':i*2000+1000,'text':text} for i,text in enumerate(['Yes.','Yes.','é'*2600])]
        blocks=group_cues(cues,'a'*64)
        recovered={c['id']:'' for c in cues}
        for b in blocks:
            self.assertLessEqual(len(b['text']),1200)
            for m in b['cue_map']:
                recovered[m['cue_id']]+=b['text'][m['block_start']:m['block_end']]
        self.assertEqual(recovered,{c['id']:c['text'] for c in cues})
    def test_large_transcript_uses_readable_batches(self):
        cues=[{'id':str(i),'start_ms':i*1000,'end_ms':i*1000+900,'text':'A useful sentence about a setting.'} for i in range(1122)]
        self.assertLessEqual((len(group_cues(cues,'a'*64))+7)//8,20)
    def test_invalid_time_and_budget(self):
        for end in [0,-1,float('nan')]:
            with self.assertRaises(ContractError):group_cues([{'id':'a','start_ms':0,'end_ms':end,'text':'hello'}],'a'*64)
    def test_vtt_preserves_repeated_words_and_source_time(self):
        cues=cues_from_vtt('WEBVTT\n\n00:00:05.000 --> 00:00:06.000\nYes.\n\n00:00:07.000 --> 00:00:08.000\nYes.\n')
        self.assertEqual([c['text'] for c in cues],['Yes.','Yes.'])
        self.assertEqual(cues[0]['start_ms'],5000)
    def test_import_binds_original_and_rejects_tampering_or_escape(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); original=root/'original.vtt';original.write_text('source')
            blocks=group_cues([{'id':'a','start_ms':1,'end_ms':2,'text':'Hello'}],hashlib.sha256(original.read_bytes()).hexdigest())
            payload=payload_for(original,blocks,root,'test')
            path=root/'normalized.json';path.write_text(json.dumps(payload))
            result=Engine(root/'state',root).ingest(path,input_format='normalized')
            engine=Engine(root/'state',root);snapshot=engine.snapshot(result['job_id'])
            self.assertEqual(snapshot['spans'][0]['text'],'Hello')
            self.assertGreaterEqual(len(snapshot['payload']['sources']),2)
            original.write_text('tampered')
            with self.assertRaises(ContractError):validate_normalized(payload,root)
            payload['source']['path']='../outside'
            with self.assertRaises(ContractError):validate_normalized(payload,root)
