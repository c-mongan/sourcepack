"""Small ffmpeg adapter. No hosted fallbacks or model downloads."""
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .contracts import ContractError


def extract(path, policy, max_frames=None, ffmpeg=None, ffprobe=None, start_ms=None, end_ms=None):
    ffmpeg=ffmpeg or ['ffmpeg'];ffprobe=ffprobe or ['ffprobe']
    count=max_frames if max_frames is not None else policy.max_frames
    if not 1<=count<=policy.max_frames:raise ContractError('Invalid frame count')
    if not shutil.which(ffmpeg[0]) or not shutil.which(ffprobe[0]):
        return [], [{'kind': 'capability', 'reason': 'ffmpeg and ffprobe required for local video'}]
    try:
        # Force supported self-contained containers. Autodetecting arbitrary formats
        # allows a DASH/HLS/concat file to dereference other local files.
        demuxer = 'mov' if Path(path).suffix in ('.mp4', '.mov') else 'matroska'
        probe = subprocess.run(ffprobe+['-v', 'error', '-protocol_whitelist', 'file,pipe',
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
        from .visuals import overview_times
        from fractions import Fraction
        rate=float(Fraction(video.get('avg_frame_rate') or '25/1')) or 25
        origin=round(float(video.get('start_time') or metadata['format'].get('start_time') or 0)*1000)
        first=max(origin,start_ms) if start_ms is not None else origin
        last=min(origin+round(duration*1000),end_ms) if end_ms is not None else origin+round(duration*1000)
        targets=overview_times(first,last-first,count,1000/rate)
        expression='+'.join(f'gte(t,{t/1000})*if(isnan(prev_selected_t),1,lt(prev_selected_t,{t/1000}))' for t in targets)
        expression=expression.replace(',',r'\,')
        interval=max(0.01,duration/count)
        with tempfile.TemporaryDirectory(prefix='sourcelens-frames-') as td:
            pattern = str(Path(td) / '%04d.png')
            run = subprocess.run(ffmpeg+['-hide_banner', '-nostdin', '-threads', '1',
                                  '-protocol_whitelist', 'file,pipe', '-f', demuxer, '-copyts', '-i', str(path),
                                  '-map', '0:v:0', '-an', '-sn', '-dn', '-vf',
                                  f'select={expression},showinfo',
                                  '-fps_mode', 'passthrough', '-frames:v', str(count),
                                  '-threads', '1', pattern], capture_output=True, timeout=60)
            if run.returncode:
                raise ContractError('Local video decoding failed')
            times = [float(x) for x in re.findall(rb'\bpts_time:([\d.eE+\-]+)', run.stderr)]
            files = sorted(Path(td).glob('*.png'))
            if not files or len(times) < len(files):
                raise ContractError('Decoded frames lack trustworthy timestamp records')
            samples=[(file,t,'overview') for file,t in zip(files,times)]
            if start_ms is None and count>=4:
                scene_dir=Path(td)/'scenes';scene_dir.mkdir()
                scene_run=subprocess.run(ffmpeg+['-hide_banner','-nostdin','-threads','1','-protocol_whitelist','file,pipe','-f',demuxer,'-copyts','-i',str(path),'-map','0:v:0','-an','-sn','-dn','-vf',r'select=gt(scene\,0.2),showinfo','-fps_mode','passthrough','-frames:v','3','-threads','1',str(scene_dir/'%04d.png')],capture_output=True,timeout=60)
                if scene_run.returncode:raise ContractError('Scene decoding failed')
                scene_times=[float(x) for x in re.findall(rb'\bpts_time:([\d.eE+\-]+)',scene_run.stderr)]
                scene_files=sorted(scene_dir.glob('*.png'))
                if len(scene_times)<len(scene_files):raise ContractError('Scene frames lack timestamps')
                samples.extend((file,t,'scene') for file,t in zip(scene_files,scene_times))
                from .visuals import select_frames
                selected=select_frames([{'source_pts_ms':round(t*1000),'file':file,'reason':reason} for file,t,reason in samples],origin+round(duration*1000)+1,[],count)
                samples=[(x['file'],x['source_pts_ms']/1000,x['reason']) for x in selected]
            frames = []
            total = sum(p.stat().st_size for p in Path(td).rglob('*.png'))
            if total>policy.max_bytes:raise ContractError('Frame candidate byte budget exceeded')
            total = 0
            for i, (file, actual_time, reason) in enumerate(samples):
                data = file.read_bytes()
                total += len(data)
                if total > policy.max_bytes:
                    raise ContractError('Frame output byte budget exceeded')
                frames.append({'kind': 'frame', 'text': '', 'method': 'ffmpeg-select-showinfo',
                               'image_bytes': data, 'locator': {'source_pts_ms': round(actual_time * 1000),
                                                               'width': width, 'height': height,
                                                               'timestamp_basis': 'decoded-source-pts', 'selection_reason':'requested-window' if start_ms is not None else reason,
                                                               'requested_window_ms':[start_ms,end_ms] if start_ms is not None else None}})
        return frames, [{'kind': 'visual_sampling', 'reason': f'{len(frames)} frames sampled about every {interval:.3f}s; brief events may be missed'}]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, StopIteration) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('Video probe/decode failed or timed out') from exc
