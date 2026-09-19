"""Atomic stage receipts; successful outputs are immutable and independently reusable."""
import json
import os
from pathlib import Path
import tempfile
from .contracts import ContractError, digest
from .normalized import file_sha, checked_path

DEPENDENTS={'metadata':['video','visual-index','report'], 'transcript':['report'],
    'video':['visual-index','report'], 'visual-index':['report'], 'documents':['report'], 'supporting-sources':['report']}

def load_run(run):return json.loads((Path(run)/'run.json').read_text())

def save_run(run,manifest):
    root=Path(run)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=root,delete=False) as f:
        json.dump(manifest,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno());temp=f.name
    os.replace(temp,root/'run.json')

def stage_reusable(record,options_hash,root):
    if record.get('status')!='ok' or record.get('options_hash')!=options_hash:return False
    for asset in record.get('artifacts',[]):
        # Videos have a larger acquisition allowance than normalized source inputs.
        p=Path(root)/asset['path']
        if Path(asset['path']).is_absolute() or '..' in Path(asset['path']).parts or p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(Path(root).resolve()) or file_sha(p)!=asset['sha256']:
            raise ContractError('Successful stage artifact changed; choose a new snapshot')
    return True

def run_stage(run,manifest,name,options,action):
    stages=manifest.setdefault('stages',{});record=stages.setdefault(name,{'status':'pending','attempts':[]})
    record.setdefault('attempts',[])
    key=digest(options)
    if stage_reusable(record,key,run):return [Path(run)/a['path'] for a in record['artifacts']]
    record.update(status='pending',options_hash=key,producer=options)
    save_run(run,manifest)
    try:
        paths=action()
        record.update(status='ok',artifacts=[{'path':str(p.relative_to(run)),'sha256':file_sha(p)} for p in paths])
        record.pop('error',None);record['attempts'].append({'status':'ok'})
        return paths
    except Exception as exc:
        record.update(status='failed',error=str(exc));record['attempts'].append({'status':'failed','error':str(exc)})
        raise
    finally:save_run(run,manifest)

def invalidate(manifest,stage):
    for name in [stage,*DEPENDENTS.get(stage,[])]:
        if name in manifest.get('stages',{}):manifest['stages'][name]['status']='pending'
    manifest.pop('acquisition_complete',None)
    manifest['status']='acquiring'
    return manifest
