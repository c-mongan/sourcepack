#!/usr/bin/env python3
"""Freeze skill eval cases and aggregate evidence-backed paired results. No model calls."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

def mean_known(values):
    known=[x for x in values if x is not None]
    return statistics.mean(known) if known else None

def validate_grade(case,grade):
    results=grade.get('assertion_results',[])
    if len(results)!=len(case['assertions']) or {x.get('text') for x in results}!=set(case['assertions']):raise ValueError('Missing, duplicate or changed assertions')
    for row in results:
        if type(row.get('passed')) is not bool or not isinstance(row.get('evidence'),str) or not row['evidence'].strip():raise ValueError('Every verdict requires concrete evidence')
    return sum(x['passed'] for x in results),len(results)

def initialize(dataset,destination):
    raw=Path(dataset).read_bytes();data=json.loads(raw);dest=Path(destination)
    if dest.exists():raise ValueError('Iteration destination must be new')
    dest.mkdir(parents=True)
    (dest/'evals.frozen.json').write_bytes(raw)
    receipt={'dataset_sha256':hashlib.sha256(raw).hexdigest(),'case_count':len(data['evals']),'status':'prepared_not_run'}
    (dest/'protocol.json').write_text(json.dumps(receipt,indent=2))
    for case in data['evals']:
        for mode in ('with_skill','without_skill'):
            out=dest/f"eval-{case['id']}-{case['name']}"/mode; (out/'outputs').mkdir(parents=True)
            (out/'prompt.txt').write_text(case['prompt'])
    return receipt

def aggregate(iteration):
    root=Path(iteration);raw=(root/'evals.frozen.json').read_bytes();protocol=json.loads((root/'protocol.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=protocol['dataset_sha256']:raise ValueError('Frozen dataset changed')
    rows=[];pending=[]
    for case in json.loads(raw)['evals']:
        pair={}
        for mode in ('with_skill','without_skill'):
            folder=root/f"eval-{case['id']}-{case['name']}"/mode
            if not (folder/'grading.json').exists():pending.append({'id':case['id'],'mode':mode});continue
            grade=json.loads((folder/'grading.json').read_text());passed,total=validate_grade(case,grade)
            timing=json.loads((folder/'timing.json').read_text()) if (folder/'timing.json').exists() else {}
            pair[mode]={'passed':passed,'total':total,'duration_ms':timing.get('duration_ms'),'total_tokens':timing.get('total_tokens'),'observable_cost':timing.get('observable_cost')}
        rows.append({'id':case['id'],'results':pair})
    summary={}
    for mode in ('with_skill','without_skill'):
        completed=[r['results'][mode] for r in rows if mode in r['results']]
        summary[mode]={'runs':len(completed),'passed':sum(x['passed'] for x in completed),'assertions':sum(x['total'] for x in completed),
                       'mean_duration_ms':mean_known([x['duration_ms'] for x in completed]),'mean_tokens':mean_known([x['total_tokens'] for x in completed])}
    paired=[r for r in rows if len(r['results'])==2]
    delta=sum(r['results']['with_skill']['passed']-r['results']['without_skill']['passed'] for r in paired) if paired else None
    result={'status':'incomplete' if pending else 'graded','pending':pending,'cases':rows,'summary':summary,'paired_pass_delta':delta,'paired_cases':len(paired),
            'limits':'Human/model grades require evidence review. No statistical significance or adoption claim from a small suite. Unknown usage stays null.'}
    (root/'benchmark.json').write_text(json.dumps(result,indent=2));return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('init');p.add_argument('dataset');p.add_argument('destination')
    p=sub.add_parser('aggregate');p.add_argument('iteration')
    a=parser.parse_args()
    print(json.dumps(initialize(a.dataset,a.destination) if a.action=='init' else aggregate(a.iteration),indent=2))

if __name__=='__main__':main()
