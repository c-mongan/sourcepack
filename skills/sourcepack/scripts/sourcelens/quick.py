"""Compact evidence browsing and one-shot findings over bounded core leases."""
import json
from pathlib import Path
import re
from .contracts import ContractError, digest, object_fields, text_value


def readable_text(span):
    """Collapse overlapping rolling updates in a derived view; never edit evidence."""
    text = span['text']
    cues = span['locator'].get('cue_map', [])
    if not cues:
        return text
    parts, previous, previous_end, previous_start, rolling = [], [], None, None, False
    for cue in cues:
        words = text[cue['block_start']:cue['block_end']].split()
        start, end = cue['start_ms'], cue.get('end_ms')
        overlap = previous_end is not None and (
            (start < previous_end and start - previous_start <= 2500)
            or (start <= previous_end + 100 and start - previous_start <= 250))
        common = 0
        if overlap:
            for n in range(min(len(previous), len(words)), 0, -1):
                if previous[-n:] == words[:n]:
                    common = n
                    break
        growing = common and len(words) > common
        # Exact repeated speech is retained unless part of a very fast rolling update.
        duplicate_update = rolling and common == len(words) and start - previous_start <= 250
        if (growing and (common >= 2 or common == len(previous))) or duplicate_update:
            if words[common:]:
                parts[-1] += ' ' + ' '.join(words[common:])
            rolling = True
        else:
            parts.append(' '.join(words))
            rolling = False
        previous, previous_end, previous_start = words, end, start
    return '\n'.join(parts)


def compact_span(span):
    location = {k: v for k, v in span['locator'].items() if k not in ('cue_map', 'original_source_sha256')}
    item = {'id': span['id'], 'kind': span['kind'], 'locator': location}
    if span['kind'] == 'frame':
        item['image'] = span['artifact_path']
    else:
        item['text'] = readable_text(span)
    for key in ('search_match', 'matched_observations'):
        if key in span:
            item[key] = span[key]
    return item


def _view(run, manifest):
    from . import workflow as w
    engine = w.Engine(run/'state', run/'acquired')
    spans = []
    gaps = [{'source':'acquisition', 'reason':g} for g in manifest['gaps']]
    for job in manifest['jobs']:
        snapshot = engine.snapshot(job['job_id'])
        if snapshot['cancelled']:
            raise ContractError('Cannot inspect a cancelled job')
        gaps.extend({'source':job['source'], 'job_id':job['job_id'], **gap}
                    for gap in engine.report(snapshot)['gaps'])
        for span in snapshot['spans']:
            span['artifact_path'] = str(engine.store.path(job['job_id'], span))
            spans.append(span)
    sections = ['# Evidence reading view',
                'Derived caption cleanup, not verbatim quotations. Originals and cue mappings remain unchanged. '
                'Reading this index does not establish image inspection. Open native frames to verify visual claims.']
    if gaps:
        sections.append('## Known gaps\n\n' + '\n'.join(json.dumps(g, ensure_ascii=False) for g in gaps))
    for span in spans:
        item = compact_span(span)
        sections.append(f"## {item['id']}\n\n{json.dumps(item['locator'], ensure_ascii=False)}\n\n" +
                        (f"Native frame: {item['image']}" if 'image' in item else item['text']))
    markdown = '\n\n'.join(sections) + '\n'
    review_id = 'review-' + digest({'schema':'sourcepack.review.v1', 'identity':manifest['identity'],
                                    'spans':spans, 'markdown':markdown})[:32]
    return engine, spans, markdown, review_id, gaps


def inspect_run(run):
    from . import workflow as w
    run, m = w.load(run)
    if m['status'] not in ('ready', 'ready_partial'):
        raise ContractError('Run is not ready')
    engine, spans, markdown, review_id, gaps = _view(run, m)
    folder = run/'reviews'/review_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'reading.md').write_text(markdown)
    w.write_json(folder/'evidence.json', [compact_span(s) for s in spans])
    return {'schema':'sourcepack.review.v1', 'review_id':review_id,
            'reading_file':str(folder/'reading.md'), 'evidence_file':str(folder/'evidence.json'),
            'text_evidence_ids':[s['id'] for s in spans if s['kind'] != 'frame'],
            'frame_count':sum(s['kind'] == 'frame' for s in spans), 'gaps':gaps,
            'inspection':'No inspection is recorded until finish explicitly reports inspected IDs.'}


