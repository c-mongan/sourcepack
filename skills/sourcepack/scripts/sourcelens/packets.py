"""Readable host packets backed by unchanged engine leases."""
import json
from pathlib import Path
from .contracts import ContractError,digest

def packet_markdown(spans):
    return '\n\n'.join(f"### {s['id']}\n{json.dumps(s['locator'],ensure_ascii=False)}\n\n"+(s['text'] or f"Open native image: {s['artifact_path']}") for s in spans)

def present_packet(run):
    from . import workflow as w
    run,m=w.load(run)
    packet=w.next_ticket(run)
    if 'ticket' not in packet:return packet
    packet['markdown']=packet_markdown(packet['spans'])
    packet_id='packet-'+digest({'ticket':packet['ticket'],'spans':packet['spans'],'markdown':packet['markdown']})[:32]
    packet['packet_id']=packet_id
    directory=run/'packets';directory.mkdir(exist_ok=True)
    w.write_json(directory/(packet_id+'.json'),packet)
    return packet

def record_packet(run,packet_id,annotations):
    from . import workflow as w
    run,m=w.load(run)
    if not isinstance(packet_id,str) or not packet_id.startswith('packet-') or len(packet_id)!=39 or any(c not in '0123456789abcdef' for c in packet_id[7:]):raise ContractError('Invalid packet ID')
    path=run/'packets'/(packet_id+'.json')
    packet=json.loads(path.read_text());ticket=packet['ticket']
    engine=w.Engine(run/'state',run/'acquired')
    spans=[engine.read(ticket['job_id'],eid) for eid in ticket['input_evidence_ids']]
    expected={'ticket':ticket,'spans':spans,'markdown':packet_markdown(spans)}
    if 'packet-'+digest(expected)[:32]!=packet_id or packet['spans']!=spans or packet['markdown']!=expected['markdown']:
        raise ContractError('Packet content changed; read a fresh packet')
    if annotations.keys()-{'inspected_ids','observations','gaps'}:raise ContractError('Unknown annotation field')
    inspected=annotations.get('inspected_ids',[])
    if not isinstance(inspected,list) or len(set(inspected))!=len(inspected) or not set(inspected)<=set(ticket['input_evidence_ids']):raise ContractError('Unknown or duplicate inspected evidence')
    result=packet['result_template']
    result.update(inspection_records=[{'evidence_id':eid,'provenance':'model_self_report'} for eid in inspected],
                  observations=annotations.get('observations',[]),gaps=annotations.get('gaps',[]))
    engine=w.Engine(run/'state',run/'acquired')
    if ticket['job_id'] not in {j['job_id'] for j in m['jobs']}:raise ContractError('Packet belongs to another run')
    return engine.submit(result)
