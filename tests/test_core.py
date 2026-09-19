import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    from sourcelens.engine import Engine
    from sourcelens.contracts import ContractError
except ImportError:
    Engine = None
    ContractError = ValueError


def answer(ticket, **changes):
    result = {k: ticket[k] for k in (
        'job_id', 'task_id', 'attempt_id', 'lease_id', 'policy_id', 'source_revision_ids')}
    result.update(schema_version='sourcelens.host-result.v1',
                  inspection_records=[{'evidence_id': e, 'provenance': 'model_self_report'}
                                      for e in ticket['input_evidence_ids']],
                  observations=[{'text': 'The source discusses retries.',
                                 'evidence_ids': [ticket['input_evidence_ids'][0]],
                                 'certainty': 'observed'}], gaps=[])
    result.update(changes)
    return result


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Engine, 'The evidence engine has not been implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.inputs = self.base / 'inputs'
        self.inputs.mkdir()
        self.root = self.base / 'state'
        self.engine = Engine(self.root, self.inputs)

    def put(self, name, text):
        p = self.inputs / name
        p.write_text(text, encoding='utf-8')
        return p

    def start(self, text='Retry limit is 7.\n', **kwargs):
        path = self.put('source.md', text)
        return self.engine.ingest(path, **kwargs)['job_id']

    def test_raw_bytes_and_repeat_mentions_survive(self):
        text = 'See https://example.org/spec twice: https://example.org/spec\n'
        job = self.start(text)
        state = self.engine.status(job)
        self.assertEqual(state['coverage']['reference_mentions'], 2)
        self.assertEqual(state['coverage']['distinct_targets'], 1)
        ticket = self.engine.advance(job)['ticket']
        span = self.engine.read(job, ticket['input_evidence_ids'][0])
        self.assertEqual(Path(span['artifact_path']).read_bytes(), text.encode())
        self.assertEqual(span['artifact_sha256'], hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(span['locator']['start_line'], 1)

    def test_restart_reuses_live_ticket_and_completed_result(self):
        job = self.start()
        ticket = self.engine.advance(job)['ticket']
        other = Engine(self.root, self.inputs)
        self.assertEqual(other.advance(job)['ticket'], ticket)
        result = answer(ticket)
        first = other.submit(result)
        self.assertEqual(Engine(self.root, self.inputs).submit(result), first)
        self.assertEqual(other.status(job)['status'], 'completed')

    def test_conflicting_duplicate_is_rejected(self):
        job = self.start()
        result = answer(self.engine.advance(job)['ticket'])
        self.engine.submit(result)
        result['observations'][0]['text'] = 'Changed claim'
        with self.assertRaises(ContractError):
            self.engine.submit(result)

    def test_foreign_evidence_is_rejected_atomically(self):
        first = self.start()
        second = self.engine.ingest(self.put('other.md', 'Unrelated secret'))['job_id']
        ticket = self.engine.advance(first)['ticket']
        foreign = self.engine.advance(second)['ticket']['input_evidence_ids'][0]
        result = answer(ticket)
        result['observations'][0]['evidence_ids'] = [foreign]
        with self.assertRaises(ContractError):
            self.engine.submit(result)
        self.assertEqual(self.engine.status(first)['coverage']['observations'], 0)
        self.assertEqual(self.engine.status(first)['status'], 'awaiting_host')

    def test_policy_revision_and_lease_must_match(self):
        job = self.start()
        ticket = self.engine.advance(job)['ticket']
        for field, bad in [('policy_id', 'other'), ('lease_id', 'stale'),
                           ('source_revision_ids', ['wrong']), ('attempt_id', 'wrong')]:
            with self.subTest(field=field), self.assertRaises(ContractError):
                self.engine.submit(answer(ticket, **{field: bad}))

    def test_expired_ticket_reissues_and_old_result_fails(self):
        job = self.start()
        old = self.engine.advance(job)['ticket']
        import sqlite3
        with sqlite3.connect(self.root / 'state.sqlite3') as db:
            db.execute('UPDATE tasks SET expires_at = 0 WHERE id = ?', (old['task_id'],))
        new = self.engine.advance(job)['ticket']
        self.assertNotEqual(new['lease_id'], old['lease_id'])
        with self.assertRaises(ContractError):
            self.engine.submit(answer(old))
        self.engine.submit(answer(new))

    def test_empty_result_cannot_claim_completion(self):
        job = self.start()
        ticket = self.engine.advance(job)['ticket']
        with self.assertRaises(ContractError):
            self.engine.submit(answer(ticket, inspection_records=[], observations=[]))

    def test_unknown_schema_and_extra_operations_rejected(self):
        job = self.start()
        ticket = self.engine.advance(job)['ticket']
        for changes in ({'schema_version': 'sourcelens.host-result.v2'},
                        {'shell': 'rm -rf /'}, {'requested_reads': [{'operation': 'shell'}]}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                self.engine.submit(answer(ticket, **changes))

    def test_exact_quote_must_exist(self):
        job = self.start()
        ticket = self.engine.advance(job)['ticket']
        result = answer(ticket)
        result['observations'][0]['quote'] = 'Retry limit is 99.'
        with self.assertRaises(ContractError):
            self.engine.submit(result)
        result['observations'][0]['quote'] = 'Retry limit is 7.'
        self.engine.submit(result)

    def test_uninspected_citation_and_forged_tool_record_rejected(self):
        job = self.start()
        ticket = self.engine.advance(job)['ticket']
        with self.assertRaises(ContractError):
            self.engine.submit(answer(ticket, inspection_records=[]))
        result = answer(ticket)
        result['inspection_records'][0]['provenance'] = 'host_tool_record'
        with self.assertRaises(ContractError):
            self.engine.submit(result)

    def test_gaps_remain_partial(self):
        job = self.start()
        ticket = self.engine.advance(job)['ticket']
        gap = {'evidence_id': ticket['input_evidence_ids'][0], 'reason': 'Unreadable source'}
        self.engine.submit(answer(ticket, inspection_records=[], observations=[], gaps=[gap]))
        self.assertEqual(self.engine.status(job)['status'], 'partial')

    def test_unfetched_reference_remains_partial(self):
        job = self.start('See https://example.org/spec\n')
        self.engine.submit(answer(self.engine.advance(job)['ticket']))
        state = self.engine.status(job)
        self.assertEqual(state['status'], 'partial')
        self.assertEqual(state['coverage']['references_fetched'], 0)

    def test_subtitle_overlap_preserved_and_end_rejected(self):
        path = self.put('captions.vtt', 'WEBVTT\n\n00:00.000 --> 00:02.000\nFirst\n\n00:01.000 --> 00:03.000\nSecond\n')
        job = self.engine.ingest(path)['job_id']
        ticket = self.engine.advance(job)['ticket']
        spans = [self.engine.read(job, e) for e in ticket['input_evidence_ids']]
        self.assertEqual([(s['locator']['start_ms'], s['locator']['end_ms']) for s in spans], [(0, 2000), (1000, 3000)])
        bad = self.put('bad.srt', '1\n00:00:05,000 --> 00:00:01,000\nWrong\n')
        with self.assertRaises(ContractError):
            self.engine.ingest(bad)

    def test_summarize_import_preserves_unknown_end_and_raw(self):
        payload = {'extracted': {'content': 'Retry limit is 7.', 'url': 'https://example.org/video',
                                'transcriptSegments': [{'startMs': 1500, 'text': 'Retry limit is 7.'}]}}
        path = self.put('extracted.json', json.dumps(payload))
        job = self.engine.ingest(path, input_format='summarize')['job_id']
        span = self.engine.read(job, self.engine.advance(job)['ticket']['input_evidence_ids'][0])
        self.assertIsNone(span['locator']['end_ms'])
        self.assertEqual(span['method'], 'summarize-json-import')
        self.assertEqual(json.loads(Path(span['artifact_path']).read_text()), payload)
        self.assertTrue(self.engine.status(job)['gaps'])

    def test_changed_file_creates_new_job_without_mutating_old(self):
        first = self.start('old content')
        second = self.start('new content')
        self.assertNotEqual(first, second)
        ticket = self.engine.advance(first)['ticket']
        self.assertEqual(self.engine.read(first, ticket['input_evidence_ids'][0])['text'], 'old content')
        self.assertEqual(self.start('new content'), second)

    def test_outside_root_and_symlink_are_rejected(self):
        secret = self.base / 'secret.txt'
        secret.write_text('secret')
        link = self.inputs / 'link.txt'
        link.symlink_to(secret)
        for p in (secret, link):
            with self.subTest(path=p), self.assertRaises(ContractError):
                self.engine.ingest(p)

    def test_corrupt_artifact_fails_read(self):
        job = self.start()
        eid = self.engine.advance(job)['ticket']['input_evidence_ids'][0]
        span = self.engine.read(job, eid)
        Path(span['artifact_path']).write_bytes(b'tampered')
        with self.assertRaises(ContractError):
            self.engine.read(job, eid)

    def test_search_is_scoped_and_literal(self):
        first = self.start('unique_identifier retry retry')
        second = self.engine.ingest(self.put('other.md', 'unrelated unique_identifier'))['job_id']
        hits = self.engine.search(first, 'unique_identifier')
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['job_id'], first)
        self.assertEqual(self.engine.search(second, 'retry'), [])
        self.assertEqual(self.engine.search(first, '" OR *'), [])

    def test_cancel_blocks_submission(self):
        job = self.start()
        ticket = self.engine.advance(job)['ticket']
        self.engine.cancel(job)
        with self.assertRaises(ContractError):
            self.engine.submit(answer(ticket))
        self.assertEqual(self.engine.status(job)['status'], 'cancelled')

    def test_html_links_preserved_before_text_pruning(self):
        p = self.put('page.html', '<html><nav><a href="https://example.org/a">Menu</a></nav><p>Retry</p><script>ignore me</script></html>')
        job = self.engine.ingest(p)['job_id']
        self.assertEqual(self.engine.status(job)['coverage']['reference_mentions'], 1)
        ticket = self.engine.advance(job)['ticket']
        text = '\n'.join(self.engine.read(job, x)['text'] for x in ticket['input_evidence_ids'])
        self.assertNotIn('ignore me', text)

    def test_large_text_is_bounded_in_tickets_without_loss(self):
        text = '\n'.join(f'Line {i}: retry ' + 'x' * 90 for i in range(300))
        job = self.start(text)
        seen = set()
        while 'ticket' in (step := self.engine.advance(job)):
            ticket = step['ticket']
            self.assertLessEqual(len(ticket['input_evidence_ids']), 8)
            spans = [self.engine.read(job, x) for x in ticket['input_evidence_ids']]
            self.assertLessEqual(sum(len(s['text']) for s in spans), 12000)
            seen.update(ticket['input_evidence_ids'])
            self.engine.submit(answer(ticket))
        self.assertGreater(len(seen), 8)
        self.assertEqual(self.engine.status(job)['coverage']['spans_reported_inspected'], len(seen))


if __name__ == '__main__':
    unittest.main()
