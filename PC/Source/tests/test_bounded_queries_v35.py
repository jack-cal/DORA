"""Legacy-equivalent P2P hints without replaying complete block bodies."""
from contextlib import ExitStack
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from sumuww.block import Block
from sumuww.chain import Chain
from sumuww.errors import StorageError, ValidationError
from sumuww.wallet import RegtestKey

ALICE, BOB = RegtestKey.from_int(1), RegtestKey.from_int(2)
EVIDENCE = {'owned_regtest_heights': [2048, 4096]}


def legacy_locator(chain, tip_hash=None):
    with chain.read_snapshot():
        path = chain._path(chain.tip_hash if tip_hash is None else tip_hash)
        result, position, step = [], len(path) - 1, 1
        while position > 0 and len(result) < 31:
            result.append(path[position][0][0])
            if len(result) > 10:
                step *= 2
            position = max(position - step, 0)
        result.append(path[0][0][0])
        return tuple(result)


def legacy_headers(chain, locator, stop=bytes(32), limit=128):
    with chain.read_snapshot():
        path = chain._path(chain.tip_hash)
        heights = {row[0]: height for height, (row, _) in enumerate(path)}
        common = next((heights[digest] for digest in locator if digest in heights), 0)
        result = []
        for row, block in path[common + 1:]:
            result.append(block.header)
            if row[0] == stop or len(result) == limit:
                break
        return tuple(result)


def forbid_full_work(chain):
    stack = ExitStack()
    for name in ('_path', '_read_index_path', '_replay', '_load_utxos', 'state_commitment'):
        stack.enter_context(patch.object(chain, name, side_effect=AssertionError('Hint query performed full work: ' + name)))
    stack.enter_context(patch.object(Block, 'deserialize', side_effect=AssertionError('Hint query deserialized a block body')))
    return stack


class BoundedQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_directory = tempfile.TemporaryDirectory(prefix='sumuww-v35-bounded-seed-')
        cls.directory = Path(cls.seed_directory.name)
        cls.seeds = {}
        with Chain(cls.directory / 'builder.sqlite') as chain:
            for height in (2048, 4096):
                chain.mine(ALICE.script_pubkey, 2048)
                chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                seed = cls.directory / f'seed-{height}.sqlite'
                shutil.copyfile(chain.database, seed)
                cls.seeds[height] = seed

    @classmethod
    def tearDownClass(cls):
        cls.seed_directory.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-v35-bounded-case-')
        self.directory = Path(self.temporary.name)
        self.database = self.directory / 'owned.sqlite'
        shutil.copyfile(self.seeds[4096], self.database)
        self.chain = Chain(self.database)

    def tearDown(self):
        self.chain.close()
        self.temporary.cleanup()

    def test_locators_match_legacy_for_genesis_active_and_side_branches(self):
        path = self.chain._path(self.chain.tip_hash)
        tips = [path[height][0][0] for height in (0, 1, 11, 12, 100, 2048, 4096)]
        first = self.chain.make_block(BOB.script_pubkey, parent_hash=path[2047][0][0], extra_nonce=42)
        self.assertFalse(self.chain.accept_block(first))
        second = self.chain.make_block(BOB.script_pubkey, parent_hash=first.block_hash(), extra_nonce=43)
        self.assertFalse(self.chain.accept_block(second))
        tips.extend((first.block_hash(), second.block_hash()))
        cases = 0
        for tip in tips:
            expected = legacy_locator(self.chain, tip)
            with forbid_full_work(self.chain):
                actual = self.chain.block_locator(tip)
            self.assertEqual(expected, actual)
            self.assertLessEqual(len(actual), 32)
            cases += 1
        expected = legacy_locator(self.chain)
        with forbid_full_work(self.chain):
            self.assertEqual(expected, self.chain.block_locator())
        EVIDENCE['legacy_locator_equivalence_cases'] = cases + 1

    def test_headers_match_legacy_for_input_order_stop_limits_and_side_branches(self):
        path = self.chain._path(self.chain.tip_hash)
        digest = lambda height: path[height][0][0]
        branch = self.chain.make_block(BOB.script_pubkey, parent_hash=digest(2047), extra_nonce=44)
        self.assertFalse(self.chain.accept_block(branch))
        locators = [(digest(0),), (digest(4096),), (b'\x91' * 32,),
                    (digest(2048), digest(100)), (digest(100), digest(2048)),
                    (b'\x91' * 32, digest(4090), digest(100)),
                    (branch.block_hash(), digest(2047)), self.chain.block_locator(branch.block_hash())]
        cases = 0
        for locator in locators:
            for limit in (1, 17, 128):
                for stop in (bytes(32), digest(3), digest(2050), b'\x92' * 32):
                    expected = legacy_headers(self.chain, locator, stop, limit)
                    with forbid_full_work(self.chain):
                        actual = self.chain.headers_after(locator, stop, limit)
                    self.assertEqual(expected, actual)
                    cases += 1
        EVIDENCE['legacy_header_equivalence_cases'] = cases

    def test_external_commits_at_both_long_heights_need_zero_full_paths_or_replays(self):
        measurements = []
        for height in (2048, 4096):
            database = self.directory / f'external-{height}.sqlite'
            shutil.copyfile(self.seeds[height], database)
            with Chain(database) as reader, Chain(database) as writer:
                previous = reader.tip_hash
                for _ in range(3):
                    writer.mine(BOB.script_pubkey)
                    with forbid_full_work(reader), patch.object(reader, '_summary_row', wraps=reader._summary_row) as rows:
                        began = time.perf_counter()
                        locator = reader.block_locator()
                        locator_seconds = time.perf_counter() - began
                        locator_rows = rows.call_count
                        rows.reset_mock()
                        began = time.perf_counter()
                        headers = reader.headers_after((previous,))
                        header_seconds = time.perf_counter() - began
                        header_rows = rows.call_count
                    with patch.object(reader, '_read_index_path', wraps=reader._read_index_path) as paths:
                        began = time.perf_counter()
                        expected_locator = legacy_locator(reader)
                        legacy_seconds = time.perf_counter() - began
                        legacy_path_reads = paths.call_count
                    expected_headers = legacy_headers(reader, (previous,))
                    self.assertEqual(expected_locator, locator)
                    self.assertEqual(expected_headers, headers)
                    self.assertEqual(1, len(headers))
                    self.assertEqual(1, legacy_path_reads)
                    self.assertEqual(len(locator), locator_rows)
                    self.assertLessEqual(header_rows, len(headers) + 2)
                    measurements.append({'initial_height': height, 'locator_seconds': locator_seconds,
                                         'header_seconds': header_seconds, 'legacy_cold_locator_seconds': legacy_seconds,
                                         'bounded_locator_header_rows': locator_rows,
                                         'bounded_response_header_rows': header_rows, 'header_bytes_per_row': 80,
                                         'legacy_full_path_reads': legacy_path_reads,
                                         'bounded_full_path_reads': 0, 'bounded_replays': 0, 'bounded_block_body_deserializations': 0})
                    previous = reader.tip_hash
        EVIDENCE['external_commit_queries'] = measurements

    def test_queries_keep_one_snapshot_during_other_connection_commit(self):
        with Chain(self.database) as writer:
            before_locator = legacy_locator(self.chain)
            genesis = self.chain.network.genesis.block_hash()
            before_headers = legacy_headers(self.chain, (genesis,), limit=17)
            original = self.chain._summary_row
            fired = False

            def interleave(digest):
                nonlocal fired
                row = original(digest)
                if not fired:
                    fired = True
                    writer.mine(BOB.script_pubkey)
                return row

            with patch.object(self.chain, '_summary_row', interleave):
                self.assertEqual(before_locator, self.chain.block_locator())
            self.assertTrue(fired)
            self.assertNotEqual(before_locator[0], self.chain.block_locator()[0])
            with self.chain.read_snapshot():
                locator = self.chain.block_locator()
                writer.mine(BOB.script_pubkey)
                self.assertEqual(locator, self.chain.block_locator())
                self.assertEqual(before_headers, self.chain.headers_after((genesis,), limit=17))
                self.assertEqual((), self.chain.headers_after(locator))
                self.assertTrue(self.chain.connection.in_transaction)
            self.assertFalse(self.chain.connection.in_transaction)
        EVIDENCE['snapshot_consistency'] = {'commit_interleaved_after_tip_header_read': True,
                                           'nested_snapshot_retained_until_owner_releases': True}

    def test_selected_header_corruption_and_broken_ancestry_are_rejected(self):
        row = self.chain._row(self.chain.tip_hash)
        malformed = bytes([row[4][0] ^ 1]) + row[4][1:]
        self.chain.connection.execute('UPDATE blocks SET raw=? WHERE hash=?', (malformed, row[0]))
        for query in (self.chain.block_locator, lambda: self.chain.headers_after((self.chain.network.genesis.block_hash(),))):
            with self.assertRaises(StorageError):
                query()
            self.assertFalse(self.chain.connection.in_transaction)
        self.chain.connection.execute('UPDATE blocks SET raw=? WHERE hash=?', (row[4], row[0]))
        parent = self.chain._row(row[1])
        self.chain.connection.execute('UPDATE blocks SET parent=? WHERE hash=?', (parent[0], parent[0]))
        for query in (self.chain.block_locator, lambda: self.chain.headers_after((self.chain.network.genesis.block_hash(),))):
            with self.assertRaises(StorageError):
                query()
            self.assertFalse(self.chain.connection.in_transaction)
        EVIDENCE['selected_header_integrity'] = {'mismatching_tip_header_rejected': True,
                                                 'broken_parent_cycle_rejected_without_unbounded_sql': True}

    def test_argument_errors_and_existing_write_transaction_ownership_are_preserved(self):
        genesis = self.chain.network.genesis.block_hash()
        for invalid in (b'', '00' * 32, bytearray(32), True):
            with self.assertRaises(ValidationError):
                self.chain.block_locator(invalid)
        with self.assertRaises(ValidationError):
            self.chain.block_locator(b'\x91' * 32)
        for invalid in ((), [], (genesis,) * 33, genesis, (b'',)):
            with self.assertRaises(ValidationError):
                self.chain.headers_after(invalid)
        for invalid in (0, 129, True, '1', None):
            with self.assertRaises(ValidationError):
                self.chain.headers_after((genesis,), limit=invalid)
        self.assertFalse(self.chain.connection.in_transaction)
        self.chain.connection.execute('BEGIN IMMEDIATE')
        self.chain.connection.execute("INSERT INTO metadata VALUES ('owned-query-test','uncommitted')")
        self.chain.block_locator()
        self.chain.headers_after((genesis,), limit=1)
        self.assertTrue(self.chain.connection.in_transaction)
        self.chain.connection.execute('ROLLBACK')
        self.assertIsNone(self.chain.connection.execute("SELECT value FROM metadata WHERE name='owned-query-test'").fetchone())


if __name__ == '__main__':
    unittest.main()
