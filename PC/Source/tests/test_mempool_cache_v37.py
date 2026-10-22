"""Real-signature admission cache invalidation and SQLite commit races.

All keys are public test fixtures and all databases are owned temporary files.
"""
from dataclasses import replace
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from sumuww.block import GENESIS_TIME
from sumuww.chain import Chain
from sumuww.errors import InvalidTransaction, ValidationError
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


NOW = GENESIS_TIME + 4000
ALICE = RegtestKey.from_int(3731)
BOB = RegtestKey.from_int(3732)


class ConnectionProxy:
    """Inject a failure or another commit at the actual commit boundary."""
    def __init__(self, connection, *, after_commit=None, fail_commit=False):
        self.connection = connection
        self.after_commit = after_commit
        self.fail_commit = fail_commit

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, sql, *args):
        if sql == 'COMMIT' and self.fail_commit:
            self.fail_commit = False
            raise sqlite3.OperationalError('owned commit fault')
        result = self.connection.execute(sql, *args)
        if sql == 'COMMIT' and self.after_commit is not None:
            action, self.after_commit = self.after_commit, None
            action()
        return result


class MempoolCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_directory = tempfile.TemporaryDirectory(
            prefix='sumuww-owned-pool-seed-', dir=os.environ.get('SUMUWW_TEST_WORKDIR'))
        cls.seed = Path(cls.seed_directory.name) / 'seed.sqlite'
        with Chain(cls.seed, clock=lambda: NOW) as chain:
            blocks = chain.mine(ALICE.script_pubkey, 100)
            cls.branch_parent = chain.tip_hash
            first = blocks[0].transactions[0]
            unit = (first.outputs[0].value - 100_000) // 16
            funding = Transaction(2, (TxInput(first.txid(), 0),),
                                  tuple(TxOutput(unit, ALICE.script_pubkey) for _ in range(16)))
            cls.funding = sign_p2wpkh(funding, 0, first.outputs[0], ALICE)
            chain.submit_transaction(cls.funding)
            chain.mine(ALICE.script_pubkey)
            cls.funded_tip = chain.tip_hash
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @classmethod
    def tearDownClass(cls):
        cls.seed_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(
            prefix='sumuww-owned-pool-case-', dir=os.environ.get('SUMUWW_TEST_WORKDIR'))
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'chain.sqlite'
        shutil.copy2(self.seed, self.database)
        self.chain = Chain(self.database, clock=lambda: NOW)
        self.addCleanup(self.chain.close)

    def spend(self, index, *, fee=1000, previous=None, key=ALICE):
        previous = self.funding if previous is None else previous
        output = previous.outputs[index]
        transaction = Transaction(2, (TxInput(previous.txid(), index),),
                                  (TxOutput(output.value - fee, ALICE.script_pubkey),))
        return sign_p2wpkh(transaction, 0, output, key)

    @staticmethod
    def insert(connection, transaction):
        connection.execute('INSERT INTO mempool(txid,raw) VALUES (?,?)',
                           (transaction.txid(), transaction.serialize()))

    def external(self):
        connection = sqlite3.connect(str(self.database), isolation_level=None)
        self.addCleanup(connection.close)
        return connection

    def test_warm_cache_validates_new_signed_child_and_conflicts(self):
        parent = self.spend(0)
        self.chain.submit_transaction(parent)
        child = self.spend(0, previous=parent)
        with patch.object(self.chain, '_apply_transaction', wraps=self.chain._apply_transaction) as apply:
            self.chain.submit_transaction(child)
            self.assertEqual(1, apply.call_count)
        cached = self.chain._validated_mempool_cache
        before = cached[1].copy()
        with self.assertRaises(InvalidTransaction):
            self.chain.submit_transaction(self.spend(0, previous=parent, fee=2000))
        self.assertIs(cached, self.chain._validated_mempool_cache)
        self.assertEqual(before, cached[1])
        self.chain.submit_transaction(self.spend(1))
        self.assertEqual(3, self.chain.summary()['mempool'])

    def test_invalid_signature_does_not_mutate_committed_overlay(self):
        self.chain.submit_transaction(self.spend(0))
        cached = self.chain._validated_mempool_cache
        before = cached[1].copy()
        valid = self.spend(1)
        forged = replace(valid, outputs=(replace(valid.outputs[0], value=valid.outputs[0].value - 1),))
        with self.assertRaises(InvalidTransaction):
            self.chain.submit_transaction(forged)
        self.assertIs(cached, self.chain._validated_mempool_cache)
        self.assertEqual(before, cached[1])
        self.chain.submit_transaction(valid)
        self.assertEqual(2, self.chain.summary()['mempool'])

    def test_warm_cache_keeps_serialized_byte_policy_and_rejection_state(self):
        first, second = self.spend(0), self.spend(1)
        self.chain.submit_transaction(first)
        cached = self.chain._validated_mempool_cache
        overlay = cached[1].copy()
        commitment = self.chain.state_commitment()
        # A reduced local test policy exercises the exact serialized-byte edge;
        # production block limits and consensus validation are unchanged.
        limit = len(first.serialize()) + len(second.serialize()) - 1
        with patch('sumuww.chain.MAX_MEMPOOL_BYTES', limit):
            with self.assertRaisesRegex(ValidationError, 'Local mempool resource limit'):
                self.chain.submit_transaction(second)
        self.assertIs(cached, self.chain._validated_mempool_cache)
        self.assertEqual(overlay, cached[1])
        self.assertEqual(commitment, self.chain.state_commitment())
        self.assertEqual(1, self.chain.summary()['mempool'])
        self.chain.submit_transaction(second)
        self.assertEqual(2, self.chain.summary()['mempool'])

    def test_same_connection_pool_insert_and_delete_invalidate(self):
        self.chain.submit_transaction(self.spend(0))
        inserted = self.spend(1)
        self.insert(self.chain.connection, inserted)
        with self.assertRaises(InvalidTransaction):
            self.chain.submit_transaction(self.spend(1, fee=2000))
        self.chain.connection.execute('DELETE FROM mempool WHERE txid=?', (inserted.txid(),))
        with patch.object(self.chain, '_apply_transaction', wraps=self.chain._apply_transaction) as apply:
            self.chain.submit_transaction(self.spend(1, fee=2000))
            self.assertEqual(2, apply.call_count)

    def test_external_pool_insert_and_delete_invalidate(self):
        writer = self.external()
        self.chain.submit_transaction(self.spend(0))
        inserted = self.spend(1)
        self.insert(writer, inserted)
        with self.assertRaises(InvalidTransaction):
            self.chain.submit_transaction(self.spend(1, fee=2000))
        writer.execute('DELETE FROM mempool WHERE txid=?', (inserted.txid(),))
        with patch.object(self.chain, '_apply_transaction', wraps=self.chain._apply_transaction) as apply:
            self.chain.submit_transaction(self.spend(1, fee=2000))
            self.assertEqual(2, apply.call_count)

    def test_corrupt_existing_pool_signature_is_revalidated_after_any_writer(self):
        transaction = self.spend(0)
        self.chain.submit_transaction(transaction)
        forged = replace(transaction, outputs=(replace(transaction.outputs[0],
                                                       value=transaction.outputs[0].value - 1),))
        self.assertEqual(len(transaction.serialize()), len(forged.serialize()))
        for index, writer in enumerate((self.chain.connection, self.external()), start=1):
            with self.subTest(external=index == 2):
                cached = self.chain._validated_mempool_cache
                before = cached[1].copy()
                writer.execute('UPDATE mempool SET raw=? WHERE txid=?',
                               (forged.serialize(), transaction.txid()))
                with self.assertRaises(InvalidTransaction):
                    self.chain.submit_transaction(self.spend(index))
                self.assertIs(cached, self.chain._validated_mempool_cache)
                self.assertEqual(before, cached[1])
                writer.execute('UPDATE mempool SET raw=? WHERE txid=?',
                               (transaction.serialize(), transaction.txid()))
                self.chain.submit_transaction(self.spend(index))

    def test_rolled_back_local_write_invalidates_without_changing_cache(self):
        self.chain.submit_transaction(self.spend(0))
        cached = self.chain._validated_mempool_cache
        self.chain.connection.execute('BEGIN IMMEDIATE')
        self.insert(self.chain.connection, self.spend(1))
        self.chain.connection.execute('ROLLBACK')
        self.assertIs(cached, self.chain._validated_mempool_cache)
        with patch.object(self.chain, '_apply_transaction', wraps=self.chain._apply_transaction) as apply:
            self.chain.submit_transaction(self.spend(1))
            self.assertEqual(2, apply.call_count)

    def test_before_submit_mutation_is_seen_under_write_lock(self):
        self.chain.submit_transaction(self.spend(0))
        cached = self.chain._validated_mempool_cache
        inserted = self.spend(1)
        with self.assertRaises(InvalidTransaction):
            self.chain.submit_transaction(self.spend(1, fee=2000),
                before_submit=lambda chain: self.insert(chain.connection, inserted))
        self.assertFalse(self.chain.has_mempool_transaction(inserted.txid()))
        self.assertIs(cached, self.chain._validated_mempool_cache)
        self.chain.submit_transaction(self.spend(1))

    def test_before_submit_exception_rolls_back_without_cache_publication(self):
        self.chain.submit_transaction(self.spend(0))
        cached = self.chain._validated_mempool_cache
        def policy(chain):
            self.insert(chain.connection, self.spend(1))
            raise RuntimeError('owned policy rejection')
        with self.assertRaisesRegex(RuntimeError, 'owned policy rejection'):
            self.chain.submit_transaction(self.spend(2), before_submit=policy)
        self.assertIs(cached, self.chain._validated_mempool_cache)
        self.assertEqual(1, self.chain.summary()['mempool'])
        self.chain.submit_transaction(self.spend(1))

    def test_confirmed_block_invalidates_pool_overlay(self):
        transaction = self.spend(0)
        self.chain.submit_transaction(transaction)
        self.chain.mine(ALICE.script_pubkey)
        self.assertEqual(0, self.chain.summary()['mempool'])
        with patch.object(self.chain, '_apply_transaction', wraps=self.chain._apply_transaction) as apply:
            self.chain.submit_transaction(self.spend(1))
            self.assertEqual(1, apply.call_count)
        with self.assertRaises(InvalidTransaction):
            self.chain.submit_transaction(self.spend(0, fee=2000))

    def test_external_reorg_revalidates_disconnected_funding_and_parent(self):
        with Chain(self.database, clock=lambda: NOW) as writer:
            self.chain.submit_transaction(self.spend(0))
            first = writer.make_block(BOB.script_pubkey, (), parent_hash=self.branch_parent,
                                      extra_nonce=371)
            writer.accept_block(first)
            second = writer.make_block(BOB.script_pubkey, (), parent_hash=first.block_hash(),
                                       extra_nonce=372)
            writer.accept_block(second)
            self.assertEqual(second.block_hash(), self.chain.tip_hash)
            self.assertNotEqual(self.funded_tip, self.chain.tip_hash)
            with patch.object(self.chain, '_apply_transaction', wraps=self.chain._apply_transaction) as apply:
                self.chain.submit_transaction(self.spend(1))
                self.assertEqual(3, apply.call_count)
            self.assertEqual(3, self.chain.summary()['mempool'])

    def test_external_commit_before_publication_cannot_tag_stale_overlay(self):
        writer = self.external()
        self.chain.submit_transaction(self.spend(0))
        external = self.spend(2)
        self.chain.connection = ConnectionProxy(self.chain.connection,
            after_commit=lambda: self.insert(writer, external))
        self.chain.submit_transaction(self.spend(1))
        cache_token = self.chain._validated_mempool_cache[0]
        self.assertNotEqual(cache_token, (*self.chain._path_cache_token(), self.chain.tip_hash))
        with self.assertRaises(InvalidTransaction):
            self.chain.submit_transaction(self.spend(2, fee=2000))
        self.assertEqual(3, self.chain.summary()['mempool'])

    def test_commit_failure_rolls_back_without_publishing_trial_state(self):
        self.chain.submit_transaction(self.spend(0))
        cached = self.chain._validated_mempool_cache
        before = cached[1].copy()
        self.chain.connection = ConnectionProxy(self.chain.connection, fail_commit=True)
        with self.assertRaisesRegex(sqlite3.OperationalError, 'owned commit fault'):
            self.chain.submit_transaction(self.spend(1))
        self.assertIs(cached, self.chain._validated_mempool_cache)
        self.assertEqual(before, cached[1])
        self.assertEqual(1, self.chain.summary()['mempool'])
        with patch.object(self.chain, '_apply_transaction', wraps=self.chain._apply_transaction) as apply:
            self.chain.submit_transaction(self.spend(1))
            self.assertEqual(2, apply.call_count)


if __name__ == '__main__':
    unittest.main()
