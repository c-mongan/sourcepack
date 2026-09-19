import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import patch
from sourcelens import workflow as w
from sourcelens.contracts import ContractError

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.source=self.root/'notes.md'
        self.source.write_text('The retry limit is 7.\nSee https://example.org/spec\n')
        self.run=self.root/'run'
    def test_prepare_resume_change_refusal_and_citation_roundtrip(self):
        a=w.prepare(str(self.source),self.run)
        self.assertEqual(a['jobs'],w.prepare(str(self.source),self.run)['jobs'])
        packet=w.next_ticket(self.run); t=packet['ticket']; eid=t['input_evidence_ids'][0]
        result=packet['result_template']; result['inspection_records']=[{'evidence_id':e,'provenance':'model_self_report'} for e in t['input_evidence_ids']]
        result['gaps']=[];result['observations']=[{'text':'Retry limit is seven.','evidence_ids':[eid],'certainty':'observed'}]
        path=self.root/'result.json';path.write_text(json.dumps(result));w.submit(self.run,path)
        self.assertEqual(w.query(self.run,'seven')[0]['id'],eid)
        self.assertEqual(w.next_ticket(self.run)['status'],'finished')
        destination=self.root/'export';w.export_run(self.run,destination)
        self.assertTrue((destination/'index.md').is_file())
        self.source.write_text('Changed source')
        with self.assertRaises(ContractError):w.prepare(str(self.source),self.run)
    def test_original_tampering_refused_on_resume(self):
        w.prepare(str(self.source),self.run)
        (self.run/'acquired/source.md').write_text('tampered')
        with self.assertRaises(ContractError):w.prepare(str(self.source),self.run)
    def test_rejects_unowned_output_and_nonpublic_urls(self):
        self.run.mkdir();(self.run/'keep').write_text('mine')
        with self.assertRaises(ContractError):w.prepare(str(self.source),self.run)
        for url in ['http://127.0.0.1/a','https://user:pass@example.org','file:///etc/passwd','https://localhost/a']:
            with self.assertRaises(ContractError):w.source_identity(url)
    def test_caption_normalization_keeps_original_timeline(self):
        raw='WEBVTT\n\n00:00:05.000 --> 00:00:06.000\nHello world\n\n00:00:06.000 --> 00:00:07.000\nHello world again\n'
        text=w.normalize_vtt(raw)
        self.assertIn('00:00:05.000 --> 00:00:06.000',text)
        self.assertIn('\nagain\n',text)
        self.assertEqual(raw.count('Hello world'),2)
    def test_install_local_tool_configuration_works_without_shell_environment(self):
        config=self.root/'tool-paths.json'
        config.write_text(json.dumps({'summarize':['/custom/node','/custom/cli.js']}))
        with patch.object(w,'TOOL_CONFIG',config),patch.dict('os.environ',{},clear=True):
            self.assertEqual(w.command('summarize'),['/custom/node','/custom/cli.js'])
            self.assertEqual(w.command('ffmpeg'),['ffmpeg'])

    def test_provider_environment_is_not_inherited(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'not-a-real-key','HOME':'/sensitive','SUMMARIZE_MODEL':'paid'}):
            env=w.extraction_env()
        self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('HOME',env);self.assertNotIn('SUMMARIZE_MODEL',env)
    def test_failed_extractor_retains_diagnostics_and_no_ready_status(self):
        with patch.object(w,'source_identity',return_value={'kind':'web','source':'https://example.org/'}),patch.object(w,'extract_web',side_effect=ContractError('adapter failed')):
            with self.assertRaises(ContractError):w.prepare('https://example.org/',self.run)
        m=json.loads((self.run/'run.json').read_text())
        self.assertEqual(m['status'],'failed');self.assertIn('adapter failed',m['error'])
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
    def test_focus_creates_bounded_job_at_original_video_time(self):
        def acquire(run,m):
            path=run/'acquired/video.mp4'
            subprocess.run(['ffmpeg','-v','error','-nostdin','-f','lavfi','-i','color=c=red:s=160x90:r=2:d=10',
                            '-c:v','mpeg4','-g','2',str(path)],check=True,capture_output=True)
            (run/'acquired/metadata.json').write_text(json.dumps({'duration':10}))
            m['imports']=[{'path':'acquired/video.mp4','format':None}]
        with patch.object(w,'source_identity',return_value={'kind':'youtube','source':'https://www.youtube.com/watch?v=abcdefghijk'}),patch.object(w,'extract_youtube',side_effect=acquire):
            w.prepare('source',self.run)
        result=w.focus(self.run,5,8)
        engine=w.Engine(self.run/'state',self.run/'acquired')
        frames=engine.snapshot(result['job_id'])['spans']
        self.assertTrue(frames)
        self.assertGreaterEqual(frames[0]['locator']['source_pts_ms'],4000)
        self.assertLessEqual(frames[0]['locator']['source_pts_ms'],5000)
        self.assertEqual(result['job_id'],w.focus(self.run,5,8)['job_id'])
        with self.assertRaises(ContractError):w.focus(self.run,0,301)

    def test_ingestion_retry_reuses_acquired_snapshot(self):
        from sourcelens.engine import Engine
        with patch.object(Engine,'ingest',side_effect=ContractError('temporary ingestion failure')):
            with self.assertRaises(ContractError):w.prepare(str(self.source),self.run)
        first=(self.run/'acquired/source.md').read_bytes()
        with patch.object(w.shutil,'copyfile',side_effect=AssertionError('acquisition repeated')):
            m=w.prepare(str(self.source),self.run)
        self.assertEqual(m['status'],'ready')
        self.assertEqual((self.run/'acquired/source.md').read_bytes(),first)

if __name__=='__main__':unittest.main()
