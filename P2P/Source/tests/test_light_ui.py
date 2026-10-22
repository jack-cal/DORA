import gc
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from smw_trade.market.application import MarketApplication
from smw_trade.market.desktop import MarketDesktop
from smw_trade.market.light_network import DEFAULT_SERVERS
from test_market import ROOT, PASSWORD


class LightUiTests(unittest.TestCase):
    def test_all_languages_connection_fields_and_real_buttons(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = MarketApplication(ROOT, Path(tmp) / 'light', 'test', flavor='light')
            peer = MarketApplication(ROOT, Path(tmp) / 'full', 'test')
            root = tk.Tk();root.withdraw();ui = MarketDesktop(app, root)
            failures = []
            def drain():
                deadline = time.monotonic() + 20
                while ui.busy and time.monotonic() < deadline:
                    root.update();time.sleep(.01)
                self.assertFalse(ui.busy);root.update()
            try:
                app.connect('127.0.0.1', peer.relay.address[1]);peer.connect('127.0.0.1', app.relay.address[1])
                ui.vars['node_coin'].set('BTC');ui.load_connection()
                self.assertNotIn('Select file', ui.buttons)
                self.assertEqual([ui.vars['server' + str(i)].get() for i in range(1, 4)], list(DEFAULT_SERVERS))
                for code, name in ui.localization.languages.items():
                    ui.language.set(name);ui.change_language();root.update()
                    self.assertEqual(set(ui.extra[code]), set(ui.extra['en']))
                    self.assertNotIn('Select file', ui.buttons)
                    self.assertEqual(ui.vars['node_coin'].get(), 'BTC')
                    for key in ('Bitcoin: light client', 'Bitcoin server', 'Light mode checks proofs but relies on servers for complete transaction history.', 'Bitcoin headers'):
                        self.assertTrue(ui.extra[code][key].strip(), (code, key))
                    for button in ui.buttons.values():self.assertTrue(button.cget('command'))
                ui.language.set('English');ui.change_language()
                with patch('smw_trade.market.desktop.messagebox.showerror', side_effect=lambda *a, **k: failures.append(a)), patch('smw_trade.market.desktop.messagebox.askyesno', return_value=True):
                    # Save captures the three editable endpoints on the UI thread.
                    with patch.object(app, 'configure', return_value={'height': 100}) as configure:
                        ui.buttons['Save connection'].invoke();drain()
                        self.assertEqual(configure.call_args.args, ('BTC', {'mode': 'light', 'servers': list(DEFAULT_SERVERS)}))
                    ui.vars['node_coin'].set('SMW');ui.load_connection();self.assertIn('Select file', ui.buttons)
                    ui.vars['quantity'].set('2');ui.vars['price'].set('0.1');ui.vars['title'].set('Light / Full test')
                    ui.buttons['Publish'].invoke();drain()
                    order = app.store.listing()[0];self.assertEqual(order['total'], '0.2')
                    ui.orders.selection_set(order['id']);ui.buttons['Cancel my order'].invoke();drain()
                    self.assertEqual(app.store.listing()[0]['status'], 'canceled')
                    post = peer.create(side='sell', coin='BTC', quantity='3', price='0.2')
                    ui.buttons['Synchronize'].invoke();drain();ui.orders.selection_set(post['id'])
                    ui.buttons['Reserve selected order'].invoke();drain();self.assertEqual(len(app.store.sessions()), 1)
                    ui.vars['password'].set(PASSWORD);ui.vars['confirm'].set(PASSWORD);ui.buttons['Create wallet'].invoke();drain()
                    self.assertFalse(app.vault.state()['locked'])
                    ui.buttons['Lock'].invoke();drain();self.assertTrue(app.vault.state()['locked'])
                    ui.vars['password'].set(PASSWORD);ui.buttons['Unlock vault'].invoke();drain();self.assertFalse(app.vault.state()['locked'])
                    self.assertFalse(failures, failures)
            finally:
                ui.close();app.close();peer.close();del ui;del root;gc.collect()

    def test_cross_edition_backup_keeps_wallet_and_order_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            full = MarketApplication(ROOT, path / 'full', 'test')
            light = MarketApplication(ROOT, path / 'light', 'test', flavor='light')
            restored = MarketApplication(ROOT, path / 'restored', 'test')
            try:
                full.vault.create(PASSWORD);full.create(side='sell', coin='BTC', quantity='1', price='0.1')
                identity, addresses = full.store.identity.public, full.vault.state()['addresses']
                full.backup(path / 'full.smwbackup');full.close()
                light.restore_backup(path / 'full.smwbackup', PASSWORD)
                self.assertEqual(light.store.identity.public, identity);self.assertEqual(light.vault.state()['addresses'], addresses)
                self.assertEqual(light.config['nodes']['BTC']['mode'], 'light')
                light.backup(path / 'light.smwbackup');light.close()
                restored.restore_backup(path / 'light.smwbackup', PASSWORD)
                self.assertEqual(restored.vault.state()['addresses'], addresses)
                self.assertNotIn('BTC', restored.engine.nodes)  # Core must be configured explicitly.
            finally:
                full.close();light.close();restored.close()


if __name__ == '__main__':unittest.main()
