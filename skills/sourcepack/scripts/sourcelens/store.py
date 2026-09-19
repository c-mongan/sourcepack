"""Job-scoped content store and SQLite coordination; no external services."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .contracts import ContractError, canonical

SCHEMA = '''
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, payload TEXT NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), ordinal INTEGER NOT NULL, state TEXT NOT NULL, ticket TEXT NOT NULL, expires_at REAL NOT NULL DEFAULT 0, accepted_hash TEXT, accepted_response TEXT);
CREATE TABLE IF NOT EXISTS results(task_id TEXT PRIMARY KEY REFERENCES tasks(id), job_id TEXT NOT NULL REFERENCES jobs(id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, job_id TEXT NOT NULL, kind TEXT NOT NULL, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(evidence_id UNINDEXED, job_id UNINDEXED, text);
'''


class Store:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.root / 'state.sqlite3'
        with self.db() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1, 2):
                raise ContractError('Unsupported database schema; no automatic migration')
            db.executescript(SCHEMA)
            db.execute('BEGIN IMMEDIATE')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS observation_index USING fts5(job_id UNINDEXED, payload UNINDEXED, text)')
            if version < 2:
                for row in db.execute('SELECT job_id,payload FROM results').fetchall():
                    self.index_observations(db, row['job_id'], json.loads(row['payload']))
                db.execute('PRAGMA user_version=2')

    @staticmethod
    def index_observations(db, job_id, result):
        for observation in result['observations']:
            db.execute('INSERT INTO observation_index(job_id,payload,text) VALUES(?,?,?)',
                       (job_id, canonical(observation), observation['text']))

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, job_id: str, raw: bytes, suffix: str) -> dict:
        sha = hashlib.sha256(raw).hexdigest()
        directory = self.root / 'objects' / job_id
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = sha + suffix
        path = directory / name
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise ContractError('Existing artifact integrity failure')
        else:
            fd, temporary = tempfile.mkstemp(dir=directory)
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(raw)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return {'artifact_name': name, 'artifact_sha256': sha, 'artifact_bytes': len(raw)}

    def path(self, job_id: str, artifact: dict) -> Path:
        parent = self.root / 'objects' / job_id
        path = parent / artifact['artifact_name']
        if path.is_symlink() or not path.resolve().is_relative_to(parent.resolve()):
            raise ContractError('Unsafe artifact path')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact['artifact_sha256']:
            raise ContractError('Missing or corrupted artifact')
        return path

    @staticmethod
    def job(db, job_id):
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ContractError('Unknown job')
        return row, json.loads(row['payload'])

    @staticmethod
    def evidence(db, job_id, eid):
        row = db.execute('SELECT payload FROM evidence WHERE id=? AND job_id=?', (eid, job_id)).fetchone()
        if not row:
            raise ContractError('Evidence does not belong to this job')
        return json.loads(row[0])

    @staticmethod
    def event(db, job_id, kind):
        db.execute('INSERT INTO events(job_id,kind) VALUES(?,?)', (job_id, kind))
