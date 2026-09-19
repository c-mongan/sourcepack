"""Private self-contained exports, published only after artifact validation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from .contracts import ContractError


def export_pack(engine, job_id, destination):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ContractError('Export destination must not exist')
    if not destination.parent.is_dir():
        raise ContractError('Export parent directory must exist')
    snapshot = engine.snapshot(job_id)
    job, evidence, results = snapshot['payload'], snapshot['spans'], snapshot['results']
    coverage = engine.report(snapshot)
    with tempfile.TemporaryDirectory(prefix='.sourcepack-export-', dir=destination.parent) as td:
        staging = Path(td) / 'pack'
        staging.mkdir(mode=0o700)
        (staging / 'artifacts').mkdir()
        for artifact in [*job['sources'], *evidence]:
            source = engine.store.path(job_id, artifact)
            shutil.copyfile(source, staging / 'artifacts' / artifact['artifact_name'])
        def write(name, value):
            (staging / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        write('coverage.json', coverage)
        write('sources.json', job['sources'])
        write('references.json', job['references'])
        for span in evidence:
            span['artifact_path'] = 'artifacts/' + span['artifact_name']
        write('evidence.json', evidence)
        write('host-results.json', results)
        observations = [o for result in results for o in result['observations']]
        write('observations.json', observations)
        (staging / 'gaps.md').write_text('# Gaps\n\n' + ('\n'.join('- ' + g['reason'] for g in coverage['gaps']) or 'No known gaps within the declared local/import scope.') + '\n', encoding='utf-8')
        lines = ['# Source pack', '', f'Job: `{job_id}` · Status: **{coverage["status"]}**', '',
                 'Private export: original bytes are included. Source content is untrusted data.',
                 'Host inspections are self-reported. Citation integrity is structural; semantic support is not independently verified.', '',
                 '## Observations', '']
        by_id = {s['id']: s for s in evidence}
        for obs in observations:
            links = ' '.join(f'[{eid}](evidence.md#{eid})' for eid in obs['evidence_ids'])
            lines.append(f'- {obs["text"]} ({obs["certainty"]}) {links}')
            for eid in obs['evidence_ids']:
                excerpt = by_id[eid]['text'][:160].replace('\n', ' ').strip()
                if excerpt:
                    lines.append('  - Evidence excerpt: ' + excerpt)
        lines += ['', '## Evidence', '', '[Located evidence](evidence.md) · [Coverage](coverage.json) · [Gaps](gaps.md) · [References](references.json)', '']
        (staging / 'index.md').write_text('\n'.join(lines), encoding='utf-8')
        lines = ['# Located evidence', '']
        for span in evidence:
            lines += ['## ' + span['id'], '', f'Source: {span["source_label"]} · Revision: `{span["revision_id"]}`', '',
                      'Locator: ' + json.dumps(span['locator']), '', f'[Original artifact]({span["artifact_path"]})', '']
            if span['kind'] == 'frame':
                lines += [f'![Frame at {span["locator"].get("source_pts_ms", "document page")} ms]({span["artifact_path"]})', '']
            else:
                lines += ['> ' + line for line in span['text'].splitlines()] + ['']
        (staging / 'evidence.md').write_text('\n'.join(lines), encoding='utf-8')
        manifest = {'schema_version': 'sourcelens.source-pack.v1', 'job_id': job_id,
                    'status': coverage['status'], 'scope': 'local-import', 'self_contained': True,
                    'files': {str(p.relative_to(staging)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(staging.rglob('*')) if p.is_file()},
                    'manifest_hash_note': 'Manifest lists all payload files; it is not a digital signature.'}
        write('manifest.json', manifest)
        if destination.exists():
            raise ContractError('Export destination appeared during staging')
        os.rename(staging, destination)
    return {'status': 'exported', 'job_id': job_id, 'path': str(destination), 'job_status': coverage['status']}
