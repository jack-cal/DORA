"""Exact, expiring payment quotes; all chain and wallet fixtures are temporary."""

from concurrent.futures import Future
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from coincurve import PrivateKey

from sumuww.__main__ import create_payment
from sumuww.app_service import AppService, PAYMENT_QUOTE_TTL
from sumuww.chain import Chain
from sumuww.keystore import WalletKey
from sumuww.primitives import COIN, hash_to_display
from sumuww.profiles import REGTEST
from sumuww.fees import estimate_payment_fee
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import sign_p2wpkh


ALICE = WalletKey(PrivateKey((1).to_bytes(32, 'big')), REGTEST)
BOB = WalletKey(PrivateKey((2).to_bytes(32, 'big')), REGTEST)


class PaymentQuoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-payment-quote-')
        self.directory = Path(self.temp.name)
        self.database = self.directory / 'node.sqlite'
        with Chain(self.database, network=REGTEST) as chain:
            for _ in range(100):
                chain.accept_block(chain.make_block(ALICE.script_pubkey))
        self.service = AppService(self.directory, network=REGTEST, peers=[])
        self.service.start().result(timeout=10)
        with patch('sumuww.app_service.keystore_create', return_value=ALICE):
            self.service.create_wallet('fixture.json', 'test only').result(timeout=5)

    def tearDown(self):
        self.service.stop().result(timeout=15)
        self.temp.cleanup()

    def prepare(self, fee=None):
        return self.service.prepare_payment(BOB.address, '1', fee).result(timeout=5)

    def submit(self, quote):
        return self.service.submit_payment(quote['quote_id']).result(timeout=5)

    def test_auto_initial_quote_and_submission_use_exact_fee(self):
        quote = self.prepare()
        self.assertEqual('1.00000000', quote['amount_smw'])
        self.assertEqual('0.00000141', quote['fee_smw'])
        self.assertEqual('1.00000141', quote['total_smw'])
        self.assertEqual('live_mempool', quote['source'])
        self.assertNotIn('transaction', quote)
        self.assertNotIn('key', quote)
        self.assertNotIn('hex', json.dumps(quote))
        result = self.submit(quote)
        self.assertEqual(quote['fee_smw'], result['fee_smw'])
        with Chain(self.database, network=REGTEST) as chain:
            transaction, = chain.mempool_transactions()
            self.assertEqual(141, 50 * COIN - sum(o.value for o in transaction.outputs))
            self.assertEqual(result['txid'], hash_to_display(transaction.txid()))
        with self.assertRaisesRegex(Exception, 'no longer valid'):
            self.submit(quote)

    def test_explicit_zero_fee_and_legacy_send_are_preserved(self):
        quote = self.prepare('0')
        self.assertEqual(('0.00000000', '1.00000000', 'manual'),
                         (quote['fee_smw'], quote['total_smw'], quote['source']))
        self.assertEqual('0.00000000', self.submit(quote)['fee_smw'])
        # A second mature coin becomes available for a distinct legacy send.
        with Chain(self.database, network=REGTEST) as chain:
            chain.accept_block(chain.make_block(ALICE.script_pubkey))
        result = self.service.send(BOB.address, '2', '0.002').result(timeout=5)
        self.assertEqual('0.00200000', result['fee_smw'])

    def test_no_estimation_or_resigning_after_confirmation(self):
        estimate = {'fee_units': 12345, 'estimated_vsize': 141,
                    'source': 'live_mempool', 'capped': False}
        with patch('sumuww.app_service.estimate_payment_fee', return_value=estimate) as estimator:
            quote = self.prepare()
        with patch('sumuww.app_service.estimate_payment_fee', side_effect=AssertionError('recalculated')), \
                patch('sumuww.app_service.create_payment', side_effect=AssertionError('resigned')):
            result = self.submit(quote)
        estimator.assert_called_once()
        self.assertEqual('0.00012345', result['fee_smw'])
        self.assertEqual('1.00012345', quote['total_smw'])

    def test_expiry_rejects_original_transaction_and_releases_quote(self):
        with patch('sumuww.app_service._quote_clock', return_value=10):
            quote = self.prepare()
        with patch('sumuww.app_service._quote_clock', return_value=10 + PAYMENT_QUOTE_TTL):
            with self.assertRaisesRegex(Exception, 'expired'):
                self.submit(quote)
        with Chain(self.database, network=REGTEST) as chain:
            self.assertFalse(chain.mempool_transactions())

    def test_lock_open_and_network_change_invalidate_quotes(self):
        quote = self.prepare()
        self.service.lock_wallet().result(timeout=5)
        with self.assertRaisesRegex(Exception, 'no longer valid'):
            self.submit(quote)
        with patch('sumuww.app_service.keystore_load', return_value=ALICE):
            self.service.open_wallet('fixture.json', 'test only').result(timeout=5)
            quote = self.prepare()
            self.service.open_wallet('fixture.json', 'test only').result(timeout=5)
        with self.assertRaisesRegex(Exception, 'no longer valid'):
            self.submit(quote)
        quote = self.prepare()
        self.service.configure_network('127.0.0.1:0', [], allow_lan=True).result(timeout=10)
        with self.assertRaisesRegex(Exception, 'no longer valid'):
            self.submit(quote)

    def test_replaced_quote_and_wrong_identifier_cannot_submit(self):
        first = self.prepare()
        second = self.prepare()
        self.assertNotEqual(first['quote_id'], second['quote_id'])
        with self.assertRaisesRegex(Exception, 'no longer valid'):
            self.submit(first)
        # An incorrect identifier consumes the outstanding confirmation too.
        with self.assertRaisesRegex(Exception, 'no longer valid'):
            self.submit(second)

    def test_current_pending_spend_validation_rejects_prepared_transaction(self):
        quote = self.prepare()
        with Chain(self.database, network=REGTEST) as chain:
            competing = create_payment(chain, ALICE, BOB.script_pubkey, 2 * COIN, 0)
            chain.submit_transaction(competing)
        with self.assertRaises(Exception):
            self.submit(quote)
        with Chain(self.database, network=REGTEST) as chain:
            self.assertEqual([competing.txid()], [tx.txid() for tx in chain.mempool_transactions()])

    def test_reorg_that_removes_confirmed_input_rejects_quote(self):
        quote = self.prepare()
        with Chain(self.database, network=REGTEST) as chain:
            parent = chain.network.genesis.block_hash()
            for _ in range(101):
                block = chain.make_block(BOB.script_pubkey, parent_hash=parent)
                chain.accept_block(block)
                parent = block.block_hash()
            self.assertFalse(chain.list_utxos(ALICE.script_pubkey))
        with self.assertRaises(Exception):
            self.submit(quote)
        with Chain(self.database, network=REGTEST) as chain:
            self.assertFalse(chain.mempool_transactions())

    def test_local_fee_rate_changes_after_quote_keep_original_signed_fee(self):
        with Chain(self.database, network=REGTEST) as chain:
            chain.accept_block(chain.make_block(ALICE.script_pubkey))
        quote = self.prepare()
        with Chain(self.database, network=REGTEST) as chain:
            outpoint, coin = next((outpoint, coin) for outpoint, coin in chain.list_utxos(ALICE.script_pubkey)
                                  if coin.height == 2)
            transaction = Transaction(2, (TxInput(*outpoint),),
                                      (TxOutput(coin.output.value - 1_000_000, BOB.script_pubkey),))
            transaction = sign_p2wpkh(transaction, 0, coin.output, ALICE)
            chain.submit_transaction(transaction)
            changed = estimate_payment_fee(chain, ALICE.script_pubkey, BOB.script_pubkey, COIN)
            self.assertEqual('live_mempool', changed['source'])
            self.assertNotEqual(100_000, changed['fee_units'])
        self.assertEqual('0.00000141', self.submit(quote)['fee_smw'])


class PaymentQuoteUiTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from sumuww.app import SumuwwApp
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-payment-ui-')
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.temp.cleanup()
            self.skipTest(str(error))
        self.root.withdraw()
        self.prepare_calls, self.submit_calls = [], []
        self.prepare_future, self.submit_future = Future(), Future()
        self.status = {'node': {'height': 100, 'peers': 0},
                       'wallet': {'address': ALICE.address, 'path': 'fixture.json', 'unlocked': True}}
        def done(value):
            future = Future()
            future.set_result(value)
            return future
        self.service = SimpleNamespace(
            directory=Path(self.temp.name), network=REGTEST,
            start=lambda: done(self.status), status=lambda: done(self.status),
            prepare_payment=lambda *args: (self.prepare_calls.append(args) or self.prepare_future),
            submit_payment=lambda quote_id: (self.submit_calls.append(quote_id) or self.submit_future))
        self.app = SumuwwApp(self.root, self.service, language='en', language_path=Path(self.temp.name) / 'language.json')
        self.app._started = True
        self.app._apply_status(self.status)
        self.app.send_address.set(BOB.address)
        self.app.send_amount.set('1')
        self.quote = {'quote_id': 'a' * 32, 'amount_smw': '1.00000000',
                      'fee_smw': '0.00234567', 'total_smw': '1.00234567',
                      'estimated_vsize': 141, 'source': 'live_mempool', 'capped': False}

    def tearDown(self):
        self.app._finish_close()
        self.temp.cleanup()

    def test_automatic_default_confirms_exact_total_then_submits_same_quote(self):
        self.assertFalse(self.app.manual_fee.get())
        self.assertEqual('readonly', str(self.app.fee_entry.cget('state')))
        self.app._send()
        self.assertTrue(self.app._busy)
        self.assertEqual([(BOB.address, '1', 'auto:normal')], self.prepare_calls)
        self.assertFalse(self.submit_calls)
        self.assertEqual('disabled', str(self.app.amount_entry.cget('state')))
        with patch('sumuww.app.messagebox.askyesno', return_value=True) as confirmation:
            self.prepare_future.set_result(self.quote)
            self.app._pump()
        self.assertIn('Total debit: 1.00234567 SMW', str(confirmation.call_args.args[1]))
        self.assertEqual([self.quote['quote_id']], self.submit_calls)
        self.assertTrue(self.app._busy)
        self.submit_future.set_result({'txid': 'b' * 64, 'fee_smw': '0.00234567'})
        self.app._pump()
        self.assertFalse(self.app._busy)
        self.assertEqual('', self.app.send_amount.get())

    def test_manual_rate_cancel_and_language_switch_preserve_inputs(self):
        self.app.manual_fee.set(True)
        self.app.send_fee.set('1')
        self.app._sync_controls()
        self.assertEqual('normal', str(self.app.fee_entry.cget('state')))
        for language in ('ko', 'ar', 'hi', 'en'):
            self.assertTrue(self.app.set_language(language))
            self.assertTrue(self.app.manual_fee.get())
            self.assertEqual('1', self.app.send_fee.get())
            self.assertEqual(BOB.address, self.app.send_address.get())
        self.app._send()
        self.assertEqual([(BOB.address, '1', 'rate:1')], self.prepare_calls)
        manual_quote = dict(self.quote, fee_smw='0.00000141', total_smw='1.00000141', source='manual_rate')
        with patch('sumuww.app.messagebox.askyesno', return_value=False):
            self.prepare_future.set_result(manual_quote)
            self.app._pump()
        self.assertFalse(self.submit_calls)
        self.assertFalse(self.app._busy)
        self.assertEqual('1', self.app.send_amount.get())
        self.assertEqual(BOB.address, self.app.send_address.get())

    def test_capped_quote_is_explicit_in_confirmation(self):
        self.app._send()
        with patch('sumuww.app.messagebox.askyesno', return_value=False) as confirmation:
            self.prepare_future.set_result(dict(self.quote, capped=True))
            self.app._pump()
        self.assertIn('automatic fee cap', str(confirmation.call_args.args[1]))
        self.assertFalse(self.submit_calls)


if __name__ == '__main__':
    unittest.main()
