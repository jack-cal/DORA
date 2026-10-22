"""Nonce-space retries use fresh, immutable templates without pinned SQLite reads."""

from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from sumuww.block import GENESIS_TIME, genesis_block, mine_header
from sumuww.chain import Chain
from sumuww.errors import MiningExhausted
from sumuww.primitives import COIN
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


NOW = GENESIS_TIME + 1000
ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)


class MiningRetryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-nonce-retry-')
        self.database = Path(self.directory.name) / 'node.sqlite'
        self.chain = Chain(self.database, clock=lambda: NOW)

    def tearDown(self):
        self.chain.close()
        self.directory.cleanup()

    def test_bounded_header_failure_has_dedicated_runtimeerror_subtype(self):
        header = replace(genesis_block().header, bits=0x01010000)
        with self.assertRaises(MiningExhausted):
            mine_header(header, max_attempts=1)
        self.assertTrue(issubclass(MiningExhausted, RuntimeError))
        with self.assertRaises(RuntimeError) as caught:
            mine_header(header, cancel_check=lambda: True)
        self.assertNotIsInstance(caught.exception, MiningExhausted)

    def test_retry_rolls_coinbase_and_does_not_pin_read_snapshot(self):
        headers = []
        checkpoints = []
        original_tip = self.chain.tip_hash
        def search(header, **options):
            self.assertFalse(self.chain.connection.in_transaction)
            headers.append(header)
            with Chain(self.database, clock=lambda: NOW) as other:
                checkpoints.append(other.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone())
            if len(headers) == 1:
                raise MiningExhausted('simulated full nonce space')
            return mine_header(header, **options)
        with patch('sumuww.chain.mine_header', side_effect=search):
            block = self.chain.make_block(ALICE.script_pubkey)
        self.assertEqual(2, len(headers))
        self.assertNotEqual(headers[0].merkle_root, headers[1].merkle_root)
        self.assertEqual(original_tip, headers[1].previous_hash)
        self.assertEqual(1, int.from_bytes(block.transactions[0].inputs[0].script_sig[-4:], 'little'))
        self.assertTrue(all(result[0] == 0 for result in checkpoints))
        self.assertTrue(self.chain.accept_block(block))

    def test_default_parent_refreshes_after_external_tip_change(self):
        competitor = self.chain.make_block(BOB.script_pubkey, extra_nonce=42)
        headers = []
        def search(header, **options):
            self.assertFalse(self.chain.connection.in_transaction)
            headers.append(header)
            if len(headers) == 1:
                with Chain(self.database, clock=lambda: NOW) as external:
                    self.assertTrue(external.accept_block(competitor))
                raise MiningExhausted('simulated full nonce space')
            return mine_header(header, **options)
        with patch('sumuww.chain.mine_header', side_effect=search):
            block = self.chain.make_block(ALICE.script_pubkey)
        self.assertEqual(competitor.block_hash(), headers[1].previous_hash)
        self.assertTrue(self.chain.accept_block(block))
        self.assertEqual(2, self.chain.info()['height'])

    def test_explicit_branch_parent_is_preserved_on_retry(self):
        parent = self.chain.tip_hash
        competitor = self.chain.make_block(BOB.script_pubkey, extra_nonce=42)
        self.chain.accept_block(competitor)
        headers = []
        def search(header, **options):
            headers.append(header)
            if len(headers) == 1:
                raise MiningExhausted('simulated full nonce space')
            return mine_header(header, **options)
        with patch('sumuww.chain.mine_header', side_effect=search):
            block = self.chain.make_block(ALICE.script_pubkey, parent_hash=parent)
        self.assertTrue(all(header.previous_hash == parent for header in headers))
        self.assertFalse(self.chain.accept_block(block))
        self.assertTrue(self.chain.has_block(block.block_hash()))
        self.assertEqual(competitor.block_hash(), self.chain.tip_hash)

    def test_cancellation_after_exhaustion_stops_before_another_template(self):
        cancellation = threading.Event()
        original = self.chain.info()
        def search(*_arguments, **_options):
            cancellation.set()
            raise MiningExhausted('simulated full nonce space')
        with patch('sumuww.chain.mine_header', side_effect=search) as search_mock:
            with self.assertRaisesRegex(RuntimeError, 'Mining cancelled'):
                self.chain.make_block(ALICE.script_pubkey, mining_cancel=cancellation.is_set)
        self.assertEqual(1, search_mock.call_count)
        self.assertEqual(original, self.chain.info())
        self.assertFalse(self.chain.connection.in_transaction)

    def test_extranonce_wrap_updates_timestamp_and_remains_valid(self):
        headers = []
        def search(header, **options):
            headers.append(header)
            if len(headers) == 1:
                raise MiningExhausted('simulated full nonce space')
            return mine_header(header, **options)
        with patch('sumuww.chain.mine_header', side_effect=search):
            block = self.chain.make_block(ALICE.script_pubkey, timestamp=NOW, extra_nonce=0xFFFFFFFF)
        self.assertEqual(NOW + 1, headers[1].timestamp)
        self.assertEqual(0, int.from_bytes(block.transactions[0].inputs[0].script_sig[-4:], 'little'))
        self.assertNotEqual(headers[0].merkle_root, headers[1].merkle_root)
        self.assertTrue(self.chain.accept_block(block))

    def test_retry_keeps_explicit_transaction_iterable(self):
        first = self.chain.mine(ALICE.script_pubkey, 100)[0].transactions[0]
        transaction = sign_p2wpkh(Transaction(2, (TxInput(first.txid(), 0),),
                                            (TxOutput(50 * COIN - 1, BOB.script_pubkey),)),
                                 0, first.outputs[0], ALICE)
        attempts = []
        def search(header, **options):
            attempts.append(header)
            if len(attempts) == 1:
                raise MiningExhausted('simulated full nonce space')
            return mine_header(header, **options)
        with patch('sumuww.chain.mine_header', side_effect=search):
            block = self.chain.make_block(ALICE.script_pubkey, transactions=(item for item in (transaction,)))
        self.assertEqual((transaction,), block.transactions[1:])
        self.assertEqual(50 * COIN + 1, block.transactions[0].outputs[0].value)
        self.assertTrue(self.chain.accept_block(block))

    def test_bad_extranonce_fails_before_nonce_search(self):
        for extra_nonce in (-1, 1 << 32, True, 1.0, None):
            with self.subTest(extra_nonce=extra_nonce), patch('sumuww.chain.mine_header') as search:
                with self.assertRaises((TypeError, ValueError)):
                    self.chain.make_block(ALICE.script_pubkey, extra_nonce=extra_nonce)
                search.assert_not_called()
                self.assertFalse(self.chain.connection.in_transaction)


if __name__ == '__main__':
    unittest.main()
