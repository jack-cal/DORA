"""Block-template budgets differ from the mempool's local byte limit."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sumuww.block import MAX_BLOCK_WEIGHT
from sumuww.chain import Chain
from sumuww.errors import ValidationError
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


class MiningResourceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix='sumuww-mining-resources-')
        self.key = RegtestKey.from_int(1)
        self.chain = Chain(Path(self.directory.name) / 'chain.sqlite')
        self.chain.mine(self.key.script_pubkey, 101)
        self.coins = [(outpoint, coin) for outpoint, coin in self.chain.list_utxos(self.key.script_pubkey) if coin.height in (1, 2)]

    def tearDown(self):
        self.chain.close()
        self.directory.cleanup()

    def transaction(self, outpoint, spent_output, burn_script, fee=10_000):
        unsigned = Transaction(2, (TxInput(*outpoint),), (
            TxOutput(0, burn_script),
            TxOutput(spent_output.value - fee, self.key.script_pubkey),
        ))
        return sign_p2wpkh(unsigned, 0, spent_output, self.key)

    def large_pool(self):
        transactions = []
        for outpoint, coin in self.coins:
            transaction = self.transaction(outpoint, coin.output, b'\x6a' + bytes(600_000))
            self.chain.submit_transaction(transaction)
            transactions.append(transaction)
        return transactions

    def test_weight_budget_mines_one_and_retains_remaining_transaction(self):
        transactions = self.large_pool()
        self.assertLess(sum(len(tx.serialize()) for tx in transactions), MAX_BLOCK_WEIGHT)
        self.assertGreater(sum(tx.weight() for tx in transactions), MAX_BLOCK_WEIGHT)
        template = self.chain.make_block(self.key.script_pubkey)
        self.assertEqual(template.transactions[1:], (transactions[0],))
        self.assertLessEqual(template.weight(), MAX_BLOCK_WEIGHT)
        self.assertTrue(self.chain.accept_block(template))
        self.assertEqual(self.chain.mempool_transactions(), (transactions[1],))
        self.chain.mine(self.key.script_pubkey, 1)
        self.assertEqual(self.chain.mempool_transactions(), ())

    def test_explicit_transactions_exceeding_weight_raise(self):
        transactions = self.large_pool()
        with self.assertRaisesRegex(ValidationError, 'template weight'):
            self.chain.make_block(self.key.script_pubkey, transactions=transactions)
        self.assertEqual(self.chain.mempool_transactions(), tuple(transactions))

    def test_excluded_parent_and_child_remain_then_mine_together(self):
        transactions = self.large_pool()
        parent = transactions[1]
        # A zero-fee child cannot raise its parent's package rate above the
        # first transaction, preserving this excluded-parent resource fixture.
        child = self.transaction((parent.txid(), 1), parent.outputs[1], b'\x6a', fee=0)
        self.chain.submit_transaction(child)
        first = self.chain.mine(self.key.script_pubkey, 1)[0]
        self.assertEqual(first.transactions[1:], (transactions[0],))
        self.assertEqual(self.chain.mempool_transactions(), (parent, child))
        second = self.chain.mine(self.key.script_pubkey, 1)[0]
        self.assertEqual(second.transactions[1:], (parent, child))
        self.assertEqual(self.chain.mempool_transactions(), ())

    def test_sigops_budget_and_explicit_overflow(self):
        transactions = []
        for outpoint, coin in self.coins:
            transaction = self.transaction(outpoint, coin.output, b'\x6a' + b'\xac' * 12_000)
            self.chain.submit_transaction(transaction)
            transactions.append(transaction)
        self.assertLess(sum(tx.weight() for tx in transactions), MAX_BLOCK_WEIGHT)
        with self.assertRaisesRegex(ValidationError, 'template sigops'):
            self.chain.make_block(self.key.script_pubkey, transactions=transactions)
        template = self.chain.make_block(self.key.script_pubkey)
        self.assertEqual(template.transactions[1:], (transactions[0],))
        self.assertTrue(self.chain.accept_block(template))
        self.assertEqual(self.chain.mempool_transactions(), (transactions[1],))


if __name__ == '__main__':
    unittest.main()
