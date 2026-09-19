import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from sourcelens.engine import Engine
from sourcelens.contracts import ContractError
from test_core import answer


class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.inputs = self.base / 'inputs'
        self.inputs.mkdir()
        self.engine = Engine(self.base / 'store', self.inputs)

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'sourcelens', '--store', str(self.base / 'store'),
                               '--allow-root', str(self.inputs), *args], capture_output=True, text=True)

    def test_cli_returns_json_error_and_nonzero_for_unknown_job(self):
        result = self.cli('job', 'status', 'missing')
        self.assertTrue(result.stdout.strip(), 'CLI must emit a structured response')
        data = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(data['status'], 'error')
        self.assertTrue(data['errors'])

    def test_cli_process_restart_and_export(self):
        path = self.inputs / 'notes.md'
        path.write_text('Retry limit is 7.\n')
        first = self.cli('ingest', str(path))
        self.assertEqual(first.returncode, 0, first.stderr)
        job = json.loads(first.stdout)['data']['job_id']
        ticket = json.loads(self.cli('job', 'advance', job).stdout)['data']['ticket']
        result_path = self.inputs / 'result.json'
        result_path.write_text(json.dumps(answer(ticket)))
        self.assertEqual(self.cli('task', 'submit', str(result_path)).returncode, 0)
        status = json.loads(self.cli('job', 'status', job).stdout)
        self.assertEqual(status['data']['status'], 'completed')
        out = self.base / 'export'
        self.assertEqual(self.cli('export', job, str(out)).returncode, 0)
        manifest = json.loads((out / 'manifest.json').read_text())
        for member, sha in manifest['files'].items():
            self.assertEqual(hashlib.sha256((out / member).read_bytes()).hexdigest(), sha)
        self.assertIn('Retry limit is 7.', (out / 'index.md').read_text())

    def test_export_refuses_existing_destination(self):
        source = self.inputs / 'a.txt'
        source.write_text('Evidence')
        job = self.engine.ingest(source)['job_id']
        out = self.base / 'already'
        out.mkdir()
        (out / 'keep.txt').write_text('keep')
        with self.assertRaises(ContractError):
            self.engine.export(job, out)
        self.assertEqual((out / 'keep.txt').read_text(), 'keep')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg/ffprobe required')
    def test_media_preserves_nonzero_decoded_pts(self):
        source = self.inputs / 'offset.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=red:s=160x90:r=2:d=3',
                        '-c:v', 'mpeg4', '-output_ts_offset', '5', str(source)], check=True, capture_output=True)
        job = self.engine.ingest(source)['job_id']
        ticket = self.engine.advance(job)['ticket']
        frames = [self.engine.read(job, x) for x in ticket['input_evidence_ids']]
        self.assertTrue(frames)
        self.assertEqual(frames[0]['kind'], 'frame')
        self.assertEqual(frames[0]['locator']['source_pts_ms'], 5000)
        self.assertEqual(frames[1]['locator']['source_pts_ms'], 5500)
        self.assertTrue(Path(frames[0]['artifact_path']).read_bytes().startswith(b'\x89PNG'))
        self.assertEqual(self.engine.status(job)['coverage']['frames_reported_inspected'], 0)
        self.engine.submit(answer(ticket))
        self.assertEqual(self.engine.status(job)['status'], 'partial')


if __name__ == '__main__':
    unittest.main()
