"""Small ffmpeg adapter. No hosted fallbacks or model downloads."""
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .contracts import ContractError


def extract(path, policy):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        return [], [{'kind': 'capability', 'reason': 'ffmpeg and ffprobe required for local video'}]
    try:
        # Force supported self-contained containers. Autodetecting arbitrary formats
        # allows a DASH/HLS/concat file to dereference other local files.
        demuxer = 'mov' if Path(path).suffix in ('.mp4', '.mov') else 'matroska'
        probe = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                                '-f', demuxer, '-show_streams', '-show_format', '-of', 'json', str(path)],
                               check=True, capture_output=True, timeout=15)
        metadata = json.loads(probe.stdout)
        video = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
        duration = float(video.get('duration') or metadata['format']['duration'])
        width, height = int(video['width']), int(video['height'])
        if not math.isfinite(duration) or not 0 < duration <= policy.max_video_seconds:
            raise ContractError('Video duration exceeds supported bound')
        if width * height > 4096 * 2304:
            raise ContractError('Video resolution exceeds the local decode bound')
        interval = max(0.01, duration / policy.max_frames)
        with tempfile.TemporaryDirectory(prefix='sourcelens-frames-') as td:
            pattern = str(Path(td) / '%04d.png')
            run = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-threads', '1',
                                  '-protocol_whitelist', 'file,pipe', '-f', demuxer, '-copyts', '-i', str(path),
                                  '-map', '0:v:0', '-an', '-sn', '-dn', '-vf',
                                  f'select=isnan(prev_selected_t)+gte(t-prev_selected_t\\,{interval}),showinfo',
                                  '-fps_mode', 'passthrough', '-frames:v', str(policy.max_frames),
                                  '-threads', '1', pattern], capture_output=True, timeout=60)
            if run.returncode:
                raise ContractError('Local video decoding failed')
            times = [float(x) for x in re.findall(rb'\bpts_time:([\d.eE+\-]+)', run.stderr)]
            files = sorted(Path(td).glob('*.png'))
            if not files or len(times) < len(files):
                raise ContractError('Decoded frames lack trustworthy timestamp records')
            frames = []
            total = 0
            for i, file in enumerate(files):
                data = file.read_bytes()
                total += len(data)
                if total > policy.max_bytes:
                    raise ContractError('Frame output byte budget exceeded')
                frames.append({'kind': 'frame', 'text': '', 'method': 'ffmpeg-select-showinfo',
                               'image_bytes': data, 'locator': {'source_pts_ms': round(times[i] * 1000),
                                                               'width': width, 'height': height,
                                                               'timestamp_basis': 'decoded-source-pts'}})
        return frames, [{'kind': 'visual_sampling', 'reason': f'{len(frames)} frames sampled about every {interval:.3f}s; brief events may be missed'}]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, StopIteration) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('Video probe/decode failed or timed out') from exc
