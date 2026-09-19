"""Lossless derived reading blocks with hashed original-source associations."""
import hashlib
from html import unescape
import json
import math
from pathlib import Path
import re
from .contracts import ContractError
from .adapters import timestamp

SCHEMA = 'sourcepack.normalized.v1'

def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''): h.update(part)
    return h.hexdigest()

def group_cues(cues, source_sha256, max_chars=1200):
    if not 1 <= max_chars <= 1200: raise ContractError('Invalid block bound')
    blocks=[]; previous=-1; seen=set()
    for cue in cues:
        start,end,text=cue['start_ms'],cue.get('end_ms'),cue['text']
        valid=lambda v:type(v) in (int,float) and math.isfinite(v) and 0<=v<=10**12
        if not valid(start) or start<previous or (end is not None and (not valid(end) or end<=start)):
            raise ContractError('Invalid cue timing')
        if not isinstance(text,str) or not text.strip() or cue['id'] in seen: raise ContractError('Invalid or duplicate cue')
        seen.add(cue['id']);previous=start;offset=0
        while offset<len(text):
            if not blocks or len(blocks[-1]['text'])>=max_chars-1:
                if len(blocks)>=2000: raise ContractError('Block budget exceeded')
                blocks.append({'id':f'block-{len(blocks)+1}', 'kind':'transcript','text':'',
                    'source_sha256':source_sha256,'method':'lossless-cue-group-v1',
                    'locator':{'start_ms':start,'end_ms':end,'coordinate_basis':'original-caption-time'},'cue_map':[]})
            b=blocks[-1]
            if b['text']: b['text']+='\n'
            pos=len(b['text']);part=text[offset:offset+max_chars-pos]
            b['text']+=part
            b['cue_map'].append({'cue_id':cue['id'],'start_ms':start,'end_ms':end,'source_start':offset,
                                 'source_end':offset+len(part),'block_start':pos,'block_end':pos+len(part)})
            b['locator']['end_ms']=end;offset+=len(part)
    return blocks

def cues_from_vtt(raw):
    cues=[]
    for block in re.split(r'\n\s*\n',raw.replace('\r\n','\n')):
        lines=block.splitlines()
        if not lines or lines[0].startswith(('NOTE','STYLE','REGION')):continue
        for i,line in enumerate(lines):
            if '-->' not in line:continue
            a,b=line.split('-->',1)
            text=unescape(re.sub(r'<[^>]*>','','\n'.join(lines[i+1:])))
            if text.strip():cues.append({'id':str(len(cues)),'start_ms':timestamp(a.strip()),
                'end_ms':timestamp(b.strip().split()[0]),'text':text})
            break
    if not cues:raise ContractError('No usable caption cues')
    return cues

def payload_for(source, blocks, root, producer, assets=None, origin=None):
    return {'schema':SCHEMA,'source':{'path':str(Path(source).relative_to(root)),
        'sha256':file_sha(source),'origin':origin},'producer':producer,'blocks':blocks,'assets':assets or []}

def checked_path(root, item):
    name=item.get('path');base=Path(root).resolve()
    if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts:raise ContractError('Unsafe normalized path')
    p=base/name
    if any(parent.is_symlink() for parent in [p,*p.parents] if parent!=base and parent.is_relative_to(base)):
        raise ContractError('Symlink normalized asset')
    try:resolved=p.resolve(strict=True)
    except OSError as exc:raise ContractError('Missing normalized artifact') from exc
    if not resolved.is_relative_to(base) or not resolved.is_file():raise ContractError('Escaping normalized artifact')
    if resolved.stat().st_size>64*1024*1024 or file_sha(resolved)!=item.get('sha256'):raise ContractError('Normalized artifact hash/budget mismatch')
    return resolved

def validate_normalized(payload, root):
    if payload.get('schema')!=SCHEMA:raise ContractError('Unsupported normalized schema')
    source=payload['source'];checked_path(root,source)
    blocks=payload['blocks'];assets=payload.get('assets',[])
    if not isinstance(blocks,list) or not 0<len(blocks)<=2000 or not isinstance(assets,list) or len(assets)>200:
        raise ContractError('Normalized block/asset budget exceeded')
    ids=set();asset_paths=set()
    for asset in assets:
        checked_path(root,asset)
        if asset.get('source_sha256')!=source['sha256']:raise ContractError('Asset source mismatch')
        asset_paths.add(asset['path'])
    for b in blocks:
        if b.get('id') in ids or not isinstance(b.get('id'),str):raise ContractError('Invalid block ID')
        ids.add(b['id'])
        if b.get('source_sha256')!=source['sha256']:raise ContractError('Block source mismatch')
        if b.get('kind') not in ('text','transcript','web','frame','document','table'):raise ContractError('Invalid block kind')
        if not isinstance(b.get('text'),str) or len(b['text'])>1200 or not isinstance(b.get('locator'),dict):raise ContractError('Invalid normalized block')
        if b.get('asset_path') and b['asset_path'] not in asset_paths:raise ContractError('Unknown block asset')
        if b['kind']=='frame' and not b.get('asset_path'):raise ContractError('Frame requires image asset')
        for m in b.get('cue_map',[]):
            if not 0<=m['block_start']<m['block_end']<=len(b['text']) or m['source_end']-m['source_start']!=m['block_end']-m['block_start']:
                raise ContractError('Invalid cue map')
    return payload

def read_payload(path):
    p=Path(path)
    if p.stat().st_size>64*1024*1024:raise ContractError('Normalized payload too large')
    return validate_normalized(json.loads(p.read_text()),p.parent)
