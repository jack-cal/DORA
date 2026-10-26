import gc,json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from smw_trade.market.application import MarketApplication
from smw_trade.market.desktop import MarketDesktop
from test_market import ROOT,PASSWORD

class MarketUiTests(unittest.TestCase):
    def test_34_languages_and_order_buttons(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=MarketApplication(ROOT,Path(tmp)/'a','test');peer=MarketApplication(ROOT,Path(tmp)/'b','test');root=tk.Tk();root.withdraw();ui=MarketDesktop(app,root)
            failures=[]
            def drain():
                deadline=time.monotonic()+20
                while ui.busy and time.monotonic()<deadline:root.update();time.sleep(.01)
                self.assertFalse(ui.busy)
                root.update()
            try:
                app.connect('127.0.0.1',peer.relay.address[1]);peer.connect('127.0.0.1',app.relay.address[1])
                self.assertEqual(len(ui.extra),34)
                ui.message.set(ui.tr('Done.'))
                ui.vars['quantity'].set('10.12345678');ui.vars['price'].set('1');ui.set_side(1)
                with patch('smw_trade.market.desktop.messagebox.showerror',side_effect=lambda *a,**k:failures.append(a)),patch('smw_trade.market.desktop.messagebox.askyesno',return_value=True):
                    for code,name in ui.localization.languages.items():
                        ui.language.set(name);ui.change_language();root.update()
                        self.assertEqual(set(ui.extra[code]),set(ui.extra['en']),code)
                        self.assertTrue(all(isinstance(v,str) and v.strip() for v in ui.extra[code].values()))
                        self.assertEqual(ui.vars['quantity'].get(),'10.12345678');self.assertEqual(ui.side.get(),1)
                        self.assertEqual(ui.buttons['Publish'].cget('text'),ui.tr('Publish'))
                        self.assertEqual(ui.message.get(),ui.tr('Done.'))
                        for button in ui.buttons.values():self.assertTrue(button.cget('command'))
                        self.assertIn('9100',ui.tr('SUMUWW transfers activate at block 9100.'))
                        self.assertEqual(tuple(ui.pair_select['values']),('BTC',))
                        self.assertEqual(tuple(ui.node_select['values']),('SMW','BTC'))
                        self.assertNotIn('contract',ui.vars)
                    # Deposit-free publishing must fail through actual buttons.
                    ui.language.set('English');ui.change_language()
                    for coin in ('BTC',):
                        for side in (0,1):
                            ui.vars['coin'].set(coin);ui.vars['quantity'].set('10');ui.vars['price'].set('0.5');ui.set_side(side)
                            ui.buttons['Publish'].invoke();drain()
                            self.assertFalse(app.store.listing());self.assertEqual(len(failures),1);failures.clear()
                    ui.vars['password'].set(PASSWORD);ui.vars['confirm'].set(PASSWORD);ui.buttons['Create wallet'].invoke();drain();self.assertFalse(app.vault.state()['locked'])
                    ui.buttons['Lock'].invoke();drain();self.assertTrue(app.vault.state()['locked'])
                    ui.vars['password'].set(PASSWORD);ui.buttons['Unlock vault'].invoke();drain();self.assertFalse(app.vault.state()['locked'])
                    self.assertNotIn('peer',ui.vars);self.assertNotIn('listen',ui.vars)
                    ui.buttons['Connect'].invoke();drain()
                    self.assertFalse(failures,failures)
                out=os.environ.get('SUMUWW_UI_SCREENSHOTS')
                if out:
                    from capture_market_window import capture
                    dest=Path(out);dest.mkdir(parents=True,exist_ok=True);root.deiconify()
                    for code in ('en','ko','ar','mn-Mong'):
                        ui.language.set(ui.localization.languages[code]);ui.change_language();root.update();time.sleep(.1)
                        capture(root,dest/(code+'.png'))
            finally:
                ui.close();peer.close();app.close();del ui;del root;gc.collect()

    def test_encrypted_complete_recovery_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);a=MarketApplication(ROOT,path/'a','test');b=None
            try:
                a.vault.create(PASSWORD);a.store.create(side='buy',coin='BTC',quantity='1',price='0.001')
                identity=a.store.identity.public;addresses=a.vault.state()['addresses'];a.backup(path/'recovery.smwbackup')
                b=MarketApplication(ROOT,path/'b','test');b.restore_backup(path/'recovery.smwbackup',PASSWORD)
                self.assertEqual(b.store.identity.public,identity);self.assertEqual(b.vault.state()['addresses'],addresses)
                self.assertEqual(b.store.listing(),a.store.listing())
                with self.assertRaises(ValueError):b.restore_backup(path/'recovery.smwbackup',PASSWORD)
            finally:
                a.close()
                if b:b.close()

if __name__=='__main__':unittest.main()
