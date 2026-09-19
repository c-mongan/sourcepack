"""Foreground JSON CLI. Exits never imply that the job is complete."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import sys
import uuid

from . import __version__
from .contracts import ContractError, Policy
from .engine import Engine


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ContractError(message)


def parser():
    p = Parser(prog='sourcelens')
    p.add_argument('--store', default='.sourcelens')
    p.add_argument('--allow-root', default='.')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    ingest = sub.add_parser('ingest')
    ingest.add_argument('input')
    ingest.add_argument('--related', action='append', default=[])
    ingest.add_argument('--captions')
    ingest.add_argument('--input-format', choices=['summarize'])
    job = sub.add_parser('job')
    job.add_argument('action', choices=['advance', 'status', 'cancel', 'synthesize'])
    job.add_argument('job_id')
    job.add_argument('--evidence', action='append', default=[])
    task = sub.add_parser('task')
    task.add_argument('action', choices=['submit'])
    task.add_argument('file')
    evidence = sub.add_parser('evidence')
    evidence.add_argument('action', choices=['read'])
    evidence.add_argument('job_id')
    evidence.add_argument('evidence_id')
    query = sub.add_parser('query')
    query.add_argument('job_id')
    query.add_argument('text')
    export = sub.add_parser('export')
    export.add_argument('job_id')
    export.add_argument('destination')
    return p


def main(argv=None):
    envelope = {'schema_version': 'sourcelens.response.v1', 'request_id': uuid.uuid4().hex,
                'status': 'ok', 'data': None, 'errors': []}
    code = 0
    try:
        args = parser().parse_args(argv)
        if args.command == 'doctor':
            with sqlite3.connect(':memory:') as db:
                db.execute('CREATE VIRTUAL TABLE canary USING fts5(text)')
                db.execute("INSERT INTO canary VALUES('probe')")
                fts = bool(db.execute("SELECT * FROM canary WHERE canary MATCH 'probe'").fetchone())
            data = {'version': __version__, 'python': platform.python_version(), 'execution_machine': platform.platform(),
                    'sqlite_fts5_canary': fts, 'ffmpeg_detected': bool(shutil.which('ffmpeg')),
                    'ffprobe_detected': bool(shutil.which('ffprobe')), 'host_vision': 'not_probed',
                    'source_access': 'local-only', 'model_inference': 'not_probed',
                    'install_performed': False, 'limits': Policy().__dict__}
        else:
            engine = Engine(Path(args.store), Path(args.allow_root))
            if args.command == 'ingest':
                data = engine.ingest(args.input, args.related, args.captions, args.input_format)
            elif args.command == 'job':
                data = (engine.synthesize(args.job_id, args.evidence) if args.action == 'synthesize'
                        else getattr(engine, args.action)(args.job_id))
            elif args.command == 'task':
                _, raw = engine._input(args.file)
                if len(raw) > engine.policy.max_result_bytes:
                    raise ContractError('Host result exceeds size limit')
                data = engine.submit(json.loads(raw))
            elif args.command == 'evidence':
                data = engine.read(args.job_id, args.evidence_id)
            elif args.command == 'query':
                data = {'matches': engine.search(args.job_id, args.text)}
            else:
                data = engine.export(args.job_id, args.destination)
        envelope['data'] = data
        if isinstance(data, dict) and data.get('status'):
            envelope['status'] = data['status']
    except (ContractError, OSError, ValueError, sqlite3.Error) as exc:
        code = 2
        envelope.update(status='error', errors=[{'code': type(exc).__name__, 'message': str(exc)}])
    print(json.dumps(envelope, ensure_ascii=False, allow_nan=False))
    return code
