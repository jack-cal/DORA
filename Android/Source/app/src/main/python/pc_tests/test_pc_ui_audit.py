"""Actual Tk controls with isolated wallets and chains; no production data."""
from pathlib import Path
from concurrent.futures import Future
import tempfile,time,tkinter as tk,unittest
from tkinter import ttk
from unittest.mock import patch
from coincurve import PrivateKey
from sumuww.app import SumuwwApp, _PasswordDialog, _ConnectionDialog, _RpcDialog
from sumuww.app_service import AppService
from sumuww.keystore import WalletKey
from sumuww.profiles import REGTEST
from sumuww.i18n import Translator,set_translator,tr

PASSWORD='temporary-ui-test-password'
class PcControlIntegrationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='sumuww-ui-audit-');self.folder=Path(self.temp.name)
  self.root=tk.Tk();self.root.withdraw()
  self.service=AppService(self.folder/'node',network=REGTEST,peers=[],bootstrap=False)
  self.app=SumuwwApp(self.root,self.service,language='en',language_path=self.folder/'lang.json')
  self.callbacks=[];self.root.report_callback_exception=lambda *args:self.callbacks.append(args)
  self.pump(lambda:self.app._started)
 def tearDown(self):
  import gc
  self.service.stop().result(timeout=15)
  self.app._finish_close()
  # Reclaim each test-owned Tcl interpreter on its creating thread, before a
  # later service thread can trigger cyclic collection of the closed widgets.
  self.app=None;self.root=None;gc.collect()
  self.temp.cleanup();set_translator(Translator('en'))
 def pump(self,condition=None,timeout=25):
  condition=condition or (lambda:not self.app._busy and not self.app._pending)
  deadline=time.monotonic()+timeout
  while True:
   self.root.update()
   if condition():break
   if time.monotonic()>deadline:raise AssertionError('UI operation deadline')
   time.sleep(.005)
  self.assertFalse(self.callbacks,self.callbacks)
 def widgets(self,parent):
  return [w for child in parent.winfo_children() for w in [child]+self.widgets(child)]
 def dialog_action(self,action):
  errors=[]
  def run():
   try:
    dialog=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel))
    action(dialog)
   except Exception as e:errors.append(e)
   finally:
    for w in self.root.winfo_children():
     if isinstance(w,tk.Toplevel) and w.winfo_exists():w.destroy()
  self.root.after(20,run);self.app.hardware_button.invoke()
  self.assertFalse(errors,errors);self.assertFalse(self.app._dialog_open)
 def test_hardware_cancel_and_apply_failure_are_visible_and_controls_recover(self):
  def cancel(dialog):
   self.assertTrue(self.app._dialog_open)
   self.assertEqual('disabled',str(self.app.create_button.cget('state')))
   radios=[w for w in self.widgets(dialog) if isinstance(w,ttk.Radiobutton)]
   self.assertEqual(['normal','disabled','disabled'],[str(w.cget('state')) for w in radios])
   next(w for w in self.widgets(dialog) if isinstance(w,ttk.Button) and str(w.cget('text'))==str(tr('Cancel'))).invoke()
  self.dialog_action(cancel)
  self.assertEqual('normal',str(self.app.create_button.cget('state')))
  for synchronous in [False,True]:
   failed=Future();failed.set_exception(ValueError('Hardware test rejected'))
   kwargs={'side_effect':ValueError('Hardware test rejected')} if synchronous else {'return_value':failed}
   with patch.object(self.service,'configure_mining_hardware',**kwargs),patch('sumuww.app.messagebox.showerror') as errors:
    self.dialog_action(lambda dialog:next(w for w in self.widgets(dialog) if isinstance(w,ttk.Button) and str(w.cget('text'))==str(tr('Apply'))).invoke())
    self.pump();errors.assert_called_once()
   self.assertFalse(self.app._busy);self.assertEqual('normal',str(self.app.hardware_button.cget('state')))
 def test_wallet_mining_transfer_history_backup_and_restore_controls_use_real_service(self):
  wallet=self.folder/'wallet.json';backup=self.folder/'backup.json';restored=self.folder/'restored.json'
  with patch.object(self.app,'_choose_file',return_value=wallet),patch.object(self.app,'_password',return_value=PASSWORD),patch('sumuww.app.messagebox.showerror') as errors:
   self.app.create_button.invoke();self.pump();errors.assert_not_called()
  address=self.app.address_text.get();self.assertTrue(address)
  self.assertEqual('disabled',str(self.app.open_button.cget('state')))
  with patch.object(self.app,'_choose_file') as choose:
   for button in (self.app.create_button,self.app.open_button,self.app.restore_button,self.app.seed_create_button,self.app.seed_recover_button):
    self.assertEqual('disabled',str(button.cget('state')));button.invoke()
   for handler in (self.app._create_wallet,self.app._open_wallet,self.app._restore_wallet,self.app._create_seed_wallet,self.app._recover_seed_wallet):handler()
   choose.assert_not_called()
  with patch.object(self.root,'clipboard_clear') as clear,patch.object(self.root,'clipboard_append') as copy:
   self.app.copy_button.invoke();clear.assert_called_once();copy.assert_called_once_with(address)
  self.app.mine_count.set('0');self.app.mine_start_button.invoke();self.assertFalse(self.app._mining)
  self.app.mine_count.set('101');self.app.mine_start_button.invoke()
  self.pump(lambda:not self.app._mining and not self.app._mine_inflight,timeout=40)
  self.pump();self.assertEqual(101,self.app._mine_completed)
  with patch.object(self.app,'_choose_file',return_value=backup),patch.object(self.app,'_password',return_value=PASSWORD):
   self.app.backup_button.invoke();self.pump()
  self.assertTrue(backup.exists());self.app.lock_button.invoke();self.pump();self.assertFalse(self.app._wallet['unlocked'])
  self.assertEqual('normal',str(self.app.open_button.cget('state')))
  with patch.object(self.app,'_choose_file',return_value=wallet),patch.object(self.app,'_password',return_value='wrong-password'),patch('sumuww.app.messagebox.showerror') as errors:
   self.app.open_button.invoke();self.pump();errors.assert_called_once()
  with patch.object(self.app,'_choose_file',return_value=wallet),patch.object(self.app,'_password',return_value=PASSWORD):
   self.app.open_button.invoke();self.pump()
  self.assertEqual('disabled',str(self.app.open_button.cget('state')))
  self.app.lock_button.invoke();self.pump()
  with patch.object(self.app,'_choose_file',side_effect=[backup,restored]),patch.object(self.app,'_password',return_value=PASSWORD):
   self.app.restore_button.invoke();self.pump()
  self.assertEqual(address,self.app.address_text.get());self.assertTrue(restored.exists())
  bob=WalletKey(PrivateKey((2).to_bytes(32,'big')),REGTEST)
  self.app.send_address.set('invalid');self.app.send_amount.set('1')
  with patch('sumuww.app.messagebox.showerror') as errors:
   self.app.send_button.invoke();errors.assert_called_once()
  self.app.send_address.set(bob.address);self.app.send_amount.set('1');self.app.manual_fee.set(True);self.app.send_fee.set('1');self.app._sync_controls()
  with patch('sumuww.app.messagebox.askyesno',return_value=False) as confirmation:
   self.app.send_button.invoke();self.pump();confirmation.assert_called_once()
  self.assertEqual('1',self.app.send_amount.get())
  with patch('sumuww.app.messagebox.askyesno',return_value=True),patch('sumuww.app.messagebox.showerror') as errors:
   self.app.send_button.invoke();self.pump();errors.assert_not_called()
  self.assertEqual('',self.app.send_amount.get())
  self.app.mine_count.set('1');self.app.mine_start_button.invoke();self.pump(lambda:not self.app._mining and not self.app._mine_inflight);self.pump()
  self.app.history_button.invoke();history=self.app._history_dialog;self.pump(lambda:not history._busy)
  self.assertGreater(history.total,100);history.next_button.invoke();self.pump(lambda:not history._busy)
  self.assertEqual(50,history.offset);history.previous_button.invoke();self.pump(lambda:not history._busy)
  history.refresh_button.invoke();self.pump(lambda:not history._busy);history.close()
  self.app.peer_endpoint.set('invalid');
  with patch('sumuww.app.messagebox.showerror') as errors:
   self.app.peer_button.invoke();self.pump();errors.assert_called_once()
  self.assertEqual(address,self.app.address_text.get())
 def test_network_rpc_password_dialogs_cancel_without_changes(self):
  before=self.service.status().result(timeout=5)
  for klass,button in [(_ConnectionDialog,self.app.settings_button),(_RpcDialog,self.app.rpc_button)]:
   class CancelDialog(klass):
    def buttonbox(dialog):
     super().buttonbox();dialog.after(20,dialog.cancel)
   with patch('sumuww.app.'+klass.__name__,CancelDialog):button.invoke()
   self.pump();self.assertFalse(self.app._dialog_open)
  after=self.service.status().result(timeout=5)
  self.assertEqual(before.get('connection'),after.get('connection'));self.assertEqual(before.get('rpc'),after.get('rpc'))
  checks=[]
  class PasswordDialog(_PasswordDialog):
   def buttonbox(dialog):
    super().buttonbox()
    def perform():
     dialog.password_entry.insert(0,PASSWORD);dialog.confirm_entry.insert(0,'not-matching')
     with patch('sumuww.app.messagebox.showerror'):
      checks.append(not dialog.validate())
     dialog.confirm_entry.delete(0,'end');dialog.confirm_entry.insert(0,PASSWORD)
     checks.append(dialog.validate());dialog.visibility_button.invoke();checks.append(dialog.password_entry.cget('show')=='');dialog.cancel()
    dialog.after(20,perform)
  PasswordDialog(self.root,creating=True);self.assertEqual([True,True,True],checks)

if __name__=='__main__':unittest.main()
