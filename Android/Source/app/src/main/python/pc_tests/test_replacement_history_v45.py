"""Wallet-scoped RBF history on disposable chains, including restart and rollback."""
from unittest import TestCase
from unittest.mock import patch
from dataclasses import replace
from sumuww.chain import Chain
from sumuww.wallet_history import WalletHistory
from sumuww.wallet import RegtestKey, sign_p2wpkh
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.primitives import hash_to_display
from tests import test_fee_policy_v43 as support
KEY, NOW = support.KEY, support.NOW

class ReplacementHistoryTests(TestCase):
    setUpClass = classmethod(support.FeePolicyTests.setUpClass.__func__)
    tearDownClass = classmethod(support.FeePolicyTests.tearDownClass.__func__)
    setUp = support.FeePolicyTests.setUp
    spend = support.FeePolicyTests.spend

    def rows(self, history=None):
        return {r['txid']: r for r in (history or WalletHistory(KEY.script_pubkey)).page(self.chain)['transactions']}

    def test_replacement_and_descendant_are_retained_without_changing_balance(self):
        original = self.spend(); child = self.spend(previous=original)
        self.chain.submit_transaction(original); self.chain.submit_transaction(child)
        history = WalletHistory(KEY.script_pubkey)
        history.recent(self.chain)
        replacement = self.spend(fee=4000)
        self.chain.submit_transaction(replacement)
        before = self.chain.state_commitment()
        rows = self.rows(history)
        self.assertEqual('conflict', rows[hash_to_display(original.txid())]['replacement_reason'])
        self.assertEqual('ancestor_replaced', rows[hash_to_display(child.txid())]['replacement_reason'])
        self.assertEqual(-1000, rows[hash_to_display(child.txid())]['net_amount'])
        self.assertEqual('pending', rows[hash_to_display(replacement.txid())]['status'])
        self.assertEqual(before, self.chain.state_commitment())
        self.assertEqual(2, sum(r['status'] == 'replaced' for r in rows.values()))

    def test_restart_and_wallet_not_open_during_replacement(self):
        recipient = RegtestKey.from_int(45123)
        original = Transaction(2, (TxInput(self.funding.txid(), 0),),
                               (TxOutput(self.funding.outputs[0].value-1000, recipient.script_pubkey),))
        original = sign_p2wpkh(original, 0, self.funding.outputs[0], KEY)
        self.chain.submit_transaction(original); self.chain.submit_transaction(self.spend(fee=4000))
        with Chain(self.path, clock=lambda: NOW) as reopened:
            rows = WalletHistory(recipient.script_pubkey).page(reopened)['transactions']
            self.assertEqual(1, len(rows)); self.assertEqual('replaced', rows[0]['status'])
            self.assertEqual(original.outputs[0].value, rows[0]['net_amount'])
            self.assertEqual([], WalletHistory(RegtestKey.from_int(45124).script_pubkey).recent(reopened))

    def test_active_chain_and_return_to_pool_override_old_record(self):
        original = self.spend(); self.chain.submit_transaction(original)
        history = WalletHistory(KEY.script_pubkey); history.recent(self.chain)
        self.chain.submit_transaction(self.spend(fee=4000))
        block = self.chain.make_block(KEY.script_pubkey, transactions=(original,))
        self.chain.accept_block(block)
        row = self.rows(history)[hash_to_display(original.txid())]
        self.assertEqual('confirmed', row['status']); self.assertEqual(1, row['confirmations'])
        # Rebuild history against a competing branch: the confirmed result must not stick.
        parent = block.header.previous_hash
        for _ in range(2):
            alternative = self.chain.make_block(KEY.script_pubkey, parent_hash=parent, transactions=())
            self.chain.accept_block(alternative); parent = alternative.block_hash()
        row = self.rows(history).get(hash_to_display(original.txid()))
        self.assertIsNotNone(row); self.assertNotEqual('confirmed', row['status'])

    def test_preflight_invalid_replacement_and_sql_failure_leave_records_unchanged(self):
        original = self.spend(); self.chain.submit_transaction(original)
        replacement = self.spend(fee=4000)
        self.assertTrue(self.chain.test_mempool_accept(replacement)['allowed'])
        self.assertEqual(0, self.chain.connection.execute('SELECT count(*) FROM mempool_replacement_effects').fetchone()[0])
        forged = replace(replacement, outputs=(replace(replacement.outputs[0], value=1),))
        self.assertFalse(self.chain.test_mempool_accept(forged)['allowed'])
        self.chain.connection.execute("CREATE TEMP TRIGGER fail_history BEFORE INSERT ON mempool_replacement_effects BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(Exception): self.chain.submit_transaction(replacement)
        self.assertEqual((original,), self.chain.mempool_transactions())
        self.assertEqual(0, self.chain.connection.execute('SELECT count(*) FROM mempool_replacements').fetchone()[0])

    def test_public_history_budget_and_other_writer_invalidate_cache(self):
        original = self.spend(); self.chain.submit_transaction(original)
        history = WalletHistory(KEY.script_pubkey); history.recent(self.chain)
        with Chain(self.path, clock=lambda: NOW) as other:
            other.submit_transaction(self.spend(fee=4000))
        self.assertEqual('replaced', self.rows(history)[hash_to_display(original.txid())]['status'])
        with patch('sumuww.mempool_policy.MAX_REPLACEMENT_EFFECT_BYTES', 1):
            self.chain.submit_transaction(self.spend(fee=8000))
        self.assertEqual(0, self.chain.connection.execute('SELECT coalesce(sum(length(effects)),0) FROM mempool_replacement_effects').fetchone()[0])
        self.assertEqual('replaced', self.chain.transaction_status(original.txid())['status'])
