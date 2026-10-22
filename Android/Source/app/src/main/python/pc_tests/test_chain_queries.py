"""Bounded P2P queries and coherent reads across independent SQLite writers."""

from pathlib import Path
from unittest.mock import patch
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from sumuww.block import GENESIS_TIME, genesis_block
from sumuww.chain import Chain
from sumuww.errors import StorageError, ValidationError
from sumuww.primitives import COIN, hash_to_display
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))
NOW = GENESIS_TIME + 1000
ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)
MINER = RegtestKey.from_int(3)


class ChainQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(exist_ok=True)
        cls.seed_dir = tempfile.TemporaryDirectory(prefix='query-seed-', dir=WORK)
        cls.seed = Path(cls.seed_dir.name) / 'seed.sqlite'
        with Chain(cls.seed, clock=lambda: NOW) as chain:
            cls.blocks = chain.mine(ALICE.script_pubkey, 100)
            cls.genesis_hash = genesis_block().block_hash()
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @classmethod
    def tearDownClass(cls):
        cls.seed_dir.cleanup()

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='query-case-', dir=WORK)
        self.addCleanup(self.scratch.cleanup)
        self.database = Path(self.scratch.name) / 'chain.sqlite'
        shutil.copy2(self.seed, self.database)
        self.chain = Chain(self.database, clock=lambda: NOW)
        self.addCleanup(self.chain.close)

    def writer(self):
        writer = Chain(self.database, clock=lambda: NOW)
        self.addCleanup(writer.close)
        return writer

    def spend(self):
        previous = self.blocks[0].transactions[0]
        tx = Transaction(2, (TxInput(previous.txid(), 0),), (
            TxOutput(3 * COIN, BOB.script_pubkey),
            TxOutput(47 * COIN - 100_000, ALICE.script_pubkey)))
        return sign_p2wpkh(tx, 0, previous.outputs[0], ALICE)

    def test_block_queries_cover_genesis_active_and_side_branch(self):
        main = self.blocks[-1]
        branch = self.chain.make_block(MINER.script_pubkey,
                                       parent_hash=self.blocks[49].block_hash(), extra_nonce=42)
        self.assertFalse(self.chain.accept_block(branch))
        for block in (genesis_block(), main, branch):
            with self.subTest(block=block.block_hash().hex()):
                self.assertTrue(self.chain.has_block(block.block_hash()))
                self.assertEqual(block, self.chain.get_block(block.block_hash()))
        self.assertFalse(self.chain.has_block(b'\x91' * 32))
        with self.assertRaises(ValidationError):
            self.chain.get_block(b'\x91' * 32)
        self.assertFalse(self.chain.connection.in_transaction)

    def test_mempool_queries_return_only_current_entries(self):
        tx = self.spend()
        self.assertFalse(self.chain.has_mempool_transaction(tx.txid()))
        self.assertIsNone(self.chain.get_mempool_transaction(tx.txid()))
        self.chain.submit_transaction(tx)
        self.assertTrue(self.chain.has_mempool_transaction(tx.txid()))
        self.assertEqual(tx, self.chain.get_mempool_transaction(tx.txid()))
        self.chain.mine(MINER.script_pubkey)
        self.assertFalse(self.chain.has_mempool_transaction(tx.txid()))
        self.assertIsNone(self.chain.get_mempool_transaction(tx.txid()))

    def test_mempool_query_detects_index_bytes_mismatch(self):
        tx = self.spend()
        self.chain.submit_transaction(tx)
        altered = Transaction(tx.version, tx.inputs, (
            TxOutput(tx.outputs[0].value - 1, tx.outputs[0].script_pubkey),) + tx.outputs[1:],
            tx.lock_time)
        self.chain.connection.execute('UPDATE mempool SET raw=? WHERE txid=?',
                                      (altered.serialize(), tx.txid()))
        with self.assertRaises(StorageError):
            self.chain.get_mempool_transaction(tx.txid())
        self.assertFalse(self.chain.connection.in_transaction)

    def test_locator_is_recent_then_exponential_with_genesis(self):
        locator = self.chain.block_locator()
        self.assertEqual(tuple(block.block_hash() for block in reversed(self.blocks[89:100])), locator[:11])
        heights = {block.block_hash(): i + 1 for i, block in enumerate(self.blocks)}
        heights[self.genesis_hash] = 0
        self.assertEqual([100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 88, 84, 76, 60, 28, 0],
                         [heights[digest] for digest in locator])
        self.assertLessEqual(len(locator), 32)
        self.assertEqual(self.genesis_hash, locator[-1])
        self.assertEqual((self.genesis_hash,), self.chain.block_locator(self.genesis_hash))

    def test_side_branch_locator_finds_active_common_ancestor(self):
        common = self.blocks[49].block_hash()
        branch_a = self.chain.make_block(MINER.script_pubkey, parent_hash=common, extra_nonce=42)
        self.chain.accept_block(branch_a)
        branch_b = self.chain.make_block(MINER.script_pubkey, parent_hash=branch_a.block_hash(), extra_nonce=43)
        self.chain.accept_block(branch_b)
        locator = self.chain.block_locator(branch_b.block_hash())
        self.assertEqual((branch_b.block_hash(), branch_a.block_hash(), common), locator[:3])
        headers = self.chain.headers_after(locator, stop=self.blocks[52].block_hash())
        self.assertEqual(tuple(block.header for block in self.blocks[50:53]), headers)

    def test_headers_use_first_matching_locator_entry(self):
        locator = (b'\x91' * 32, self.blocks[79].block_hash(), self.blocks[49].block_hash())
        self.assertEqual(tuple(block.header for block in self.blocks[80:85]),
                         self.chain.headers_after(locator, limit=5))

    def test_unknown_locator_falls_back_to_after_genesis(self):
        self.assertEqual(tuple(block.header for block in self.blocks[:3]),
                         self.chain.headers_after((b'\x91' * 32,), limit=3))
        self.assertEqual((), self.chain.headers_after(self.chain.block_locator()))

    def test_headers_stop_is_included_and_unknown_stop_does_not_truncate(self):
        self.assertEqual(tuple(block.header for block in self.blocks[:3]),
                         self.chain.headers_after((self.genesis_hash,), stop=self.blocks[2].block_hash()))
        self.assertEqual(tuple(block.header for block in self.blocks[:5]),
                         self.chain.headers_after((self.genesis_hash,), stop=b'\x91' * 32, limit=5))

    def test_header_pagination_is_ordered_without_duplicates(self):
        result = []
        locator = (self.genesis_hash,)
        while True:
            page = self.chain.headers_after(locator, limit=17)
            if not page:
                break
            result.extend(page)
            locator = (page[-1].digest(),)
        self.assertEqual(tuple(block.header for block in self.blocks), tuple(result))

    def test_default_headers_limit_is_128(self):
        extra = self.chain.mine(ALICE.script_pubkey, 40)
        expected = self.blocks + extra
        self.assertEqual(tuple(block.header for block in expected[:128]),
                         self.chain.headers_after((self.genesis_hash,)))

    def test_query_argument_validation_does_not_leave_transactions(self):
        for invalid in (None, '00' * 32, b'', b'\x00' * 31, b'\x00' * 33, bytearray(32), True):
            for query in (self.chain.has_block, self.chain.get_block,
                          self.chain.has_mempool_transaction, self.chain.get_mempool_transaction):
                with self.subTest(query=query.__name__, invalid=repr(invalid)):
                    with self.assertRaises(ValidationError):
                        query(invalid)
            if invalid is not None:
                with self.assertRaises(ValidationError):
                    self.chain.block_locator(invalid)
        for invalid in ((), [], (self.genesis_hash,) * 33, self.genesis_hash, {'x': self.genesis_hash}, (b'',)):
            with self.assertRaises(ValidationError):
                self.chain.headers_after(invalid)
        for invalid in (0, -1, 129, True, 1.0, '1', None):
            with self.assertRaises(ValidationError):
                self.chain.headers_after((self.genesis_hash,), limit=invalid)
        with self.assertRaises(ValidationError):
            self.chain.headers_after((self.genesis_hash,), stop=b'')
        with self.assertRaises(ValidationError):
            self.chain.block_locator(b'\x91' * 32)
        self.assertFalse(self.chain.connection.in_transaction)

    def _write_between_tip_and_utxo_reads(self, writer_action):
        original = self.chain._row
        fired = False

        def interleave(digest):
            nonlocal fired
            row = original(digest)
            if not fired:
                fired = True
                writer_action()
            return row

        return patch.object(self.chain, '_row', side_effect=interleave)

    def test_info_snapshot_has_consistent_tip_utxo_and_mempool(self):
        writer = self.writer()
        self.chain.submit_transaction(self.spend())
        before = self.chain.info()
        with self._write_between_tip_and_utxo_reads(lambda: writer.mine(MINER.script_pubkey)):
            self.assertEqual(before, self.chain.info())
        after = self.chain.info()
        self.assertEqual(101, after['height'])
        self.assertEqual(0, after['mempool'])
        self.assertNotEqual(before['utxo_commitment'], after['utxo_commitment'])
        self.assertFalse(self.chain.connection.in_transaction)

    def test_balance_maturity_uses_same_tip_and_utxo_snapshot(self):
        writer = self.writer()
        with self._write_between_tip_and_utxo_reads(lambda: writer.mine(ALICE.script_pubkey)):
            self.assertEqual(50 * COIN, self.chain.balance(ALICE.script_pubkey, mature_only=True))
        self.assertEqual(100 * COIN, self.chain.balance(ALICE.script_pubkey, mature_only=True))

    def test_nested_reads_keep_snapshot_until_owner_releases(self):
        writer = self.writer()
        tx = self.spend()
        self.chain.submit_transaction(tx)
        before = self.chain.info()
        with self.chain.read_snapshot():
            self.assertEqual(before, self.chain.info())  # Establish this revision.
            writer.mine(MINER.script_pubkey)
            self.assertEqual(before['utxo_commitment'], self.chain.state_commitment())
            self.assertEqual(before['utxos'], len(self.chain.list_utxos()))
            self.assertEqual((tx,), self.chain.mempool_transactions())
            self.assertTrue(self.chain.has_mempool_transaction(tx.txid()))
            self.assertEqual(tx, self.chain.get_mempool_transaction(tx.txid()))
            self.assertEqual(before['tip'], hash_to_display(self.chain.block_locator()[0]))
            self.assertEqual((), self.chain.headers_after(self.chain.block_locator()))
            self.assertTrue(self.chain.connection.in_transaction)
        self.assertFalse(self.chain.connection.in_transaction)
        self.assertEqual(101, self.chain.info()['height'])

    def test_existing_write_transaction_remains_owned_by_caller(self):
        self.chain.connection.execute('BEGIN IMMEDIATE')
        self.chain.connection.execute("INSERT INTO metadata VALUES ('query-test', 'uncommitted')")
        self.chain.info()
        self.chain.balance(ALICE.script_pubkey)
        self.chain.headers_after((self.genesis_hash,), limit=1)
        self.assertTrue(self.chain.connection.in_transaction)
        with self.assertRaises(ValidationError):
            self.chain.get_block(b'\x91' * 32)
        self.assertTrue(self.chain.connection.in_transaction)
        self.chain.connection.execute('ROLLBACK')
        self.assertIsNone(self.chain.connection.execute("SELECT value FROM metadata WHERE name='query-test'").fetchone())

    def test_snapshot_rolls_back_on_base_exception(self):
        with self.assertRaises(KeyboardInterrupt):
            with self.chain.read_snapshot():
                self.chain.info()
                raise KeyboardInterrupt()
        self.assertFalse(self.chain.connection.in_transaction)
        self.assertEqual(100, self.chain.info()['height'])

    def test_other_process_can_commit_while_query_snapshot_is_held(self):
        before = self.chain.info()
        script = (
            'from sumuww.chain import Chain\n'
            'from sumuww.wallet import RegtestKey\n'
            'import sys\n'
            f'with Chain(sys.argv[1], clock=lambda: {NOW}) as chain:\n'
            '    chain.mine(RegtestKey.from_int(3).script_pubkey)\n'
        )

        def mine_in_process():
            result = subprocess.run([sys.executable, '-B', '-c', script, str(self.database)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

        with self._write_between_tip_and_utxo_reads(mine_in_process):
            self.assertEqual(before, self.chain.info())
        self.assertEqual(101, self.chain.info()['height'])

    def test_block_template_uses_one_snapshot_during_concurrent_append(self):
        writer = self.writer()
        before_tip = self.chain.tip_hash
        with self._write_between_tip_and_utxo_reads(lambda: writer.mine(ALICE.script_pubkey)):
            template = self.chain.make_block(MINER.script_pubkey)
        self.assertEqual(before_tip, template.header.previous_hash)
        self.assertFalse(self.chain.connection.in_transaction)
        # A concurrent commit makes this a valid side branch of equal work.
        self.assertFalse(self.chain.accept_block(template))
        self.assertTrue(self.chain.has_block(template.block_hash()))


if __name__ == '__main__':
    unittest.main()
