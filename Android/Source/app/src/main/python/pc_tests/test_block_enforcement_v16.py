"""Definite invalid work rejected before costly fork-state replay."""

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww.chain import Chain
from sumuww.errors import InvalidBlock, TransientValidationError, ValidationError
from sumuww.primitives import check_pow
from sumuww.wallet import RegtestKey

KEY = RegtestKey.from_int(1)


class BlockEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-block-enforcement-')
        self.root = Path(self.temp.name)
        self.chain = Chain(self.root / 'node.sqlite')

    def tearDown(self):
        self.chain.close()
        self.temp.cleanup()

    def state(self):
        return self.chain.tip_hash, self.chain.state_commitment(), self.chain.connection.execute('SELECT COUNT(*) FROM blocks').fetchone()[0]

    def test_wrong_contextual_bits_rejected_before_fork_replay(self):
        parents = self.chain.mine(KEY.script_pubkey, 3)
        block = self.chain.make_block(KEY.script_pubkey, parent_hash=parents[0].block_hash(), extra_nonce=777)
        invalid = replace(block, header=replace(block.header, bits=block.header.bits - 1))
        before = self.state()
        with patch.object(self.chain, '_replay', side_effect=AssertionError('should not replay invalid work')):
            with self.assertRaisesRegex(InvalidBlock, 'contextual nBits'):
                self.chain.accept_block(invalid)
        self.assertEqual(before, self.state())
        self.assertFalse(self.chain.has_block(invalid.block_hash()))

    def test_wrong_pow_rejected_before_reading_active_utxos(self):
        block = self.chain.make_block(KEY.script_pubkey)
        nonce = 0
        while check_pow(replace(block.header, nonce=nonce).digest(), block.header.bits, self.chain.network.pow_limit):
            nonce += 1
        invalid = replace(block, header=replace(block.header, nonce=nonce))
        before = self.state()
        with patch.object(self.chain, '_load_utxos', side_effect=AssertionError('should not load state for invalid work')):
            with self.assertRaisesRegex(InvalidBlock, 'Invalid proof'):
                self.chain.accept_block(invalid)
        self.assertEqual(before, self.state())

    def test_future_clock_condition_is_retryable_not_permanent(self):
        clock = [2_000_000_000]
        self.chain.clock = lambda: clock[0]
        block = self.chain.make_block(KEY.script_pubkey, timestamp=clock[0] + 7201)
        before = self.state()
        with self.assertRaises(TransientValidationError):
            self.chain.accept_block(block)
        self.assertEqual(before, self.state())
        clock[0] += 2
        self.assertTrue(self.chain.accept_block(block))

    def test_unknown_parent_is_not_a_definite_invalid_block(self):
        block = self.chain.make_block(KEY.script_pubkey)
        unknown = replace(block, header=replace(block.header, previous_hash=b'\x77' * 32))
        with self.assertRaises(ValidationError) as caught:
            self.chain.accept_block(unknown)
        self.assertNotIsInstance(caught.exception, InvalidBlock)


if __name__ == '__main__':
    unittest.main()
