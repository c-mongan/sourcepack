"""Skill-facing acquisition and collection wrapper. No model calls or auto-installs."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from html import unescape
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, parse_qs

from .adapters import timestamp, URL
from .contracts import ContractError
from .engine import Engine

VERSION = '0.4.0'
TOOL_CONFIG = Path(__file__).resolve().parent.parent / 'tool-paths.json'
MAX_DOWNLOAD = 256 * 1024 * 1024
TEXT_SUFFIXES = {'.txt', '.md', '.html', '.htm', '.vtt', '.srt'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''): h.update(part)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n'); name = f.name
    os.replace(name, path)


def extraction_env():
    # No HOME, API keys, extractor provider defaults, or shell evaluation.
    return {k: os.environ[k] for k in ('PATH', 'LANG', 'SYSTEMROOT', 'TMPDIR') if k in os.environ} | {'NO_COLOR': '1'}


def command(tool):
    # Explicit local overrides are argv arrays, not shell commands.
    key = 'SOURCEPACK_' + tool.upper().replace('-', '_')
    value = os.environ.get(key)
    config = json.loads(TOOL_CONFIG.read_text()) if TOOL_CONFIG.exists() else {}
    if not isinstance(config, dict):
        raise ContractError('Local tool-paths.json must be an object')
    result = json.loads(value) if value else config.get(tool, [tool])
    if not isinstance(result, list) or not result or any(not isinstance(x, str) or not x for x in result):
        raise ContractError(f'{key} must be a JSON argv array')
    return result


def run_tool(run, label, argv, timeout=120):
    logs = Path(run) / 'logs'; logs.mkdir(exist_ok=True)
    attempt = len(list(logs.glob(label + '-*.json'))) + 1
    prefix = logs / f'{label}-{attempt}'
    start = datetime.now(timezone.utc)
    receipt = {'argv': argv, 'started': start.isoformat(), 'provider_environment': 'allowlist; no HOME or provider keys'}
    try:
        with prefix.with_suffix('.stdout').open('wb') as stdout, prefix.with_suffix('.stderr').open('wb') as stderr:
            p = subprocess.run(argv, stdout=stdout, stderr=stderr, env=extraction_env(), timeout=timeout)
        receipt['exit_code'] = p.returncode
        if p.returncode:
            raise ContractError(f'{label} failed ({p.returncode}); inspect {prefix.with_suffix(".stderr")}')
        if prefix.with_suffix('.stdout').stat().st_size > MAX_DOWNLOAD:
            raise ContractError(f'{label} output exceeds budget')
        return prefix.with_suffix('.stdout').read_bytes()
    except (OSError, subprocess.SubprocessError) as exc:
        receipt['error'] = str(exc)
        raise ContractError(f'{label} unavailable or timed out; inspect logs') from exc
    finally:
        receipt['elapsed_seconds'] = (datetime.now(timezone.utc) - start).total_seconds()
        write_json(prefix.with_suffix('.json'), receipt)


def source_identity(source):
    parts = urlsplit(source)
    if parts.scheme:
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            raise ContractError('Expected a public HTTP(S) URL without credentials')
        if parts.hostname == 'localhost' or parts.hostname.endswith('.local'):
            raise ContractError('Private network sources are not supported')
        try:
            addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ContractError('Private network sources are not supported')
        except socket.gaierror as exc:
            raise ContractError('Source hostname could not be resolved') from exc
        if parts.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'):
            video = parts.path.strip('/') if parts.hostname == 'youtu.be' else parse_qs(parts.query).get('v', [''])[0]
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
                raise ContractError('Use one YouTube watch URL or youtu.be video URL, not a playlist')
            return {'kind': 'youtube', 'source': 'https://www.youtube.com/watch?v=' + video}
        if Path(parts.path).suffix.lower() in {'.pdf', '.epub', '.mp3', '.mp4', '.wav', '.m4a', '.webm', '.zip'}:
            raise ContractError('This URL type needs a separate document/media adapter; not supported by the web route')
        return {'kind': 'web', 'source': source}
    p = Path(source).expanduser().resolve(strict=True)
    if p.suffix.lower() in {'.pdf','.docx','.pptx','.xlsx'}:
        from .documents import document_preflight
        document_preflight(p)
        return {'kind':'document','source':str(p),'sha256':sha(p)}
    if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
        raise ContractError('Supported local inputs: UTF-8 txt, md, html, vtt, srt')
    if p.stat().st_size > 64 * 1024 * 1024:
        raise ContractError('Local source exceeds 64 MiB')
    return {'kind': 'local', 'source': str(p), 'sha256': sha(p)}


@contextmanager
def locked(run):
    # Advisory lock releases on process termination; no stale-lock deletion.
    import fcntl
    with (Path(run) / '.lock').open('a') as f:
        try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise ContractError('Another process owns this run') from exc
        try: yield
        finally: fcntl.flock(f, fcntl.LOCK_UN)


def load(run):
    run = Path(run).resolve(strict=True)
    m = json.loads((run / 'run.json').read_text())
    if m.get('schema') not in ('sourcepack.run.v1','sourcepack.run.v2'): raise ContractError('Not a SourcePack run')
    return run, m


def check_artifacts(run, m):
    for name, expected in m.get('artifacts', {}).items():
        p = run / name
        if Path(name).is_absolute() or '..' in Path(name).parts or not p.resolve().is_relative_to(run.resolve()) or any(x.is_symlink() for x in [p,*p.parents] if x!=run and x.is_relative_to(run)) or not p.is_file() or sha(p) != expected:
            raise ContractError(f'Acquired artifact changed or missing: {name}; use a new run')


def summarize(run, source):
    raw = run_tool(run, 'summarize', command('summarize') + [source, '--extract', '--json', '--timestamps', '--format', 'md',
        '--youtube', 'web', '--firecrawl', 'off', '--markdown-mode', 'readability', '--preprocess', 'off',
        '--embedded-video', 'off', '--no-slides', '--no-slides-ocr', '--no-cache', '--no-media-cache', '--timeout', '60s'])
    data = json.loads(raw)
    if not data.get('extracted', {}).get('content'): raise ContractError('Summarize returned no content')
    if data.get('llm') is not None: raise ContractError('Unexpected inference reported by extractor')
    return raw


def extract_web(run, m):
    p = run / 'acquired/extraction.json'
    p.write_bytes(summarize(run, m['identity']['source']))
    m['imports'] = [{'path': str(p.relative_to(run)), 'format': 'summarize'}]
    m['gaps'].append('Web evidence is saved extractor output, not an original HTML snapshot; embedded visuals are not inspected automatically.')


def format_ms(ms):
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d}.{ms%1000:03d}'


def normalize_vtt(raw):
    """Derived reading copy; strip markup and rolling overlap without shifting times."""
    entries = []; previous = []
    blocks = re.split(r'\n\s*\n', raw.replace('\r\n', '\n'))
    for block in blocks:
        lines = block.splitlines()
        for i, line in enumerate(lines):
            if '-->' not in line: continue
            a, b = line.split('-->', 1); start = timestamp(a.strip()); end = timestamp(b.strip().split()[0])
            words = unescape(re.sub(r'<[^>]*>', '', ' '.join(lines[i+1:]))).split()
            overlap = 0
            for n in range(min(len(previous), len(words)), 0, -1):
                if previous[-n:] == words[:n]: overlap = n; break
            fresh = words[overlap:]; previous = words
            # Bound each cue for the existing evidence contract.
            text = ' '.join(fresh)
            for j in range(0, len(text), 1100):
                entries.append(f'{format_ms(start)} --> {format_ms(end)}\n{text[j:j+1100]}')
            break
    if not entries: raise ContractError('No usable caption cues; original retained')
    return 'WEBVTT\n\n' + '\n\n'.join(entries) + '\n'


def probe(run, path):
    return json.loads(run_tool(run, 'ffprobe', command('ffprobe') + ['-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-f', 'mov', '-show_streams', '-show_format', '-of', 'json', str(path)], 30))


def extract_youtube(run, m):
    from .stages import run_stage
    from .normalized import cues_from_vtt, group_cues, payload_for
    acquired=run/'acquired'; source=m['identity']['source']; m['imports']=[]
    ytdlp=command('yt-dlp')+['--ignore-config','--no-playlist','--socket-timeout','20','--retries','1']
    def metadata_action():
        p=acquired/'metadata.json';p.write_bytes(run_tool(run,'metadata',ytdlp+['--skip-download','--dump-single-json',source]));return [p]
    try:
        run_stage(run,m,'metadata',{'argv':ytdlp,'source':source},metadata_action)
        info=json.loads((acquired/'metadata.json').read_text())
        duration=info.get('duration')
        if type(duration) not in (int,float) or not 0<duration<=3600 or info.get('is_live'):
            raise ContractError('This release supports finite YouTube videos up to one hour')
    except (ContractError,ValueError) as exc:
        m['gaps'].append('Metadata unavailable: '+str(exc));info={};duration=None
    def transcript_action():
        originals=[];cues=None
        try:
            path=acquired/'extraction.json';path.write_bytes(summarize(run,source));originals.append(path)
            segments=json.loads(path.read_text()).get('extracted',{}).get('transcriptSegments')
            if segments:cues=[{'id':str(i),'start_ms':x['startMs'],'end_ms':x.get('endMs'),'text':x['text']} for i,x in enumerate(segments)]
        except (ContractError,ValueError,KeyError) as exc:m['gaps'].append('Summarize route failed: '+str(exc))
        try:
            run_tool(run,'captions',ytdlp+['--skip-download','--write-subs','--write-auto-subs','--sub-langs','en-orig,en','--sub-format','vtt','-o',str(acquired/'video.%(ext)s'),source],180)
        except ContractError as exc:m['gaps'].append('Caption download failed: '+str(exc))
        captions=sorted(acquired.glob('video.*.vtt'),key=lambda p:('.en-orig.' not in p.name,p.name))
        originals.extend(captions)
        if cues:original=acquired/'extraction.json'
        elif captions:original=captions[0];cues=cues_from_vtt(original.read_text())
        else:raise ContractError('No timed transcript available; no ASR or paid fallback invoked')
        if captions:
            try:
                legacy=acquired/'captions-normalized.vtt';legacy.write_text(normalize_vtt(captions[0].read_text()));originals.append(legacy)
            except ContractError:pass
        out=acquired/'transcript.json'
        write_json(out,payload_for(original,group_cues(cues,sha(original)),acquired,'timed-transcript-v1',origin=source))
        return [*originals,out]
    try:
        run_stage(run,m,'transcript',{'summarize':command('summarize'),'yt-dlp':ytdlp,'revision':'grouped-v1'},transcript_action)
        m['imports'].append({'path':'acquired/transcript.json','format':'normalized'})
        m['gaps'].append('Captions may be automatic; speech accuracy unverified. Original cues and timing retained; grouped text is derived.')
    except (ContractError,ValueError) as exc:m['gaps'].append('Transcript: '+str(exc))
    m['outbound_links']=[{'url':x.rstrip('.,;)'),'status':'not_inspected'} for x in dict.fromkeys(URL.findall(info.get('description') or ''))]
    if m.get('detail')=='text':
        m.setdefault('stages',{})['video']={'status':'skipped','reason':'text-only request'}
        m['gaps'].append('Text-only request: video visuals not acquired or inspected.');return
    if duration is None:
        m.setdefault('stages',{})['video']={'status':'failed','error':'Valid bounded metadata required'};return
    def video_action():
        media=acquired/'video.mp4'
        run_tool(run,'video',ytdlp+['--max-filesize',str(MAX_DOWNLOAD),'-f','bestvideo[height<=720][ext=mp4]','-o',str(media),source],600)
        if not media.exists() or media.stat().st_size>MAX_DOWNLOAD:raise ContractError('No video within acquisition budget')
        return [media]
    try:run_stage(run,m,'video',{'argv':ytdlp,'source':source,'height':720},video_action)
    except ContractError as exc:m['gaps'].append('Video: '+str(exc));return
    def visual_action():
        segments=acquired/'segments';segments.mkdir(exist_ok=True)
        run_tool(run,'segment',command('ffmpeg')+['-v','error','-nostdin','-y','-protocol_whitelist','file,pipe','-f','mov','-copyts','-i',str(acquired/'video.mp4'),'-map','0:v:0','-c','copy','-an','-f','segment','-segment_time','240','-reset_timestamps','0',str(segments/'segment-%03d.mp4')],180)
        clips=sorted(segments.glob('segment-*.mp4'))
        if not clips or len(clips)>20:raise ContractError('Unexpected segment count')
        for clip in clips:
            meta=probe(run,clip);stream=next(x for x in meta['streams'] if x['codec_type']=='video')
            d=float(stream.get('duration') or meta['format']['duration'])
            if not 0<d<=300 or clip.stat().st_size>64*1024*1024:raise ContractError('A segment exceeds core bounds')
        return clips
    try:
        clips=run_stage(run,m,'visual-index',{'argv':command('ffmpeg'),'detail':m.get('detail','auto')},visual_action)
        m['imports'].extend({'path':str(p.relative_to(run)),'format':None} for p in clips)
    except ContractError as exc:m['gaps'].append('Visual index: '+str(exc))
    m['gaps'].append('Video-only rendition; audio not independently inspected. Bounded frame samples can miss brief events.')


def prepare(source, destination, question=None, detail=None, document_profile=None):
    identity = source_identity(source); run = Path(destination).absolute()
    if run.is_symlink(): raise ContractError('Run directory cannot be a symlink')
    if run.exists():
        if not (run/'run.json').is_file(): raise ContractError('Refusing an unowned output directory')
        _, m = load(run)
        if m['identity'] != identity: raise ContractError('Source changed; choose a new run directory')
    else:
        run.mkdir(parents=True, mode=0o700)
        m = {'schema': 'sourcepack.run.v2', 'version': VERSION, 'identity': identity,
             'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'acquiring',
             'jobs': [], 'gaps': [], 'artifacts': {}, 'outbound_links': []}
        write_json(run/'run.json', m)
    run = run.resolve()
    with locked(run):
        _, m = load(run); check_artifacts(run, m)
        if document_profile and document_profile!=m.get('document_profile','documents-basic'):
            from .stages import invalidate
            invalidate(m,'documents')
        m['document_profile']=document_profile or m.get('document_profile','documents-basic')
        if question and not any(x['question']==question for x in m.setdefault('analysis_requests',[])):
            m['analysis_requests'].append({'question':question,'created_at':datetime.now(timezone.utc).isoformat()})
        if detail and detail != m.get('detail','auto'):
            from .stages import invalidate
            invalidate(m,'video' if m.get('detail')=='text' else 'visual-index')
        m['detail']=detail or m.get('detail','auto');write_json(run/'run.json',m)
        if m['status'] in ('ready','ready_partial'): return m
        if m['schema']=='sourcepack.run.v1':raise ContractError('Use upgrade-run before acquisition resume')
        (run/'acquired').mkdir(exist_ok=True, mode=0o700)
        try:
            if not m.get('acquisition_complete'):
                m['gaps'] = []
                if identity['kind']=='local':
                    target=run/'acquired'/('source'+Path(identity['source']).suffix.lower())
                    shutil.copyfile(identity['source'],target)
                    m['imports']=[{'path':str(target.relative_to(run)),'format':None}]
                elif identity['kind']=='document':
                    from .documents import convert_document
                    config=json.loads(TOOL_CONFIG.read_text()) if TOOL_CONFIG.exists() else {}
                    profile=m.get('document_profile','documents-basic')
                    options=config.get(profile,{})
                    from .stages import run_stage
                    def convert():
                        converted=convert_document(Path(identity['source']),run/'acquired/document',profile,options)
                        m['gaps'].extend(converted.get('gaps',[]))
                        return [p for p in (run/'acquired/document').rglob('*') if p.is_file()]
                    run_stage(run,m,'documents',{'profile':profile,'config':options},convert)
                    m['imports']=[{'path':'acquired/document/normalized.json','format':'normalized'}]
                elif identity['kind']=='web': extract_web(run,m)
                else: extract_youtube(run,m)
                m['artifacts']={str(p.relative_to(run)):sha(p) for p in sorted((run/'acquired').rglob('*')) if p.is_file()}
                m['acquisition_complete']=True; write_json(run/'run.json',m)
            video_count=sum(Path(x['path']).suffix in ('.mp4','.mov','.webm','.mkv') for x in m['imports'])
            media_options={'max_frames':min(12,max(1,96//max(1,video_count))),'ffmpeg':command('ffmpeg'),'ffprobe':command('ffprobe')}
            engine=Engine(run/'state',run/'acquired',media_options=media_options)
            m.setdefault('jobs',[])
            for item in m['imports']:
                try:result=engine.ingest(run/item['path'],input_format=item['format'])
                except ContractError as exc:
                    if Path(item['path']).suffix not in ('.mp4','.mov','.webm','.mkv'):raise
                    m.setdefault('stages',{}).setdefault('visual-index',{}).update(status='failed',error=str(exc))
                    m['gaps'].append('Video import failed: '+str(exc));continue
                if result['job_id'] not in {j['job_id'] for j in m['jobs']}:
                    m['jobs'].append({'job_id':result['job_id'],'source':item['path']})
                write_json(run/'run.json',m)
            if not m['jobs']:raise ContractError('No usable evidence acquired; inspect stage gaps')
            m['status']='ready_partial' if any(x.get('status')=='failed' for x in m.get('stages',{}).values()) else 'ready';m.pop('error',None);write_json(run/'run.json',m)
            return m
        except Exception as exc:
            m['status']='failed';m['error']=str(exc);write_json(run/'run.json',m)
            raise


def upgrade_run(run):
    run,m=load(run)
    with locked(run):
        if m['schema']=='sourcepack.run.v2':return m
        backup=run/'run.v1.json'
        if backup.exists():raise ContractError('Upgrade backup exists; inspect previous attempt')
        shutil.copyfile(run/'run.json',backup)
        m['schema']='sourcepack.run.v2';m.setdefault('stages',{});write_json(run/'run.json',m)
    return m

def retry(run,stage):
    from .stages import invalidate, DEPENDENTS
    run,m=load(run)
    if stage not in DEPENDENTS:raise ContractError('Unknown acquisition stage')
    with locked(run):
        _,m=load(run);invalidate(m,stage);write_json(run/'run.json',m)
    return prepare(m['identity']['source'],run)

def next_ticket(run):
    run,m=load(run)
    if m['status'] not in ('ready','ready_partial'):raise ContractError('Run is not ready; retry prepare with the same source')
    engine=Engine(run/'state',run/'acquired')
    for job in m['jobs']:
        result=engine.advance(job['job_id'])
        if 'ticket' in result:
            t=result['ticket'];template={k:t[k] for k in ('job_id','task_id','attempt_id','lease_id','policy_id','source_revision_ids')}
            template.update(schema_version='sourcelens.host-result.v1',inspection_records=[],observations=[],gaps=[])
            return {**result,'spans':[engine.read(t['job_id'],eid) for eid in t['input_evidence_ids']], 'result_template':template}
    return {'status':'finished','meaning':'No pending host tickets; not proof of exhaustive understanding',
            'jobs':[engine.status(j['job_id']) for j in m['jobs']], 'acquisition_gaps':m['gaps']}


def submit(run,path):
    run,m=load(run);p=Path(path)
    if p.stat().st_size>64000:raise ContractError('Result exceeds byte budget')
    result=json.loads(p.read_text())
    if result.get('job_id') not in {j['job_id'] for j in m['jobs']}:raise ContractError('Result belongs to another run')
    return Engine(run/'state',run/'acquired').submit(result)


def query(run,text):
    run,m=load(run);engine=Engine(run/'state',run/'acquired')
    return [hit for j in m['jobs'] for hit in engine.search(j['job_id'],text)]


def focus(run,start,end):
    run,m=load(run)
    if m['identity']['kind']!='youtube' or not (0<=start<end and end-start<=240):
        raise ContractError('Focus requires a YouTube run and an interval of at most 240 seconds')
    info=json.loads((run/'acquired/metadata.json').read_text())
    if end>info['duration']:raise ContractError('Focus exceeds source duration')
    with locked(run):
        _,m=load(run);check_artifacts(run,m)
        clip=run/'acquired'/f'focus-{start:g}-{end:g}.mp4'
        if str(clip.relative_to(run)) not in m['artifacts']:
            run_tool(run,'focus',command('ffmpeg')+['-v','error','-nostdin','-y','-protocol_whitelist','file,pipe',
                '-ss',str(start),'-to',str(end),'-copyts','-f','mov','-i',str(run/'acquired/video.mp4'),
                '-map','0:v:0','-an','-c','copy',str(clip)],120)
        options={'max_frames':12,'ffmpeg':command('ffmpeg'),'ffprobe':command('ffprobe'),'start_ms':round(start*1000),'end_ms':round(end*1000)}
        engine=Engine(run/'state',run/'acquired',media_options=options)
        total=sum(sum(s['kind']=='frame' for s in engine.snapshot(j['job_id'])['spans']) for j in m['jobs'])
        existing=next((j for j in m['jobs'] if j['source']==str(clip.relative_to(run))),None)
        if not existing and total+12>144:raise ContractError('Collection frame budget exhausted')
        result=engine.ingest(clip)
        if result['job_id'] not in {j['job_id'] for j in m['jobs']}:
            m['jobs'].append({'job_id':result['job_id'],'source':str(clip.relative_to(run))})
        m['artifacts'][str(clip.relative_to(run))]=sha(clip);write_json(run/'run.json',m)
        return result


def export_run(run,destination,include_originals=True):
    from .pack import build_pack
    return build_pack(run,destination,include_originals)


def doctor():
    tools={}
    for name in ('summarize','yt-dlp','ffmpeg','ffprobe'):
        argv=command(name);found=bool(shutil.which(argv[0]));version=None;error=None
        if found:
            try:
                p=subprocess.run(argv+(['-version'] if name in ('ffmpeg','ffprobe') else ['--version']),capture_output=True,timeout=8,env=extraction_env())
                version=(p.stdout or p.stderr).decode(errors='replace').splitlines()[0][:200]
                if p.returncode:error='Version probe failed'
            except (OSError,subprocess.SubprocessError,IndexError):error='Version probe unavailable'
        tools[name]={'argv':argv,'found':found,'version':version,'error':error}
    config=json.loads(TOOL_CONFIG.read_text()) if TOOL_CONFIG.exists() else {};profiles={}
    for name,package in [('documents-basic','markitdown'),('documents-layout','docling-slim')]:
        options=config.get(name,{});argv=options.get('argv') if isinstance(options,dict) else None
        result={'ready':False,'version':None,'gap':'Optional interpreter not configured'}
        if isinstance(argv,list) and argv:
            try:
                code='from importlib.metadata import version; print(version('+repr(package)+'))'
                p=subprocess.run(argv+['-c',code],capture_output=True,timeout=10,env=extraction_env())
                result={'ready':p.returncode==0,'version':p.stdout.decode().strip() or None,'gap':None if p.returncode==0 else 'Package unavailable in configured interpreter'}
                if name=='documents-layout':
                    from .documents import layout_readiness
                    readiness=layout_readiness(options);result['ready']=result['ready'] and readiness['ready'];result['layout']=readiness
            except (OSError,subprocess.SubprocessError):result['gap']='Interpreter unavailable'
        profiles[name]=result
    return {'version':VERSION,'python':sys.version.split()[0],'platform':sys.platform,'tools':tools,'profiles':profiles,
            'note':'Version/readiness probes do not prove extraction. No installs, model downloads or account changes.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('doctor')
    a=sub.add_parser('prepare');a.add_argument('source');a.add_argument('--out',required=True);a.add_argument('--question');a.add_argument('--detail',choices=['auto','text','deep']);a.add_argument('--document-profile',choices=['documents-basic','documents-layout'])
    a=sub.add_parser('retry');a.add_argument('run');a.add_argument('--stage',required=True)
    a=sub.add_parser('upgrade-run');a.add_argument('run')
    a=sub.add_parser('next');a.add_argument('run')
    a=sub.add_parser('read');a.add_argument('run')
    a=sub.add_parser('inspect');a.add_argument('run')
    a=sub.add_parser('finish');a.add_argument('run');a.add_argument('findings')
    a=sub.add_parser('record');a.add_argument('run');a.add_argument('annotations')
    a=sub.add_parser('submit');a.add_argument('run');a.add_argument('result')
    a=sub.add_parser('query');a.add_argument('run');a.add_argument('text');a.add_argument('--compact',action='store_true')
    a=sub.add_parser('focus');a.add_argument('run');a.add_argument('start',type=float);a.add_argument('end',type=float)
    a=sub.add_parser('export');a.add_argument('run');a.add_argument('destination');a.add_argument('--lightweight',action='store_true')
    a=sub.add_parser('support');a.add_argument('run');a.add_argument('child_run');a.add_argument('--role',required=True)
    a=sub.add_parser('answer');a.add_argument('run');a.add_argument('file')
    args=p.parse_args(argv)
    try:
        if args.action=='doctor':result=doctor()
        elif args.action=='prepare':result=prepare(args.source,args.out,args.question,args.detail,args.document_profile)
        elif args.action=='retry':result=retry(args.run,args.stage)
        elif args.action=='upgrade-run':result=upgrade_run(args.run)
        elif args.action=='next':result=next_ticket(args.run)
        elif args.action=='inspect':
            from .quick import inspect_run
            result=inspect_run(args.run)
        elif args.action=='finish':
            from .quick import finish_run
            path=Path(args.findings)
            if path.stat().st_size>128000:raise ContractError('Findings byte budget exceeded')
            result=finish_run(args.run,json.loads(path.read_text()))
        elif args.action=='read':
            from .packets import present_packet
            result=present_packet(args.run)
        elif args.action=='record':
            from .packets import record_packet
            p=Path(args.annotations)
            if p.stat().st_size>64000:raise ContractError('Annotation byte budget exceeded')
            annotations=json.loads(p.read_text());packet_id=annotations.pop('packet_id')
            result=record_packet(args.run,packet_id,annotations)
        elif args.action=='submit':result=submit(args.run,args.result)
        elif args.action=='query':
            result=query(args.run,args.text)
            if args.compact:
                from .quick import compact_span
                result=[compact_span(s) for s in result]
        elif args.action=='focus':result=focus(args.run,args.start,args.end)
        elif args.action=='support':
            from .pack import register_supporting_source
            result=register_supporting_source(args.run,args.child_run,args.role)
        elif args.action=='answer':
            from .pack import save_answer
            result=save_answer(args.run,args.file)
        else:result=export_run(args.run,args.destination,not args.lightweight)
        print(json.dumps({'status':'ok','data':result},ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'error','error':str(exc)},ensure_ascii=False));return 2
