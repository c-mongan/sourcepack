"""Bounded optional document conversion through an isolated interpreter."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from .contracts import ContractError
from .normalized import file_sha,payload_for,validate_normalized

SUFFIXES={'.pdf','.docx','.pptx','.xlsx'}

def document_preflight(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.suffix.lower() not in SUFFIXES:raise ContractError('Supported documents: PDF, DOCX, PPTX, XLSX; no macro formats')
    if p.stat().st_size>64*1024*1024:raise ContractError('Document exceeds 64 MiB')
    if p.suffix.lower()!='.pdf':
        try:
            with zipfile.ZipFile(p) as z:
                entries=z.infolist()
                if len(entries)>10000 or sum(x.file_size for x in entries)>256*1024*1024:raise ContractError('Office archive expansion exceeds budget')
                for x in entries:
                    if x.flag_bits&1 or Path(x.filename).is_absolute() or '..' in Path(x.filename).parts or '\\' in x.filename:raise ContractError('Unsafe/encrypted office entry')
                    if x.filename.lower().endswith('vbaproject.bin'):raise ContractError('Office macros are unsupported')
        except zipfile.BadZipFile as exc:raise ContractError('Malformed office document') from exc
    elif not p.read_bytes()[:8].startswith(b'%PDF-'):raise ContractError('Invalid PDF header')
    return {'suffix':p.suffix.lower(),'bytes':p.stat().st_size,'sha256':file_sha(p)}

def layout_readiness(config):
    root=config.get('artifacts_path');manifest=config.get('artifacts_manifest')
    result={'ready':False,'artifacts_present':False,'ocr_available':False,'gaps':[]}
    if not root or not Path(root).is_dir() or not isinstance(manifest,list) or not manifest:
        result['gaps'].append('Explicit existing layout artifacts and hash manifest required; no model downloads');return result
    try:
        from .normalized import checked_path
        for entry in manifest:checked_path(Path(root),entry)
    except (ContractError,OSError):result['gaps'].append('Layout artifacts missing or changed');return result
    result.update(ready=False,artifacts_present=True,completeness_verified=False)
    result['gaps'].append('Model completeness unverified: no model-backed layout profile has been qualified for this release')
    result['gaps'].append('OCR disabled until an explicit local backend is qualified')
    return result

def convert_document(path,output,profile,options):
    source=Path(path);document_preflight(source)
    if profile not in ('documents-basic','documents-layout'):raise ContractError('Unknown document profile')
    if profile=='documents-layout':
        readiness=layout_readiness(options)
        if not readiness['ready']:raise ContractError('; '.join(readiness['gaps']))
    argv=options.get('argv')
    if not isinstance(argv,list) or not argv or any(not isinstance(x,str) or not x for x in argv):raise ContractError('Configure document interpreter argv; no automatic installation')
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    original=out/('original'+source.suffix.lower());shutil.copyfile(source,original)
    request={'source':str(original.resolve()),'output':str(out.resolve()),'profile':profile,
             'artifacts_path':options.get('artifacts_path'),'artifacts_manifest':options.get('artifacts_manifest')}
    (out/'request.json').write_text(json.dumps(request))
    cmd=argv+([] if options.get('worker_override') else [str(Path(__file__).with_name('document_worker.py'))])+[str(out/'request.json')]
    env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','SYSTEMROOT','TMPDIR')}
    env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',DO_NOT_TRACK='1')
    try:
        with (out/'worker.stdout').open('wb') as stdout,(out/'worker.stderr').open('wb') as stderr:
            proc=subprocess.run(cmd,env=env,stdout=stdout,stderr=stderr,timeout=120)
        if proc.returncode:raise ContractError('Document converter failed; inspect worker.stderr')
    except (OSError,subprocess.SubprocessError) as exc:raise ContractError('Document converter unavailable or timed out; inspect worker diagnostics') from exc
    producer=out/'producer.json'
    if not producer.is_file() or producer.stat().st_size>16*1024*1024:raise ContractError('Invalid converter output budget')
    data=json.loads(producer.read_text());blocks=[];source_hash=file_sha(original)
    for item in data['blocks']:
        text=item['text']
        if not isinstance(text,str):raise ContractError('Invalid converter text')
        for start in range(0,len(text),1200):
            if len(blocks)>=2000:raise ContractError('Document block budget exceeded')
            blocks.append({'id':f'block-{len(blocks)+1}','kind':item.get('kind','document'),'text':text[start:start+1200],
                'source_sha256':source_hash,'method':profile,'locator':{**item['locator'],'derived_start_char':start,'derived_end_char':min(start+1200,len(text))}})
    if not blocks:raise ContractError('No readable document text; scanned/image content requires visual inspection or a qualified OCR profile')
    assets=[{'path':'producer.json','sha256':file_sha(producer),'source_sha256':source_hash,'locator':{'coordinate_basis':'producer-output'}}]
    for asset in data.get('assets',[]):
        name=asset['path']
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ContractError('Unsafe converter asset')
        p=out/name
        if p.is_symlink() or not p.resolve().is_relative_to(out.resolve()):raise ContractError('Escaping converter asset')
        assets.append({**asset,'sha256':file_sha(p),'source_sha256':source_hash})
    for asset in assets:
        if asset['path'].lower().endswith('.png'):
            if len(blocks)>=2000:raise ContractError('Document block budget exceeded')
            blocks.append({'id':f'block-{len(blocks)+1}','kind':'frame','text':'','source_sha256':source_hash,
                'method':profile,'locator':asset['locator'],'asset_path':asset['path']})
    payload=payload_for(original,blocks,out,{'profile':profile,'version':data['version']},assets=assets)
    payload['gaps']=data.get('gaps',[])
    validate_normalized(payload,out)
    (out/'normalized.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    (out/'document.md').write_text(data.get('markdown',''),encoding='utf-8')
    return payload
