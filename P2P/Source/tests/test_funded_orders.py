"""Real disposable chain deposits and application/UI entry points."""
import gc,json,time,tkinter as tk,unittest
from unittest.mock import patch
import test_market
from test_market import ROOT,PASSWORD
from smw_trade.market.application import MarketApplication
from smw_trade.market.desktop import MarketDesktop


class FundedOrders(unittest.TestCase):
    setUp=test_market.BitcoinTradeTests.setUp
    tearDown=test_market.BitcoinTradeTests.tearDown

    def test_funded_trade_through_shared_peer_without_counterparty_ip(self):
        relay=MarketApplication(ROOT,self.path/'relay','test')
        try:
            for app in (self.a,self.b):
                for session in list(app.relay.sessions.values()):session.close()
                app.relay.peers.clear()
            for app in (self.a,self.b):app.connect(*relay.relay.address)
            post=self.a.create(side='sell',coin='BTC',quantity='1',price='0.1')
            relay.relay.pull(relay.relay.sessions[self.a.store.identity.public])
            self.b.sync()
            sid=self.b.reserve(post['id'])
            self.assertTrue(self.a.engine._load(sid)[1]['remote'])
            self.assertTrue(self.b.engine._load(sid)[1]['remote'])
            self.assertNotIn(self.a.store.identity.public,self.b.relay.sessions)
            self.assertNotIn(self.b.store.identity.public,self.a.relay.sessions)
            self.a.sync_trade(sid)  # The seller also learns the buyer's reverse route.
            for app,coin in ((self.a,'SMW'),(self.b,'BTC')):
                test_market.BitcoinTradeTests.send(self,app,sid,'lock',coin);app.sync_trade(sid)
            test_market.BitcoinTradeTests.send(self,self.a,sid,'claim','BTC')
            test_market.BitcoinTradeTests.send(self,self.b,sid,'claim','SMW')
            self.assertEqual(self.a.engine.status(sid)['state'],'completed')
            self.assertEqual(self.b.engine.status(sid)['state'],'completed')
        finally:relay.close()

    def test_wallet_deposit_fee_and_duplicate_allocation(self):
        empty=MarketApplication(ROOT,self.path/'empty','test')
        try:
            with self.assertRaisesRegex(ValueError,'Create a trading wallet'):
                empty.create(side='sell',coin='BTC',quantity='1',price='1')
        finally:empty.close()
        self.a.vault.lock()
        with self.assertRaisesRegex(ValueError,'Unlock'):
            self.a.create(side='sell',coin='BTC',quantity='1',price='1')
        self.a.vault.unlock(PASSWORD)
        with self.assertRaisesRegex(ValueError,'Deposit confirmed'):
            self.a.create(side='buy',coin='BTC',quantity='1',price='1')
        node=self.a.engine.nodes['SMW'];coins=node.coins(self.a.vault.key('SMW'))[:1]
        with patch.object(node,'coins',return_value=coins):
            exact=str(coins[0]['value']/100000000)
            with self.assertRaisesRegex(ValueError,'Deposit confirmed'):
                self.a.create(side='sell',coin='BTC',quantity=exact,price='1')
            first=self.a.create(side='sell',coin='BTC',quantity='1',price='1')
            with self.assertRaisesRegex(ValueError,'Deposit confirmed'):
                self.a.create(side='sell',coin='BTC',quantity='1',price='1')
            self.a.cancel_post(first['id'])
            second=self.a.create(side='sell',coin='BTC',quantity='1',price='1')
            self.assertNotEqual(first['id'],second['id'])
            balances=self.a.refresh_balances()
            self.assertEqual(balances['SMW']['available'],'0')

    def test_reservation_rechecks_maker_and_taker_funds(self):
        order=self.a.create(side='sell',coin='BTC',quantity='1',price='1')
        self.b.sync()
        with patch.object(self.b.engine.nodes['BTC'],'coins',return_value=[]):
            with self.assertRaisesRegex(ValueError,'Deposit confirmed'):self.b.reserve(order['id'])
        self.assertEqual(self.a.store.listing()[0]['status'],'active')
        with patch.object(self.a.engine.nodes['SMW'],'coins',return_value=[]):
            with self.assertRaises(ValueError):self.b.reserve(order['id'])
        self.assertEqual(self.a.store.listing()[0]['status'],'active')
        sid=self.b.reserve(order['id'])
        self.assertTrue(self.a.engine._load(sid)[1]['remote'])
        self.assertTrue(self.b.engine._load(sid)[1]['remote'])

    def test_hold_survives_recovery_and_no_text_is_published(self):
        p=self.a.create(side='sell',coin='BTC',quantity='1',price='1',title='removed',note='removed')
        self.assertEqual(self.a.store.post(p['id'])['title'],'')
        self.assertEqual(self.a.store.post(p['id'])['note'],'')
        held=self.a.engine.funding.active();self.a.backup(self.path/'recovery.smwbackup')
        restored=MarketApplication(ROOT,self.path/'restored','test')
        try:
            restored.restore_backup(self.path/'recovery.smwbackup',PASSWORD)
            self.assertEqual(held,restored.engine.funding.active())
        finally:restored.close()

    def test_real_row_button_enters_prepared_trade_in_34_languages(self):
        root=tk.Tk();root.withdraw();ui=MarketDesktop(self.b,root)
        errors=[]
        def drain():
            deadline=time.monotonic()+35
            while ui.busy and time.monotonic()<deadline:root.update();time.sleep(.01)
            self.assertFalse(ui.busy);root.update()
        try:
            p=self.a.create(side='sell',coin='BTC',quantity='2',price='0.1')
            self.b.sync();ui.paint()
            self.assertNotIn('title',ui.vars);self.assertNotIn('details',ui.vars)
            for code,name in ui.localization.languages.items():
                ui.language.set(name);ui.change_language();root.update()
                self.assertEqual(set(ui.extra[code]),set(ui.extra['en']))
                self.assertEqual(ui.orders.rows[p['id']]['button'].cget('text'),ui.tr('Trade'))
                self.assertTrue(ui.orders.rows[p['id']]['button'].cget('command'))
            ui.language.set('English');ui.change_language()
            with patch('smw_trade.market.desktop.messagebox.askyesno',return_value=True),patch('smw_trade.market.desktop.messagebox.showerror',side_effect=lambda *a,**k:errors.append(a)):
                ui.orders.rows[p['id']]['button'].invoke();drain()
                self.assertEqual(ui.tabs.index(ui.tabs.select()),1)
                sid=self.b.store.sessions()[0]['session']
                self.assertEqual(ui.trades.selection(),(sid,))
                self.assertTrue(self.b.engine._load(sid)[1]['remote'])
                self.assertTrue(self.a.engine._load(sid)[1]['remote'])
                self.assertFalse(errors,errors)
            # Capture an actual populated screen, not a generated mock-up.
            import os
            if os.environ.get('SUMUWW_UI_SCREENSHOTS'):
                from pathlib import Path
                from capture_market_window import capture
                dest=Path(os.environ['SUMUWW_UI_SCREENSHOTS']);dest.mkdir(parents=True,exist_ok=True)
                root.deiconify();ui.tabs.select(0)
                for code in ('en','ko','ar','mn-Mong'):
                    ui.language.set(ui.localization.languages[code]);ui.change_language();root.update();time.sleep(.1)
                    capture(root,dest/(code+'.png'))
        finally:ui.close();del ui;del root;gc.collect()


if __name__=='__main__':unittest.main()
