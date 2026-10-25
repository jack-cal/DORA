"""Current congestion, cache invalidation and unsigned live status coverage."""
from fractions import Fraction
from unittest.mock import patch
import unittest
from sumuww.fees import _queue_rate, _pending_book, fee_overview, estimate_fee, MAX_AUTO_FEE_UNITS
from tests.test_fee_estimation import FeeEstimationTests
from tests.test_app_fees import PaymentQuoteTests, PaymentQuoteUiTests
from sumuww.__main__ import create_payment
from sumuww.primitives import COIN
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import sign_p2wpkh
from sumuww.chain import Chain


class QueueBudgetTests(unittest.TestCase):
    def book(self, count, price=10):
        return {'packages':tuple((Fraction(price),500,4) for _ in range(count)),
                'block_vsize_capacity':1000,'block_sigops_capacity':80_000}

    def test_quiet_network_keeps_all_three_rates_at_floor(self):
        for mode in ('slow','normal','fast'):
            self.assertEqual(1,_queue_rate(self.book(1,10000),Fraction(1),mode,140))

    def test_backlog_targets_raise_only_competing_budgets(self):
        book=self.book(7)
        self.assertEqual(Fraction('10.001'),_queue_rate(book,Fraction(1),'fast',140))
        self.assertEqual(Fraction('10.001'),_queue_rate(book,Fraction(1),'normal',140))
        self.assertEqual(1,_queue_rate(book,Fraction(1),'slow',140))

    def test_weighted_volume_not_number_of_price_samples(self):
        book=self.book(0);book['packages']=((Fraction(100),10,4),(Fraction(5),2000,4))
        self.assertEqual(Fraction('5.001'),_queue_rate(book,Fraction(1),'fast',140))

    def test_candidate_size_and_sigops_pressure_are_accounted_for(self):
        self.assertEqual(1,_queue_rate(self.book(1),Fraction(1),'fast',400))
        self.assertEqual(Fraction('10.001'),_queue_rate(self.book(1),Fraction(1),'fast',501))
        book=self.book(0);book['packages']=((Fraction(7),140,79999),)
        self.assertEqual(Fraction('7.001'),_queue_rate(book,Fraction(1),'fast',140))


class LiveChainTests(FeeEstimationTests):
    def test_signed_large_backlog_raises_then_mining_clears_live_recommendation(self):
        # Five valid ~248 kB transactions exceed a one-block size budget.
        for _ in range(5):
            pending={i.outpoint() for tx in self.chain.mempool_transactions() for i in tx.inputs}
            point,coin=next((p,c) for p,c in self.chain.list_utxos(self.alice.script_pubkey)
                if c.height <= 5 and TxInput(*p).outpoint() not in pending)
            outputs=(TxOutput(1,self.bob.script_pubkey),)*8000
            fee=5_000_000
            outputs+=(TxOutput(coin.output.value-fee-8000,self.alice.script_pubkey),)
            tx=sign_p2wpkh(Transaction(2,(TxInput(*point),),outputs),0,coin.output,self.alice)
            self.chain.submit_transaction(tx)
        preview=fee_overview(self.chain)
        self.assertGreater(preview['pending_vsize'],preview['block_vsize_capacity'])
        self.assertGreater(Fraction(preview['rates']['fast']),1)
        self.assertEqual('1',preview['rates']['normal'])
        self.chain.mine(self.alice.script_pubkey,2)
        self.assertEqual({'fast':'1','normal':'1','slow':'1'},fee_overview(self.chain)['rates'])

    def test_preview_does_not_sign_and_external_writes_invalidate_cache(self):
        first=fee_overview(self.chain)
        with Chain(self.chain.database) as other:
            tx=create_payment(other,self.alice,self.bob.script_pubkey,COIN,1000)
            other.submit_transaction(tx)
        with patch('sumuww.__main__.create_payment',side_effect=AssertionError('signed')):
            second=fee_overview(self.chain)
        self.assertEqual(0,first['pending_count']);self.assertEqual(1,second['pending_count'])

    def test_parent_child_packages_count_parent_once(self):
        tx=create_payment(self.chain,self.alice,self.bob.script_pubkey,COIN,140)
        self.chain.submit_transaction(tx)
        output=tx.outputs[0]
        child=sign_p2wpkh(Transaction(2,(TxInput(tx.txid(),0),),(TxOutput(output.value-10000,self.alice.script_pubkey),)),0,output,self.bob)
        self.chain.submit_transaction(child)
        book=_pending_book(self.chain)
        self.assertEqual(1,len(book['packages']))
        price,size,_=book['packages'][0]
        self.assertEqual(10140,price*size)

    def test_auto_cap_preserved_under_real_capacity_pressure(self):
        with patch('sumuww.fees._suggestion',return_value=(Fraction(1_000_000),'live_mempool',1000)):
            result=estimate_fee(self.chain,140,'fast')
        self.assertTrue(result['capped']);self.assertEqual(MAX_AUTO_FEE_UNITS,result['fee_units'])

    def test_observed_growth_is_diagnostic_and_resets_after_gap(self):
        with patch('sumuww.fees.time.monotonic',return_value=10):first=fee_overview(self.chain)
        self.chain.submit_transaction(create_payment(self.chain,self.alice,self.bob.script_pubkey,COIN,1000))
        with patch('sumuww.fees.time.monotonic',return_value=15):second=fee_overview(self.chain)
        self.assertIsNone(first['backlog_change_vb_per_second'])
        self.assertGreater(second['backlog_change_vb_per_second'],0)
        self.assertEqual('1',second['rates']['fast'])
        with patch('sumuww.fees.time.monotonic',return_value=100):stale=fee_overview(self.chain)
        self.assertIsNone(stale['backlog_change_vb_per_second'])


class LiveServiceTests(PaymentQuoteTests):
    def test_readonly_status_cannot_invalidate_or_resign_confirmation(self):
        quote=self.prepare()
        with patch('sumuww.app_service.create_payment',side_effect=AssertionError('signed')):
            for _ in range(3):status=self.service.status().result(timeout=5)
            result=self.submit(quote)
        self.assertIn('rates',status['fees'])
        self.assertEqual(quote['fee_smw'],result['fee_smw'])


class LiveUiTests(PaymentQuoteUiTests):
    def test_automatic_preview_refresh_preserves_manual_and_frozen_confirmation(self):
        state=dict(self.status,fees={'pending_vsize':2000000,'rates':{'slow':'1','normal':'3','fast':'5'},'target_blocks':{'slow':6,'normal':3,'fast':1}})
        self.app._apply_status(state)
        self.assertEqual('3',self.app.send_fee.get())
        self.app.fee_preset.current(2);self.app._sync_controls()
        self.assertEqual('5',self.app.send_fee.get())
        self.app.manual_fee.set(True);self.app.send_fee.set('7.5')
        self.app._apply_status(state)
        self.assertEqual('7.5',self.app.send_fee.get())
        self.app.manual_fee.set(False);self.app._busy=True
        self.app._apply_status(state)
        self.assertEqual('7.5',self.app.send_fee.get())
