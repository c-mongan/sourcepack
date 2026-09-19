"""Portable source register and readable evidence pack; original evidence stays private."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from .contracts import ContractError

def portable(value):
    if isinstance(value,dict):return {k:portable(v) for k,v in value.items()}
    if isinstance(value,list):return [portable(v) for v in value]
    if isinstance(value,str) and Path(value).is_absolute():return Path(value).name
    return value

def register_supporting_source(run,child_run,role):
    from . import workflow as w
    run,m=w.load(run);child,c=w.load(child_run)
    if child==run or not isinstance(role,str) or not role.strip() or len(role)>200:raise ContractError('Invalid supporting source')
    with w.locked(run):
        _,m=w.load(run);sources=m.setdefault('supporting_sources',[])
        if any(x['run']==str(child) for x in sources):return m
        if len(sources)>=3:raise ContractError('Supporting source limit is three')
        sources.append({'run':str(child),'role':role,'identity':c['identity']});w.write_json(run/'run.json',m)
    return m

def save_answer(run,path):
    from . import workflow as w
    run,m=w.load(run);p=Path(path)
    if p.stat().st_size>128000:raise ContractError('Answer exceeds 128 KB')
    text=p.read_text();known=set()
    for root in [run,*[Path(s['run']) for s in m.get('supporting_sources',[])]]:
        _,cm=w.load(root);engine=w.Engine(root/'state',root/'acquired')
        for job in cm['jobs']:
            snapshot=engine.snapshot(job['job_id'])
            for r in snapshot['results']:
                known.update(x['evidence_id'] for x in r['inspection_records'])
    cited=set(re.findall(r'ev-[a-f0-9]{32}',text))
    if cited-known:raise ContractError('Answer cites uninspected or unknown evidence')
    (run/'answer.md').write_text(text)
    return {'saved':True,'citations':len(cited),'semantic_accuracy':'host judgment'}

def build_pack(run,destination,include_originals=True):
    from . import workflow as w
    run,m=w.load(run);dest=Path(destination).absolute()
    if dest.exists():raise ContractError('Export destination must not exist')
    dest.parent.mkdir(parents=True,exist_ok=True)
    roots=[(run,'primary'),*[(Path(s['run']),s['role']) for s in m.get('supporting_sources',[])]]
    with tempfile.TemporaryDirectory(dir=dest.parent,prefix='.sourcepack-export-') as td:
        stage=Path(td)/'pack';stage.mkdir(mode=0o700);register=[];text_sections=[];frames=[];evidence_links={};observations=[];omissions=[];gaps=[];number=0
        for root,role in roots:
            root,cm=w.load(root);w.check_artifacts(root,cm);engine=w.Engine(root/'state',root/'acquired')
            gaps.extend(cm.get('gaps',[]));scope='acquired' if root==run else f'companion-{len(register)+1}-acquired'
            if include_originals:
                for p in (root/'acquired').rglob('*'):
                    if not p.is_file():continue
                    if p.name=='request.json' or p.name.startswith('worker.'):
                        omissions.append({'path':str(p.relative_to(root)),'reason':'runtime diagnostics; retained privately in run'});continue
                    target=stage/scope/p.relative_to(root/'acquired');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
            else:omissions.append({'path':scope,'reason':'lightweight export omits acquisition originals'})
            for job in cm['jobs']:
                number+=1;name=f'source-{number:03d}';engine.export(job['job_id'],stage/name)
                snapshot=engine.snapshot(job['job_id']);inspected=set()
                for r in snapshot['results']:
                    inspected.update(x['evidence_id'] for x in r['inspection_records']);observations.extend(r['observations'])
                register.append({'job_id':job['job_id'],'label':job['source'],'role':role,'index':name+'/index.md',
                    'identity':portable(cm['identity']),'acquired':True,'inspected_count':len(inspected),'span_count':len(snapshot['spans'])})
                for span in snapshot['spans']:
                    evidence_links[span['id']]=name+'/evidence.md#'+span['id']
                    location={k:v for k,v in span['locator'].items() if k not in ('cue_map','original_source_sha256')}
                    if span['kind']=='frame':
                        # Locate the same immutable artifact in the job export.
                        candidates=list((stage/name).rglob(span['artifact_sha256']+'.*'))
                        if not candidates:
                            candidates=[p for p in (stage/name).rglob('*') if p.is_file() and p.suffix=='.png' and w.sha(p)==span['artifact_sha256']]
                        if candidates:evidence_links[span['id']]=str(candidates[0].relative_to(stage))
                        if candidates:frames.append({'id':span['id'],'path':str(candidates[0].relative_to(stage)),'locator':location,'inspected':span['id'] in inspected})
                    elif span['text']:
                        text_sections.append(f"### {span['id']}\n\nSource: [{job['source']}]({name}/index.md) · {json.dumps(location,ensure_ascii=False)}\n\n{span['text']}")
        w.write_json(stage/'sources.json',register);w.write_json(stage/'observations.json',observations)
        w.write_json(stage/'run.json',portable(m));w.write_json(stage/'visual-index.json',frames)
        (stage/'document.md').write_text('# Source text\n\n'+'\n\n'.join(text_sections))
        (stage/'gaps.md').write_text('# Gaps\n\n'+'\n'.join('- '+g for g in gaps))
        answer=(run/'answer.md').read_text() if (run/'answer.md').exists() else 'No host answer has been saved. Read the evidence and record findings before drawing conclusions.\n'
        # Link evidence IDs to searchable full job indexes without changing source text.
        # Replace whole evidence links first; placeholders prevent nested Markdown.
        placeholders={}
        def link(eid):
            if eid not in evidence_links:return eid
            marker=f'\x00CITATION{len(placeholders)}\x00';placeholders[marker]=f'[{eid}]({evidence_links[eid]})';return marker
        answer=re.sub(r'\[(ev-[a-f0-9]{32})\]\([^\n]*?\)',lambda match:link(match.group(1)),answer)
        answer=re.sub(r'ev-[a-f0-9]{32}',lambda match:link(match.group()),answer)
        for marker,value in placeholders.items():answer=answer.replace(marker,value)
        (stage/'answer.md').write_text(answer)
        visual=['# Visual index','Native images are evidence; contact sheets are navigation.']
        for f in frames:visual.append(f"- [{f['id']}]({f['path']}) — {json.dumps(f['locator'])}; inspected: {f['inspected']}")
        if frames and shutil.which(w.command('ffmpeg')[0]):
            sheets=stage/'contact-sheets';sheets.mkdir()
            for offset in range(0,len(frames),12):
                batch=frames[offset:offset+12]
                with tempfile.TemporaryDirectory() as images:
                    folder=Path(images)
                    for n,f in enumerate(batch):shutil.copyfile(stage/f['path'],folder/f'{n:03d}.png')
                    target=sheets/f'sheet-{offset//12+1:02d}.jpg'
                    try:
                        proc=subprocess.run(w.command('ffmpeg')+['-v','error','-nostdin','-threads','1','-framerate','1','-i',str(folder/'%03d.png'),'-vf','scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2,tile=4x3','-frames:v','1',str(target)],capture_output=True,timeout=60)
                    except (OSError,subprocess.SubprocessError):proc=None
                    if proc is None or proc.returncode or not target.exists():gaps.append('Contact sheet generation failed or timed out; use native images')
                    else:visual.append(f"\n![Sheet {offset//12+1}](contact-sheets/{target.name})\n\nTiles left-to-right: "+', '.join(f"[{f['id']}]({f['path']})" for f in batch))
        (stage/'gaps.md').write_text('# Gaps\n\n'+'\n'.join('- '+g for g in gaps))
        (stage/'visual-index.md').write_text('\n\n'.join(visual))
        (stage/'index.md').write_text('# SourcePack evidence\n\nPrivate pack. Inspection is a host self-report, not a certification.\n\n[Answer](answer.md) · [Source text](document.md) · [Visuals](visual-index.md) · [Gaps](gaps.md) · [Source register](sources.json)\n\n'+'\n'.join(f"- [{s['label']}]({s['index']}) — {s['role']}; inspected {s['inspected_count']}/{s['span_count']}" for s in register))
        w.write_json(stage/'manifest.json',{'schema':'sourcepack.collection.v2','self_contained_originals':include_originals,'omissions':omissions,
            'files':{str(p.relative_to(stage)):w.sha(p) for p in stage.rglob('*') if p.is_file()}})
        os.rename(stage,dest)
    return {'status':'exported','path':str(dest),'self_contained_originals':include_originals,'omissions':omissions}
