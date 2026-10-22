"""Native widget integration tests with disposable state, no user input injection."""
import gc,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from smw_trade.app import Application, default_data_directory
from smw_trade.desktop import Desktop
from smw_trade.orders import Store,order_id
from smw_trade.network import Relay

ROOT=Path(__file__).resolve().parents[1]

class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        self.app=Application(ROOT,self.path/'app');self.root=tk.Tk();self.root.withdraw()
        self.ui=Desktop(self.app,window=self.root)
    def tearDown(self):
        try:
            if self.root.winfo_exists():
                self.ui.close();self.wait(lambda:not self.window_exists())
        except tk.TclError:pass
        self.app.close();self.ui=None;self.root=None;gc.collect();self.tmp.cleanup()
    def window_exists(self):
        try:return bool(self.root.winfo_exists())
        except tk.TclError:return False
    def wait(self,condition,seconds=12):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            try:self.root.update()
            except tk.TclError:pass
            if condition():return
            time.sleep(.02)
        self.fail('Native operation did not complete before deadline')
    def test_create_and_cancel_from_native_buttons(self):
        self.ui.smw.set('15');self.ui.btc.set('0.0003');self.ui.create_button.invoke()
        self.wait(lambda:not self.ui.busy)
        orders=self.app.store.listing();self.assertEqual(len(orders),1)
        self.assertEqual(orders[0]['smw'],'15.00000000')
        self.ui.orders.selection_set(orders[0]['id']);self.ui.selection_changed()
        self.assertEqual(str(self.ui.cancel_button['state']),'normal')
        self.ui.cancel_button.invoke();self.wait(lambda:not self.ui.busy)
        self.assertEqual(self.app.store.listing()[0]['status'],'canceled')
    def test_invalid_input_does_not_create_order(self):
        self.ui.smw.set('-1');self.ui.btc.set('0.0003');self.ui.create_button.invoke()
        self.wait(lambda:not self.ui.busy)
        self.assertEqual(self.app.store.listing(),[])
        self.assertNotEqual(self.ui.message.get(),'Signed test order published.')

    def test_native_public_wallet_read_button(self):
        from test_wallet_link import PublicProfileNode
        from sumuww.address import encode_address
        from sumuww.wallet import RegtestKey
        with PublicProfileNode(self.path/'public-node') as node:
            self.ui.tabs.select(4);self.root.update()
            values={'coin':'smw','url':f'http://127.0.0.1:{node.port}/rpc',
                    'credential_file':str(node.token_file),
                    'address':encode_address(RegtestKey.from_int(77).script_pubkey,network='sumuww')}
            for key,value in values.items():self.ui.link_vars[key].set(value)
            self.ui.link_button.invoke();self.wait(lambda:not self.ui.busy)
            self.assertEqual(self.app.state()['wallet_links']['results']['smw']['confirmed_units'],0)
            self.assertIn('read_only',self.ui.link_result.get('1.0','end'))
            self.assertTrue(self.app.state()['wallet']['locked'])

    def test_native_peer_listener_and_invalid_swap_are_not_reported_successful(self):
        self.ui.listen_host.set('0.0.0.0');self.ui.listen_port.set('0')
        self.ui.listen_button.invoke();self.wait(lambda:not self.ui.busy)
        self.assertEqual(self.app.state()['relay_host'],'0.0.0.0')
        self.ui.peer_session.set('0'*64)
        self.ui.peer_buttons['prepare'].invoke();self.wait(lambda:not self.ui.busy)
        self.assertIn('first',self.ui.message.get())
    def test_native_connect_and_reservation(self):
        maker=Store(self.path/'maker');relay=Relay(maker).start()
        try:
            p=maker.create('sell','12','0.0002');oid=order_id(p['body'])
            self.ui.port.set(str(relay.address[1]));self.ui.connect_button.invoke();self.wait(lambda:not self.ui.busy)
            self.assertEqual(self.ui.peers.get(),'1')
            self.ui.orders.selection_set(oid);self.ui.selection_changed()
            with patch('smw_trade.desktop.messagebox.askyesno',return_value=True):self.ui.reserve_button.invoke()
            self.wait(lambda:not self.ui.busy)
            self.assertEqual(maker.listing()[0]['status'],'reserved')
            self.assertEqual(self.app.store.listing()[0]['status'],'reserved')
        finally:relay.close()
    def test_wallet_view_reports_unconnected(self):
        self.assertEqual(len(self.ui.tabs.tabs()),6)
        self.ui.tabs.select(1);self.root.update()
        text=[]
        def visit(w):
            try:text.append(str(w.cget('text')))
            except tk.TclError:pass
            for child in w.winfo_children():visit(child)
        visit(self.root)
        self.assertEqual(text.count('Real wallet: not connected'),2)
        self.assertEqual(self.ui.data_path.get(),str(self.app.store.directory))
    def test_no_browser_open_or_http_server_on_native_start(self):
        # Native Desktop receives the model directly. There is no HTTP server handle.
        self.assertFalse(hasattr(self.ui,'server'))
        self.assertFalse(hasattr(self.app,'http_server'))
        self.assertIn('SUMUWW',str(default_data_directory()))
        self.assertNotIn('OneDrive',str(default_data_directory()))
    def test_native_wallet_create_lock_unlock_and_backup(self):
        password='native-test-password-012345'
        self.ui.tabs.select(1);self.root.update()
        self.ui.wallet_password.set(password);self.ui.wallet_confirm.set(password)
        self.ui.wallet_buttons['create'].invoke();self.wait(lambda:not self.ui.busy)
        expected=self.app.state()['wallet']['addresses'];self.assertEqual(len(expected),2)
        self.assertEqual(self.ui.wallet_password.get(),'');self.assertEqual(self.ui.wallet_confirm.get(),'')
        self.assertEqual(self.ui.wallet_password_entry.cget('show'),'•')
        self.assertEqual(self.ui.wallet_entries['btc'].get(),expected['btc'])
        self.ui.wallet_buttons['lock'].invoke();self.wait(lambda:not self.ui.busy)
        self.assertEqual(self.ui.wallet_entries['btc'].get(),'')
        self.ui.wallet_password.set('wrong-native-password-012345');self.ui.wallet_buttons['unlock'].invoke()
        self.wait(lambda:not self.ui.busy);self.assertTrue(self.app.state()['wallet']['locked'])
        self.assertNotIn('wrong-native-password',self.ui.message.get())
        self.ui.wallet_password.set(password);self.ui.wallet_buttons['unlock'].invoke();self.wait(lambda:not self.ui.busy)
        self.assertEqual(self.app.state()['wallet']['addresses'],expected)
        backup=self.path/'native-backup.smwvault'
        with patch('smw_trade.desktop.filedialog.asksaveasfilename',return_value=str(backup)):
            self.ui.wallet_buttons['backup'].invoke()
        self.wait(lambda:not self.ui.busy);self.assertTrue(backup.exists());self.assertNotIn(password.encode(),backup.read_bytes())
        self.assertEqual(str(self.ui.wallet_buttons['restore']['state']),'disabled')
    def test_native_wallet_restore_verifies_backup_and_same_addresses(self):
        from smw_trade.vault import Vault
        source=Vault(self.path/'source.vault');password='native-restore-password-012345'
        try:
            expected=source.create(password);backup=self.path/'source.smwvault';source.backup(backup)
        finally:source.lock()
        self.ui.wallet_password.set(password)
        with patch('smw_trade.desktop.filedialog.askopenfilename',return_value=str(backup)):
            self.ui.wallet_buttons['restore'].invoke()
        self.wait(lambda:not self.ui.busy)
        self.assertEqual(self.app.state()['wallet']['addresses'],expected['addresses'])
        self.assertEqual(str(self.ui.wallet_buttons['create']['state']),'disabled')
    def test_native_close_cancels_owned_check(self):
        self.app.command('check',{'mode':'refund'})
        self.ui.close();self.wait(lambda:not self.window_exists(),seconds=40)
        self.assertFalse(self.app.worker_thread.is_alive())
        self.assertFalse(self.app.state()['job']['running'])
    def test_reserved_order_executes_exact_terms_from_native_button(self):
        maker=Store(self.path/'maker');relay=Relay(maker).start()
        try:
            packet=maker.create('sell','5.12345678','0.00009');oid=order_id(packet['body'])
            self.ui.port.set(str(relay.address[1]));self.ui.connect_button.invoke();self.wait(lambda:not self.ui.busy)
            self.ui.orders.selection_set(oid);self.ui.selection_changed()
            with patch('smw_trade.desktop.messagebox.askyesno',return_value=True):self.ui.reserve_button.invoke()
            self.wait(lambda:not self.ui.busy)
            self.ui.tabs.select(3);self.root.update()
            sid=self.app.state()['trades'][0]['session']
            self.ui.trade_rows.selection_set(sid);self.ui.trade_selection_changed()
            self.assertEqual(str(self.ui.execute_button['state']),'normal')
            with patch('smw_trade.desktop.messagebox.askyesno',return_value=True):self.ui.execute_button.invoke()
            self.wait(lambda:not self.ui.busy)
            self.wait(lambda:not self.app.state()['job']['running'],seconds=60)
            self.ui._paint();trade=self.app.state()['trades'][0]
            self.assertEqual(trade['state'],'COMPLETED',self.app.state()['job'])
            self.assertEqual(trade['evidence']['smw_received_atoms'],512345678)
            self.assertEqual(trade['evidence']['btc_received_sats'],9000)
            self.assertEqual(str(self.ui.execute_button['state']),'disabled')
            self.ui.trade_evidence_button.invoke();self.root.update()
            dialogs=[w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel)]
            self.assertEqual(len(dialogs),1);dialogs[0].destroy()
        finally:relay.close()
