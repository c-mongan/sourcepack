import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sourcelens import adapters
from sourcelens.contracts import ContractError
from sourcelens.engine import Engine
from test_core import answer


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.inputs = self.base / 'inputs'
        self.inputs.mkdir()
        self.engine = Engine(self.base / 'state', self.inputs)

    def start(self, content, name='source.md'):
        path = self.inputs / name
        path.write_text(content)
        return self.engine.ingest(path)['job_id']

    def test_url_crossing_chunk_boundary_is_preserved(self):
        target = 'https://example.org/important/reference'
        job = self.start('x' * 1190 + ' ' + target)
        with self.engine.store.db() as db:
            _, data = self.engine.store.job(db, job)
        self.assertEqual([r['target'] for r in data['references']], [target])

    def test_bare_html_url_is_inventoried(self):
        job = self.start('<p>Read https://example.org/important</p>', 'source.html')
        self.assertEqual(self.engine.status(job)['coverage']['reference_mentions'], 1)

    def test_span_budget_is_enforced_before_materializing_excess(self):
        # A small nondefault parser budget lets us verify that parse itself fails,
        # before the engine's later decoration/storage step.
        with self.assertRaises(ContractError):
            adapters.parse(b'x\nx\nx\nx\n', '.txt', max_spans=3)

    def test_export_uses_one_snapshot_for_results_and_coverage(self):
        job = self.start('Evidence for one observation')
        ticket = self.engine.advance(job)['ticket']
        original_status = self.engine.status
        def concurrent_submit(*args, **kwargs):
            self.engine.submit(answer(ticket))
            return original_status(*args, **kwargs)
        out = self.base / 'export'
        with patch.object(self.engine, 'status', side_effect=concurrent_submit):
            self.engine.export(job, out)
        coverage = json.loads((out / 'coverage.json').read_text())
        observations = json.loads((out / 'observations.json').read_text())
        self.assertEqual(coverage['coverage']['observations'], len(observations))
        if coverage['status'] == 'completed':
            self.assertTrue(observations)

    @unittest.skipUnless(os.name == 'posix', 'POSIX file modes')
    def test_private_export_root_is_not_world_readable(self):
        job = self.start('private test content')
        before = os.umask(0o022)
        try:
            out = self.base / 'export'
            self.engine.export(job, out)
            self.assertEqual(out.stat().st_mode & 0o077, 0)
        finally:
            os.umask(before)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
    def test_disguised_dash_manifest_cannot_read_external_local_video(self):
        external = self.base / 'outside.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi', '-i',
                        'color=c=blue:s=160x90:r=2:d=2', '-c:v', 'mpeg4', str(external)],
                       check=True, capture_output=True)
        manifest = self.inputs / 'disguised.mp4'
        manifest.write_text(f'''<?xml version="1.0"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" mediaPresentationDuration="PT2S" minBufferTime="PT1S" profiles="urn:mpeg:dash:profile:isoff-on-demand:2011">
<Period><AdaptationSet mimeType="video/mp4" contentType="video"><Representation id="0" bandwidth="100000" width="160" height="90">
<BaseURL>{external}</BaseURL><SegmentBase/></Representation></AdaptationSet></Period></MPD>''')
        with self.assertRaises(ContractError):
            self.engine.ingest(manifest)

    def test_huge_imported_timestamp_returns_structured_cli_error(self):
        import sys
        source = self.inputs / 'huge.json'
        source.write_text(json.dumps({'extracted': {'transcriptSegments': [{'startMs': 10 ** 400, 'text': 'a'}]}}))
        result = subprocess.run([sys.executable, '-m', 'sourcelens', '--store', str(self.base / 'store2'),
                                 '--allow-root', str(self.inputs), 'ingest', str(source), '--input-format', 'summarize'],
                                capture_output=True, text=True)
        self.assertTrue(result.stdout.strip(), 'Malformed numbers must not escape the JSON envelope')
        self.assertEqual(json.loads(result.stdout)['status'], 'error')
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
