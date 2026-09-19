import json
import sqlite3
from pathlib import Path
import tempfile
import unittest

from sourcelens.engine import Engine
from sourcelens.contracts import ContractError
from test_core import answer


class ExperimentRepairs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.inputs = self.base / 'inputs'
        self.inputs.mkdir()
        self.engine = Engine(self.base / 'state', self.inputs)

    def ingest(self, name, text):
        p = self.inputs / name
        p.write_text(text)
        return self.engine.ingest(p)['job_id']

    def test_explicit_root_accepts_system_alias_ancestor_but_not_child_symlinks(self):
        alias = self.base / 'system-alias'
        alias.symlink_to(self.inputs, target_is_directory=True)
        (self.inputs / 'a.md').write_text('safe')
        engine = Engine(self.base / 'alias-state', alias)
        try:
            job = engine.ingest(alias / 'a.md')['job_id']
        except ContractError as exc:
            self.fail(f'Explicit root alias rejected: {exc}')
        self.assertEqual(engine.status(job)['coverage']['spans_acquired'], 1)
        (self.inputs / 'child.md').symlink_to(self.inputs / 'a.md')
        with self.assertRaises(ContractError):
            engine.ingest(alias / 'child.md')

    def test_html_link_binds_anchor_and_empty_link_never_binds_unrelated_text(self):
        job = self.ingest('page.html', '<p>Intro</p><p><a href="https://example.org/a">Target text</a></p><img src="https://example.org/img"><p>Unrelated</p>')
        snapshot = self.engine.snapshot(job)
        refs = snapshot['payload']['references']
        self.assertEqual(self.engine.read(job, refs[0]['evidence_id'])['text'].strip(), 'Target text')
        self.assertIsNone(refs[1]['evidence_id'])

    def test_observation_search_returns_original_evidence_and_survives_restart(self):
        job = self.ingest('source.md', 'Source says alpha')
        result = answer(self.engine.advance(job)['ticket'])
        result['observations'][0]['text'] = 'Warm Bot Backends is five'
        self.engine.submit(result)
        engine = Engine(self.base / 'state', self.inputs)
        hits = engine.search(job, 'Warm Bot Backends')
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['text'], 'Source says alpha')
        self.assertEqual(hits[0]['matched_observations'][0]['text'], 'Warm Bot Backends is five')
        other = self.ingest('other.md', 'unrelated')
        self.assertEqual(engine.search(other, 'Warm Bot Backends'), [])
        self.assertEqual(engine.submit(result)['status'], 'accepted')
        self.assertEqual(len(engine.search(job, 'Warm Bot Backends')), 1)

    def test_html_multiline_blocks_do_not_shift_link_evidence(self):
        job = self.ingest('multiline.html', '<p>Introduction\nMore introductory text</p><a href="https://example.org">Actual anchor</a>')
        ref = self.engine.snapshot(job)['payload']['references'][0]
        self.assertEqual(self.engine.read(job, ref['evidence_id'])['text'].strip(), 'Actual anchor')

    def test_synthesis_authorizes_selected_previously_inspected_evidence_only(self):
        self.assertTrue(callable(getattr(self.engine, 'synthesize', None)), 'Missing synthesis authorization')
        job = self.ingest('nine.md', '\n'.join(f'Line {i}' for i in range(9)))
        first = self.engine.advance(job)['ticket']
        self.engine.submit(answer(first))
        second = self.engine.advance(job)['ticket']
        direct = answer(second)
        direct['observations'][0]['evidence_ids'].append(first['input_evidence_ids'][0])
        with self.assertRaises(ContractError):
            self.engine.submit(direct)
        self.engine.submit(answer(second))
        ids = [first['input_evidence_ids'][0], second['input_evidence_ids'][0]]
        ticket = self.engine.synthesize(job, ids)['ticket']
        self.assertEqual(ticket['input_evidence_ids'], ids)
        result = answer(ticket)
        result['observations'][0]['evidence_ids'] = ids
        self.engine.submit(result)
        self.assertEqual(self.engine.status(job)['coverage']['observations'], 3)
        other = self.ingest('other.md', 'foreign')
        foreign = self.engine.advance(other)['ticket']['input_evidence_ids'][0]
        with self.assertRaises(ContractError):
            self.engine.synthesize(job, [foreign])
        with self.assertRaises(ContractError):
            self.engine.synthesize(other, [foreign])

    def test_legacy_results_are_searchable_after_additive_index_upgrade(self):
        job = self.ingest('source.md', 'Original')
        result = answer(self.engine.advance(job)['ticket'])
        result['observations'][0]['text'] = 'Historically inspected setting'
        self.engine.submit(result)
        with self.engine.store.db() as db:
            db.execute('DROP TABLE IF EXISTS observation_index')
            db.execute('PRAGMA user_version=1')
        upgraded = Engine(self.base / 'state', self.inputs)
        self.assertEqual(len(upgraded.search(job, 'Historically')), 1)
        self.assertEqual(upgraded.submit(result)['status'], 'accepted')


if __name__ == '__main__':
    unittest.main()
