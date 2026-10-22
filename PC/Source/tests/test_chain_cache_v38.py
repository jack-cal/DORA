"""Bounded verified branch reuse, immutable replay views and live-output indexes.

Public keys and temporary SQLite files only; no network or actual user state.
"""
from dataclasses import replace
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from sumuww.block import Block, GENESIS_TIME
from sumuww.chain import (Chain, Coin, _CoinState, _PathPrefix, MAX_VALIDATED_BRANCHES,
                        MAX_VALIDATED_COINS, MAX_VALIDATED_PATH_ITEMS, MAX_VALIDATED_BODY_BYTES)
from sumuww.errors import InvalidTransaction, StorageError, ValidationError
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh

NOW = GENESIS_TIME + 100_000
ALICE, BOB = RegtestKey.from_int(3801), RegtestKey.from_int(3802)


class ChainCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_directory = tempfile.TemporaryDirectory(prefix='sumuww-owned-cache-seed-',
            dir=os.environ.get('SUMUWW_TEST_WORKDIR'))
        cls.seed = Path(cls.seed_directory.name) / 'seed.sqlite'
        with Chain(cls.seed, clock=lambda: NOW) as chain:
            blocks = chain.mine(ALICE.script_pubkey, 128)
            first = blocks[0].transactions[0]
            cls.funding = sign_p2wpkh(Transaction(2, (TxInput(first.txid(), 0),),
                tuple(TxOutput((first.outputs[0].value - 100_000) // 4, ALICE.script_pubkey)
                      for _ in range(4))), 0, first.outputs[0], ALICE)
            chain.submit_transaction(cls.funding)
            chain.mine(ALICE.script_pubkey)
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @classmethod
    def tearDownClass(cls):
        cls.seed_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-owned-cache-case-',
            dir=os.environ.get('SUMUWW_TEST_WORKDIR'))
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'chain.sqlite'
        shutil.copy2(self.seed, self.database)
        self.chain = Chain(self.database, clock=lambda: NOW)
        self.addCleanup(self.chain.close)

    def spend(self, index=0, *, outputs=None):
        output = self.funding.outputs[index]
        transaction = Transaction(2, (TxInput(self.funding.txid(), index),),
            tuple(outputs or (TxOutput(output.value - 1000, BOB.script_pubkey),)))
        return sign_p2wpkh(transaction, 0, output, ALICE)

    def writer(self):
        writer = sqlite3.connect(str(self.database), isolation_level=None)
        self.addCleanup(writer.close)
        return writer

    def fork(self, *, extra_nonce=38001):
        parent = self.chain._path(self.chain.tip_hash)[-10][0][0]
        block = self.chain.make_block(BOB.script_pubkey, (), parent_hash=parent, extra_nonce=extra_nonce)
        self.assertFalse(self.chain.accept_block(block))
        return parent, block

    def test_replay_prefixes_share_backing_path_and_keep_all_validation(self):
        path = self.chain._path(self.chain.tip_hash)
        prefixes = []
        connect = self.chain._connect
        def record(block, state, prefix, **kwargs):
            self.assertIsInstance(prefix, _PathPrefix)
            self.assertIs(prefix.items, path)
            self.assertEqual(tuple(prefix), path[:len(prefix)])
            self.assertEqual(self.chain._mtp(prefix), self.chain._mtp(path[:len(prefix)]))
            prefixes.append(len(prefix))
            return connect(block, state, prefix, **kwargs)
        with patch.object(self.chain, '_connect', side_effect=record):
            replayed = self.chain._replay(path)
        self.assertEqual(list(range(1, len(path))), prefixes)
        self.assertEqual(self.chain._load_utxos(), replayed)
        prefix = _PathPrefix(path, 0, len(path))
        self.assertEqual(path[2:9], tuple(prefix[2:9]))
        self.assertEqual(path[::-2], prefix[::-2])
        self.assertEqual(0, len(prefix[9:2]))
        self.assertEqual((), tuple(prefix[9:2]))
        with self.assertRaises((AttributeError, TypeError)):
            prefix.stop = 1

    def test_explicit_verification_never_uses_warm_branch_state(self):
        self.fork()
        height = self.chain.summary()['height']
        with patch.object(self.chain, '_connect', wraps=self.chain._connect) as connect, \
             patch.object(Block, 'deserialize', wraps=Block.deserialize) as parse:
            self.assertTrue(self.chain.verify_persisted_state())
        self.assertEqual(height, connect.call_count)
        self.assertGreaterEqual(parse.call_count, height + 1)

    def test_repeated_fork_parent_keeps_new_block_validation_without_replay(self):
        parent, _ = self.fork()
        with patch.object(self.chain, '_replay', side_effect=AssertionError('cached prefix replayed')), \
             patch.object(self.chain, '_read_index_path', side_effect=AssertionError('cached path reread')), \
             patch.object(self.chain, '_connect', wraps=self.chain._connect) as connect:
            for extra in range(3):
                block = self.chain.make_block(BOB.script_pubkey, (), parent_hash=parent,
                    extra_nonce=38010 + extra)
                self.assertFalse(self.chain.accept_block(block))
        self.assertEqual(3, connect.call_count)

    def test_cached_states_and_paths_do_not_alias_returned_working_state(self):
        parent, _ = self.fork()
        state, path = self.chain._state_for(parent)
        original = state.copy()
        state.clear()
        recovered, recovered_path = self.chain._state_for(parent)
        self.assertEqual(original, recovered)
        self.assertIs(path, recovered_path)
        with self.assertRaises(TypeError):
            path[0] = path[-1]

    def test_confirmed_cache_excludes_pending_overlay(self):
        pending = self.spend()
        self.chain.submit_transaction(pending)
        block = self.chain.make_block(ALICE.script_pubkey, ())
        self.chain.accept_block(block)
        state, _ = self.chain._state_for(self.chain.tip_hash)
        self.assertIn((self.funding.txid(), 0), state)
        self.assertNotIn((pending.txid(), 0), state)
        self.assertTrue(self.chain.has_mempool_transaction(pending.txid()))

    def test_cache_has_entry_coin_path_and_body_aggregate_limits(self):
        parent, _ = self.fork()
        for extra in range(12):
            block = self.chain.make_block(BOB.script_pubkey, (), parent_hash=parent,
                extra_nonce=38100 + extra)
            self.chain.accept_block(block)
            entries = self.chain._branch_entries()
            self.assertLessEqual(len(entries), MAX_VALIDATED_BRANCHES)
            self.assertLessEqual(sum(len(entry[0]) for entry in entries.values()), MAX_VALIDATED_COINS)
            self.assertLessEqual(sum(len(entry[1]) for entry in entries.values()), MAX_VALIDATED_PATH_ITEMS)
            self.assertLessEqual(sum(entry[2] for entry in entries.values()), MAX_VALIDATED_BODY_BYTES)
        with patch('sumuww.chain.MAX_VALIDATED_COINS', 1):
            self.chain.verify_persisted_state()
            self.assertEqual({}, self.chain._branch_entries())

    def test_same_and_external_index_edits_invalidate_cached_branches(self):
        parent, block = self.fork()
        for writer in (self.chain.connection, self.writer()):
            row = self.chain._row(block.block_hash())
            writer.execute("UPDATE blocks SET work='0' WHERE hash=?", (block.block_hash(),))
            with self.assertRaises(StorageError):
                self.chain._path(block.block_hash())
            writer.execute('UPDATE blocks SET work=? WHERE hash=?', (row[3], block.block_hash()))
            state, path = self.chain._state_for(parent)
            self.assertEqual(len(path) - 1, len(state))

    def test_body_corruption_after_cache_is_fully_rejected(self):
        parent, block = self.fork()
        coinbase = block.transactions[0]
        changed = replace(coinbase, outputs=(replace(coinbase.outputs[0],
            value=coinbase.outputs[0].value + 1),))
        corrupt = Block(block.header, (changed,))
        self.writer().execute('UPDATE blocks SET raw=? WHERE hash=?',
            (corrupt.serialize(), block.block_hash()))
        with self.assertRaises(ValidationError):
            self.chain._state_for(block.block_hash())

    def test_uncommitted_read_and_rollback_never_publish_branch_state(self):
        cached = self.chain._validated_branch_cache
        outpoint = (self.funding.txid(), 0)
        before = self.chain._load_utxos()[outpoint]
        self.chain.connection.execute('BEGIN IMMEDIATE')
        self.chain.connection.execute('UPDATE utxos SET value=value+1 WHERE txid=? AND idx=?', outpoint)
        dirty, _ = self.chain._state_for(self.chain.tip_hash)
        self.assertEqual(before.output.value + 1, dirty[outpoint].output.value)
        self.assertIs(cached, self.chain._validated_branch_cache)
        self.chain.connection.execute('ROLLBACK')
        recovered, _ = self.chain._state_for(self.chain.tip_hash)
        self.assertEqual(before, recovered[outpoint])

    def test_fault_hook_rollback_clears_branch_publication(self):
        parent, _ = self.fork()
        tip = self.chain.tip_hash
        block = self.chain.make_block(BOB.script_pubkey, (), parent_hash=parent, extra_nonce=38999)
        def fault(stage):
            if stage == 'after_block_saved':
                raise RuntimeError('owned rollback')
        self.chain.fault_hook = fault
        with self.assertRaisesRegex(RuntimeError, 'owned rollback'):
            self.chain.accept_block(block)
        self.assertIsNone(self.chain._validated_branch_cache)
        self.assertFalse(self.chain.has_block(block.block_hash()))
        self.assertEqual(tip, self.chain.tip_hash)
        self.chain.fault_hook = None
        self.assertTrue(self.chain.verify_persisted_state())

    def test_foreign_commit_after_our_commit_cannot_retag_cached_state(self):
        writer = self.writer()
        outpoint = (self.funding.txid(), 0)
        connection = self.chain.connection
        class CommitRace:
            fired = False
            def __getattr__(self, name):
                return getattr(connection, name)
            def execute(proxy, sql, *args):
                result = connection.execute(sql, *args)
                if sql == 'COMMIT' and not proxy.fired:
                    proxy.fired = True
                    writer.execute('DELETE FROM utxos WHERE txid=? AND idx=?', outpoint)
                return result
        block = self.chain.make_block(ALICE.script_pubkey, ())
        self.chain.connection = CommitRace()
        self.chain.accept_block(block)
        self.assertNotEqual(self.chain._validated_branch_cache[0], self.chain._path_cache_token())
        state, _ = self.chain._state_for(self.chain.tip_hash)
        self.assertNotIn(outpoint, state)
        with self.assertRaises(InvalidTransaction):
            self.chain.make_block(ALICE.script_pubkey, (self.spend(),))

    def test_failed_commit_cannot_publish_uncommitted_branch(self):
        parent, _ = self.fork()
        block = self.chain.make_block(BOB.script_pubkey, (), parent_hash=parent, extra_nonce=38888)
        tip, commitment = self.chain.tip_hash, self.chain.state_commitment()
        connection = self.chain.connection
        class CommitFailure:
            fail = True
            def __getattr__(self, name):
                return getattr(connection, name)
            def execute(proxy, sql, *args):
                if sql == 'COMMIT' and proxy.fail:
                    proxy.fail = False
                    raise sqlite3.OperationalError('owned commit failure')
                return connection.execute(sql, *args)
        self.chain.connection = CommitFailure()
        with self.assertRaisesRegex(sqlite3.OperationalError, 'owned commit failure'):
            self.chain.accept_block(block)
        self.assertIsNone(self.chain._validated_branch_cache)
        self.assertFalse(self.chain.has_block(block.block_hash()))
        self.assertEqual(tip, self.chain.tip_hash)
        self.assertEqual(commitment, self.chain.state_commitment())
        self.assertFalse(self.chain.accept_block(block))

    def test_cached_parent_still_rejects_invalid_new_signature(self):
        self.chain.mine(ALICE.script_pubkey)
        tip = self.chain.tip_hash
        self.assertIn(tip, self.chain._branch_entries())
        valid = self.spend()
        bad = replace(valid, outputs=(replace(valid.outputs[0], value=valid.outputs[0].value - 1),))
        with patch.object(self.chain, '_replay', side_effect=AssertionError('warm parent replayed')):
            with self.assertRaisesRegex(InvalidTransaction, 'signature'):
                self.chain.make_block(ALICE.script_pubkey, (bad,))
        self.assertEqual(tip, self.chain.tip_hash)

    def test_external_active_appends_do_not_add_full_genesis_replay(self):
        with Chain(self.database, clock=lambda: NOW) as writer, \
             patch.object(self.chain, '_replay', side_effect=AssertionError('active external append replayed')):
            for _ in range(100):
                writer.mine(BOB.script_pubkey)
                self.chain.mine(ALICE.script_pubkey)
            self.assertEqual(329, self.chain.summary()['height'])
        self.assertTrue(self.chain.verify_persisted_state())

    def test_fork_reorganization_and_restart_keep_exact_utxos(self):
        _, first = self.fork()
        parent = first.block_hash()
        for extra in range(10):
            block = self.chain.make_block(BOB.script_pubkey, (), parent_hash=parent, extra_nonce=38200 + extra)
            self.chain.accept_block(block)
            parent = block.block_hash()
        self.assertEqual(parent, self.chain.tip_hash)
        commitment = self.chain.state_commitment()
        self.assertTrue(self.chain.verify_persisted_state())
        with Chain(self.database, clock=lambda: NOW) as restarted:
            self.assertEqual(parent, restarted.tip_hash)
            self.assertEqual(commitment, restarted.state_commitment())

    def test_partial_live_outputs_keep_duplicate_rule_for_indexed_and_plain_state(self):
        transaction = self.spend()
        base, path = self.chain._state_for(self.chain.tip_hash)
        for state in (base.copy(), dict(base)):
            with self.subTest(indexed=isinstance(state, _CoinState)):
                coin = Coin(transaction.outputs[0], len(path), False)
                state[(transaction.txid(), 0)] = coin
                state[(transaction.txid(), 1)] = coin
                del state[(transaction.txid(), 0)]
                before = state.copy()
                with self.assertRaisesRegex(InvalidTransaction, 'Live outputs'):
                    self.chain._apply_transaction(transaction, state, len(path), path)
                self.assertEqual(before, state)
                del state[(transaction.txid(), 1)]
                self.chain._apply_transaction(transaction, state, len(path), path)
                self.assertTrue(self.chain._has_live_outputs(state, transaction.txid()))

    def test_block_duplicate_live_output_check_keeps_plain_dict_fallback(self):
        base, path = self.chain._state_for(self.chain.tip_hash)
        block = self.chain.make_block(ALICE.script_pubkey, ())
        for state in (base.copy(), dict(base)):
            state[(block.transactions[0].txid(), 1)] = Coin(TxOutput(1, ALICE.script_pubkey), 1, False)
            with self.assertRaisesRegex(ValidationError, 'BIP30'):
                self.chain._connect(block, state, path)

    def test_nonspendable_outputs_do_not_leave_live_id_counts(self):
        state, path = self.chain._state_for(self.chain.tip_hash)
        transaction = self.spend(outputs=(TxOutput(self.funding.outputs[0].value - 1000, b'\x6a'),))
        self.chain._apply_transaction(transaction, state, len(path), path)
        self.assertFalse(self.chain._has_live_outputs(state, transaction.txid()))
        block = self.chain.make_block(b'\x6a', ())
        self.chain._connect(block, state, path)
        self.assertFalse(self.chain._has_live_outputs(state, block.transactions[0].txid()))

    def test_indexed_dict_mutators_and_copies_keep_exact_live_counts(self):
        first, second = b'a' * 32, b'b' * 32
        a, b, c = (first, 0), (first, 1), (second, 0)
        state = _CoinState({a: 1, b: 2})
        def check():
            expected = {}
            for key in state:
                expected[key[0]] = expected.get(key[0], 0) + 1
            self.assertEqual(expected, state._txids)
        state[a] = 3; check()
        del state[a]; check()
        state.setdefault(a, 4); check()
        self.assertEqual(4, state.setdefault(a, 99)); check()
        state.update({b: 5, c: 6}); check()
        clone = state.copy()
        state.pop(a); check()
        state.pop((second, 99), None); check()
        state.popitem(); check()
        state |= {c: 7}; check()
        state.clear(); check()
        self.assertEqual({first: 2, second: 1}, clone._txids)
        self.assertEqual({first: 2}, _CoinState.fromkeys((a, b))._txids)


if __name__ == '__main__':
    unittest.main()
