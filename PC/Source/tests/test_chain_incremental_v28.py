"""Incremental active-chain writes and snapshot cache safety; disposable state."""
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sumuww.block import Block, GENESIS_TIME
from sumuww.chain import Chain
from sumuww.errors import StorageError
from sumuww.primitives import COIN
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)
NOW = GENESIS_TIME + 100_000


class IncrementalChainTests(unittest.TestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory(prefix="sumuww-chain-incremental-v28-")
        self.addCleanup(self.scratch.cleanup)
        self.database = Path(self.scratch.name) / "chain.sqlite"
        self.chain = Chain(self.database, clock=lambda: NOW)
        self.addCleanup(self.chain.close)

    def writer(self):
        connection = sqlite3.connect(self.database, isolation_level=None)
        self.addCleanup(connection.close)
        return connection

    @staticmethod
    def ledger(chain):
        return {table: chain.connection.execute("SELECT * FROM " + table + " ORDER BY 1,2").fetchall()
                for table in ("metadata", "blocks", "utxos", "mempool")}

    def test_active_extension_writes_only_its_delta(self):
        self.chain.mine(ALICE.script_pubkey, 20)
        block = self.chain.make_block(ALICE.script_pubkey)
        trace = []
        self.chain.connection.set_trace_callback(trace.append)
        previous_changes = self.chain.connection.total_changes
        self.assertTrue(self.chain.accept_block(block))
        self.chain.connection.set_trace_callback(None)
        # Block, tip, new coinbase UTXO, and its one derived fee-index row.
        self.assertEqual(4, self.chain.connection.total_changes - previous_changes)
        self.assertEqual((0,), self.chain.connection.execute(
            'SELECT fees FROM block_reward_fees WHERE blockhash=?',
            (block.block_hash(),)).fetchone())
        self.assertFalse(any(query.upper().strip() == "DELETE FROM UTXOS" for query in trace))
        self.assertEqual(21 * 50 * COIN, self.chain.balance(ALICE.script_pubkey))
        self.assertTrue(self.chain.verify_persisted_state())

    def test_same_block_parent_child_spend_is_not_resurrected(self):
        first = self.chain.mine(ALICE.script_pubkey, 100)[0].transactions[0]
        parent = sign_p2wpkh(Transaction(2, (TxInput(first.txid(), 0),),
                                       (TxOutput(10 * COIN, BOB.script_pubkey),
                                        TxOutput(39 * COIN, ALICE.script_pubkey))),
                            0, first.outputs[0], ALICE)
        child = sign_p2wpkh(Transaction(2, (TxInput(parent.txid(), 0),),
                                      (TxOutput(9 * COIN, ALICE.script_pubkey),)),
                           0, parent.outputs[0], BOB)
        self.chain.submit_transaction(parent)
        self.chain.submit_transaction(child)
        block = self.chain.make_block(ALICE.script_pubkey)
        self.assertTrue(self.chain.accept_block(block))
        coins = dict(self.chain.list_utxos())
        self.assertNotIn((first.txid(), 0), coins)
        self.assertNotIn((parent.txid(), 0), coins)
        self.assertEqual(39 * COIN, coins[(parent.txid(), 1)].output.value)
        self.assertEqual(9 * COIN, coins[(child.txid(), 0)].output.value)
        self.assertEqual(52 * COIN, block.transactions[0].outputs[0].value)
        self.assertFalse(self.chain.mempool_transactions())
        self.assertTrue(self.chain.verify_persisted_state())

    def test_repeated_same_snapshot_queries_do_not_reparse_blocks(self):
        self.chain.mine(ALICE.script_pubkey, 12)
        with patch.object(Block, "deserialize", wraps=Block.deserialize) as deserialize:
            for _ in range(5):
                self.assertEqual(13, len(self.chain._path(self.chain.tip_hash)))
                self.chain.expected_bits()
            self.assertEqual(0, deserialize.call_count)

    def test_cache_does_not_hide_same_connection_index_tampering(self):
        self.chain.mine(ALICE.script_pubkey, 4)
        tip = self.chain.tip_hash
        self.chain._path(tip)
        self.chain.connection.execute("UPDATE blocks SET work='0' WHERE hash=?", (tip,))
        with self.assertRaisesRegex(StorageError, "Height/chainwork"):
            self.chain._path(tip)

    def test_cache_does_not_hide_foreign_writer_same_tip_index_tampering(self):
        self.chain.mine(ALICE.script_pubkey, 4)
        tip = self.chain.tip_hash
        self.chain._path(tip)
        self.writer().execute("UPDATE blocks SET work='0' WHERE hash=?", (tip,))
        self.assertEqual(tip, self.chain.tip_hash)
        with self.assertRaisesRegex(StorageError, "Height/chainwork"):
            self.chain._path(tip)

    def test_foreign_writer_same_tip_body_tampering_is_detected(self):
        self.chain.mine(ALICE.script_pubkey, 4)
        tip = self.chain.tip_hash
        self.chain._path(tip)
        raw = bytearray(self.chain._row(tip)[4])
        raw[4] ^= 1
        self.writer().execute("UPDATE blocks SET raw=? WHERE hash=?", (bytes(raw), tip))
        with self.assertRaisesRegex(StorageError, "Block bytes/index"):
            self.chain._path(tip)

    def test_explicit_verification_rereads_cache_and_rejects_utxo_tampering(self):
        self.chain.mine(ALICE.script_pubkey, 4)
        self.chain._path(self.chain.tip_hash)
        self.writer().execute("UPDATE utxos SET value=value+1 WHERE height=1")
        with patch.object(Block, "deserialize", wraps=Block.deserialize) as deserialize:
            with self.assertRaisesRegex(StorageError, "Stored UTXO"):
                self.chain.verify_persisted_state()
            self.assertGreaterEqual(deserialize.call_count, 5)

    def test_foreign_append_invalidates_after_read_snapshot_ends(self):
        self.chain.mine(ALICE.script_pubkey, 4)
        other = Chain(self.database, clock=lambda: NOW)
        self.addCleanup(other.close)
        old_tip = self.chain.tip_hash
        with self.chain.read_snapshot():
            self.assertEqual(old_tip, self.chain.tip_hash)
            self.assertEqual(5, len(self.chain._path(old_tip)))
            new_block = other.mine(BOB.script_pubkey, 1)[0]
            self.assertEqual(old_tip, self.chain.tip_hash)
            self.assertEqual(5, len(self.chain._path(old_tip)))
        self.assertEqual(new_block.block_hash(), self.chain.tip_hash)
        with patch.object(self.chain, "_read_index_path", wraps=self.chain._read_index_path) as reread:
            self.assertEqual(6, len(self.chain._path(self.chain.tip_hash)))
            self.assertEqual(1, reread.call_count)
        self.assertTrue(self.chain.verify_persisted_state())

    def test_rollback_cannot_publish_uncommitted_path_or_utxos(self):
        self.chain.mine(ALICE.script_pubkey, 4)
        block = self.chain.make_block(BOB.script_pubkey)
        before = self.ledger(self.chain)
        for target in ("after_block_saved", "after_utxos_saved", "after_tip_saved"):
            def fail(stage):
                if stage == target:
                    raise RuntimeError("fixture rollback")
            self.chain.fault_hook = fail
            with self.assertRaisesRegex(RuntimeError, "fixture rollback"):
                self.chain.accept_block(block)
            self.assertEqual(before, self.ledger(self.chain))
            self.assertEqual(5, len(self.chain._path(self.chain.tip_hash)))
        self.chain.fault_hook = None
        self.assertTrue(self.chain.accept_block(block))
        self.assertEqual(6, len(self.chain._path(self.chain.tip_hash)))
        self.assertEqual(50 * COIN, self.chain.balance(BOB.script_pubkey))
        self.assertTrue(self.chain.verify_persisted_state())

    def test_reorganization_uses_full_validated_replacement(self):
        active = self.chain.mine(ALICE.script_pubkey, 4)
        parent = self.chain.network.genesis.block_hash()
        with patch.object(self.chain, "_replace_utxos", wraps=self.chain._replace_utxos) as replacement:
            for height in range(1, 6):
                block = self.chain.make_block(BOB.script_pubkey, parent_hash=parent,
                                              timestamp=NOW + 100 + height)
                self.chain.accept_block(block)
                parent = block.block_hash()
            self.assertEqual(1, replacement.call_count)
        self.assertNotEqual(active[-1].block_hash(), self.chain.tip_hash)
        self.assertEqual(parent, self.chain.tip_hash)
        self.assertEqual(0, self.chain.balance(ALICE.script_pubkey))
        self.assertEqual(5 * 50 * COIN, self.chain.balance(BOB.script_pubkey))
        self.assertTrue(self.chain.verify_persisted_state())

    def test_read_path_cannot_mutate_cached_sequence(self):
        self.chain.mine(ALICE.script_pubkey, 2)
        path = self.chain._path(self.chain.tip_hash)
        with self.assertRaises(TypeError):
            path[0] = path[-1]
        self.assertEqual(self.chain.network.genesis.block_hash(), self.chain._path(self.chain.tip_hash)[0][0][0])


if __name__ == "__main__":
    unittest.main()
