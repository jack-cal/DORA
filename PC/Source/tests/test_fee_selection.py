"""Local fee-rate policy must preserve dependency and consensus validation."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import shutil
import unittest

from sumuww.block import MAX_BLOCK_WEIGHT, build_coinbase
from sumuww.chain import Chain
from sumuww.primitives import COIN, encode_compact_size
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


class FeeSelectionTests(unittest.TestCase):
    key = RegtestKey.from_int(1)

    @classmethod
    def setUpClass(cls):
        cls.seed_directory = TemporaryDirectory(prefix='sumuww-fee-seed-')
        cls.seed = Path(cls.seed_directory.name) / 'seed.sqlite'
        with Chain(cls.seed) as chain:
            chain.mine(cls.key.script_pubkey, 104)
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @classmethod
    def tearDownClass(cls):
        cls.seed_directory.cleanup()

    def setUp(self):
        self.directory = TemporaryDirectory(prefix='sumuww-fee-selection-')
        self.database = Path(self.directory.name) / 'chain.sqlite'
        shutil.copy2(self.seed, self.database)
        self.chain = Chain(self.database)
        self.coins = sorted(self.chain.list_utxos(self.key.script_pubkey), key=lambda pair: pair[1].height)[:5]

    def tearDown(self):
        self.chain.close()
        self.directory.cleanup()

    def spend(self, outpoint, output, fee, padding=0, outputs=None):
        outputs = outputs or (TxOutput(output.value - fee, self.key.script_pubkey),)
        if padding:
            outputs += (TxOutput(0, b'\x6a' + bytes(padding)),)
        unsigned = Transaction(2, (TxInput(*outpoint),), tuple(outputs))
        return sign_p2wpkh(unsigned, 0, output, self.key)

    def coin_spend(self, index, fee, padding=0, outputs=None):
        outpoint, coin = self.coins[index]
        return self.spend(outpoint, coin.output, fee, padding, outputs)

    def child(self, parent, fee, index=0, padding=0):
        return self.spend((parent.txid(), index), parent.outputs[index], fee, padding)

    def add(self, *transactions):
        for transaction in transactions:
            self.chain.submit_transaction(transaction)

    def inject(self, *transactions):
        # Corrupt local pool fixtures bypass admission; selection must still
        # verify signatures, amounts and ancestor validity before using them.
        self.chain.connection.executemany('INSERT INTO mempool(txid,raw) VALUES (?,?)',
                                         [(tx.txid(), tx.serialize()) for tx in transactions])

    def template(self):
        with self.chain.read_snapshot():
            return self.chain._block_template(self.key.script_pubkey)

    def test_fee_per_vbyte_overrides_absolute_fee_and_arrival(self):
        large = self.coin_spend(0, 2_000, padding=1_000)
        small = self.coin_spend(1, 1_000)
        self.assertGreater(large.weight(), small.weight())
        self.add(large, small)
        block = self.chain.make_block(self.key.script_pubkey)
        self.assertEqual(block.transactions[1:], (small, large))
        self.assertEqual(block.transactions[0].outputs[0].value, 50 * COIN + 3_000)
        self.assertTrue(self.chain.accept_block(block))

    def test_high_fee_child_pays_for_parent_package(self):
        ordinary = self.coin_spend(0, 1_000)
        parent = self.coin_spend(1, 0, padding=500)
        child = self.child(parent, 100_000)
        self.add(ordinary, parent, child)
        block = self.chain.make_block(self.key.script_pubkey)
        self.assertEqual(block.transactions[1:], (parent, child, ordinary))
        self.assertTrue(self.chain.accept_block(block))

    def test_shared_ancestor_cost_is_removed_after_selection(self):
        outputs = (TxOutput(COIN, self.key.script_pubkey),
                   TxOutput(COIN, self.key.script_pubkey),
                   TxOutput(48 * COIN, self.key.script_pubkey))
        parent = self.coin_spend(0, 0, outputs=outputs)
        first = self.child(parent, 100_000, index=0)
        second = self.child(parent, 6_000, index=1)
        ordinary = self.coin_spend(1, 5_000)
        self.add(parent, first, ordinary, second)
        block = self.chain.make_block(self.key.script_pubkey)
        self.assertEqual(block.transactions[1:], (parent, first, second, ordinary))
        self.assertTrue(self.chain.accept_block(block))

    def fixed_rate_spend(self, index, rate):
        # DER signature size can change by a byte when the fee changes. Find
        # real signed fixtures having precisely equal integer fee/vbyte rates.
        for padding in range(5):
            for guessed_size in range(90, 145):
                tx = self.coin_spend(index, guessed_size * rate, padding)
                if (tx.weight() + 3) // 4 == guessed_size:
                    return tx
        self.fail('Could not make an exact-rate fixture')

    def test_equal_rates_preserve_fifo_deterministically(self):
        first = self.fixed_rate_spend(0, 5)
        second = self.fixed_rate_spend(1, 5)
        third = self.fixed_rate_spend(2, 5)
        self.add(second, first, third)
        for _ in range(3):
            self.assertEqual(self.template().transactions[1:], (second, first, third))

    def test_zero_fee_remains_eligible_after_paid_transaction(self):
        free = self.coin_spend(0, 0)
        paid = self.coin_spend(1, 100)
        self.add(free, paid)
        block = self.chain.make_block(self.key.script_pubkey)
        self.assertEqual(block.transactions[1:], (paid, free))
        self.assertEqual(block.transactions[0].outputs[0].value, 50 * COIN + 100)
        self.assertTrue(self.chain.accept_block(block))

    def test_unordered_parent_child_pool_is_topologically_validated(self):
        parent = self.coin_spend(0, 0)
        child = self.child(parent, 1_000)
        self.inject(child, parent)
        block = self.chain.make_block(self.key.script_pubkey)
        self.assertEqual(block.transactions[1:], (parent, child))
        self.assertTrue(self.chain.accept_block(block))

    def test_oversized_parent_excludes_child_but_not_unrelated_transaction(self):
        parent = self.coin_spend(0, 1_000_000, padding=999_800)
        child = self.child(parent, 100_000)
        ordinary = self.coin_spend(1, 1)
        self.assertLess(parent.weight(), MAX_BLOCK_WEIGHT)
        self.add(parent, child, ordinary)
        block = self.chain.make_block(self.key.script_pubkey)
        self.assertEqual(block.transactions[1:], (ordinary,))
        self.assertTrue(self.chain.accept_block(block))
        self.assertEqual(self.chain.mempool_transactions(), (parent, child))

    def test_rejected_child_package_does_not_exclude_fitting_parent(self):
        parent = self.coin_spend(0, 100_000, padding=3_000)
        child = self.child(parent, 1_000_000, padding=3_000)
        ordinary = self.coin_spend(1, 1)
        self.add(parent, child, ordinary)
        with patch('sumuww.chain.MAX_BLOCK_WEIGHT', 20_000):
            block = self.chain.make_block(self.key.script_pubkey)
            self.assertEqual(block.transactions[1:], (parent, ordinary))
            self.assertTrue(self.chain.accept_block(block))
        self.assertEqual(self.chain.mempool_transactions(), (child,))

    def test_invalid_signature_and_minted_value_cannot_buy_priority(self):
        for mode in ('signature', 'mint'):
            with self.subTest(mode=mode):
                valid = self.coin_spend(0, 100)
                value = valid.outputs[0].value - 1_000_000 if mode == 'signature' else self.coins[0][1].output.value + 1
                invalid = replace(valid, outputs=(TxOutput(value, self.key.script_pubkey),))
                child = self.child(invalid, 1_000)
                ordinary = self.coin_spend(1, 1)
                self.inject(invalid, child, ordinary)
                block = self.chain.make_block(self.key.script_pubkey)
                self.assertEqual(block.transactions[1:], (ordinary,))
                self.assertEqual(block.transactions[0].outputs[0].value, 50 * COIN + 1)
                self.chain.connection.execute('DELETE FROM mempool')

    def test_compactsize_count_transition_and_witness_coinbase_budget(self):
        parent = self.coin_spend(0, 0, outputs=tuple(TxOutput(1_000, self.key.script_pubkey) for _ in range(252)))
        children = tuple(self.child(parent, 0, index=index) for index in range(252))
        self.inject(parent, *children)
        fees = self.coins[0][1].output.value - 252_000
        coinbase = build_coinbase(105, self.key.script_pubkey, fees, 0, bytes(32), bytes(32))
        limit = (80 + len(encode_compact_size(252))) * 4
        limit += coinbase.weight() + parent.weight() + sum(tx.weight() for tx in children[:250])
        with patch('sumuww.chain.MAX_BLOCK_WEIGHT', limit):
            block = self.template()
        self.assertEqual(len(block.transactions), 252)
        self.assertEqual(block.transactions[1:], (parent,) + children[:250])
        self.assertEqual(block.weight(), limit)
        self.assertTrue(self.chain.accept_block(self.chain.make_block(self.key.script_pubkey, block.transactions[1:])))

    def test_pool_bound_and_each_transaction_is_validated_once(self):
        transactions = [self.coin_spend(0, 0)]
        for _ in range(1_000):
            transactions.append(self.child(transactions[-1], 0))
        self.inject(*transactions)
        with patch.object(self.chain, '_apply_transaction', wraps=self.chain._apply_transaction) as validate:
            block = self.template()
        self.assertEqual(validate.call_count, 1_000)
        self.assertEqual(block.transactions[1:], tuple(transactions[:1_000]))
        self.assertEqual(self.chain.info()['mempool'], 1_001)


if __name__ == '__main__':
    unittest.main()