def finish_run(run, notes):
    from . import workflow as w
    from .pack import save_answer
    run, m = w.load(run)
    object_fields(notes, {'schema','review_id','inspected_ids','observations','answer'})
    if notes['schema'] != 'sourcepack.findings.v1' or len(json.dumps(notes).encode()) > 128000:
        raise ContractError('Unsupported or oversized findings')
    with w.locked(run):
        _, m = w.load(run)
        engine, spans, markdown, review_id, gaps = _view(run, m)
        if notes['review_id'] != review_id:
            raise ContractError('Evidence changed; inspect again before finishing')
        folder = run/'reviews'/review_id
        if (folder/'reading.md').read_text() != markdown or json.loads((folder/'evidence.json').read_text()) != [compact_span(s) for s in spans]:
            raise ContractError('Review presentation changed; inspect again')
        by_id = {s['id']:s for s in spans}
        inspected = notes['inspected_ids']
        if (not isinstance(inspected,list) or any(not isinstance(eid,str) for eid in inspected)
                or len(inspected) > 2000 or len(set(inspected)) != len(inspected)
                or not set(inspected) <= by_id.keys()):
            raise ContractError('Unknown or duplicate inspected evidence')
        observations = notes['observations']
        if not isinstance(observations,list) or len(observations) > 64:
            raise ContractError('Findings require at most 64 observations')
        batches, covered = [], set()
        # Validate every observation before submitting anything. Cross-job facts need separate observations.
        for obs in observations:
            object_fields(obs, {'text','evidence_ids','certainty'}, {'quote'})
            text_value(obs['text'])
            ids = obs['evidence_ids']
            if (not isinstance(ids,list) or not ids or any(not isinstance(eid,str) or eid not in inspected for eid in ids)
                    or len(ids)>engine.policy.max_ticket_spans or len(set(ids))!=len(ids)):
                raise ContractError('Observation requires bounded inspected evidence IDs')
            if len({by_id[eid]['job_id'] for eid in ids}) != 1:
                raise ContractError('Use separate observations for different source jobs')
            if obs['certainty'] not in ('observed','inferred','uncertain'):
                raise ContractError('Unsupported certainty label')
            if 'quote' in obs and not any(by_id[eid]['kind']!='frame' and text_value(obs['quote']) in by_id[eid]['text'] for eid in ids):
                raise ContractError('Quotation does not match original text')
            if sum(len(by_id[eid]['text']) for eid in ids) > engine.policy.max_ticket_characters:
                raise ContractError('Observation exceeds text budget')
            batches.append((by_id[ids[0]]['job_id'], ids, [obs]))
            covered.update(ids)
        for job in m['jobs']:
            remaining = [eid for eid in inspected if eid not in covered and by_id[eid]['job_id']==job['job_id']]
            for start in range(0,len(remaining),engine.policy.max_ticket_spans):
                batches.append((job['job_id'],remaining[start:start+engine.policy.max_ticket_spans],[]))
        answer = text_value(notes['answer'],128000)
        prior = {x['evidence_id'] for j in m['jobs'] for r in engine.snapshot(j['job_id'])['results'] for x in r['inspection_records']}
        cited = set(re.findall(r'ev-[a-f0-9]{32}',answer))
        if not cited <= prior | set(inspected):
            raise ContractError('Answer cites unknown or uninspected evidence')
        request_id = digest(notes)
        pending = folder/(request_id+'.json')
        w.write_json(pending,notes)
        for number,(job_id,ids,obs) in enumerate(batches):
            ticket = engine.inspection_ticket(job_id,ids,request_id+f'-{number}')
            result = {k:ticket[k] for k in ('job_id','task_id','attempt_id','lease_id','policy_id','source_revision_ids')}
            result.update(schema_version='sourcelens.host-result.v2',
                          inspection_records=[{'evidence_id':eid,'provenance':'model_self_report'} for eid in ids],
                          observations=obs,gaps=[],no_findings_reason=None if obs else 'Inspected; no finding retained for this answer.')
            engine.submit(result)
        draft = folder/(request_id+'.md');draft.write_text(answer)
        save_answer(run,draft)
        response = {'status':'saved','answer':str(run/'answer.md'),'findings':str(pending),
                    'inspected_count':len(inspected),'observations':len(observations),
                    'uninspected_count':len(by_id.keys()-(prior|set(inspected))),
                    'coverage':'Selected evidence only; unrelated inspection tasks remain pending.',
                    'semantic_support':'host self-report; not independently verified', 'gaps':gaps}
        w.write_json(folder/(request_id+'-receipt.json'),response)
        return response
