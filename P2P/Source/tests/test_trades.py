import copy,json,tempfile,time,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from smw_trade.orders import Store,order_id
from smw_trade.network import Relay,exchange
from smw_trade.trades import TradeBook
from smw_trade.app import Application
from smw_trade.settlement import run_round

ROOT=Path(__file__).resolve().parents[1]

class TradeBookTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
        self.maker=Store(self.path/'maker');self.taker=Store(self.path/'taker')
        self.book=TradeBook(self.taker)
    def reserve(self,side='sell'):
        order=self.maker.create(side,'12.34567890','0.00031234');oid=self.taker.import_order(order)
        request=self.taker.acceptance_request(oid);confirmation=self.maker.reserve(request)
        self.taker.import_event(confirmation);terms=self.book.remember(request,confirmation)
        return terms,request,confirmation
    def test_signed_terms_and_both_role_directions_survive_reopen(self):
        sell,_,_=self.reserve('sell');buy,_,_=self.reserve('buy')
        rows=TradeBook(Store(self.path/'taker')).listing()
        self.assertEqual({r['direction'] for r in rows},{'buy','sell'})
        self.assertTrue(all(r['can_execute'] for r in rows))
        self.assertEqual(self.book.terms(sell['session'])['smw_atoms'],1234567890)
        self.assertEqual(self.book.terms(buy['session'])['btc_sats'],31234)
    def test_unsigned_amount_change_or_wrong_confirmation_rejected(self):
        terms,request,confirmation=self.reserve()
        bad=copy.deepcopy(request);bad['body']['nonce']='ab'*16
        with self.assertRaises(Exception):self.book.remember(bad,confirmation)
        bad=self.maker.identity.sign({**confirmation['body'],'session':'cd'*32})
        with self.assertRaises(ValueError):self.book.remember(request,bad)
        with self.taker.connect() as c:
            original=c.execute('SELECT packet FROM orders WHERE id=?',(terms['order_id'],)).fetchone()[0]
            packet=json.loads(original);packet['body']['smw_atoms']+=1
            c.execute('UPDATE orders SET packet=? WHERE id=?',(json.dumps(packet),terms['order_id']))
        with self.assertRaises(Exception):self.book.terms(terms['session'])
    def test_only_taker_can_start_and_cannot_start_unknown_order(self):
        terms,_,_=self.reserve()
        with self.assertRaises(ValueError):TradeBook(self.maker).start(terms['session'],'success')
        with self.assertRaises(ValueError):self.book.start('00'*32,'success')
        self.book.start(terms['session'],'success')
    def test_concurrent_start_exactly_once(self):
        terms,_,_=self.reserve()
        def run(_):
            try:self.book.start(terms['session'],'success');return True
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=12) as pool:self.assertEqual(sum(pool.map(run,range(12))),1)
    def test_restart_never_repeats_funding_or_discards_refund_plan(self):
        terms,_,_=self.reserve();session=terms['session'];self.book.start(session,'refund')
        self.book.update(session,'SMW_LOCK_CONFIRMED',{'smw_refund_raw':'signed-refund-test-evidence'})
        reopened=TradeBook(Store(self.path/'taker'));reopened.mark_interrupted()
        row=reopened.listing()[0]
        self.assertEqual(row['state'],'INTERRUPTED')
        self.assertEqual(row['evidence']['smw_refund_raw'],'signed-refund-test-evidence')
        self.assertEqual(row['evidence']['last_phase'],'SMW_LOCK_CONFIRMED')
        with self.assertRaises(ValueError):reopened.start(session,'success')
    def test_result_cannot_change_signed_amount_and_terminal_state(self):
        terms,_,_=self.reserve();session=terms['session'];self.book.start(session,'success')
        with self.assertRaises(ValueError):self.book.update(session,'COMPLETED',{'smw_atoms':1})
        self.assertEqual(self.book.listing()[0]['state'],'STARTING')
        self.book.update(session,'COMPLETED',{'passed':True})
        with self.assertRaises(ValueError):self.book.update(session,'FAILED',{})
        with self.assertRaises(ValueError):self.book.start(session,'refund')
    def test_peer_cannot_write_local_execution_or_send_wallet_commands(self):
        terms,_,_=self.reserve();relay=Relay(self.taker).start();self.addCleanup(relay.close)
        for kind in ('execute','completed','wallet','checkpoint'):
            with self.assertRaises(ValueError):exchange(relay.address,{'protocol':'smw-trade-regtest-1','type':kind,'session':terms['session']})
        self.assertEqual(self.book.listing()[0]['state'],'RESERVED')
    def test_tcp_acceptance_records_signed_agreement_in_both_stores(self):
        packet=self.maker.create('sell','3','0.00001234');oid=order_id(packet['body'])
        maker=Relay(self.maker).start();taker=Relay(self.taker).start()
        self.addCleanup(maker.close);self.addCleanup(taker.close)
        taker.connect(*maker.address);confirmation=taker.accept(maker.address,oid)
        sid=confirmation['body']['session']
        self.assertEqual(self.book.terms(sid),TradeBook(self.maker).terms(sid))

class OrderedExecutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
        self.maker=Application(ROOT,self.path/'maker');self.taker=Application(ROOT,self.path/'taker')
        self.addCleanup(self.maker.close);self.addCleanup(self.taker.close)
    def reserve(self,side,smw,btc):
        order=self.maker.command('order',{'side':side,'smw':smw,'btc':btc})['order']
        self.taker.command('connect',{'port':self.maker.relay.address[1]})
        result=self.taker.command('reserve',{'id':order_id(order['body'])})
        return result['confirmation']['body']['session']
    def finish(self):
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            state=self.taker.state()
            if not state['job']['running']:
                self.assertTrue(state['job'].get('passed'),state['job']);return state
            time.sleep(.1)
        self.fail('Order-bound real chain execution did not finish')
    def test_reserved_buy_order_multiple_inputs_exact_smw_and_btc(self):
        sid=self.reserve('buy','100.12345678','0.00031234')
        with self.assertRaises(ValueError):self.taker.command('execute',{'session':sid,'mode':'success','smw_atoms':1})
        self.taker.command('execute',{'session':sid,'mode':'success'});state=self.finish()
        result=state['job']['result'];self.assertEqual(result['smw_received_atoms'],10012345678)
        self.assertEqual(result['btc_received_sats'],31234)
        self.assertEqual(result['session'],sid);self.assertEqual(result['order_side'],'buy')
        self.assertEqual(state['trades'][0]['direction'],'sell')
        self.assertEqual(state['trades'][0]['state'],'COMPLETED')
        self.assertTrue(result['local_simulated_counterparty']);self.assertFalse(result['public_funds'])
        for k in ('smw_lock_address','btc_lock_address','smw_claim','btc_claim'):self.assertTrue(result[k])
        with self.assertRaises(ValueError):self.taker.command('execute',{'session':sid,'mode':'success'})
        self.taker.close();self.taker=Application(ROOT,self.path/'taker');self.addCleanup(self.taker.close)
        self.assertEqual(self.taker.state()['trades'][0]['state'],'COMPLETED')
    def test_reserved_sell_refund_exact_amounts_and_bitcoin_restart(self):
        sid=self.reserve('sell','0.12345678','0.00004321')
        self.taker.command('execute',{'session':sid,'mode':'refund'});state=self.finish()
        result=state['job']['result'];self.assertEqual(result['smw_refunded_atoms'],12345678)
        self.assertEqual(result['btc_refunded_sats'],4321)
        self.assertTrue(result['bitcoin_node_restarted']);self.assertTrue(result['smw_chain_and_journal_reopened'])
        self.assertEqual(state['trades'][0]['state'],'REFUNDED')
        self.assertEqual(self.maker.state()['trades'][0]['state'],'RESERVED') # No unverified remote settlement assertion.
    def test_dust_failure_recorded_without_funding_or_retry(self):
        sid=self.reserve('sell','1','0.00000001')
        self.taker.command('execute',{'session':sid,'mode':'success'})
        deadline=time.monotonic()+10
        while self.taker.state()['job']['running'] and time.monotonic()<deadline:time.sleep(.05)
        row=self.taker.state()['trades'][0];self.assertEqual(row['state'],'FAILED')
        self.assertNotIn('smw_funding',row['evidence'])
        self.assertIn('294',row['evidence']['error'])
        with self.assertRaises(ValueError):self.taker.command('execute',{'session':sid,'mode':'success'})
    def test_insufficient_disposable_balance_fails_before_htlc_lock(self):
        with self.assertRaisesRegex(ValueError,'insufficient mature balance'):
            run_round(self.path/'insufficient',ROOT/'tools/bitcoin-31.1/bin/bitcoind.exe',smw_atoms=201*100000000)
        self.assertFalse((self.path/'insufficient/bitcoin').exists())
    def test_second_process_cannot_reinterpret_active_directory_as_interrupted(self):
        from smw_trade.instance import AlreadyRunning
        with self.assertRaises(AlreadyRunning):Application(ROOT,self.path/'taker')
        self.taker.close();self.taker=Application(ROOT,self.path/'taker');self.addCleanup(self.taker.close)
    def test_journal_failure_does_not_leave_job_running(self):
        from unittest.mock import patch
        with patch.object(self.taker.store,'checkpoint',side_effect=OSError('Injected disk failure')):
            self.taker.command('check',{'mode':'success'})
            deadline=time.monotonic()+10
            while self.taker.state()['job']['running'] and time.monotonic()<deadline:time.sleep(.05)
            self.assertFalse(self.taker.state()['job']['running'])
            self.assertFalse(self.taker.state()['job']['passed'])
        self.assertFalse((self.path/'taker/checks').exists())
